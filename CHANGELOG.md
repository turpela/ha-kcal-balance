# Changelog

All notable changes to this project are documented here.

---

## [Unreleased]

### Planned
- Phase 2: FatSecret REST API integration (custom Python scripts)
- Phase 3: Template sensors for deficit/surplus, macros, calorie goal
- Phase 4: Per-user Lovelace dashboards

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
