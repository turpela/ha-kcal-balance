# Changelog

All notable changes to this project are documented here.

---

## [Unreleased]

### Planned
- Phase 2: FatSecret REST API integration (custom Python scripts)
- Phase 3: Template sensors for deficit/surplus, macros, calorie goal
- Phase 4: Per-user Lovelace dashboards

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
