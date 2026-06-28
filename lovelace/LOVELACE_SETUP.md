# Phase 4 — Lovelace Dashboard Setup

No HACS or custom cards required — everything uses built-in HA card types.

---

## Prerequisites

Make sure these sensors are populated before adding the dashboard:

| Sensor | Source |
|--------|--------|
| `sensor.fatsecret_u1` | Kcal Balance add-on |
| `sensor.kcal_u1_goal` | Kcal Balance add-on |
| `sensor.kcal_u1_balance` | Kcal Balance add-on |
| `sensor.kcal_u1_net` | Kcal Balance add-on |
| `sensor.garmin_connect_calories` | Garmin Connect (HACS) |
| `sensor.garmin_connect_steps` | Garmin Connect (HACS) |
| `sensor.garmin_connect_body_battery` | Garmin Connect (HACS) |
| `sensor.garmin_connect_sleep_score` | Garmin Connect (HACS) |

User 2 mirrors with `_u2` / `_2` suffixes.

---

## Adding the Dashboard

### Option A — New dashboard (recommended)

1. Go to **Settings → Dashboards → Add Dashboard**
2. Name it **Kcal Balance**, icon `mdi:scale-balance`
3. Open the new dashboard
4. Click the **⋮ menu → Edit dashboard**
5. Click **⋮ menu → Raw configuration editor**
6. Replace all content with the contents of `lovelace/dashboard.yaml`
7. Click **Save**

### Option B — Add as a new view to an existing dashboard

1. Open your existing dashboard
2. Click **⋮ menu → Edit dashboard**
3. Click **+** to add a new view
4. Switch to **Raw configuration editor**
5. Paste the contents of the `views:` section from `lovelace/dashboard.yaml`

---

## Gauge Thresholds Explained

| Sensor | Green | Yellow | Red |
|--------|-------|--------|-----|
| Remaining Today (`kcal_balance`) | ≥ 100 kcal left | 0–100 (at limit) | < 0 (over goal) |
| Net Energy (`kcal_net`) | ≥ 0 (deficit) | −200 to 0 (near break-even) | < −200 (surplus) |

Adjust `min`, `max`, and `severity` values in the YAML to match your personal targets.

---

## Adjusting Garmin Entity IDs

If your Garmin entity IDs differ from the defaults, update them in the YAML:

```yaml
# Default assumed in dashboard.yaml:
sensor.garmin_connect_calories       # U1 total burned
sensor.garmin_connect_steps          # U1 steps
sensor.garmin_connect_body_battery   # U1 body battery
sensor.garmin_connect_sleep_score    # U1 sleep score

# User 2 equivalents:
sensor.garmin_connect_calories_2
sensor.garmin_connect_steps_2
sensor.garmin_connect_body_battery_2
sensor.garmin_connect_sleep_score_2
```

Find your exact entity IDs at **Developer Tools → States**, search `garmin`.

---

## User 2 Not Configured Yet?

The U2 column will show "Entity unavailable" until:
1. U2 FatSecret credentials are added to the add-on config
2. U2 Garmin instance is added in HA

The dashboard works fine with just U1 in the meantime.

---

← [Phase 3: Template Sensors](../templates/TEMPLATES.md)
