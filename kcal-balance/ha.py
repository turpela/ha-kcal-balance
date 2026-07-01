"""
ha.py — Home Assistant Supervisor API helpers and sensor push logic.
"""

import json
import logging
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger("kcal-balance")

HA_API    = "http://supervisor/core/api"
_TIMEZONE = ZoneInfo("Europe/Helsinki")


# ---------------------------------------------------------------------------
# Generic GET / POST
# ---------------------------------------------------------------------------

def ha_get(supervisor_token, entity_id):
    """
    Read a HA sensor state.

    Returns (value: float|None, sensor_date: date|None) where sensor_date is
    the Helsinki-local date when the sensor value last changed.  Callers can
    use sensor_date to detect whether the Garmin sensor is still showing
    yesterday's final reading (last sync before midnight).
    """
    req = urllib.request.Request(
        f"{HA_API}/states/{entity_id}",
        headers={"Authorization": f"Bearer {supervisor_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            state = data.get("state", "")
            if state in ("unavailable", "unknown", ""):
                return None, None
            value = float(state)
            # last_changed: when the state VALUE last changed (not just polled)
            ts_str = data.get("last_changed") or data.get("last_updated")
            sensor_date = _parse_date(ts_str) if ts_str else None
            return value, sensor_date
    except Exception as exc:
        log.warning("Could not read %s: %s", entity_id, exc)
        return None, None


def _parse_date(ts_str):
    """Parse an ISO 8601 HA timestamp to a Helsinki local date."""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.astimezone(_TIMEZONE).date()
    except Exception:
        return None


def ha_post(supervisor_token, entity_id, state, attributes):
    """Push a sensor state to HA. Returns HTTP status code."""
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


# ---------------------------------------------------------------------------
# Sensor push — one call per user per poll
# ---------------------------------------------------------------------------

def push_sensors(supervisor_token, suffix, label,
                 totals, burned, net,
                 gda, gda_pct,
                 weekly_totals, weekly_gda, weekly_gda_pct, days_tracked):
    """
    Push all HA sensors for one user.

    Sensors (u1 shown; u2 mirrors with _u2 suffix):
      sensor.fatsecret_u1            — consumed today (kcal + macro attrs)
      sensor.kcal_u1_net             — burned − consumed
      sensor.kcal_u1_gda_pct         — consumed as % of GDA
      sensor.kcal_u1_weekly_consumed — week total (kcal + macro attrs)
      sensor.kcal_u1_weekly_gda_pct  — weekly consumed as % of pro-rated GDA
    """
    # --- consumed today ---
    ha_post(supervisor_token, f"sensor.fatsecret_{suffix}", totals["calories"], {
        "unit_of_measurement": "kcal",
        "friendly_name": f"FatSecret {label}",
        "calories": totals["calories"],
        "protein":  totals["protein"],
        "fat":      totals["fat"],
        "carbs":    totals["carbs"],
    })

    # --- net energy (Garmin burned − consumed) ---
    if net is not None:
        ha_post(supervisor_token, f"sensor.kcal_{suffix}_net", net, {
            "unit_of_measurement": "kcal",
            "friendly_name": f"Kcal Net {label}",
            "consumed": totals["calories"],
            "burned":   burned,
            "status":   "deficit" if net >= 0 else "surplus",
        })

    # --- GDA % ---
    if gda_pct is not None:
        ha_post(supervisor_token, f"sensor.kcal_{suffix}_gda_pct", round(gda_pct, 1), {
            "unit_of_measurement": "%",
            "friendly_name": f"Kcal GDA% {label}",
            "gda": gda,
            "consumed": totals["calories"],
        })

    # --- weekly consumed ---
    ha_post(supervisor_token, f"sensor.kcal_{suffix}_weekly_consumed",
            weekly_totals["calories"], {
        "unit_of_measurement": "kcal",
        "friendly_name": f"Kcal Weekly Consumed {label}",
        "protein":      weekly_totals["protein"],
        "fat":          weekly_totals["fat"],
        "carbs":        weekly_totals["carbs"],
        "days_tracked": days_tracked,
    })

    # --- weekly GDA % ---
    if weekly_gda_pct is not None:
        ha_post(supervisor_token, f"sensor.kcal_{suffix}_weekly_gda_pct",
                round(weekly_gda_pct, 1), {
            "unit_of_measurement": "%",
            "friendly_name": f"Kcal Weekly GDA% {label}",
            "weekly_gda": weekly_gda,
            "weekly_consumed": weekly_totals["calories"],
        })

    log.debug("[%s] Sensors pushed", label)
