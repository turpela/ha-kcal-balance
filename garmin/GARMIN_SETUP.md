# Phase 1 — Garmin Connect Setup

This guide configures two independent Garmin Connect integration instances via HACS (v3.0), one per user.

---

## Prerequisites

- Home Assistant with HACS installed and running
- Two separate Garmin Connect accounts (one per user)
- Each account must have an active Garmin device syncing data

---

## 1. Install the Integration

Install once — both user instances share the same integration code.

1. Open HACS → **Integrations**
2. Search for **Garmin Connect**
3. Install **cyberjunky/home-assistant-garmin_connect**
4. Restart Home Assistant

> **v3.0 note:** This is a ground-up rewrite using the new `ha-garmin` library. If upgrading from an older version, re-authentication will be required — old tokens are not compatible.

---

## 2. Add Integration Instances

You need to add the integration **twice** — once per user account.

### User 1

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Garmin Connect**
3. Enter User 1's Garmin credentials
4. If MFA is enabled, enter the verification code when prompted

### User 2

Repeat the same steps with User 2's credentials.

When two instances are configured, Home Assistant disambiguates entity IDs from the second account with a `_2` suffix (e.g. `sensor.garmin_connect_calories_2`).

---

## 3. Configure Scan Interval

The default poll interval is **300 seconds (5 minutes)**. The minimum allowed is **60 seconds**.

To change it:

1. Go to **Settings → Devices & Services → Garmin Connect → Configure**
2. Set **Scan interval** to your preferred value (in seconds)
3. Repeat for the second instance

> Avoid setting the interval below 300 seconds. Garmin rate-limits cloud API access, and excessive polling may trigger temporary blocks.

---

## 4. Key Sensors for This Project

Entity IDs follow the pattern `sensor.garmin_connect_[sensor_name]`. The second user's sensors get a `_2` suffix.

### Calorie & Energy

| User 1                                    | User 2                                     | Description              |
|-------------------------------------------|--------------------------------------------|--------------------------|
| `sensor.garmin_connect_calories`          | `sensor.garmin_connect_calories_2`         | Total daily burn (TDEE)  |
| `sensor.garmin_connect_active_calories`   | `sensor.garmin_connect_active_calories_2`  | Calories from activity   |
| `sensor.garmin_connect_bmr_calories`      | `sensor.garmin_connect_bmr_calories_2`     | Basal Metabolic Rate     |

> `calories` = `bmr_calories` + `active_calories`. Used as **TDEE** in the calorie goal template (Phase 3).

### Activity & Steps

| User 1                                    | User 2                                     | Description              |
|-------------------------------------------|--------------------------------------------|--------------------------|
| `sensor.garmin_connect_steps`             | `sensor.garmin_connect_steps_2`            | Daily step count         |
| `sensor.garmin_connect_distance`          | `sensor.garmin_connect_distance_2`         | Distance in meters       |
| `sensor.garmin_connect_floors_ascended`   | `sensor.garmin_connect_floors_ascended_2`  | Floors climbed           |
| `sensor.garmin_connect_last_activity`     | `sensor.garmin_connect_last_activity_2`    | Most recent activity     |
| `sensor.garmin_connect_last_activities`   | `sensor.garmin_connect_last_activities_2`  | Recent activities list   |

### Wellness

| User 1                                        | User 2                                         | Description           |
|-----------------------------------------------|------------------------------------------------|-----------------------|
| `sensor.garmin_connect_body_battery`          | `sensor.garmin_connect_body_battery_2`         | Body Battery (0–100)  |
| `sensor.garmin_connect_resting_heart_rate`    | `sensor.garmin_connect_resting_heart_rate_2`   | Resting heart rate    |
| `sensor.garmin_connect_average_stress_level`  | `sensor.garmin_connect_average_stress_level_2` | Average stress        |
| `sensor.garmin_connect_sleep_score`           | `sensor.garmin_connect_sleep_score_2`          | Sleep quality score   |
| `sensor.garmin_connect_sleep_duration`        | `sensor.garmin_connect_sleep_duration_2`       | Total sleep time      |
| `sensor.garmin_connect_vo2_max`               | `sensor.garmin_connect_vo2_max_2`              | VO2 Max estimate      |
| `sensor.garmin_connect_latest_spo2`           | `sensor.garmin_connect_latest_spo2_2`          | Blood oxygen (%)      |
| `sensor.garmin_connect_hrv_weekly_average`    | `sensor.garmin_connect_hrv_weekly_average_2`   | HRV weekly average    |

---

## 5. Activities Attribute

The `sensor.garmin_connect_last_activities` sensor exposes a `last_activities` attribute — a list of recent activities. Each entry contains:

```json
{
  "activityId": 1234567890,
  "activityType": "running",
  "activityName": "Morning Run",
  "startTime": "2024-01-15 07:30:00",
  "duration": 3600,
  "calories": 450,
  "distance": 8500,
  "averageHR": 148,
  "maxHR": 172
}
```

This attribute is parsed in Phase 3 (template sensors) to display per-activity rows on the dashboard.

---

## 6. Data Update Flow

v3.0 uses **8 independent coordinators** that fetch data in parallel on each poll:

| Coordinator    | Data fetched                                                              |
|----------------|---------------------------------------------------------------------------|
| Core           | Steps, distance, calories, heart rate, stress, sleep, body battery, SpO2 |
| Activity       | Last activity, recent activities, workouts                                |
| Training       | Training readiness/status, HRV, lactate threshold, VO2 Max               |
| Body           | Weight, BMI, body fat, muscle mass, hydration                            |
| Goals          | Active/future goals, goal history, badges                                 |
| Gear           | Shoes, bikes, equipment usage                                             |
| Blood Pressure | Systolic, diastolic, pulse                                                |
| Menstrual      | Cycle phase, day, fertile window (disabled by default)                   |

> Data is only as fresh as the last device sync. Garmin devices sync when in Bluetooth range of the paired phone or via Wi-Fi. The HA integration picks up new data on its next poll.

---

## 7. Verify Data Is Flowing

In **Developer Tools → States**, search for `garmin_connect`. You should see sensors for both users — User 1 without suffix, User 2 with `_2`.

If sensors show `unavailable`:
- Confirm the Garmin device has recently synced to the Garmin Connect app
- Go to **Settings → Devices & Services → Garmin Connect → Reconfigure** and re-authenticate
- Check logs at **Settings → System → Logs** — enable debug logging if needed:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.garmin_connect: debug
```

---

## Phase 1 Checklist

- [ ] HACS integration (v3.0) installed
- [ ] User 1 instance added and authenticated
- [ ] User 2 instance added and authenticated
- [ ] Scan interval configured for both instances (default 300 s is fine)
- [ ] Key sensors (calories, active_calories, bmr_calories) showing live values for both users
- [ ] `last_activities` attribute non-empty after a workout sync

---

## Next Step

→ [Phase 2: FatSecret Integration](../fatsecret/FATSECRET_SETUP.md)
