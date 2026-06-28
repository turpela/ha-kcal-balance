#!/usr/bin/env python3
"""
Kcal Balance add-on — FatSecret poller.

Reads credentials from /data/options.json (set via the HA add-on config UI),
polls FatSecret food_entries.get.v2 for each configured user on every scan
interval, and pushes sensor states to Home Assistant via the Supervisor API.

Sensors created:
  sensor.fatsecret_u1  — state: calories, attributes: protein, fat, carbs
  sensor.fatsecret_u2  — same (only if U2 credentials are configured)
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import random
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

# ---------------------------------------------------------------------------
# Logging — Python -u flag (unbuffered) ensures lines appear in HA log live
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("kcal-balance")

FATSECRET_API = "https://platform.fatsecret.com/rest/server.api"
HA_API = "http://supervisor/core/api"
OPTIONS_FILE = "/data/options.json"


# ---------------------------------------------------------------------------
# OAuth 1.0 helpers (stdlib only)
# ---------------------------------------------------------------------------

def _nonce():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=16))


def _sign(method, url, params, consumer_secret, token_secret=""):
    sorted_params = sorted(params.items())
    param_string = "&".join(
        f"{urllib.parse.quote(str(k), safe='')}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted_params
    )
    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(param_string, safe=""),
    ])
    signing_key = (
        f"{urllib.parse.quote(consumer_secret, safe='')}"
        f"&{urllib.parse.quote(token_secret, safe='')}"
    )
    sig = hmac.new(
        signing_key.encode("ascii"),
        base_string.encode("ascii"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(sig).decode()


# ---------------------------------------------------------------------------
# FatSecret API
# ---------------------------------------------------------------------------

def fetch_entries(creds):
    today_int = (date.today() - date(1970, 1, 1)).days
    params = {
        "method": "food_entries.get.v2",
        "date": str(today_int),
        "format": "json",
        "oauth_consumer_key": creds["consumer_key"],
        "oauth_nonce": _nonce(),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": creds["access_token"],
        "oauth_version": "1.0",
    }
    params["oauth_signature"] = _sign(
        "POST", FATSECRET_API, params,
        creds["consumer_secret"], creds["access_token_secret"]
    )
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(FATSECRET_API, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def summarise(raw):
    entries = raw.get("food_entries", {}).get("food_entry", [])
    if isinstance(entries, dict):
        entries = [entries]  # single entry is returned as dict, not list
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

def post_sensor(supervisor_token, entity_id, friendly_name, totals):
    payload = json.dumps({
        "state": str(totals["calories"]),
        "attributes": {
            "unit_of_measurement": "kcal",
            "friendly_name": friendly_name,
            "calories": totals["calories"],
            "protein":  totals["protein"],
            "fat":      totals["fat"],
            "carbs":    totals["carbs"],
        }
    }).encode()
    req = urllib.request.Request(
        f"{HA_API}/states/{entity_id}",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {supervisor_token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status


# ---------------------------------------------------------------------------
# Startup
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
    users = []

    # User 1 — required
    users.append({
        "label": "U1",
        "entity_id": "sensor.fatsecret_u1",
        "friendly_name": "FatSecret U1",
        "creds": {
            "consumer_key":        opts["u1_consumer_key"],
            "consumer_secret":     opts["u1_consumer_secret"],
            "access_token":        opts["u1_access_token"],
            "access_token_secret": opts["u1_access_token_secret"],
        },
    })

    # User 2 — optional
    u2_creds = {
        "consumer_key":        opts.get("u2_consumer_key", ""),
        "consumer_secret":     opts.get("u2_consumer_secret", ""),
        "access_token":        opts.get("u2_access_token", ""),
        "access_token_secret": opts.get("u2_access_token_secret", ""),
    }
    if all(u2_creds.values()):
        users.append({
            "label": "U2",
            "entity_id": "sensor.fatsecret_u2",
            "friendly_name": "FatSecret U2",
            "creds": u2_creds,
        })
        log.info("User 2 credentials found — polling both users")
    else:
        log.info("User 2 credentials not set — polling User 1 only")

    return users


def poll_once(users, supervisor_token):
    for user in users:
        label = user["label"]
        try:
            log.debug("[%s] Fetching FatSecret diary...", label)
            raw = fetch_entries(user["creds"])
            log.debug("[%s] Raw response: %s", label, raw)
            totals = summarise(raw)
            log.debug("[%s] Totals: %s", label, totals)
            status = post_sensor(supervisor_token, user["entity_id"], user["friendly_name"], totals)
            log.info("[%s] %s → HA %s", label, totals, status)
        except urllib.error.HTTPError as exc:
            log.error("[%s] HTTP %s from %s: %s", label, exc.code, exc.url, exc.reason)
        except urllib.error.URLError as exc:
            log.error("[%s] Network error: %s", label, exc.reason)
        except Exception as exc:
            log.exception("[%s] Unexpected error: %s", label, exc)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    log.info("Kcal Balance add-on starting...")

    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if not supervisor_token:
        log.error("SUPERVISOR_TOKEN not set — is homeassistant_api enabled in config.yaml?")
        sys.exit(1)
    log.debug("SUPERVISOR_TOKEN present (%d chars)", len(supervisor_token))

    opts = load_config()
    users = build_user_list(opts)
    scan_interval = int(opts.get("scan_interval", 300))

    log.info("Polling %d user(s) every %ds", len(users), scan_interval)

    while True:
        poll_once(users, supervisor_token)
        log.debug("Sleeping %ds until next poll", scan_interval)
        time.sleep(scan_interval)


if __name__ == "__main__":
    main()
