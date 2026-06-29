# Changelog

All notable changes to this project are documented here.

---

## [Unreleased]

---

## [1.4.3] — 2026-06-29

### Fixed
- FatSecret returns `{"food_entries": null}` for empty days — the key is present so `.get("food_entries", {})` returned `None` instead of `{}`, crashing on the chained `.get("food_entry", [])`. Fixed with `(raw.get("food_entries") or {})` which collapses null to an empty dict

---

## [1.4.2] — 2026-06-29

### Fixed
- `summarise()` now guards with `isinstance(raw, dict)` instead of `raw is None`; FatSecret can return other non-dict types (list, string) for empty days — all are now treated as zero consumption and logged at DEBUG level so the actual value is visible

---

## [1.4.1] — 2026-06-29

### Fixed
- `summarise()` crashed with `AttributeError: 'NoneType' object has no attribute 'get'` when FatSecret returns JSON `null` for days with no food entries; now correctly returns zero totals

---

## [1.4.0] — 2026-06-29

### Added
- **Auto sidebar registration** — on first start the add-on calls the HA Lovelace API to create the "Kcal Balance" dashboard and push its full two-view config; the dashboard appears in the HA sidebar automatically, no manual YAML pasting needed
- Dashboard registration is idempotent: if the dashboard already exists it is left untouched

---

## [1.3.0] — 2026-06-28

### Added
- **Weekly tracking sensors** per user: `sensor.kcal_u1_weekly_consumed`, `sensor.kcal_u1_weekly_goal`, `sensor.kcal_u1_weekly_balance` — week runs Mon–Sun Helsinki time
- Weekly goal = daily goal × 7 (auto-computed, no extra config needed)
- Weekly state persisted in `/data/weekly_state.json`; backfills missing days from FatSecret on startup so history is complete even if the add-on was down
- Old daily entries purged after 14 days to keep state file small
- **Europe/Helsinki timezone** for all date calculations — midnight reset now correct for Finnish users
- `lovelace/dashboard.yaml` now has two views: **Today** (daily gauges) and **This Week** (weekly gauges + macros)

### Changed
- `kcal-balance/Dockerfile` — added `tzdata` Alpine package for IANA timezone database (required by `zoneinfo.ZoneInfo`)
- `kcal-balance/config.yaml` bumped to `1.3.0`

---

## [1.2.0] — 2026-06-28

### Added
- `lovelace/dashboard.yaml` — two-column Lovelace dashboard (U1 + U2 side by side); gauges for balance and net energy, macros breakdown, Garmin stats; no HACS custom cards required
- `lovelace/LOVELACE_SETUP.md` — step-by-step guide for adding the dashboard to HA

---

## [1.1.1] — 2026-06-28

### Added
- `sensor.kcal_u1_net` / `sensor.kcal_u2_net` — actual energy balance (Garmin burned − FatSecret consumed); positive = deficit, negative = surplus
- `sensor.kcal_u1_goal` / `sensor.kcal_u2_goal` — daily calorie goal with `goal_mode` (weight_loss / maintenance / muscle_gain) and `source` (garmin / fixed) attributes
- `sensor.kcal_u1_balance` / `sensor.kcal_u2_balance` — goal minus consumed; positive = room left, negative = over goal
- New add-on config options per user: `u1_goal_mode`, `u1_goal_kcal`, `u1_goal_offset`, `u1_garmin_entity` (and `u2_` equivalents)
- `templates/TEMPLATES.md` — full sensor reference for Phase 3

### Changed
- Garmin TDEE read once per poll cycle and reused for both net and goal computation (avoids duplicate HA API calls)
- `kcal-balance/config.yaml` bumped to `1.1.1`

---

## [1.1.0] — 2026-06-28

### Added
- Phase 3 foundation: goal config schema added to `kcal-balance/config.yaml`
- `kcal-balance/fatsecret.py` — reads Garmin TDEE via HA Supervisor API, computes goal and balance, pushes `sensor.kcal_u1_goal` and `sensor.kcal_u1_balance`
- `fatsecret/fatsecret_test.py` — local integration test showing per-entry breakdown and totals

---

## [0.3.4] — 2026-06-28

### Fixed
- `kcal-balance/fatsecret.py` — replaced hand-rolled OAuth 1.0 HMAC-SHA1 signing with `requests-oauthlib`; fixes "Invalid signature" (error code 8) from FatSecret API
- `fatsecret/fatsecret_auth.py` — same replacement; ensures auth tokens obtained locally are valid
- `kcal-balance/config.yaml` bumped to `1.0.5`
- FatSecret API errors now raised as exceptions instead of silently returning zeros

### Changed
- `kcal-balance/Dockerfile` — added `pip install requests requests-oauthlib`

---

## [0.3.3] — 2026-06-28

### Fixed
- `kcal-balance/config.yaml` — added `init: false`; this was the root cause of all s6-overlay PID 1 errors (without it HA injects its own init system which conflicts with a plain Docker CMD)
- `kcal-balance/config.yaml` bumped to `1.0.3`

### Changed
- `kcal-balance/config.yaml` — secret fields (`consumer_secret`, `access_token_secret`) now use `password` / `password?` schema type so HA masks them in the UI
- `kcal-balance/Dockerfile` — switched from `python3 -u` flag to `ENV PYTHONUNBUFFERED=1` (idiomatic)

---

## [0.3.2] — 2026-06-28

### Fixed
- Replaced HA base image + s6-overlay with `python:3.11-alpine` — Python runs directly as PID 1, eliminating the `s6-overlay-suexec: fatal: can only run as pid 1` error entirely
- Removed `build.yaml` and `rootfs/` (no longer needed without s6)
- `kcal-balance/config.yaml` bumped to `1.0.2`

### Changed
- `kcal-balance/fatsecret.py` — replaced `print()` with structured `logging` (DEBUG/INFO/ERROR); startup sequence now logs options file load, token presence, user count, and per-poll HTTP status; network and HTTP errors caught and logged separately with full detail

---

## [0.3.1] — 2026-06-28

### Fixed
- Add-on now starts correctly — replaced `CMD ["/run.sh"]` + `with-contenv` shebang approach with proper s6 service directory (`rootfs/etc/services.d/kcal-balance/run`); s6-overlay is now PID 1 as required
- Removed `run.sh` from add-on root (superseded by service directory)

### Changed
- `kcal-balance/config.yaml` — U2 credential fields marked optional (`str?`); add-on works with a single user
- `kcal-balance/fatsecret.py` — skips User 2 poll when U2 credentials are absent or empty

---

## [0.3.0] — 2026-06-28

### Added
- `repository.yaml` — marks repo as an HA add-on repository; the URL can now be added directly to the HA add-on store
- `kcal-balance/config.yaml` — add-on metadata, config schema (both users' OAuth credentials + scan interval)
- `kcal-balance/build.yaml` — multi-arch base images (aarch64, amd64, armhf, armv7, i386)
- `kcal-balance/Dockerfile` — Alpine base + Python 3
- `kcal-balance/run.sh` — bashio entrypoint
- `kcal-balance/fatsecret.py` — polls FatSecret `food_entries.get.v2` for both users, pushes sensor states to HA via Supervisor REST API; no `configuration.yaml` edits needed

### Changed
- `fatsecret/FATSECRET_SETUP.md` — rewritten for add-on flow: add repo → install → fill config UI → start
- `README.md` — updated repo structure and sensor naming sections

### Removed
- `fatsecret/fatsecret_u1.py`, `fatsecret/fatsecret_u2.py` — superseded by `kcal-balance/fatsecret.py`

---

## [0.2.2] — 2026-06-28

### Changed
- `fatsecret/FATSECRET_SETUP.md` — removed Git pull add-on tip (incompatible with non-HA-config repos); replaced with `shell_command.update_kcal_balance` approach so updates can be triggered from the HA UI after initial clone

---

## [0.2.1] — 2026-06-28

### Changed
- `fatsecret/FATSECRET_SETUP.md` — replaced manual file copy with `git clone` into HA config directory; all script paths updated to `/config/ha-kcal-balance/fatsecret/`; added Git pull add-on tip for automated updates

---

## [0.2.0] — 2026-06-28

### Added
- `fatsecret/fatsecret_auth.py` — one-time 3-legged OAuth 1.0 authorization script; outputs access token + secret to save as credentials file
- `fatsecret/fatsecret_u1.py` — User 1 polling script; calls `food_entries.get.v2` for today, sums calories/protein/fat/carbs, prints JSON to stdout
- `fatsecret/fatsecret_u2.py` — User 2 equivalent
- `fatsecret/FATSECRET_SETUP.md` — full Phase 2 guide covering developer registration, one-time auth flow, HA `command_line` sensor config, and troubleshooting
- `.gitignore` — excludes `credentials_u1.json` and `credentials_u2.json` from version control

### Changed
- `README.md` — Phase 2 marked complete

---

## [0.1.2] — 2026-06-28

### Changed
- `garmin/GARMIN_SETUP.md` — removed sensor renaming section; sensors now use default integration entity IDs (`sensor.garmin_connect_*` for User 1, `sensor.garmin_connect_*_2` for User 2)
- `README.md` — updated sensor naming section to reflect default Garmin entity IDs

---

## [0.1.1] — 2026-06-28

### Changed
- `garmin/GARMIN_SETUP.md` updated for integration v3.0:
  - Corrected scan interval: default 300 s (5 min), minimum 60 s — configured via UI, not `configuration.yaml`
  - Updated default entity ID pattern to `sensor.garmin_connect_[sensor_name]`
  - Expanded sensor rename tables to include all calorie, activity, and wellness sensors
  - Corrected activities attribute name to `last_activities` on `sensor.garmin_connect_last_activities`
  - Added 8-coordinator data update table
  - Added v3.0 re-authentication note

---

## [0.1.0] — 2026-06-28

### Added
- Initial repository structure with phase-based folder layout (`garmin/`, `fatsecret/`, `templates/`, `lovelace/`)
- `garmin/GARMIN_SETUP.md` — full Phase 1 guide covering:
  - HACS installation of cyberjunky/home-assistant-garmin_connect
  - Two-instance setup (one per user)
  - Sensor renaming to `sensor.garmin_u1_*` / `sensor.garmin_u2_*` convention
  - Reference tables for calorie, activity, and wellness sensors
  - Activities JSON attribute structure for downstream parsing
  - Polling/rate-limit guidance
  - Phase 1 completion checklist
- `README.md` with project overview, architecture, sensor naming convention, phase status table, and repo structure
- `CHANGELOG.md` (this file)
