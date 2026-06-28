#!/usr/bin/env python3
"""
Kcal Balance add-on — FatSecret poller + goal/balance sensor pusher.

Reads credentials and goal config from /data/options.json (set via the HA
add-on config UI), polls FatSecret food_entries.get.v2 for each configured
user on every scan interval, computes calorie goals and balance, and pushes
all sensor states to Home Assistant via the Supervisor API.

Sensors created per user (U1 shown; U2 mirrors with _u2 suffix):
  sensor.fatsecret_u1      — calories consumed today (state), + protein/fat/carbs attrs
  sensor.kcal_u1_goal      — daily calorie goal (state), + goal_mode / source attrs
  sensor.kcal_u1_balance   — goal minus consumed (state, positive = room left)
"""

import json
import logging
import os
import sys
import time
import urllib.request
from datetime import date

import requests
from requests_oauthlib import OAuth1

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("kcal-balance")

FATSECRET_API = "https://platform.fatsecret.com/rest/server.api"
HA_API        = "http://supervisor/core/api"
OPTIONS_FILE  = "/data/options.json"

DEFAULT_GARMIN = {"U1": "sensor.garmin_connect_calories",
                  "U2": "sensor.garmin_connect_calories_2"}
DEFAULT_OFFSETS = {"weight_loss": -500, "maintenance": 0, "muscle_gain": 300}


# ---------------------------------------------------------------------------
# FatSecret API
# ---------------------------------------------------------------------------

def fetch_entries(creds):
    today_int = (date.today() - date(1970, 1, 1)).days
    auth = OAuth1(
        creds["consumer_key"],
        creds["consumer_secret"],
        creds["access_token"],
        creds["access_token_secret"],
        signature_type="query",
    )
    resp = requests.post(
        FATSECRET_API,
        params={
            "method": "food_entries.get.v2",
            "date": str(today_int),
            "format": "json",
        },
        auth=auth,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def summarise(raw):
    if "error" in raw:
        raise RuntimeError(f"FatSecret error {raw['error']['code']}: {raw['error']['message']}")
    entries = raw.get("food_entries", {}).get("food_entry", [])
    if isinstance(entries, dict):
        entries = [entries]
    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for e in entries:
        totals["calories"] += float(e.get("calories", 0))
        totals["protein"]  += float(e.get("protein", 0))
        totals["fat"]      += float(e.get("fat", 0))
        totals["carbs"]    += float(e.get("carbohydrate", 0))
    return {k: round(v, 1) for k, v in totals.items()}


# ---------------------------------------------------------------------------
# Home Assistant REST API
# ---------------------------------------------------------------------------

def ha_get(supervisor_token, entity_id):
    """Read a sensor state from HA. Returns float or None if unavailable."""
    req = urllib.request.Request(
        f"{HA_API}/states/{entity_id}",
        headers={"Authorization": f"Bearer {supervisor_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            state = data.get("state", "")
            if state in ("unavailable", "unknown", ""):
                return None
            return float(state)
    except Exception as exc:
        log.warning("Could not read %s: %s", entity_id, exc)
        return None


def ha_post(supervisor_token, entity_id, state, attributes):
    """Push a sensor state to HA via Supervisor API."""
    payload = json.dumps({"state": str(state), "attributes": attributes}).encode()
    req = urllib.request.Request(
        f"{HA_API}/states/{entity_id}",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {supervisor_token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status


# ---------------------------------------------------------------------------
# Goal computation
# ---------------------------------------------------------------------------

def compute_goal(supervisor_token, garmin_entity, goal_mode, goal_kcal, goal_offset, burned=None):
    """
    Returns (goal_kcal: float, source: str).
    Priority: Garmin TDEE + offset → fixed goal_kcal → None.
    Pass already-fetched `burned` to avoid a second HA API call.
    """
    offset = goal_offset if goal_offset else DEFAULT_OFFSETS.get(goal_mode, 0)

    tdee = burned if burned is not None else ha_get(supervisor_token, garmin_entity)
    if tdee is not None:
        return round(tdee + offset, 1), "garmin"

    if goal_kcal:
        return float(goal_kcal), "fixed"

    return None, "none"


# ---------------------------------------------------------------------------
# Sensor pushers
# ---------------------------------------------------------------------------

def push_consumed(supervisor_token, entity_id, friendly_name, totals):
    return ha_post(supervisor_token, entity_id, totals["calories"], {
        "unit_of_measurement": "kcal",
        "friendly_name": friendly_name,
        "calories": totals["calories"],
        "protein":  totals["protein"],
        "fat":      totals["fat"],
        "carbs":    totals["carbs"],
    })


def push_goal(supervisor_token, entity_id, friendly_name, goal, goal_mode, source):
    return ha_post(supervisor_token, entity_id, goal, {
        "unit_of_measurement": "kcal",
        "friendly_name": friendly_name,
        "goal_mode": goal_mode,
        "source": source,
    })


def push_balance(supervisor_token, entity_id, friendly_name, consumed, goal):
    balance = round(goal - consumed, 1)
    return ha_post(supervisor_token, entity_id, balance, {
        "unit_of_measurement": "kcal",
        "friendly_name": friendly_name,
        "consumed": consumed,
        "goal": goal,
        "status": "under" if balance >= 0 else "over",
    })


def push_net(supervisor_token, entity_id, friendly_name, consumed, burned):
    net = round(burned - consumed, 1)
    return ha_post(supervisor_token, entity_id, net, {
        "unit_of_measurement": "kcal",
        "friendly_name": friendly_name,
        "consumed": consumed,
        "burned": burned,
        "status": "deficit" if net >= 0 else "surplus",
    })


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config():
    log.debug("Reading options from %s", OPTIONS_FILE)
    try:
        with open(OPTIONS_FILE) as f:
            opts = json.load(f)
        log.debug("Options loaded: %s", list(opts.keys()))
        return opts
    except FileNotFoundError:
        log.error("Options file not found: %s", OPTIONS_FILE)
        raise
    except json.JSONDecodeError as exc:
        log.error("Options file is not valid JSON: %s", exc)
        raise


def build_user_list(opts):
    users = [{
        "label": "U1",
        "creds": {
            "consumer_key":        opts["u1_consumer_key"].strip(),
            "consumer_secret":     opts["u1_consumer_secret"].strip(),
            "access_token":        opts["u1_access_token"].strip(),
            "access_token_secret": opts["u1_access_token_secret"].strip(),
        },
        "consumed_entity":  "sensor.fatsecret_u1",
        "goal_entity":      "sensor.kcal_u1_goal",
        "balance_entity":   "sensor.kcal_u1_balance",
        "net_entity":       "sensor.kcal_u1_net",
        "consumed_name":    "FatSecret U1",
        "goal_name":        "Kcal Goal U1",
        "balance_name":     "Kcal Balance U1",
        "net_name":         "Kcal Net U1",
        "goal_mode":        opts.get("u1_goal_mode", "maintenance"),
        "goal_kcal":        opts.get("u1_goal_kcal") or 0,
        "goal_offset":      opts.get("u1_goal_offset") or 0,
        "garmin_entity":    (opts.get("u1_garmin_entity") or "").strip() or DEFAULT_GARMIN["U1"],
    }]

    u2_key = (opts.get("u2_consumer_key") or "").strip()
    if u2_key:
        users.append({
            "label": "U2",
            "creds": {
                "consumer_key":        u2_key,
                "consumer_secret":     (opts.get("u2_consumer_secret") or "").strip(),
                "access_token":        (opts.get("u2_access_token") or "").strip(),
                "access_token_secret": (opts.get("u2_access_token_secret") or "").strip(),
            },
            "consumed_entity":  "sensor.fatsecret_u2",
            "goal_entity":      "sensor.kcal_u2_goal",
            "balance_entity":   "sensor.kcal_u2_balance",
            "net_entity":       "sensor.kcal_u2_net",
            "consumed_name":    "FatSecret U2",
            "goal_name":        "Kcal Goal U2",
            "balance_name":     "Kcal Balance U2",
            "net_name":         "Kcal Net U2",
            "goal_mode":        (opts.get("u2_goal_mode") or "maintenance"),
            "goal_kcal":        opts.get("u2_goal_kcal") or 0,
            "goal_offset":      opts.get("u2_goal_offset") or 0,
            "garmin_entity":    (opts.get("u2_garmin_entity") or "").strip() or DEFAULT_GARMIN["U2"],
        })
        log.info("User 2 configured — polling both users")
    else:
        log.info("User 2 not configured — polling User 1 only")

    return users


# ---------------------------------------------------------------------------
# Poll loop
# ---------------------------------------------------------------------------

def poll_once(users, supervisor_token):
    for user in users:
        label = user["label"]
        try:
            # --- FatSecret: calories consumed ---
            log.debug("[%s] Fetching FatSecret diary...", label)
            raw    = fetch_entries(user["creds"])
            totals = summarise(raw)
            log.debug("[%s] Totals: %s", label, totals)

            status = push_consumed(supervisor_token, user["consumed_entity"],
                                   user["consumed_name"], totals)
            log.info("[%s] Consumed %s kcal → HA %s", label, totals["calories"], status)

            # --- Garmin TDEE (used for both goal and net) ---
            burned = ha_get(supervisor_token, user["garmin_entity"])
            log.debug("[%s] Garmin burned: %s kcal", label, burned)

            # --- Net energy: burned − consumed ---
            if burned is not None:
                push_net(supervisor_token, user["net_entity"],
                         user["net_name"], totals["calories"], burned)
                net = round(burned - totals["calories"], 1)
                log.info("[%s] Net %+.1f kcal (%s)",
                         label, net, "deficit" if net >= 0 else "surplus")
            else:
                log.info("[%s] Garmin unavailable — skipping net sensor", label)

            # --- Goal ---
            goal, source = compute_goal(
                supervisor_token,
                user["garmin_entity"],
                user["goal_mode"],
                user["goal_kcal"],
                user["goal_offset"],
                burned,
            )
            if goal is not None:
                push_goal(supervisor_token, user["goal_entity"],
                          user["goal_name"], goal, user["goal_mode"], source)
                log.info("[%s] Goal %s kcal (mode=%s source=%s)",
                         label, goal, user["goal_mode"], source)

                # --- Balance: goal − consumed ---
                push_balance(supervisor_token, user["balance_entity"],
                             user["balance_name"], totals["calories"], goal)
                balance = round(goal - totals["calories"], 1)
                log.info("[%s] Balance %+.1f kcal (%s goal)",
                         label, balance, "under" if balance >= 0 else "OVER")
            else:
                log.info("[%s] No goal configured — skipping goal/balance sensors", label)

        except RuntimeError as exc:
            log.error("[%s] %s", label, exc)
        except requests.HTTPError as exc:
            log.error("[%s] HTTP %s: %s", label, exc.response.status_code, exc.response.text)
        except requests.RequestException as exc:
            log.error("[%s] Network error: %s", label, exc)
        except Exception as exc:
            log.exception("[%s] Unexpected error: %s", label, exc)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("Kcal Balance add-on starting...")

    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if not supervisor_token:
        log.error("SUPERVISOR_TOKEN not set — is homeassistant_api enabled in config.yaml?")
        sys.exit(1)
    log.debug("SUPERVISOR_TOKEN present (%d chars)", len(supervisor_token))

    opts  = load_config()
    users = build_user_list(opts)
    scan_interval = int(opts.get("scan_interval", 300))

    log.info("Polling %d user(s) every %ds", len(users), scan_interval)

    while True:
        poll_once(users, supervisor_token)
        log.debug("Sleeping %ds until next poll", scan_interval)
        time.sleep(scan_interval)


if __name__ == "__main__":
    main()
