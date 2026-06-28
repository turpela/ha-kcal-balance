# ha-kcal-balance

A Home Assistant project for tracking daily calorie balance across two users, each with a Garmin device and a FatSecret food diary account.

---

## What It Does

- Tracks **calories consumed** (FatSecret) vs **calories burned** (Garmin) per user
- Calculates daily **deficit or surplus**
- Shows **macronutrients** — protein, fat, carbohydrates
- Displays **individual activities** from Garmin (runs, workouts, etc.)
- Applies a **dynamic calorie goal** based on a selectable mode:
  - **Weight Loss** — TDEE − 500 kcal
  - **Maintenance** — TDEE ±0
  - **Muscle Gain** — TDEE + 300 kcal
- TDEE is sourced directly from Garmin (BMR + active calories)

---

## Architecture

### Data Sources

| Source          | Integration                              | Users  |
|-----------------|------------------------------------------|--------|
| Garmin Connect  | cyberjunky/home-assistant-garmin_connect | U1, U2 |
| FatSecret       | Custom Python REST script                | U1, U2 |

### Sensor Naming

Garmin sensors use the integration's default entity IDs. With two instances, User 1 gets the base name and User 2 gets a `_2` suffix:

```
User 1:  sensor.garmin_connect_calories
User 2:  sensor.garmin_connect_calories_2
```

FatSecret sensors are produced by custom Python scripts and named with a user suffix:

```
sensor.fatsecret_u1_calories
sensor.fatsecret_u2_protein
```

---

## Implementation Phases

| Phase | Description              | Status       | Guide |
|-------|--------------------------|--------------|-------|
| 1     | Garmin Connect setup     | ✅ Complete   | [GARMIN_SETUP.md](garmin/GARMIN_SETUP.md) |
| 2     | FatSecret integration    | ⏳ Pending   | [FATSECRET_SETUP.md](fatsecret/FATSECRET_SETUP.md) |
| 3     | Template sensors         | ⏳ Pending   | [TEMPLATES.md](templates/TEMPLATES.md) |
| 4     | Lovelace dashboards      | ⏳ Pending   | [LOVELACE.md](lovelace/LOVELACE.md) |

---

## Repository Structure

```
ha-kcal-balance/
├── garmin/
│   └── GARMIN_SETUP.md        # Phase 1: Garmin HACS integration guide
├── fatsecret/
│   ├── FATSECRET_SETUP.md     # Phase 2: FatSecret integration guide
│   ├── fatsecret_u1.py        # FatSecret polling script — User 1
│   └── fatsecret_u2.py        # FatSecret polling script — User 2
├── templates/
│   ├── TEMPLATES.md           # Phase 3: Template sensor guide
│   └── sensors.yaml           # Template sensor definitions
├── lovelace/
│   ├── LOVELACE.md            # Phase 4: Dashboard guide
│   ├── dashboard_u1.yaml      # User 1 dashboard
│   └── dashboard_u2.yaml      # User 2 dashboard
├── README.md
└── CHANGELOG.md
```

---

## Prerequisites

- Home Assistant (any recent version)
- HACS installed
- Two Garmin Connect accounts with active devices
- Two FatSecret developer API key pairs (one per user account)

---

## Getting Started

Follow the phase guides in order:

1. [Garmin Connect Setup](garmin/GARMIN_SETUP.md)
2. FatSecret Integration _(coming in Phase 2)_
3. Template Sensors _(coming in Phase 3)_
4. Lovelace Dashboards _(coming in Phase 4)_
