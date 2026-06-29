# Kcal Balance — Home Assistant Add-On

A Home Assistant add-on that tracks daily calorie balance for up to two users, combining FatSecret food diary data with Garmin Connect activity data.

## Features

- **Web dashboard** served via HA ingress — appears as a native sidebar panel, no YAML needed
- **Today view** — calories consumed, daily goal, balance, net energy (burned − consumed), macros
- **This Week view** — bar chart of daily calories vs goal, weekly totals and macros
- **HA sensors** — thin sensor layer for automations and notifications
- **SQLite history** — full diary history queryable via `/api/history`
- **Two-user support** — side-by-side tracking for two people in one household
- **Garmin integration** — reads burned calories from the [Garmin Connect HACS integration](https://github.com/cyberjunky/home-assistant-garmin_connect)
- **Auto-refresh** — dashboard updates every 60 seconds

## Architecture

```
FatSecret API ──► background poller ──► SQLite /data/kcal.db ──► Flask web UI (ingress)
                         │
                         ├──► HA sensor push (for automations)
                         │
Garmin HACS ──► HA sensor ──► ha_get() (read on each poll)
```

## Installation

1. In Home Assistant go to **Settings → Add-ons → Add-on Store** (⋮ menu) → **Repositories**
2. Add: `https://github.com/turpela/ha-kcal-balance`
3. Find **Kcal Balance** in the store and click **Install**
4. Configure the add-on (see [Configuration](#configuration))
5. Click **Start**

The dashboard appears automatically in the HA sidebar as **Kcal Balance**.

## Prerequisites

### FatSecret credentials

Each user needs a FatSecret developer account and OAuth 1.0 credentials:

1. Register at [platform.fatsecret.com](https://platform.fatsecret.com/api/Default.aspx?screen=r)
2. Create an application — note your **Consumer Key** and **Consumer Secret**
3. Run the one-time OAuth flow using `fatsecret/fatsecret_auth.py` to obtain an **Access Token** and **Access Token Secret**

See `fatsecret/FATSECRET_SETUP.md` for the full walkthrough.

### Garmin Connect (optional but recommended)

Install the [Garmin Connect integration](https://github.com/cyberjunky/home-assistant-garmin_connect) via HACS. After setup, note your calories sensor entity ID (e.g. `sensor.garmin_connect_calories`) from **Developer Tools → States**.

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `u1_consumer_key` | string | — | FatSecret Consumer Key for User 1 |
| `u1_consumer_secret` | password | — | FatSecret Consumer Secret for User 1 |
| `u1_access_token` | string | — | FatSecret Access Token for User 1 |
| `u1_access_token_secret` | password | — | FatSecret Access Token Secret for User 1 |
| `u1_goal_mode` | list | `maintenance` | Goal mode: `weight_loss` (−500 kcal), `maintenance` (0), `muscle_gain` (+300 kcal) |
| `u1_goal_kcal` | int | — | Fixed daily goal in kcal (ignored if Garmin is connected) |
| `u1_goal_offset` | int | — | Override the default offset for the chosen goal mode |
| `u1_garmin_entity` | string | `sensor.garmin_connect_calories` | Entity ID of the Garmin calories sensor |
| `u2_*` | — | — | Same options for User 2 (all optional — omit to run single-user) |
| `scan_interval` | int | `300` | FatSecret polling interval in seconds |

### Goal calculation

When a Garmin entity is configured and readable:
```
daily_goal = garmin_burned + offset
```
where offset is `goal_offset` if set, otherwise the default for `goal_mode` (−500 / 0 / +300).

When Garmin is unavailable, `goal_kcal` is used as a fixed goal.

## HA Sensors

These sensors are pushed on every poll and can be used in automations:

| Sensor | Description |
|--------|-------------|
| `sensor.fatsecret_u1` | Calories consumed today; attributes: `protein`, `fat`, `carbs` |
| `sensor.kcal_u1_goal` | Daily calorie goal; attributes: `goal_mode`, `source` |
| `sensor.kcal_u1_balance` | Goal − consumed (positive = room left); attributes: `status` |
| `sensor.kcal_u1_net` | Garmin burned − consumed; attributes: `status` |
| `sensor.kcal_u1_weekly_consumed` | This week's total; attributes: `protein`, `fat`, `carbs`, `days_tracked` |
| `sensor.kcal_u1_weekly_goal` | Weekly goal (daily goal × 7) |
| `sensor.kcal_u1_weekly_balance` | Weekly goal − weekly consumed |

User 2 mirrors all sensors with `_u2` suffix.

## Web API

The add-on exposes a small REST API (accessible via ingress):

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard web UI |
| `GET /api/today` | Current snapshot for all users (JSON) |
| `GET /api/week` | This week's daily rows from SQLite (JSON) |
| `GET /api/history?weeks=4` | N weeks of daily history (JSON) |

## Project Structure

```
ha-kcal-balance/
├── repository.yaml              # HA add-on repository manifest
├── README.md                    # This file
├── CHANGELOG.md                 # Version history
├── kcal-balance/
│   ├── config.yaml              # Add-on manifest (version, schema, ingress)
│   ├── Dockerfile               # python:3.11-alpine + flask + requests-oauthlib
│   ├── app.py                   # Flask web app + background poller
│   ├── fatsecret.py             # FatSecret API client (OAuth 1.0)
│   ├── ha.py                    # HA Supervisor API helpers + sensor push
│   ├── store.py                 # SQLite persistence layer
│   └── CHANGELOG.md             # Add-on version history
├── fatsecret/
│   ├── fatsecret_auth.py        # One-time OAuth flow to obtain tokens
│   └── FATSECRET_SETUP.md       # FatSecret developer setup guide
└── garmin/
    └── GARMIN_SETUP.md          # Garmin Connect HACS integration guide
```

## Troubleshooting

**Dashboard doesn't appear in sidebar** — Restart the add-on. Ingress is registered on startup.

**FatSecret error 8 (Invalid signature)** — Check your credentials for typos.

**Garmin sensor unavailable / 404** — Check the entity ID in Developer Tools → States. Set `u1_garmin_entity` to the exact ID.

**Sensors show 0 but you've eaten** — FatSecret sometimes returns `{"food_entries": null}` for partially synced days. The add-on treats this as zero and picks up real data on the next poll.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
