#!/usr/bin/env python3
"""
exercise_test.py — Check what FatSecret exercise/burned-calorie data is
accessible via the API (including any Garmin-synced activity data).

Run locally BEFORE changing the add-on:
    python3 exercise_test.py

Checks:
  1. exercise_entries.get      — exercise diary for today + yesterday
  2. food_entries.get.v2       — raw top-level response (may contain calorie_burn fields)

Usage:
    pip install requests requests-oauthlib   (once)
    python3 exercise_test.py
"""
import json
import sys
from datetime import date, timedelta

try:
    import requests
    from requests_oauthlib import OAuth1
except ImportError:
    print("Install deps first:  pip install requests requests-oauthlib")
    sys.exit(1)

FATSECRET_API = "https://platform.fatsecret.com/rest/server.api"


def epoch_days(d: date) -> int:
    return (d - date(1970, 1, 1)).days


def call(consumer_key, consumer_secret, access_token, access_token_secret,
         method, extra_params=None):
    auth = OAuth1(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
        signature_type="query",
    )
    params = {"method": method, "format": "json"}
    if extra_params:
        params.update(extra_params)
    resp = requests.post(FATSECRET_API, params=params, auth=auth, timeout=15)
    resp.raise_for_status()
    return resp.json()


def section(title):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def main():
    print("=== FatSecret Exercise API Test ===\n")
    ck  = input("Consumer Key:        ").strip()
    cs  = input("Consumer Secret:     ").strip()
    at  = input("Access Token:        ").strip()
    ats = input("Access Token Secret: ").strip()

    today     = date.today()
    yesterday = today - timedelta(days=1)

    # ── 1. exercise_entries.get — today ──────────────────────────────────────
    section(f"exercise_entries.get  →  today ({today})")
    try:
        raw = call(ck, cs, at, ats, "exercise_entries.get",
                   {"date": str(epoch_days(today))})
        print(json.dumps(raw, indent=2))
    except Exception as e:
        print(f"ERROR: {e}")

    # ── 2. exercise_entries.get — yesterday ───────────────────────────────────
    section(f"exercise_entries.get  →  yesterday ({yesterday})")
    try:
        raw = call(ck, cs, at, ats, "exercise_entries.get",
                   {"date": str(epoch_days(yesterday))})
        print(json.dumps(raw, indent=2))
    except Exception as e:
        print(f"ERROR: {e}")

    # ── 3. food_entries.get.v2 — today raw (check for top-level calorie fields) ──
    section(f"food_entries.get.v2  →  today ({today})  [full raw response]")
    try:
        raw = call(ck, cs, at, ats, "food_entries.get.v2",
                   {"date": str(epoch_days(today))})
        print(json.dumps(raw, indent=2))
    except Exception as e:
        print(f"ERROR: {e}")

    # ── 4. food_entries.get.v2 — yesterday raw ───────────────────────────────
    section(f"food_entries.get.v2  →  yesterday ({yesterday})  [full raw response]")
    try:
        raw = call(ck, cs, at, ats, "food_entries.get.v2",
                   {"date": str(epoch_days(yesterday))})
        print(json.dumps(raw, indent=2))
    except Exception as e:
        print(f"ERROR: {e}")

    print(f"\n{'─'*60}")
    print("Done. Paste the output above so we can see what fields are available.")


if __name__ == "__main__":
    main()
