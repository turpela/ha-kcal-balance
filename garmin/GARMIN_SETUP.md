# Phase 1 — Garmin Connect Setup

This guide configures two independent Garmin Connect integration instances via HACS (v3.0), one per user. All sensors follow the naming convention `sensor.garmin_u1_*` and `sensor.garmin_u2_*`.

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
5. After setup, rename the integration entry to `Garmin U1`

### User 2

Repeat the same steps with User 2's credentials. Rename the entry to `Garmin U2`.

When two instances are configured, Home Assistant may append `_2` or a similar suffix to disambiguate entity IDs from the second account. You will rename all of them in the next step.

---

## 3. Configure Scan Interval

The default poll interval is **300 seconds (5 minutes)**. The minimum allowed is **60 seconds**.

To change it:

1. Go to **Settings → Devices & Services → Garmin Connect → Configure**
2. Set **Scan interval** to your preferred value (in seconds)
3. Repeat for the second instance

> Avoid setting the interval below 300 seconds. Garmin rate-limits cloud API access, and excessive polling may trigger temporary blocks. The default of 5 minutes is a safe and practical choice.

---

## 4. Rename Sensors

By default, v3.0 creates entity IDs under `sensor.garmin_connect_[sensor_name]`. When a second instance is added, HA disambiguates with a suffix like `sensor.garmin_connect_calories_2`.

You need to rename entities from both instances to match the project convention.

For each sensor, go to:
**Settings → Devices & Services → [Garmin instance] → [entity] → ⚙ → Rename**

In the rename dialog, scroll down to **Entity ID** and set it explicitly.

### User 1 — Calorie & Energy

| Default entity ID                           | Target entity ID                  |
|---------------------------------------------|-----------------------------------|
| `sensor.garmin_connect_calories`            | `sensor.garmin_u1_calories`       |
| `sensor.garmin_connect_active_calories`     | `sensor.garmin_u1_active_kcal`    |
| `sensor.garmin_connect_bmr_calories`        | `sensor.garmin_u1_bmr_kcal`       |
| `sensor.garmin_connect_burned_calories`     | `sensor.garmin_u1_burned_kcal`    |

### User 1 — Activity & Steps

| Default entity ID                           | Target entity ID                  |
|---------------------------------------------|-----------------------------------|
| `sensor.garmin_connect_steps`               | `sensor.garmin_u1_steps`          |
| `sensor.garmin_connect_distance`            | `sensor.garmin_u1_distance`       |
| `sensor.garmin_connect_floors_ascended`     | `sensor.garmin_u1_floors`         |
| `sensor.garmin_connect_last_activities`     | `sensor.garmin_u1_activities`     |
| `sensor.garmin_connect_last_activity`       | `sensor.garmin_u1_last_activity`  |
| `sensor.garmin_connect_intensity_minutes`   | `sensor.garmin_u1_intensity`      |

### User 1 — Wellness

| Default entity ID                           | Target entity ID                      |
|---------------------------------------------|---------------------------------------|
| `sensor.garmin_connect_body_battery`        | `sensor.garmin_u1_body_battery`       |
| `sensor.garmin_connect_resting_heart_rate`  | `sensor.garmin_u1_heart_rate`         |
| `sensor.garmin_connect_average_stress_level`| `sensor.garmin_u1_stress`             |
| `sensor.garmin_connect_sleep_score`         | `sensor.garmin_u1_sleep_score`        |
| `sensor.garmin_connect_sleep_duration`      | `sensor.garmin_u1_sleep_hours`        |
| `sensor.garmin_connect_vo2_max`             | `sensor.garmin_u1_vo2_max`            |
| `sensor.garmin_connect_latest_spo2`         | `sensor.garmin_u1_spo2`               |
| `sensor.garmin_connect_latest_respiration`  | `sensor.garmin_u1_respiration`        |
| `sensor.garmin_connect_hrv_weekly_average`  | `sensor.garmin_u1_hrv`                |

### User 2

Same pattern, replacing `u1` with `u2`. The second instance's default IDs will likely have a `_2` suffix (e.g. `sensor.garmin_connect_calories_2`) — rename them to the clean `u2` targets above.

---

## 5. Key Sensors for This Project

### Calorie Goal Calculation

| Sensor                          | Description                                 |
|---------------------------------|---------------------------------------------|
| `sensor.garmin_u1_calories`     | Total daily calorie burn (TDEE)             |
| `sensor.garmin_u1_active_kcal`  | Calories from activity only                 |
| `sensor.garmin_u1_bmr_kcal`     | Basal Metabolic Rate (resting)              |

> `calories` = `bmr_kcal` + `active_kcal`. This is used as **TDEE** in the calorie goal template (Phase 3).

### Activities List

| Sensor                        | Key attribute     | Description                              |
|-------------------------------|-------------------|------------------------------------------|
| `sensor.garmin_u1_activities` | `last_activities` | List of recent activities with details  |

Each entry in `last_activities` contains:

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

| Coordinator   | Data fetched                                                                 |
|---------------|------------------------------------------------------------------------------|
| Core          | Steps, distance, calories, heart rate, stress, sleep, body battery, SpO2    |
| Activity      | Last activity, recent activities, workouts                                   |
| Training      | Training readiness/status, HRV, lactate threshold, VO2 Max                  |
| Body          | Weight, BMI, body fat, muscle mass, hydration                               |
| Goals         | Active/future goals, goal history, badges                                    |
| Gear          | Shoes, bikes, equipment usage                                                |
| Blood Pressure| Systolic, diastolic, pulse                                                   |
| Menstrual     | Cycle phase, day, fertile window (disabled by default)                      |

> Data is only as fresh as the last device sync. Garmin devices sync when in Bluetooth range of the paired phone or via Wi-Fi. The HA integration then picks up the new data on its next poll.

---

## 7. Verify Data Is Flowing

In **Developer Tools → States**, search for `garmin_u1` and `garmin_u2`. You should see both sets of sensors with current values.

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
- [ ] All `sensor.garmin_u1_*` entity IDs set correctly
- [ ] All `sensor.garmin_u2_*` entity IDs set correctly
- [ ] Key sensors (calories, active_kcal, bmr_kcal) showing live values
- [ ] `sensor.garmin_u1_activities` `last_activities` attribute non-empty after a workout sync

---

## Next Step

→ [Phase 2: FatSecret Integration](../fatsecret/FATSECRET_SETUP.md)
