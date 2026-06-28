#!/usr/bin/env python3
"""
FatSecret OAuth 1.0 — one-time authorization script.

Run this once per user to obtain a permanent access token and secret.
Store the output in fatsecret/credentials_u1.json or credentials_u2.json.

Usage:
    FS_CONSUMER_KEY=<key> FS_CONSUMER_SECRET=<secret> python3 fatsecret_auth.py
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

CONSUMER_KEY = os.environ.get("FS_CONSUMER_KEY", "")
CONSUMER_SECRET = os.environ.get("FS_CONSUMER_SECRET", "")

REQUEST_TOKEN_URL = "https://authentication.fatsecret.com/oauth/request_token"
AUTHORIZE_URL = "https://authentication.fatsecret.com/oauth/authorize"
ACCESS_TOKEN_URL = "https://authentication.fatsecret.com/oauth/access_token"


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


def _post(url, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return dict(urllib.parse.parse_qsl(resp.read().decode()))


def step1_get_request_token():
    params = {
        "oauth_callback": "oob",
        "oauth_consumer_key": CONSUMER_KEY,
        "oauth_nonce": _nonce(),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_version": "1.0",
    }
    params["oauth_signature"] = _sign("POST", REQUEST_TOKEN_URL, params, CONSUMER_SECRET)
    result = _post(REQUEST_TOKEN_URL, params)
    return result["oauth_token"], result["oauth_token_secret"]


def step3_get_access_token(request_token, request_token_secret, verifier):
    params = {
        "oauth_consumer_key": CONSUMER_KEY,
        "oauth_nonce": _nonce(),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": request_token,
        "oauth_verifier": verifier,
        "oauth_version": "1.0",
    }
    params["oauth_signature"] = _sign(
        "POST", ACCESS_TOKEN_URL, params, CONSUMER_SECRET, request_token_secret
    )
    result = _post(ACCESS_TOKEN_URL, params)
    return result["oauth_token"], result["oauth_token_secret"]


def main():
    if not CONSUMER_KEY or not CONSUMER_SECRET:
        print("ERROR: Set FS_CONSUMER_KEY and FS_CONSUMER_SECRET environment variables.")
        raise SystemExit(1)

    print("Step 1: Obtaining request token...")
    request_token, request_token_secret = step1_get_request_token()

    auth_url = f"{AUTHORIZE_URL}?oauth_token={request_token}"
    print(f"\nStep 2: Open this URL in your browser and authorize the app:\n\n  {auth_url}\n")
    verifier = input("Step 3: Enter the verification code shown after authorization: ").strip()

    print("\nExchanging for access token...")
    access_token, access_token_secret = step3_get_access_token(
        request_token, request_token_secret, verifier
    )

    credentials = {
        "consumer_key": CONSUMER_KEY,
        "consumer_secret": CONSUMER_SECRET,
        "access_token": access_token,
        "access_token_secret": access_token_secret,
    }

    print("\nSuccess! Save these credentials to your credentials file:\n")
    print(json.dumps(credentials, indent=2))


if __name__ == "__main__":
    main()
