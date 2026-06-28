#!/usr/bin/env python3
"""
FatSecret polling script — User 2.

Fetches today's food diary from FatSecret and prints a JSON summary
to stdout for Home Assistant command_line sensor.

Output:
    {"calories": 1850, "protein": 120.5, "fat": 65.2, "carbs": 210.3}

Credentials are read from credentials_u2.json in the same directory.
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

API_URL = "https://platform.fatsecret.com/rest/server.api"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "credentials_u2.json")


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
        "POST", API_URL, params, creds["consumer_secret"], creds["access_token_secret"]
    )
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(API_URL, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def summarise(raw):
    entries = raw.get("food_entries", {}).get("food_entry", [])
    if isinstance(entries, dict):
        entries = [entries]  # single entry comes back as a dict, not a list
    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for e in entries:
        totals["calories"] += float(e.get("calories", 0))
        totals["protein"] += float(e.get("protein", 0))
        totals["fat"] += float(e.get("fat", 0))
        totals["carbs"] += float(e.get("carbohydrate", 0))
    return {k: round(v, 1) for k, v in totals.items()}


def main():
    try:
        with open(CREDENTIALS_FILE) as f:
            creds = json.load(f)
        raw = fetch_entries(creds)
        result = summarise(raw)
    except FileNotFoundError:
        result = {"error": "credentials_u2.json not found", "calories": 0, "protein": 0, "fat": 0, "carbs": 0}
    except Exception as e:
        result = {"error": str(e), "calories": 0, "protein": 0, "fat": 0, "carbs": 0}

    print(json.dumps(result))


if __name__ == "__main__":
    main()
