# FatSecret Setup Guide

FatSecret is the **only external API** the Kcal Balance add-on needs. It provides:

- **Food diary** — what you ate today (consumed kcal + macros)
- **Burned calories** — finalized daily Garmin activity data, synced to FatSecret after each day ends

No Garmin Connect HACS integration is required.

---

## How It Works

```
FatSecret app       →  food_entries.get.v2   →  consumed kcal + macros
Garmin watch/app    →  FatSecret (via Connected Apps)
                    →  exercise_entries.get  →  burned kcal (finalized daily total)
                    →  Kcal Balance add-on   →  SQLite + web dashboard + HA sensors
```

FatSecret receives a finalized Garmin daily summary after each day ends — this is always the complete 24-hour total, without the midnight-gap issues that affect live Garmin sensor polling.

---

## Prerequisites

- A **FatSecret account** for each user (the app they already use to log food)
- A **FatSecret developer account** (free) — one registration covers both users
- Python 3 on your local machine (for the one-time token generation step)
- The FatSecret mobile app connected to Garmin (for burned calories)

---

## Step 1 — Connect Garmin to FatSecret

In the FatSecret mobile app for each user:

1. Go to **Me → Connected Apps**
2. Find **Garmin** and tap **Connect**
3. Authorize FatSecret to read your Garmin activity data

FatSecret will now receive a daily burned calorie summary from Garmin each day. You should see it reflected in the FatSecret app's calorie balance view.

---

## Step 2 — Register a FatSecret Developer App

One application registration is shared by both users.

1. Go to [platform.fatsecret.com/register](https://platform.fatsecret.com/register) and create a developer account
2. Create a new application
3. Note the **Consumer Key** and **Consumer Secret** — you'll need them for both users

---

## Step 3 — Get Access Tokens (One-Time Per User)

The food diary API requires 3-legged OAuth 1.0. Each user authorizes once to produce a permanent access token.

Run the auth script on your **local machine** (not on the HA host):

```bash
cd fatsecret
pip3 install requests requests-oauthlib    # once, if not already installed
python3 fatsecret_auth.py
```

Enter your Consumer Key and Consumer Secret when prompted. The script will:

1. Print an authorization URL — open it in a browser
2. Log in with **that user's FatSecret account** and approve access
3. Enter the verification code shown after approval
4. Print the **Access Token** and **Access Token Secret** — save these

Repeat with the second user logged in for User 2.

> **Tokens do not expire.** This is a one-time step per user account.

---

## Step 4 — Verify the API (Optional)

Two local test scripts are available to confirm everything is working before installing the add-on:

```bash
# Test food diary fetch
python3 fatsecret_test.py

# Test burned calories fetch (Garmin exercise data)
python3 exercise_test.py
```

`exercise_test.py` should show a "Garmin" exercise entry with `minutes: 1440` for yesterday (the complete day's total). If it shows `"exercise_entries": {}` for yesterday, the Garmin connection in the FatSecret app isn't active yet — go back to Step 1.

---

## Step 5 — Install the Add-On

1. In Home Assistant: **Settings → Add-ons → Add-on Store** (⋮) → **Repositories**
2. Add: `https://github.com/turpela/ha-kcal-balance`
3. Find **Kcal Balance** and click **Install**

---

## Step 6 — Configure the Add-On

In the add-on **Configuration** tab:

| Field | Value |
|-------|-------|
| `u1_consumer_key` | Consumer Key from Step 2 |
| `u1_consumer_secret` | Consumer Secret from Step 2 |
| `u1_access_token` | Access Token for User 1 from Step 3 |
| `u1_access_token_secret` | Access Token Secret for User 1 from Step 3 |
| `u2_consumer_key` | Consumer Key (same as User 1, same app) |
| `u2_consumer_secret` | Consumer Secret (same as User 1) |
| `u2_access_token` | Access Token for User 2 from Step 3 |
| `u2_access_token_secret` | Access Token Secret for User 2 from Step 3 |
| `scan_interval` | Poll interval in seconds (default: `300`) |

User 2 fields are optional — omit them to run in single-user mode.

Click **Save**.

---

## Step 7 — Start the Add-On and Set GDA

1. Click **Start** in the add-on Info tab
2. The **Kcal Balance** panel appears in the HA sidebar
3. Open it and go to the **Settings tab**
4. Set each user's **GDA** (Guideline Daily Amount in kcal) — typically 2000–2500 kcal
5. The GDA is used to colour the consumed progress bar and compute weekly GDA%

Check the **Log tab** — you should see:

```
Kcal Balance v2.4.0 starting...
[U1] Consumed 420 kcal | GDA: 21.0% | Net: +1180 | Burned: 1600
```

---

## Troubleshooting

**`exercise_test.py` shows empty exercise entries for yesterday** — Garmin is not connected to FatSecret. Go to FatSecret → Me → Connected Apps and connect Garmin.

**FatSecret error 8 (Invalid signature)** — Consumer key/secret or access token contains a typo. Re-run `fatsecret_auth.py` and update the config.

**Consumed shows 0 but you've eaten** — No food entries logged today in FatSecret, or FatSecret returned a partially synced response. The add-on will pick up real data on the next poll.

**Net Cal shows `—` all day** — FatSecret hasn't received today's Garmin summary yet (normal until Garmin syncs). Yesterday's Net Cal is always available once the day's summary arrives.

**Add-on won't start** — Check the Log tab. A missing or invalid `u1_consumer_key` will cause an immediate error.

---

## Sensors Created

| Sensor | Description |
|--------|-------------|
| `sensor.fatsecret_u1` | Consumed kcal; attrs: `protein`, `fat`, `carbs` |
| `sensor.kcal_u1_net` | Burned − consumed; attrs: `burned`, `consumed`, `status` |
| `sensor.kcal_u1_gda_pct` | Consumed % of GDA; attrs: `gda`, `consumed` |
| `sensor.kcal_u1_weekly_consumed` | Weekly consumed; attrs: macros, `days_tracked` |
| `sensor.kcal_u1_weekly_gda_pct` | Weekly consumed % of pro-rated GDA |

User 2 mirrors all sensors with `_u2` suffix.
