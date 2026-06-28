# Phase 3 — Sensors Reference

The add-on automatically creates all sensors below on every poll. No `configuration.yaml` editing required.

---

## Sensors Created

### Per User — User 1 (U1) / User 2 (U2)

| Sensor | State | Key Attributes |
|--------|-------|----------------|
| `sensor.fatsecret_u1` | Calories consumed today (kcal) | `protein`, `fat`, `carbs` |
| `sensor.kcal_u1_goal` | Daily calorie goal (kcal) | `goal_mode`, `source` |
| `sensor.kcal_u1_balance` | Goal minus consumed (kcal) | `consumed`, `goal`, `status` |
| `sensor.kcal_u1_net` | Garmin burned minus consumed (kcal) | `consumed`, `burned`, `status` |

User 2 mirrors with `_u2` suffix.

---

## Sensor Details

### `sensor.fatsecret_u1`
- **State**: total calories consumed today
- **Attributes**: `calories`, `protein` (g), `fat` (g), `carbs` (g)
- **Updates**: every scan interval (default 300 s)

### `sensor.kcal_u1_goal`
- **State**: daily calorie goal
- **Attributes**:
  - `goal_mode`: `weight_loss` | `maintenance` | `muscle_gain`
  - `source`: `garmin` (TDEE-based) | `fixed` (manual) | `none`
- **Notes**: when source is `garmin`, goal = Garmin TDEE + offset. Offset defaults: weight_loss −500, maintenance 0, muscle_gain +300. A custom `u1_goal_offset` in the config overrides the default.

### `sensor.kcal_u1_balance`
- **State**: goal minus consumed — **positive = room left, negative = over goal**
- **Attributes**:
  - `consumed`: kcal eaten today
  - `goal`: daily goal
  - `status`: `under` | `over`

### `sensor.kcal_u1_net`
- **State**: Garmin burned minus consumed — **positive = deficit (burning more than eating), negative = surplus (eating more than burning)**
- **Attributes**:
  - `consumed`: kcal eaten today
  - `burned`: Garmin TDEE for today
  - `status`: `deficit` | `surplus`

---

## Add-on Configuration (Goal Settings)

Set these in the add-on Configuration tab in HA:

| Option | Default | Description |
|--------|---------|-------------|
| `u1_goal_mode` | `maintenance` | `weight_loss`, `maintenance`, or `muscle_gain` |
| `u1_goal_kcal` | `0` | Fixed goal in kcal. Used when Garmin is unavailable. `0` = not set. |
| `u1_goal_offset` | `0` | Override the default mode offset (kcal). `0` = use mode default. |
| `u1_garmin_entity` | *(auto)* | Garmin calories sensor entity ID. Leave blank to use `sensor.garmin_connect_calories`. |

Same options apply for User 2 with `u2_` prefix.

---

## Garmin TDEE Sensor

By default the add-on reads `sensor.garmin_connect_calories` (U1) and `sensor.garmin_connect_calories_2` (U2) as the TDEE source. This is Garmin's **total daily calories** = BMR + active calories.

If your Garmin sensor has a different entity ID, set `u1_garmin_entity` in the add-on config.

When Garmin data is unavailable (device not synced, integration down), the add-on falls back to `u1_goal_kcal` if set.

---

## Goal Mode Offsets

| Mode | Default offset | Typical use |
|------|---------------|-------------|
| `weight_loss` | −500 kcal | ~0.5 kg/week deficit |
| `maintenance` | 0 kcal | eat what you burn |
| `muscle_gain` | +300 kcal | lean bulk surplus |

Override with `u1_goal_offset` if you want a different number.

---

← [Phase 2: FatSecret Setup](../fatsecret/FATSECRET_SETUP.md) | [Phase 4: Dashboards →](../lovelace/LOVELACE_SETUP.md)
