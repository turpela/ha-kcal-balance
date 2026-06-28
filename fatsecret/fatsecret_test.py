#!/usr/bin/env python3
"""
Local integration test — verifies FatSecret returns the values the add-on needs.

Usage:
    python3 fatsecret_test.py
"""
import json
import sys
from datetime import date

try:
    import requests
    from requests_oauthlib import OAuth1
except ImportError:
    print("Install deps first:  pip install requests requests-oauthlib")
    sys.exit(1)

FATSECRET_API = "https://platform.fatsecret.com/rest/server.api"


def fetch_entries(consumer_key, consumer_secret, access_token, access_token_secret):
    today_int = (date.today() - date(1970, 1, 1)).days
    auth = OAuth1(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
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
    if not entries:
        return None, []
    if isinstance(entries, dict):
        entries = [entries]
    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for e in entries:
        totals["calories"] += float(e.get("calories", 0))
        totals["protein"]  += float(e.get("protein", 0))
        totals["fat"]      += float(e.get("fat", 0))
        totals["carbs"]    += float(e.get("carbohydrate", 0))
    return {k: round(v, 1) for k, v in totals.items()}, entries


def main():
    print("=== FatSecret Local Test ===\n")
    consumer_key        = input("Consumer Key:        ").strip()
    consumer_secret     = input("Consumer Secret:     ").strip()
    access_token        = input("Access Token:        ").strip()
    access_token_secret = input("Access Token Secret: ").strip()

    print("\nFetching today's food diary...")
    raw = fetch_entries(consumer_key, consumer_secret, access_token, access_token_secret)
    totals, entries = summarise(raw)

    if not entries:
        print("No food entries logged today.")
        return

    print(f"\n{len(entries)} food entry/entries found today:\n")
    for e in entries:
        print(f"  {e.get('food_entry_description', '?'):40s}  {float(e.get('calories', 0)):6.1f} kcal  "
              f"P:{float(e.get('protein', 0)):.1f}g  "
              f"F:{float(e.get('fat', 0)):.1f}g  "
              f"C:{float(e.get('carbohydrate', 0)):.1f}g")

    print(f"\n{'TOTAL':40s}  {totals['calories']:6.1f} kcal  "
          f"P:{totals['protein']:.1f}g  "
          f"F:{totals['fat']:.1f}g  "
          f"C:{totals['carbs']:.1f}g")

    print("\nThis is what the add-on will push to Home Assistant:")
    print(json.dumps({
        "state": str(totals["calories"]),
        "attributes": {
            "unit_of_measurement": "kcal",
            "friendly_name": "FatSecret U1",
            **totals,
        }
    }, indent=2))


if __name__ == "__main__":
    main()
