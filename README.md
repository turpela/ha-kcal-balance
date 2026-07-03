# Kcal Balance — Home Assistant Add-On

A Home Assistant add-on that tracks daily calorie balance for up to two users using FatSecret food diary and Garmin activity data. Everything is pulled from FatSecret — no separate Garmin integration required.

## Features

- **Web dashboard** served via HA ingress — appears as a native sidebar panel, no YAML needed
- **Today view** — Net Cal hero card (burned − consumed), Consumed + GDA% progress bar, macros
- **This Week view** — daily net cal bar chart (green = deficit, red = surplus), weekly summary
- **This Month view** — monthly net cal bar chart, monthly totals and deficit/surplus day counts
- **Settings tab** — editable user names and GDA (Guideline Daily Amount) per user
- **HA sensors** — thin sensor layer for automations and notifications
- **SQLite history** — full diary history queryable via `/api/history`
- **Two-user support** — side-by-side tracking for two people in one household
- **Auto-refresh** — dashboard updates every 60 seconds

## How It Works

FatSecret is the single data source for both food and burned calories:

- `food_entries.get.v2` — food diary (consumed kcal + macros)
- `exercise_entries.get` — Garmin daily summary (finalized burned kcal, synced by FatSecret from Garmin after each day ends)

No Garmin Connect HACS integration is needed. FatSecret receives the complete, finalized daily calorie total from Garmin — avoiding the midnight-gap issue that affects live Garmin sensor polling.

```
FatSecret API ──► background poller ──► SQLite /data/kcal.db ──► Flask web UI (ingress)
  food_entries.get.v2   (consumed kcal + macros)       │
  exercise_entries.get  (Garmin burned kcal, finalized) ├──► HA sensor push
```

## Installation

1. In Home Assistant go to **Settings → Add-ons → Add-on Store** (⋮ menu) → **Repositories**
2. Add: `https://github.com/turpela/ha-kcal-balance`
3. Find **Kcal Balance** in the store and click **Install**
4. Configure the add-on (see [Configuration](#configuration))
5. Click **Start**

The **Kcal Balance** panel appears automatically in the HA sidebar.

## Prerequisites

Each user needs a FatSecret developer account with OAuth 1.0 credentials, and their FatSecret account must be connected to their Garmin account (so FatSecret receives the daily activity summary).

1. Register at [platform.fatsecret.com](https://platform.fatsecret.com/api/Default.aspx?screen=r)
2. Create an application — note your **Consumer Key** and **Consumer Secret**
3. Run the one-time OAuth flow using `fatsecret/fatsecret_auth.py` to obtain an **Access Token** and **Access Token Secret** for each user

See `fatsecret/FATSECRET_SETUP.md` for the full walkthrough.

> **Garmin connection:** In the FatSecret mobile app, go to **Me → Connected Apps** and connect your Garmin account. FatSecret will then receive daily burned calorie summaries from Garmin automatically.

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `u1_consumer_key` | string | — | FatSecret Consumer Key (same for both users) |
| `u1_consumer_secret` | password | — | FatSecret Consumer Secret |
| `u1_access_token` | string | — | FatSecret Access Token for User 1 |
| `u1_access_token_secret` | password | — | FatSecret Access Token Secret for User 1 |
| `u2_consumer_key` | string | — | FatSecret Consumer Key for User 2 (optional) |
| `u2_consumer_secret` | password | — | FatSecret Consumer Secret for User 2 |
| `u2_access_token` | string | — | FatSecret Access Token for User 2 |
| `u2_access_token_secret` | password | — | FatSecret Access Token Secret for User 2 |
| `scan_interval` | int | `300` | FatSecret polling interval in seconds |

User 2 is optional — omit all `u2_*` fields to run in single-user mode.

### GDA (Guideline Daily Amount)

GDA is set per-user in the **Settings tab** of the dashboard (not in the add-on config). It defaults to 2000 kcal and is persisted in SQLite across restarts. The GDA is used to colour the consumed progress bar and compute weekly GDA%.

## Dashboard

### Today

| Card | Content |
|------|---------|
| **Net Cal** | Burned − consumed (green = deficit, red = surplus); Garmin burned shown below |
| **Consumed** | Total kcal eaten today; GDA% progress bar colour: green <90%, yellow 90–100%, red >100% |
| **Macros** | Protein / Fat / Carbs in grams |

### This Week

- Bar chart: daily Net Cal per day (green = deficit, red = surplus, grey = no Garmin data)
- Summary: weekly net, consumed, GDA%, days tracked, macros

### This Month

- Bar chart: daily Net Cal for the current month
- Summary: monthly net, consumed, deficit/surplus day counts, macros

### Settings

- Edit User 1 / User 2 display names (also editable inline by clicking the name in Today/Week/Month)
- Set GDA per user

## HA Sensors

Pushed on every poll, available for automations and dashboards:

| Sensor | Description |
|--------|-------------|
| `sensor.fatsecret_u1` | Calories consumed today; attrs: `protein`, `fat`, `carbs` |
| `sensor.kcal_u1_net` | Burned − consumed; attrs: `consumed`, `burned`, `status` |
| `sensor.kcal_u1_gda_pct` | Consumed as % of GDA; attrs: `gda`, `consumed` |
| `sensor.kcal_u1_weekly_consumed` | This week's consumed total; attrs: macros, `days_tracked` |
| `sensor.kcal_u1_weekly_gda_pct` | Weekly consumed as % of pro-rated GDA |

User 2 mirrors all sensors with `_u2` suffix.

## Web API

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard web UI |
| `GET /api/today` | Current snapshot for all users (JSON) |
| `GET /api/week` | This week's daily rows (JSON) |
| `GET /api/month` | This month's daily rows (JSON) |
| `GET /api/history?weeks=4` | N weeks of daily history (JSON) |
| `GET /api/settings` | User names and GDA values (JSON) |
| `POST /api/settings` | Update names / GDA values |

## Project Structure

```
ha-kcal-balance/
├── repository.yaml              # HA add-on repository manifest
├── README.md                    # This file
├── CHANGELOG.md                 # Version history
├── kcal-balance/
│   ├── config.yaml              # Add-on manifest (version, schema, ingress)
│   ├── Dockerfile               # python:3.11-alpine + flask + requests-oauthlib
│   ├── app.py                   # Flask web app + background poller (main entry)
│   ├── fatsecret.py             # FatSecret API client — food + burned calories
│   ├── ha.py                    # HA Supervisor API helpers + sensor push
│   ├── store.py                 # SQLite persistence layer
│   └── CHANGELOG.md             # Add-on version history
└── fatsecret/
    ├── fatsecret_auth.py        # One-time OAuth 1.0 flow to obtain user tokens
    ├── fatsecret_test.py        # Local test: verifies food diary fetch
    └── exercise_test.py         # Local test: verifies burned calorie fetch
```

> The `garmin/` directory contains legacy setup guides for the Garmin Connect HACS integration, which is no longer required by this add-on as of v2.4.0.

## Troubleshooting

**Dashboard doesn't appear in sidebar** — Restart the add-on. The ingress panel is registered on startup.

**FatSecret error 8 (Invalid signature)** — Check your credentials for typos. Re-run `fatsecret_auth.py` if needed.

**Net Cal shows `—`** — FatSecret hasn't received a Garmin daily summary yet for today (normal until mid-morning). Yesterday's value should always be present. Verify the Garmin connection is active in the FatSecret app under **Me → Connected Apps**.

**Consumed shows 0 but you've eaten** — FatSecret sometimes returns `{"food_entries": null}` for partially synced days. The add-on treats this as zero and picks up real data on the next poll.

**Burned shows yesterday's value all day** — This is correct behaviour. FatSecret receives the finalized Garmin summary after the day ends, so today's burned total builds up gradually as Garmin syncs to FatSecret throughout the day.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
