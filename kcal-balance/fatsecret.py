#!/usr/bin/env python3
"""
Kcal Balance add-on — FatSecret poller.

Reads credentials from /data/options.json (set via the HA add-on config UI),
polls FatSecret food_entries.get.v2 for both users on each scan interval,
and pushes sensor states to Home Assistant via the Supervisor REST API.

Sensors created:
  sensor.fatsecret_u1  (state = calories, attributes: protein, fat, carbs)
  sensor.fatsecret_u2  (state = calories, attributes: protein, fat, carbs)
"""

import base64
import hashlib
import hmac
import json
import os
import random
import string
import time
import urllib.parse
import urllib.request
from datetime import date

FATSECRET_API = "https://platform.fatsecret.com/rest/server.api"
HA_API = "http://supervisor/core/api"
OPTIONS_FILE = "/data/options.json"


# ---------------------------------------------------------------------------
# OAuth 1.0 helpers (stdlib only — no pip dependencies)
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
        totals["protein"] += float(e.get("protein", 0))
        totals["fat"] += float(e.get("fat", 0))
        totals["carbs"] += float(e.get("carbohydrate", 0))
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
            "protein": totals["protein"],
            "fat": totals["fat"],
            "carbs": totals["carbs"],
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
# Main loop
# ---------------------------------------------------------------------------

def main():
    with open(OPTIONS_FILE) as f:
        opts = json.load(f)

    supervisor_token = os.environ["SUPERVISOR_TOKEN"]
    scan_interval = int(opts.get("scan_interval", 300))

    users = [
        {
            "label": "U1",
            "entity_id": "sensor.fatsecret_u1",
            "friendly_name": "FatSecret U1",
            "creds": {
                "consumer_key":       opts["u1_consumer_key"],
                "consumer_secret":    opts["u1_consumer_secret"],
                "access_token":       opts["u1_access_token"],
                "access_token_secret": opts["u1_access_token_secret"],
            },
        },
        {
            "label": "U2",
            "entity_id": "sensor.fatsecret_u2",
            "friendly_name": "FatSecret U2",
            "creds": {
                "consumer_key":       opts["u2_consumer_key"],
                "consumer_secret":    opts["u2_consumer_secret"],
                "access_token":       opts["u2_access_token"],
                "access_token_secret": opts["u2_access_token_secret"],
            },
        },
    ]

    print(f"Kcal Balance started — polling every {scan_interval}s")

    while True:
        for user in users:
            try:
                raw = fetch_entries(user["creds"])
                totals = summarise(raw)
                status = post_sensor(
                    supervisor_token,
                    user["entity_id"],
                    user["friendly_name"],
                    totals,
                )
                print(f"[{user['label']}] {totals} → HA {status}")
            except Exception as exc:
                print(f"[{user['label']}] ERROR: {exc}")

        time.sleep(scan_interval)


if __name__ == "__main__":
    main()
