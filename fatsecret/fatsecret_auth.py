#!/usr/bin/env python3
"""
FatSecret OAuth 1.0 — one-time authorization script.

Run this once per user on your local machine to obtain a permanent
access token and secret. Paste the output into the add-on config UI.

Requirements:
    pip install requests requests-oauthlib

Usage:
    python3 fatsecret_auth.py
"""

import sys
import urllib.parse

try:
    import requests
    from requests_oauthlib import OAuth1
except ImportError:
    print("ERROR: Install dependencies first:  pip install requests requests-oauthlib")
    sys.exit(1)

REQUEST_TOKEN_URL = "https://authentication.fatsecret.com/oauth/request_token"
AUTHORIZE_URL     = "https://authentication.fatsecret.com/oauth/authorize"
ACCESS_TOKEN_URL  = "https://authentication.fatsecret.com/oauth/access_token"


def post_oauth(url, consumer_key, consumer_secret, token=None, token_secret=None, extra=None):
    """POST with OAuth 1.0 params in the request body (signature_type='body')."""
    auth = OAuth1(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=token or "",
        resource_owner_secret=token_secret or "",
        signature_type="body",
        callback_uri="oob" if not token else None,
    )
    data = extra or {}
    resp = requests.post(url, data=data, auth=auth)
    if not resp.ok:
        print(f"\nERROR: HTTP {resp.status_code} — {resp.text}")
        sys.exit(1)
    return dict(urllib.parse.parse_qsl(resp.text))


def main():
    print("=== FatSecret OAuth Setup ===\n")
    consumer_key    = input("Consumer Key:    ").strip()
    consumer_secret = input("Consumer Secret: ").strip()

    if not consumer_key or not consumer_secret:
        print("ERROR: Consumer key and secret cannot be empty.")
        sys.exit(1)

    # Step 1 — get request token
    print("\nStep 1: Obtaining request token...")
    token_resp = post_oauth(REQUEST_TOKEN_URL, consumer_key, consumer_secret)
    request_token        = token_resp["oauth_token"]
    request_token_secret = token_resp["oauth_token_secret"]
    print("  OK")

    # Step 2 — user authorizes in browser
    auth_url = f"{AUTHORIZE_URL}?oauth_token={request_token}"
    print(f"\nStep 2: Open this URL in your browser and log in with the user's FatSecret account:\n\n  {auth_url}\n")
    verifier = input("Step 3: Enter the verification code shown after authorization: ").strip()

    # Step 3 — exchange for access token
    print("\nExchanging for access token...")
    access_resp = post_oauth(
        ACCESS_TOKEN_URL,
        consumer_key,
        consumer_secret,
        token=request_token,
        token_secret=request_token_secret,
        extra={"oauth_verifier": verifier},
    )
    access_token        = access_resp["oauth_token"]
    access_token_secret = access_resp["oauth_token_secret"]

    print("\nSuccess! Enter these values in the add-on Configuration tab:\n")
    print(f"  u1_consumer_key:        {consumer_key}")
    print(f"  u1_consumer_secret:     {consumer_secret}")
    print(f"  u1_access_token:        {access_token}")
    print(f"  u1_access_token_secret: {access_token_secret}")


if __name__ == "__main__":
    main()
