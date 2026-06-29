#!/usr/bin/env python3
"""
Kcal Balance add-on — FatSecret poller + goal/balance/weekly sensor pusher.

Reads credentials and goal config from /data/options.json (set via the HA
add-on config UI), polls FatSecret food_entries.get.v2 for each configured
user, computes calorie goals and balances, maintains a weekly state file,
and pushes all sensor states to Home Assistant via the Supervisor API.

All dates use Europe/Helsinki timezone so midnight resets are correct.

Sensors per user (U1 shown; U2 mirrors with _u2 suffix):
  sensor.fatsecret_u1            — consumed today (kcal), + macros attrs
  sensor.kcal_u1_goal            — daily goal (kcal)
  sensor.kcal_u1_balance         — goal − consumed (positive = room left)
  sensor.kcal_u1_net             — Garmin burned − consumed
  sensor.kcal_u1_weekly_consumed — total consumed this week (Mon–today)
  sensor.kcal_u1_weekly_goal     — weekly goal (daily goal × 7)
  sensor.kcal_u1_weekly_balance  — weekly goal − weekly consumed
"""

import json
import logging
import os
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

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

FATSECRET_API      = "https://platform.fatsecret.com/rest/server.api"
HA_API             = "http://supervisor/core/api"
OPTIONS_FILE       = "/data/options.json"
STATE_FILE         = "/data/weekly_state.json"
TIMEZONE           = ZoneInfo("Europe/Helsinki")
DASHBOARD_URL_PATH = "kcal-balance"

DEFAULT_GARMIN  = {"U1": "sensor.garmin_connect_calories",
                   "U2": "sensor.garmin_connect_calories_2"}
DEFAULT_OFFSETS = {"weight_loss": -500, "maintenance": 0, "muscle_gain": 300}

# ---------------------------------------------------------------------------
# Dashboard definition (auto-registered in HA sidebar on first start)
# ---------------------------------------------------------------------------

DASHBOARD_CONFIG = {
    "title": "Kcal Balance",
    "views": [
        {
            "title": "Today",
            "path": "kcal-balance",
            "icon": "mdi:food-apple",
            "cards": [
                {
                    "type": "horizontal-stack",
                    "cards": [
                        {
                            "type": "vertical-stack",
                            "cards": [
                                {"type": "markdown", "content": "## \U0001f464 User 1"},
                                {
                                    "type": "gauge",
                                    "entity": "sensor.kcal_u1_balance",
                                    "name": "Remaining Today",
                                    "unit": "kcal",
                                    "min": -500, "max": 1000, "needle": True,
                                    "severity": {"green": 100, "yellow": 0, "red": -500},
                                },
                                {
                                    "type": "gauge",
                                    "entity": "sensor.kcal_u1_net",
                                    "name": "Net Energy (Burned − Consumed)",
                                    "unit": "kcal",
                                    "min": -500, "max": 1500, "needle": True,
                                    "severity": {"green": 0, "yellow": -200, "red": -500},
                                },
                                {
                                    "type": "entities",
                                    "title": "Calories & Macros",
                                    "entities": [
                                        {"entity": "sensor.fatsecret_u1", "name": "Consumed"},
                                        {"entity": "sensor.kcal_u1_goal", "name": "Daily Goal"},
                                        {"type": "attribute", "entity": "sensor.fatsecret_u1",
                                         "attribute": "protein", "name": "Protein", "suffix": " g"},
                                        {"type": "attribute", "entity": "sensor.fatsecret_u1",
                                         "attribute": "fat", "name": "Fat", "suffix": " g"},
                                        {"type": "attribute", "entity": "sensor.fatsecret_u1",
                                         "attribute": "carbs", "name": "Carbs", "suffix": " g"},
                                    ],
                                },
                                {
                                    "type": "glance",
                                    "title": "Garmin — User 1",
                                    "columns": 4,
                                    "entities": [
                                        {"entity": "sensor.garmin_connect_calories", "name": "Burned"},
                                        {"entity": "sensor.garmin_connect_steps", "name": "Steps"},
                                        {"entity": "sensor.garmin_connect_body_battery", "name": "Body Battery"},
                                        {"entity": "sensor.garmin_connect_sleep_score", "name": "Sleep"},
                                    ],
                                },
                            ],
                        },
                        {
                            "type": "vertical-stack",
                            "cards": [
                                {"type": "markdown", "content": "## \U0001f464 User 2"},
                                {
                                    "type": "gauge",
                                    "entity": "sensor.kcal_u2_balance",
                                    "name": "Remaining Today",
                                    "unit": "kcal",
                                    "min": -500, "max": 1000, "needle": True,
                                    "severity": {"green": 100, "yellow": 0, "red": -500},
                                },
                                {
                                    "type": "gauge",
                                    "entity": "sensor.kcal_u2_net",
                                    "name": "Net Energy (Burned − Consumed)",
                                    "unit": "kcal",
                                    "min": -500, "max": 1500, "needle": True,
                                    "severity": {"green": 0, "yellow": -200, "red": -500},
                                },
                                {
                                    "type": "entities",
                                    "title": "Calories & Macros",
                                    "entities": [
                                        {"entity": "sensor.fatsecret_u2", "name": "Consumed"},
                                        {"entity": "sensor.kcal_u2_goal", "name": "Daily Goal"},
                                        {"type": "attribute", "entity": "sensor.fatsecret_u2",
                                         "attribute": "protein", "name": "Protein", "suffix": " g"},
                                        {"type": "attribute", "entity": "sensor.fatsecret_u2",
                                         "attribute": "fat", "name": "Fat", "suffix": " g"},
                                        {"type": "attribute", "entity": "sensor.fatsecret_u2",
                                         "attribute": "carbs", "name": "Carbs", "suffix": " g"},
                                    ],
                                },
                                {
                                    "type": "glance",
                                    "title": "Garmin — User 2",
                                    "columns": 4,
                                    "entities": [
                                        {"entity": "sensor.garmin_connect_calories_2", "name": "Burned"},
                                        {"entity": "sensor.garmin_connect_steps_2", "name": "Steps"},
                                        {"entity": "sensor.garmin_connect_body_battery_2", "name": "Body Battery"},
                                        {"entity": "sensor.garmin_connect_sleep_score_2", "name": "Sleep"},
                                    ],
                                },
                            ],
                        },
                    ],
                }
            ],
        },
        {
            "title": "This Week",
            "path": "kcal-balance-week",
            "icon": "mdi:calendar-week",
            "cards": [
                {
                    "type": "horizontal-stack",
                    "cards": [
                        {
                            "type": "vertical-stack",
                            "cards": [
                                {"type": "markdown", "content": "## \U0001f464 User 1 — This Week"},
                                {
                                    "type": "gauge",
                                    "entity": "sensor.kcal_u1_weekly_balance",
                                    "name": "Weekly Remaining",
                                    "unit": "kcal",
                                    "min": -3500, "max": 7000, "needle": True,
                                    "severity": {"green": 500, "yellow": 0, "red": -3500},
                                },
                                {
                                    "type": "entities",
                                    "title": "Weekly Calories & Macros",
                                    "entities": [
                                        {"entity": "sensor.kcal_u1_weekly_consumed", "name": "Consumed this week"},
                                        {"entity": "sensor.kcal_u1_weekly_goal", "name": "Weekly goal"},
                                        {"entity": "sensor.kcal_u1_weekly_balance", "name": "Remaining"},
                                        {"type": "attribute", "entity": "sensor.kcal_u1_weekly_consumed",
                                         "attribute": "protein", "name": "Protein", "suffix": " g"},
                                        {"type": "attribute", "entity": "sensor.kcal_u1_weekly_consumed",
                                         "attribute": "fat", "name": "Fat", "suffix": " g"},
                                        {"type": "attribute", "entity": "sensor.kcal_u1_weekly_consumed",
                                         "attribute": "carbs", "name": "Carbs", "suffix": " g"},
                                        {"type": "attribute", "entity": "sensor.kcal_u1_weekly_consumed",
                                         "attribute": "days_tracked", "name": "Days tracked"},
                                    ],
                                },
                            ],
                        },
                        {
                            "type": "vertical-stack",
                            "cards": [
                                {"type": "markdown", "content": "## \U0001f464 User 2 — This Week"},
                                {
                                    "type": "gauge",
                                    "entity": "sensor.kcal_u2_weekly_balance",
                                    "name": "Weekly Remaining",
                                    "unit": "kcal",
                                    "min": -3500, "max": 7000, "needle": True,
                                    "severity": {"green": 500, "yellow": 0, "red": -3500},
                                },
                                {
                                    "type": "entities",
                                    "title": "Weekly Calories & Macros",
                                    "entities": [
                                        {"entity": "sensor.kcal_u2_weekly_consumed", "name": "Consumed this week"},
                                        {"entity": "sensor.kcal_u2_weekly_goal", "name": "Weekly goal"},
                                        {"entity": "sensor.kcal_u2_weekly_balance", "name": "Remaining"},
                                        {"type": "attribute", "entity": "sensor.kcal_u2_weekly_consumed",
                                         "attribute": "protein", "name": "Protein", "suffix": " g"},
                                        {"type": "attribute", "entity": "sensor.kcal_u2_weekly_consumed",
                                         "attribute": "fat", "name": "Fat", "suffix": " g"},
                                        {"type": "attribute", "entity": "sensor.kcal_u2_weekly_consumed",
                                         "attribute": "carbs", "name": "Carbs", "suffix": " g"},
                                        {"type": "attribute", "entity": "sensor.kcal_u2_weekly_consumed",
                                         "attribute": "days_tracked", "name": "Days tracked"},
                                    ],
                                },
                            ],
                        },
                    ],
                }
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# Date helpers (all Helsinki-local)
# ---------------------------------------------------------------------------

def today_local():
    return datetime.now(TIMEZONE).date()

def week_monday(d):
    return d - timedelta(days=d.weekday())

def week_dates(d):
    """Dates from Monday through d (inclusive)."""
    monday = week_monday(d)
    return [monday + timedelta(days=i) for i in range(d.weekday() + 1)]

def date_to_epoch_days(d):
    return (d - date(1970, 1, 1)).days


# ---------------------------------------------------------------------------
# FatSecret API
# ---------------------------------------------------------------------------

def _fatsecret_post(creds, params):
    auth = OAuth1(
        creds["consumer_key"],
        creds["consumer_secret"],
        creds["access_token"],
        creds["access_token_secret"],
        signature_type="query",
    )
    resp = requests.post(FATSECRET_API, params=params, auth=auth, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_entries(creds, target_date):
    return _fatsecret_post(creds, {
        "method": "food_entries.get.v2",
        "date": str(date_to_epoch_days(target_date)),
        "format": "json",
    })


def summarise(raw):
    if raw is None:
        # FatSecret returns JSON null when there are no entries for the day
        return {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
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


def ensure_dashboard(supervisor_token):
    """Register the Kcal Balance dashboard in the HA sidebar (idempotent)."""
    headers = {
        "Authorization": f"Bearer {supervisor_token}",
        "Content-Type": "application/json",
    }

    # 1. Check if dashboard already exists
    try:
        req = urllib.request.Request(
            f"{HA_API}/lovelace/dashboards",
            headers={"Authorization": f"Bearer {supervisor_token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            existing = json.loads(r.read())
            if any(d.get("url_path") == DASHBOARD_URL_PATH for d in existing):
                log.debug("Dashboard '%s' already registered — skipping", DASHBOARD_URL_PATH)
                return
    except Exception as exc:
        log.warning("Could not list Lovelace dashboards: %s", exc)
        return

    # 2. Create the dashboard entry (appears in sidebar)
    payload = json.dumps({
        "url_path":        DASHBOARD_URL_PATH,
        "title":           "Kcal Balance",
        "icon":            "mdi:scale-balance",
        "show_in_sidebar": True,
        "require_admin":   False,
        "mode":            "storage",
    }).encode()
    try:
        req = urllib.request.Request(
            f"{HA_API}/lovelace/dashboards",
            data=payload, method="POST", headers=headers,
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            log.info("Dashboard '%s' created (HTTP %d)", DASHBOARD_URL_PATH, r.status)
    except Exception as exc:
        log.warning("Could not create dashboard: %s", exc)
        return

    # 3. Push the view/card config
    payload = json.dumps(DASHBOARD_CONFIG).encode()
    try:
        req = urllib.request.Request(
            f"{HA_API}/lovelace/dashboards/{DASHBOARD_URL_PATH}/config",
            data=payload, method="POST", headers=headers,
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            log.info("Dashboard config pushed (HTTP %d)", r.status)
    except Exception as exc:
        log.warning("Could not push dashboard config: %s", exc)


# ---------------------------------------------------------------------------
# Weekly state persistence
# ---------------------------------------------------------------------------

def load_weekly_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_weekly_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def purge_old_entries(state, today):
    """Remove daily entries older than 14 days."""
    cutoff = (today - timedelta(days=14)).isoformat()
    for label in list(state.keys()):
        state[label] = {d: v for d, v in state[label].items() if d >= cutoff}
    return state


def backfill_week(users, state, today):
    """On startup, fetch any missing days in the current week from FatSecret."""
    for user in users:
        label = user["label"]
        user_state = state.setdefault(label, {})
        for d in week_dates(today):
            d_str = d.isoformat()
            if d_str in user_state:
                continue
            log.info("[%s] Backfilling %s from FatSecret...", label, d_str)
            try:
                raw = fetch_entries(user["creds"], d)
                user_state[d_str] = summarise(raw)
                time.sleep(0.5)  # small delay between calls
            except Exception as exc:
                log.warning("[%s] Could not backfill %s: %s", label, d_str, exc)
    return state


def compute_weekly_totals(state, label, today):
    user_data = state.get(label, {})
    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    days_tracked = 0
    for d in week_dates(today):
        day_data = user_data.get(d.isoformat())
        if day_data:
            for key in totals:
                totals[key] += day_data.get(key, 0)
            days_tracked += 1
    return {k: round(v, 1) for k, v in totals.items()}, days_tracked


# ---------------------------------------------------------------------------
# Goal computation
# ---------------------------------------------------------------------------

def compute_goal(goal_mode, goal_kcal, goal_offset, burned=None):
    """Returns (goal: float|None, source: str)."""
    offset = goal_offset if goal_offset else DEFAULT_OFFSETS.get(goal_mode, 0)
    if burned is not None:
        return round(burned + offset, 1), "garmin"
    if goal_kcal:
        return float(goal_kcal), "fixed"
    return None, "none"


# ---------------------------------------------------------------------------
# Sensor pushers
# ---------------------------------------------------------------------------

def push_consumed(supervisor_token, user, totals):
    return ha_post(supervisor_token, user["consumed_entity"], totals["calories"], {
        "unit_of_measurement": "kcal",
        "friendly_name": user["consumed_name"],
        "calories": totals["calories"],
        "protein":  totals["protein"],
        "fat":      totals["fat"],
        "carbs":    totals["carbs"],
    })


def push_goal(supervisor_token, user, goal, goal_mode, source):
    return ha_post(supervisor_token, user["goal_entity"], goal, {
        "unit_of_measurement": "kcal",
        "friendly_name": user["goal_name"],
        "goal_mode": goal_mode,
        "source": source,
    })


def push_balance(supervisor_token, user, consumed, goal):
    balance = round(goal - consumed, 1)
    return ha_post(supervisor_token, user["balance_entity"], balance, {
        "unit_of_measurement": "kcal",
        "friendly_name": user["balance_name"],
        "consumed": consumed,
        "goal": goal,
        "status": "under" if balance >= 0 else "over",
    })


def push_net(supervisor_token, user, consumed, burned):
    net = round(burned - consumed, 1)
    return ha_post(supervisor_token, user["net_entity"], net, {
        "unit_of_measurement": "kcal",
        "friendly_name": user["net_name"],
        "consumed": consumed,
        "burned": burned,
        "status": "deficit" if net >= 0 else "surplus",
    })


def push_weekly(supervisor_token, user, weekly_totals, weekly_goal, days_tracked):
    ha_post(supervisor_token, user["weekly_consumed_entity"], weekly_totals["calories"], {
        "unit_of_measurement": "kcal",
        "friendly_name": user["weekly_consumed_name"],
        "protein":      weekly_totals["protein"],
        "fat":          weekly_totals["fat"],
        "carbs":        weekly_totals["carbs"],
        "days_tracked": days_tracked,
    })
    if weekly_goal is not None:
        weekly_balance = round(weekly_goal - weekly_totals["calories"], 1)
        ha_post(supervisor_token, user["weekly_goal_entity"], weekly_goal, {
            "unit_of_measurement": "kcal",
            "friendly_name": user["weekly_goal_name"],
        })
        ha_post(supervisor_token, user["weekly_balance_entity"], weekly_balance, {
            "unit_of_measurement": "kcal",
            "friendly_name": user["weekly_balance_name"],
            "consumed": weekly_totals["calories"],
            "goal":     weekly_goal,
            "status":   "under" if weekly_balance >= 0 else "over",
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


def _user_dict(label, suffix, creds, opts_prefix, opts):
    return {
        "label":  label,
        "creds":  creds,
        "consumed_entity":        f"sensor.fatsecret_{suffix}",
        "goal_entity":            f"sensor.kcal_{suffix}_goal",
        "balance_entity":         f"sensor.kcal_{suffix}_balance",
        "net_entity":             f"sensor.kcal_{suffix}_net",
        "weekly_consumed_entity": f"sensor.kcal_{suffix}_weekly_consumed",
        "weekly_goal_entity":     f"sensor.kcal_{suffix}_weekly_goal",
        "weekly_balance_entity":  f"sensor.kcal_{suffix}_weekly_balance",
        "consumed_name":          f"FatSecret {label}",
        "goal_name":              f"Kcal Goal {label}",
        "balance_name":           f"Kcal Balance {label}",
        "net_name":               f"Kcal Net {label}",
        "weekly_consumed_name":   f"Kcal Weekly Consumed {label}",
        "weekly_goal_name":       f"Kcal Weekly Goal {label}",
        "weekly_balance_name":    f"Kcal Weekly Balance {label}",
        "goal_mode":    opts.get(f"{opts_prefix}goal_mode", "maintenance"),
        "goal_kcal":    opts.get(f"{opts_prefix}goal_kcal") or 0,
        "goal_offset":  opts.get(f"{opts_prefix}goal_offset") or 0,
        "garmin_entity": (opts.get(f"{opts_prefix}garmin_entity") or "").strip()
                          or DEFAULT_GARMIN[label],
    }


def build_user_list(opts):
    def _strip(v):
        return (v or "").strip()

    users = [_user_dict("U1", "u1", {
        "consumer_key":        _strip(opts["u1_consumer_key"]),
        "consumer_secret":     _strip(opts["u1_consumer_secret"]),
        "access_token":        _strip(opts["u1_access_token"]),
        "access_token_secret": _strip(opts["u1_access_token_secret"]),
    }, "u1_", opts)]

    if _strip(opts.get("u2_consumer_key")):
        users.append(_user_dict("U2", "u2", {
            "consumer_key":        _strip(opts.get("u2_consumer_key")),
            "consumer_secret":     _strip(opts.get("u2_consumer_secret")),
            "access_token":        _strip(opts.get("u2_access_token")),
            "access_token_secret": _strip(opts.get("u2_access_token_secret")),
        }, "u2_", opts))
        log.info("User 2 configured — polling both users")
    else:
        log.info("User 2 not configured — polling User 1 only")

    return users


# ---------------------------------------------------------------------------
# Poll loop
# ---------------------------------------------------------------------------

def poll_once(users, supervisor_token, state, today):
    today_str = today.isoformat()

    for user in users:
        label = user["label"]
        try:
            # --- FatSecret: consumed today ---
            log.debug("[%s] Fetching FatSecret diary for %s...", label, today_str)
            raw    = fetch_entries(user["creds"], today)
            totals = summarise(raw)
            log.debug("[%s] Today: %s", label, totals)

            # Update weekly state for today
            state.setdefault(label, {})[today_str] = totals

            push_consumed(supervisor_token, user, totals)
            log.info("[%s] Consumed %.1f kcal", label, totals["calories"])

            # --- Garmin TDEE ---
            burned = ha_get(supervisor_token, user["garmin_entity"])
            log.debug("[%s] Garmin burned: %s kcal", label, burned)

            # --- Net energy ---
            if burned is not None:
                push_net(supervisor_token, user, totals["calories"], burned)
                net = round(burned - totals["calories"], 1)
                log.info("[%s] Net %+.1f kcal (%s)",
                         label, net, "deficit" if net >= 0 else "surplus")
            else:
                log.info("[%s] Garmin unavailable — skipping net sensor", label)

            # --- Daily goal + balance ---
            goal, source = compute_goal(
                user["goal_mode"], user["goal_kcal"], user["goal_offset"], burned)
            if goal is not None:
                push_goal(supervisor_token, user, goal, user["goal_mode"], source)
                push_balance(supervisor_token, user, totals["calories"], goal)
                balance = round(goal - totals["calories"], 1)
                log.info("[%s] Goal %.1f kcal | Balance %+.1f kcal (mode=%s src=%s)",
                         label, goal, balance, user["goal_mode"], source)
            else:
                log.info("[%s] No goal configured — skipping goal/balance sensors", label)

            # --- Weekly totals ---
            weekly_totals, days_tracked = compute_weekly_totals(state, label, today)
            weekly_goal = round(goal * 7, 1) if goal is not None else None
            push_weekly(supervisor_token, user, weekly_totals, weekly_goal, days_tracked)
            log.info("[%s] Week: %.1f kcal consumed across %d day(s) | Goal: %s",
                     label, weekly_totals["calories"], days_tracked,
                     f"{weekly_goal:.1f}" if weekly_goal else "not set")

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

    # Auto-register dashboard in HA sidebar on first start
    ensure_dashboard(supervisor_token)

    opts  = load_config()
    users = build_user_list(opts)
    scan_interval = int(opts.get("scan_interval", 300))

    # Load weekly state and backfill any missing days this week
    state = load_weekly_state()
    today = today_local()
    log.info("Week starting %s (Helsinki time, today=%s)",
             week_monday(today).isoformat(), today.isoformat())
    state = backfill_week(users, state, today)
    state = purge_old_entries(state, today)
    save_weekly_state(state)

    log.info("Polling %d user(s) every %ds", len(users), scan_interval)

    while True:
        today = today_local()
        poll_once(users, supervisor_token, state, today)
        save_weekly_state(state)
        log.debug("Sleeping %ds until next poll", scan_interval)
        time.sleep(scan_interval)


if __name__ == "__main__":
    main()
