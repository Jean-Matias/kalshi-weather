# kalshi-low-weather-scout Agent Instructions

## Project Purpose

This project is a research-only MVP for Kalshi daily low-temperature markets.
It collects public data, scores risk, saves SQLite snapshots, and generates a
Markdown report. It must never place trades.

## AI Handoff

- Read `docs/AI_CONTEXT.md` for the compact project map, safety states, and
  low-temperature bucket-state rules before making non-trivial changes.
- Read `docs/WORKSPACE_MAP.md` when reorganizing files or cleaning generated
  artifacts.

## Hard Rules

- Do not add order placement, trading, portfolio, or account mutation behavior.
- Do not use paid APIs.
- Prefer free weather sources: weather.gov/NWS, forecast.weather.gov XML, and
  Open-Meteo fallback data.
- Prefer the exact NWS Climatological Report Daily (`CLI...`) product cited in
  the Kalshi rules whenever it is available. It is the closest source to
  settlement truth.
- Use Playwright for browser-based Kalshi page collection.
- Respect official station mappings. If Kalshi says a market uses a specific
  airport or weather sensor, update `config.py` and document the note.
- Keep the MVP runnable with `python scanner.py`.

## Local Command Guidance

- This workspace uses RTK command filtering. Prefix shell commands with `rtk`.
- Useful checks:
  - `rtk python -m unittest discover tests`
  - `rtk python -m compileall .`
  - `rtk python scanner.py`

## Design Preferences

- Prefer ugly working heuristics over a large framework.
- Missing weather or Kalshi data should produce warnings and a report, not a
  crash.
- Store raw-ish snapshots in SQLite so scoring can be improved later.
- Make all generated reports clear that they are research-only.
