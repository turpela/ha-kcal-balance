"""
ha.py — Home Assistant Supervisor API helpers and sensor push logic.
"""

import json
import logging
import urllib.request

log = logging.getLogger("kcal-balance")

HA_API = "http://supervisor/core/api"


# ---------------------------------------------------------------------------
# Generic GET / POST
# ---------------------------------------------------------------------------

def ha_get(supervisor_token, entity_id):
    """Read a HA sensor state. Returns float or None on error/unavailable."""
    req = urllib.request.Request(
        f"{HA_API}/states/{entity_id}",
        headers={"Authorization": f"Bearer {supervisor_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            state = data.get("state", "")
            if state in ("unavailable", "unknown", ""):
                return None
            return float(state)
    except Exception as exc:
        log.warning("Could not read %s: %s", entity_id, exc)
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

def push_sensors(supervisor_token, suffix, label, totals, burned,
                 goal, goal_mode, goal_source,
                 weekly_totals, weekly_goal, days_tracked):
    """
    Push all HA sensors for one user.

    Sensor IDs use the suffix (u1 / u2):
      sensor.fatsecret_u1
      sensor.kcal_u1_goal / _balance / _net
      sensor.kcal_u1_weekly_consumed / _weekly_goal / _weekly_balance
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

    # --- daily goal + balance ---
    if goal is not None:
        ha_post(supervisor_token, f"sensor.kcal_{suffix}_goal", goal, {
            "unit_of_measurement": "kcal",
            "friendly_name": f"Kcal Goal {label}",
            "goal_mode": goal_mode,
            "source":    goal_source,
        })
        balance = round(goal - totals["calories"], 1)
        ha_post(supervisor_token, f"sensor.kcal_{suffix}_balance", balance, {
            "unit_of_measurement": "kcal",
            "friendly_name": f"Kcal Balance {label}",
            "consumed": totals["calories"],
            "goal":     goal,
            "status":   "under" if balance >= 0 else "over",
        })

    # --- net energy (Garmin burned − consumed) ---
    if burned is not None:
        net = round(burned - totals["calories"], 1)
        ha_post(supervisor_token, f"sensor.kcal_{suffix}_net", net, {
            "unit_of_measurement": "kcal",
            "friendly_name": f"Kcal Net {label}",
            "consumed": totals["calories"],
            "burned":   burned,
            "status":   "deficit" if net >= 0 else "surplus",
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

    # --- weekly goal + balance ---
    if goal is not None and weekly_goal is not None:
        ha_post(supervisor_token, f"sensor.kcal_{suffix}_weekly_goal", weekly_goal, {
            "unit_of_measurement": "kcal",
            "friendly_name": f"Kcal Weekly Goal {label}",
        })
        weekly_balance = round(weekly_goal - weekly_totals["calories"], 1)
        ha_post(supervisor_token, f"sensor.kcal_{suffix}_weekly_balance", weekly_balance, {
            "unit_of_measurement": "kcal",
            "friendly_name": f"Kcal Weekly Balance {label}",
            "consumed": weekly_totals["calories"],
            "goal":     weekly_goal,
            "status":   "under" if weekly_balance >= 0 else "over",
        })

    log.debug("[%s] Sensors pushed", label)
