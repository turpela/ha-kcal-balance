# Phase 2 — FatSecret Integration

FatSecret data is delivered to Home Assistant via the **Kcal Balance add-on** — a Docker container that polls the FatSecret API on a schedule and pushes sensor states directly into HA. No `configuration.yaml` edits required.

---

## How It Works

```
FatSecret app (user logs food)
    → FatSecret cloud
        → Kcal Balance add-on (polls every 5 min)
            → HA REST API
                → sensor.fatsecret_u1 / sensor.fatsecret_u2
```

Sensors created by the add-on:

| Sensor                  | State      | Attributes                    |
|-------------------------|------------|-------------------------------|
| `sensor.fatsecret_u1`   | calories   | protein, fat, carbs           |
| `sensor.fatsecret_u2`   | calories   | protein, fat, carbs           |

---

## Prerequisites

- FatSecret developer account registered at [platform.fatsecret.com](https://platform.fatsecret.com)
- Python 3 on your local machine (to run the one-time auth script)

---

## 1. Register a FatSecret Developer Application

One app registration covers both users.

1. Go to [platform.fatsecret.com/register](https://platform.fatsecret.com/register)
2. Create a developer account
3. Note the generated **Consumer Key** and **Consumer Secret**

---

## 2. Get Access Tokens for Each User (One-Time)

FatSecret's food diary API requires 3-legged OAuth 1.0. Each user must authorize your app once to produce a permanent `access_token` and `access_token_secret`.

Run the auth script **on your local machine** (not on the HA host):

```bash
cd fatsecret
FS_CONSUMER_KEY=<your_key> FS_CONSUMER_SECRET=<your_secret> python3 fatsecret_auth.py
```

The script will:
1. Print an authorization URL — open it in your browser
2. Log in with **that user's FatSecret account** and approve the app
3. Enter the verification code
4. Print the `access_token` and `access_token_secret`

Repeat for User 2 using their FatSecret account.

> **Access tokens do not expire.** This is a one-time step per user.

---

## 3. Install the Add-on

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store**
2. Click the **⋮ menu → Repositories**
3. Add: `https://github.com/turpela/ha-kcal-balance`
4. Find **Kcal Balance** in the store and click **Install**

---

## 4. Configure the Add-on

In the add-on **Configuration** tab, fill in the credentials from steps 1 and 2:

| Field                  | Value                              |
|------------------------|------------------------------------|
| `u1_consumer_key`      | Consumer Key from FatSecret        |
| `u1_consumer_secret`   | Consumer Secret from FatSecret     |
| `u1_access_token`      | Access token for User 1            |
| `u1_access_token_secret` | Access token secret for User 1   |
| `u2_consumer_key`      | Consumer Key (same app)            |
| `u2_consumer_secret`   | Consumer Secret (same app)         |
| `u2_access_token`      | Access token for User 2            |
| `u2_access_token_secret` | Access token secret for User 2   |
| `scan_interval`        | Poll interval in seconds (default 300) |

Click **Save**.

---

## 5. Start the Add-on

Click **Start** in the add-on Info tab. Check the **Log** tab — you should see:

```
Kcal Balance started — polling every 300s
[U1] {"calories": 1850.0, "protein": 120.5, ...} → HA 201
[U2] {"calories": 2100.0, "protein": 145.0, ...} → HA 201
```

---

## 6. Verify in HA

In **Developer Tools → States**, search for `fatsecret`:

| Entity                | State | Attributes                            |
|-----------------------|-------|---------------------------------------|
| `sensor.fatsecret_u1` | 1850  | calories: 1850, protein: 120.5, ...  |
| `sensor.fatsecret_u2` | 2100  | calories: 2100, protein: 145.0, ...  |

Phase 3 template sensors will use these attributes to expose individual macro sensors and calculate the calorie balance.

---

## Troubleshooting

**Add-on log shows `ERROR: Invalid signature`** — Consumer key/secret or access token is wrong. Re-run `fatsecret_auth.py` and update the config.

**All zeros, no error** — No diary entries logged in FatSecret today. Log something and wait for the next poll.

**Sensor shows `unknown` in HA** — Add-on may not be running. Check the Info tab and restart if needed.

---

## Phase 2 Checklist

- [ ] FatSecret developer app registered (consumer key + secret obtained)
- [ ] `fatsecret_auth.py` run for User 1 → access token + secret noted
- [ ] `fatsecret_auth.py` run for User 2 → access token + secret noted
- [ ] Repo added to HA add-on store
- [ ] Add-on installed and configured
- [ ] Add-on started — log shows successful posts for both users
- [ ] `sensor.fatsecret_u1` and `sensor.fatsecret_u2` live in HA

---

## Next Step

→ [Phase 3: Template Sensors](../templates/TEMPLATES.md)
