# Garmin Connect — Legacy Setup Guide

> **This guide is no longer required for the Kcal Balance add-on.**
>
> As of v2.4.0, burned calories are sourced directly from FatSecret's exercise diary (`exercise_entries.get`), which receives a finalized daily activity summary from Garmin after each day ends. The Garmin Connect HACS integration is not needed.
>
> To get Garmin data into the add-on, connect Garmin to FatSecret via the FatSecret mobile app: **Me → Connected Apps → Garmin**. See the [FatSecret Setup Guide](../fatsecret/FATSECRET_SETUP.md) for details.

---

The content below documents the Garmin Connect HACS integration (cyberjunky/home-assistant-garmin_connect). It remains useful if you want Garmin sensors in Home Assistant for other purposes (dashboards, automations, sleep tracking, etc.), but it is not a dependency of this add-on.

---

## Installation

Install once — both user instances share the same integration code.

1. Open HACS → **Integrations**
2. Search for **Garmin Connect**
3. Install **cyberjunky/home-assistant-garmin_connect**
4. Restart Home Assistant

---

## Adding Integration Instances

Add the integration twice — once per user account.

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Garmin Connect**
3. Enter the user's Garmin credentials

When two instances are configured, Home Assistant disambiguates entity IDs from the second account with a `_2` suffix (e.g. `sensor.garmin_connect_calories_2`).

---

## Key Sensors

### Calorie & Energy

| User 1 | User 2 | Description |
|--------|--------|-------------|
| `sensor.garmin_connect_calories` | `sensor.garmin_connect_calories_2` | Total daily burn (TDEE) |
| `sensor.garmin_connect_active_calories` | `sensor.garmin_connect_active_calories_2` | Calories from activity |
| `sensor.garmin_connect_bmr_calories` | `sensor.garmin_connect_bmr_calories_2` | Basal Metabolic Rate |

### Activity & Steps

| User 1 | User 2 | Description |
|--------|--------|-------------|
| `sensor.garmin_connect_steps` | `sensor.garmin_connect_steps_2` | Daily step count |
| `sensor.garmin_connect_distance` | `sensor.garmin_connect_distance_2` | Distance in meters |
| `sensor.garmin_connect_floors_ascended` | `sensor.garmin_connect_floors_ascended_2` | Floors climbed |

### Wellness

| User 1 | User 2 | Description |
|--------|--------|-------------|
| `sensor.garmin_connect_body_battery` | `sensor.garmin_connect_body_battery_2` | Body Battery (0–100) |
| `sensor.garmin_connect_resting_heart_rate` | `sensor.garmin_connect_resting_heart_rate_2` | Resting heart rate |
| `sensor.garmin_connect_average_stress_level` | `sensor.garmin_connect_average_stress_level_2` | Average stress |
| `sensor.garmin_connect_sleep_score` | `sensor.garmin_connect_sleep_score_2` | Sleep quality score |
| `sensor.garmin_connect_vo2_max` | `sensor.garmin_connect_vo2_max_2` | VO2 Max estimate |
| `sensor.garmin_connect_hrv_weekly_average` | `sensor.garmin_connect_hrv_weekly_average_2` | HRV weekly average |

---

## Scan Interval

The default poll interval is 300 seconds (5 minutes). To change it: **Settings → Devices & Services → Garmin Connect → Configure**.

> Avoid setting the interval below 300 seconds — Garmin rate-limits cloud API access.
