"""
fatsecret.py — FatSecret Platform REST API client.

OAuth 1.0 with signature_type="query" (params in URL query string).
This is the only approach that works reliably inside the Docker container;
signature_type="body" causes Content-Length mismatches with requests-oauthlib.
"""

import logging
from datetime import date

import requests
from requests_oauthlib import OAuth1

log = logging.getLogger("kcal-balance")

FATSECRET_API = "https://platform.fatsecret.com/rest/server.api"


def _epoch_days(d: date) -> int:
    """Convert a date to days since 1970-01-01 (FatSecret's date format)."""
    return (d - date(1970, 1, 1)).days


def fetch_entries(creds: dict, target_date: date) -> dict:
    """
    Call food_entries.get.v2 for target_date.
    Returns the raw parsed JSON (may be None or non-dict for empty days).
    Raises requests.HTTPError on non-2xx responses.
    """
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
            "date":   str(_epoch_days(target_date)),
            "format": "json",
        },
        auth=auth,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def summarise(raw) -> dict:
    """
    Reduce raw food_entries.get.v2 JSON to {calories, protein, fat, carbs}.

    Handles:
    - null / non-dict responses  → zero totals (empty diary)
    - {"food_entries": null}     → zero totals
    - single entry (dict)        → wrapped in list
    - FatSecret error object     → raises RuntimeError
    """
    if not isinstance(raw, dict):
        # FatSecret returns JSON null for days with no entries
        return {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}

    if "error" in raw:
        raise RuntimeError(
            f"FatSecret error {raw['error']['code']}: {raw['error']['message']}"
        )

    entries = (raw.get("food_entries") or {}).get("food_entry", [])
    if isinstance(entries, dict):
        entries = [entries]

    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for e in entries:
        totals["calories"] += float(e.get("calories", 0))
        totals["protein"]  += float(e.get("protein", 0))
        totals["fat"]      += float(e.get("fat", 0))
        totals["carbs"]    += float(e.get("carbohydrate", 0))
    return {k: round(v, 1) for k, v in totals.items()}


def fetch_burned(creds: dict, d: date):
    """
    Fetch Garmin-synced burned calories (TDEE) from the FatSecret exercise diary.

    FatSecret receives a finalized daily summary from Garmin after the day ends
    and stores it as a single exercise entry named "Garmin" with minutes=1440
    (full 24-hour day).  This is the same value shown in the FatSecret app and
    is always complete — no midnight-gap issue.

    Returns float (kcal) or None if no Garmin data exists for this date.
    """
    auth = OAuth1(
        creds["consumer_key"],
        creds["consumer_secret"],
        creds["access_token"],
        creds["access_token_secret"],
        signature_type="query",
    )
    try:
        resp = requests.post(
            FATSECRET_API,
            params={
                "method": "exercise_entries.get",
                "date":   str(_epoch_days(d)),
                "format": "json",
            },
            auth=auth,
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()
    except Exception as exc:
        log.warning("FatSecret exercise fetch failed for %s: %s", d.isoformat(), exc)
        return None

    if not isinstance(raw, dict) or "error" in raw:
        return None

    entry = (raw.get("exercise_entries") or {}).get("exercise_entry")
    if not entry:
        return None
    if isinstance(entry, dict):
        entry = [entry]

    # Garmin sends one full-day TDEE entry (1440 min = 24 h).
    # Filter to that entry to avoid double-counting manually logged workouts
    # which are already included in the Garmin TDEE total.
    total = sum(
        float(e.get("calories", 0))
        for e in entry
        if str(e.get("minutes", "")) == "1440"
           or e.get("exercise_name", "").lower() == "garmin"
    )
    return round(total, 1) if total > 0 else None


def fetch_day(creds: dict, d: date):
    """
    Convenience wrapper: fetch + summarise for one date.
    Returns totals dict, or None if the request fails entirely.
    """
    try:
        raw = fetch_entries(creds, d)
        return summarise(raw)
    except Exception as exc:
        log.warning("FatSecret fetch failed for %s: %s", d.isoformat(), exc)
        return None
