# Phase 1 — Garmin Connect Setup

This guide configures two independent Garmin Connect integration instances via HACS, one per user. All sensors follow the naming convention `sensor.garmin_u1_*` and `sensor.garmin_u2_*`.

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

---

## 2. Add Integration Instances

You need to add the integration **twice** — once per user account.

### User 1

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Garmin Connect**
3. Enter User 1's Garmin credentials
4. After setup, rename the integration entry to something like `Garmin U1`

### User 2

Repeat the same steps with User 2's Garmin credentials and rename to `Garmin U2`.

> **Note:** If Garmin prompts for MFA, complete it during initial setup. The integration stores a session cookie — re-authentication may be needed occasionally.

---

## 3. Rename Sensors

By default, the integration names sensors after the account owner's display name, e.g. `sensor.janne_steps`. You need to rename them to match the project convention.

For each sensor you intend to use, go to:
**Settings → Devices & Services → [Garmin instance] → [entity] → ⚙ → Rename**

### User 1 target names

| Original (example)          | Target name                          |
|-----------------------------|--------------------------------------|
| `sensor.joe_calories`     | `sensor.garmin_u1_calories`          |
| `sensor.joe_total_kcal`   | `sensor.garmin_u1_total_kcal`        |
| `sensor.joe_steps`        | `sensor.garmin_u1_steps`             |
| `sensor.joe_active_kcal`  | `sensor.garmin_u1_active_kcal`       |
| `sensor.joe_bmr_kcal`     | `sensor.garmin_u1_bmr_kcal`          |
| `sensor.joe_body_battery` | `sensor.garmin_u1_body_battery`      |
| `sensor.joe_heart_rate`   | `sensor.garmin_u1_heart_rate`        |
| `sensor.joe_stress`       | `sensor.garmin_u1_stress`            |
| `sensor.joe_sleep_hours`  | `sensor.garmin_u1_sleep_hours`       |
| `sensor.joe_sleep_score`  | `sensor.garmin_u1_sleep_score`       |
| `sensor.joe_vo2_max`      | `sensor.garmin_u1_vo2_max`           |
| `sensor.joe_activities`   | `sensor.garmin_u1_activities`        |

### User 2 target names

Same pattern, replacing `u1` with `u2` and the original account name prefix accordingly.

> **Tip:** Use the entity ID field (not just the friendly name) to set the ID. In the rename dialog, scroll down to **Entity ID** and set it manually to `sensor.garmin_u1_*`.

---

## 4. Key Sensors for This Project

These are the sensors used downstream in template sensors and dashboards.

### Calorie & Energy

| Sensor                         | Description                                    |
|--------------------------------|------------------------------------------------|
| `sensor.garmin_u1_total_kcal`  | Total daily calorie burn (TDEE estimate)       |
| `sensor.garmin_u1_active_kcal` | Active/exercise calories only                  |
| `sensor.garmin_u1_bmr_kcal`    | Basal Metabolic Rate (resting calories)        |

> `total_kcal` = `bmr_kcal` + `active_kcal`. This is used as **TDEE** for goal calculations.

### Activity

| Sensor                         | Description                                    |
|--------------------------------|------------------------------------------------|
| `sensor.garmin_u1_steps`       | Steps today                                    |
| `sensor.garmin_u1_activities`  | JSON attribute with today's activity list      |
| `sensor.garmin_u1_floors`      | Floors climbed                                 |
| `sensor.garmin_u1_distance`    | Distance in km                                 |
| `sensor.garmin_u1_intensity`   | Intensity minutes                              |

### Wellness

| Sensor                          | Description                                   |
|---------------------------------|-----------------------------------------------|
| `sensor.garmin_u1_body_battery` | Body Battery (0–100)                          |
| `sensor.garmin_u1_heart_rate`   | Resting heart rate                            |
| `sensor.garmin_u1_stress`       | Average stress level                          |
| `sensor.garmin_u1_sleep_hours`  | Total sleep duration (hours)                  |
| `sensor.garmin_u1_sleep_score`  | Sleep quality score                           |
| `sensor.garmin_u1_vo2_max`      | VO2 Max estimate                              |
| `sensor.garmin_u1_respiration`  | Average respiration rate                      |
| `sensor.garmin_u1_spo2`         | Blood oxygen saturation (%)                   |

---

## 5. Polling & Update Interval

The integration polls Garmin Connect on a schedule. By default this is every 15–30 minutes.

To adjust, add to your `configuration.yaml`:

```yaml
# configuration.yaml
garmin_connect:
  scan_interval: 900  # seconds (15 minutes)
```

> Garmin rate-limits API access. Polling more frequently than every 10 minutes risks temporary account lockouts.

---

## 6. Verify Data Is Flowing

In Home Assistant Developer Tools → States, search for `garmin_u1` and `garmin_u2`. You should see both sets of sensors with current values.

If sensors show `unavailable`:
- Confirm the Garmin device has synced to the app recently
- Check **Settings → Devices & Services → Garmin Connect → [instance] → Configure** to re-authenticate if needed
- Check Home Assistant logs for OAuth errors (**Settings → System → Logs**)

---

## 7. Activities Attribute Structure

The `sensor.garmin_u1_activities` sensor exposes a JSON list in its `data` attribute. Each entry looks like:

```json
{
  "activityId": 1234567890,
  "activityName": "Running",
  "startTimeLocal": "2024-01-15 07:30:00",
  "duration": 3600,
  "calories": 450,
  "distance": 8500,
  "averageHR": 148,
  "maxHR": 172
}
```

This will be parsed in Phase 3 (template sensors) to display individual activities on the dashboard.

---

## Phase 1 Checklist

- [ ] HACS integration installed
- [ ] User 1 instance added and authenticated
- [ ] User 2 instance added and authenticated
- [ ] All `sensor.garmin_u1_*` entity IDs set correctly
- [ ] All `sensor.garmin_u2_*` entity IDs set correctly
- [ ] Key sensors (total_kcal, active_kcal, bmr_kcal) verified with live data
- [ ] Activities attribute confirmed non-empty after a workout sync

---

## Next Step

→ [Phase 2: FatSecret Integration](../fatsecret/FATSECRET_SETUP.md)
