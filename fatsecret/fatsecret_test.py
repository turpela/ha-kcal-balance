#!/usr/bin/env python3
"""
Quick local test — calls food_entries.get.v2 directly.
Run this to verify your credentials and signing work outside of the add-on.

Usage:
    python3 fatsecret_test.py
"""
import sys
from datetime import date

try:
    import requests
    from requests_oauthlib import OAuth1
except ImportError:
    print("Install deps first:  pip install requests requests-oauthlib")
    sys.exit(1)

FATSECRET_API = "https://platform.fatsecret.com/rest/server.api"

consumer_key        = input("Consumer Key:        ").strip()
consumer_secret     = input("Consumer Secret:     ").strip()
access_token        = input("Access Token:        ").strip()
access_token_secret = input("Access Token Secret: ").strip()

today_int = (date.today() - date(1970, 1, 1)).days
print(f"\nToday as days-since-epoch: {today_int}")

for sig_type in ("body", "query", "AUTH_HEADER"):
    print(f"\n--- signature_type={sig_type} ---")
    auth = OAuth1(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
        signature_type=sig_type,
    )
    if sig_type == "query":
        resp = requests.get(FATSECRET_API, params={
            "method": "food_entries.get.v2",
            "date": str(today_int),
            "format": "json",
        }, auth=auth)
    else:
        resp = requests.post(FATSECRET_API, data={
            "method": "food_entries.get.v2",
            "date": str(today_int),
            "format": "json",
        }, auth=auth)
    print(f"HTTP {resp.status_code}: {resp.text[:300]}")
