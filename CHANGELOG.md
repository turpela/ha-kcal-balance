# Changelog

All notable changes to this project are documented here.

---

## [Unreleased]

### Planned
- Phase 2: FatSecret REST API integration (custom Python scripts)
- Phase 3: Template sensors for deficit/surplus, macros, calorie goal
- Phase 4: Per-user Lovelace dashboards

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
