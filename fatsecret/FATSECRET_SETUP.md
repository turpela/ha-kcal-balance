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
- One consumer key + secret pair (one app registration is enough for both users)
- Python 3 available on the HA host (`python3 --version`)
- SSH access to the HA host

---

## 1. Register a FatSecret Developer Application

One app registration covers both users — you authorize two separate FatSecret accounts against the same consumer key.

1. Go to [platform.fatsecret.com/register](https://platform.fatsecret.com/register) and create a developer account
2. After registration, a **Consumer Key** and **Consumer Secret** are generated automatically
3. Note these down — they go into the credentials files in step 3

---

## 2. Clone the Repo into HA Config

Instead of copying files manually, clone this repo directly into your HA config directory. All scripts are then always in the right place — updates are a single `git pull`.

```bash
# SSH into your HA host, then:
cd /config
git clone https://github.com/<your-username>/ha-kcal-balance.git
```

The scripts are now at:

```
/config/ha-kcal-balance/fatsecret/
├── fatsecret_auth.py       # one-time OAuth setup
├── fatsecret_u1.py         # User 1 polling script
└── fatsecret_u2.py         # User 2 polling script
```

Credentials files (`credentials_u1.json`, `credentials_u2.json`) are created here in step 3 and are excluded from git via `.gitignore`.

### Keeping scripts up to date

Add this to `configuration.yaml` once — it creates a button in HA that pulls the latest changes without needing SSH:

```yaml
# configuration.yaml
shell_command:
  update_kcal_balance: "cd /config/ha-kcal-balance && git pull"
```

After restarting HA, call it from **Developer Tools → Actions → shell_command.update_kcal_balance** whenever you push an update from GitHub Desktop. You can also attach it to an automation to run on a schedule.

---

## 3. Authorize Each User — One-Time OAuth Flow

FatSecret's food diary API uses 3-legged OAuth 1.0. Each user must authorize your app once. The result is a permanent `access_token` and `access_token_secret` stored in a local credentials file.

### Run the auth script (User 1)

```bash
cd /config/ha-kcal-balance/fatsecret
FS_CONSUMER_KEY=<your_key> FS_CONSUMER_SECRET=<your_secret> python3 fatsecret_auth.py
```

The script will:
1. Obtain a request token
2. Print an authorization URL — open it in your browser
3. Log in with **User 1's FatSecret account** and approve the app
4. Enter the verification code shown on screen
5. Print the credentials JSON

Save the output as `credentials_u1.json` in the same folder:

```json
{
  "consumer_key": "your_consumer_key",
  "consumer_secret": "your_consumer_secret",
  "access_token": "obtained_access_token",
  "access_token_secret": "obtained_access_token_secret"
}
```

### Run the auth script (User 2)

Repeat with **User 2's FatSecret account** in the browser. Save as `credentials_u2.json`.

> **Access tokens do not expire.** This is a one-time step per user unless access is revoked in FatSecret account settings.

---

## 4. Test the Scripts

```bash
python3 /config/ha-kcal-balance/fatsecret/fatsecret_u1.py
# Expected: {"calories": 1850.0, "protein": 120.5, "fat": 65.2, "carbs": 210.3}

python3 /config/ha-kcal-balance/fatsecret/fatsecret_u2.py
# Expected: {"calories": 2100.0, "protein": 145.0, "fat": 72.0, "carbs": 245.0}
```

All zeros with no `error` key = diary is empty today. That's fine — log something in the app and retest.

---

## 5. Add command_line Sensors to HA

Add the following to `/config/configuration.yaml`:

```yaml
# configuration.yaml
command_line:
  - sensor:
      name: "FatSecret U1"
      unique_id: fatsecret_u1
      command: "python3 /config/ha-kcal-balance/fatsecret/fatsecret_u1.py"
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
      command: "python3 /config/ha-kcal-balance/fatsecret/fatsecret_u2.py"
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

In **Developer Tools → States**, search for `fatsecret`:

| Entity                | State | Attributes                            |
|-----------------------|-------|---------------------------------------|
| `sensor.fatsecret_u1` | 1850  | calories: 1850, protein: 120.5, ...  |
| `sensor.fatsecret_u2` | 2100  | calories: 2100, protein: 145.0, ...  |

Phase 3 template sensors will expose `protein`, `fat`, and `carbs` as individual sensors from these attributes.

---

## Troubleshooting

**`credentials_u*.json not found`** — Make sure the file is in `/config/ha-kcal-balance/fatsecret/`, not somewhere else.

**`Invalid signature` error** — Consumer key/secret or access token is wrong. Re-run `fatsecret_auth.py`.

**All zeros, no error** — No diary entries logged today yet. Log food in the app and re-run the script.

**`sensor.fatsecret_u1` shows `unavailable`** — Run the script manually via SSH to see the raw output and error.

---

## Phase 2 Checklist

- [ ] FatSecret developer app registered (consumer key + secret obtained)
- [ ] Repo cloned into `/config/ha-kcal-balance/`
- [ ] `fatsecret_auth.py` run for User 1 → `credentials_u1.json` created
- [ ] `fatsecret_auth.py` run for User 2 → `credentials_u2.json` created
- [ ] Scripts tested manually — valid JSON output confirmed for both users
- [ ] `command_line` sensors added to `configuration.yaml`
- [ ] HA restarted — `sensor.fatsecret_u1` and `sensor.fatsecret_u2` live

---

## Next Step

→ [Phase 3: Template Sensors](../templates/TEMPLATES.md)
