# Phase 2 — FatSecret Integration

This phase adds food diary data from FatSecret to Home Assistant via two Python scripts, one per user. Each script polls the FatSecret REST API and outputs daily totals (calories, protein, fat, carbs) as JSON. Home Assistant reads this via the `command_line` sensor platform.

No external Python packages are required — the scripts use stdlib only.

---

## How It Works

```
FatSecret app (user logs food)
    → FatSecret cloud
        → Python script calls food_entries.get.v2 API
            → stdout JSON
                → HA command_line sensor
```

Each script runs on the HA host on a 5-minute poll interval and produces one sensor with macro totals as attributes:

| Sensor                  | State      | Attributes                    |
|-------------------------|------------|-------------------------------|
| `sensor.fatsecret_u1`   | calories   | protein, fat, carbs           |
| `sensor.fatsecret_u2`   | calories   | protein, fat, carbs           |

---

## Prerequisites

- FatSecret developer account with an application registered at [platform.fatsecret.com](https://platform.fatsecret.com)
- One consumer key + secret pair per user (each user registers their own app, or you reuse one key pair and authorize two separate user accounts)
- Python 3 available on the HA host (`python3 --version`)

---

## 1. Register a FatSecret Developer Application

Each user needs their own consumer key and secret. If both users are comfortable sharing one app registration, one key pair can be used for both — just authorize two different FatSecret accounts.

1. Go to [platform.fatsecret.com/register](https://platform.fatsecret.com/register) and create a developer account
2. After registration, a **Consumer Key** and **Consumer Secret** are generated automatically
3. Note these down — they go into the credentials files below

---

## 2. Copy Scripts to Your HA Config Directory

Copy the entire `fatsecret/` folder to your HA config directory:

```
/config/fatsecret/
├── fatsecret_auth.py       # one-time OAuth setup
├── fatsecret_u1.py         # User 1 polling script
├── fatsecret_u2.py         # User 2 polling script
├── credentials_u1.json     # created in step 3 (not in git)
└── credentials_u2.json     # created in step 3 (not in git)
```

> The HA config directory is typically `/config/` on HA OS / Container, or `~/.homeassistant/` on manual installs.

---

## 3. Authorize Each User — One-Time OAuth Flow

FatSecret's food diary API uses 3-legged OAuth 1.0. Each user must authorize your app once. The result is a permanent `access_token` and `access_token_secret` stored locally.

### Run the auth script (User 1)

On the HA host (via SSH or terminal):

```bash
cd /config/fatsecret
FS_CONSUMER_KEY=<your_key> FS_CONSUMER_SECRET=<your_secret> python3 fatsecret_auth.py
```

The script will:
1. Obtain a request token
2. Print an authorization URL — open it in your browser
3. Log in with **User 1's FatSecret account** and approve the app
4. Enter the verification code shown on screen
5. Print the access token and secret

Save the output as `/config/fatsecret/credentials_u1.json`:

```json
{
  "consumer_key": "your_consumer_key",
  "consumer_secret": "your_consumer_secret",
  "access_token": "obtained_access_token",
  "access_token_secret": "obtained_access_token_secret"
}
```

### Run the auth script (User 2)

Repeat the same process but log in with **User 2's FatSecret account** when the browser opens. Save the result as `credentials_u2.json`.

> **Access tokens do not expire.** You only need to run this once per user unless you revoke access in the FatSecret app settings.

---

## 4. Test the Scripts

```bash
python3 /config/fatsecret/fatsecret_u1.py
# Expected output:
# {"calories": 1850.0, "protein": 120.5, "fat": 65.2, "carbs": 210.3}

python3 /config/fatsecret/fatsecret_u2.py
# Expected output:
# {"calories": 2100.0, "protein": 145.0, "fat": 72.0, "carbs": 245.0}
```

If the diary is empty for today you'll get all zeros — that's correct. If you see an `error` key in the output, check the credentials file path and content.

---

## 5. Add command_line Sensors to HA

Add the following to your `configuration.yaml`. Adjust the Python path if needed (`which python3` on the HA host).

```yaml
# configuration.yaml
command_line:
  - sensor:
      name: "FatSecret U1"
      unique_id: fatsecret_u1
      command: "python3 /config/fatsecret/fatsecret_u1.py"
      scan_interval: 300
      unit_of_measurement: "kcal"
      value_template: "{{ value_json.calories }}"
      json_attributes:
        - calories
        - protein
        - fat
        - carbs

  - sensor:
      name: "FatSecret U2"
      unique_id: fatsecret_u2
      command: "python3 /config/fatsecret/fatsecret_u2.py"
      scan_interval: 300
      unit_of_measurement: "kcal"
      value_template: "{{ value_json.calories }}"
      json_attributes:
        - calories
        - protein
        - fat
        - carbs
```

Restart Home Assistant after saving.

---

## 6. Verify in HA

In **Developer Tools → States**, search for `fatsecret`. You should see:

| Entity              | State  | Attributes                              |
|---------------------|--------|-----------------------------------------|
| `sensor.fatsecret_u1` | 1850 | calories: 1850, protein: 120.5, ...   |
| `sensor.fatsecret_u2` | 2100 | calories: 2100, protein: 145.0, ...   |

In Phase 3, template sensors will expose `protein`, `fat`, and `carbs` as individual sensors using these attributes.

---

## Troubleshooting

**`credentials_u*.json not found`** — Make sure the files are in `/config/fatsecret/`, not a subdirectory.

**`Invalid signature` error** — The consumer key/secret or access token is wrong. Re-run `fatsecret_auth.py`.

**All zeros, no error** — The FatSecret diary for today has no entries logged yet. Log something in the app and wait for the next poll.

**`sensor.fatsecret_u1` shows `unavailable`** — Check HA logs. The script may be failing silently; run it manually via SSH to see the raw output.

---

## Phase 2 Checklist

- [ ] FatSecret developer app registered (consumer key + secret obtained)
- [ ] `fatsecret_auth.py` run for User 1 → `credentials_u1.json` created
- [ ] `fatsecret_auth.py` run for User 2 → `credentials_u2.json` created
- [ ] Scripts tested manually via SSH — valid JSON output confirmed
- [ ] `command_line` sensors added to `configuration.yaml`
- [ ] HA restarted — `sensor.fatsecret_u1` and `sensor.fatsecret_u2` visible with live data

---

## Next Step

→ [Phase 3: Template Sensors](../templates/TEMPLATES.md)
