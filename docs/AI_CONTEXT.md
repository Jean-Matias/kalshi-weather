# AI Context Guide: kalshi-weather-scout

Purpose: research-only scanner for Kalshi daily high-temperature markets. It collects free public weather data, scrapes visible Kalshi page content with Playwright, scores heuristic risk, saves SQLite JSON snapshots, and writes Markdown reports. It must never place trades or use paid APIs.

Fast start for future AI conversations:

```powershell
rtk python scanner.py
rtk python -m unittest discover tests
rtk python -m pytest
rtk python -m compileall .
```

Use `rtk` before shell commands in this workspace.

## Hard Boundaries

- No order placement, auto-trading, account mutation, portfolio logic, or Kalshi trading API behavior.
- No paid APIs. Allowed data sources are NWS/weather.gov, forecast.weather.gov DWML/XML, NWS station observations, and Open-Meteo fallback/comparison.
- Missing weather or Kalshi data should add warnings and degrade confidence, not crash the scan.
- Final same-day, date-matched NWS CLI is the strongest settlement-aligned source.
- Stale, wrong-date, inconsistent, or unparseable-date CLI must not override same-day station observations.
- Forecast-only signals during live same-day conditions must be treated conservatively.

## Current File Map

- `scanner.py`: runnable entrypoint. Loops through `CITY_CONFIGS`, fetches weather and Kalshi market data, scores rows/signals, writes reports and snapshots.
- `config.py`: station/market configuration. Official station mappings live here. Update this when Kalshi rules specify a different station/sensor.
- `weather_sources.py`: free weather collection and derived weather state. Owns CLI parsing, station observations/history, forecast.gov DWML, Open-Meteo fallback, raw/rounded high, latest observation time, and active heating-window logic.
- `kalshi_browser.py`: Playwright visible-text scraper and contract parser. Read-only browser collection only.
- `scoring.py`: heuristics, probabilities, source safety state, bucket state, signal labels, and blocked near-miss gating.
- `report.py`: Markdown report builders. Reports must stay blunt about data source quality and research-only status.
- `database.py`: SQLite snapshot persistence. Snapshots store JSON payloads; no schema migration is needed for most new fields.
- `tests/`: unittest-style tests, also collected by `python -m pytest`.
- `reports/`: generated Markdown outputs.
- `data/snapshots.sqlite3`: generated SQLite history.
- `docs/prompts/`: historical handoff prompts and prior audit context.

## Core Data States

Weather/source states used by scoring and reports:

- `FINAL_CLI_AVAILABLE`: date-matched CLI high is available and trusted.
- `CLI_STALE`: CLI exists but is wrong-date, inconsistent, or has unverified date.
- `LIVE_OBS_PRELIMINARY`: station observations exist but final CLI is not trusted.
- `FORECAST_ONLY`: no station observation/high-so-far is available.

Bucket states:

- `FINAL_YES` / `FINAL_NO`: final CLI resolves the bucket yes/no.
- `LOCKED_BY_OBSERVED_HIGH`: rounded official-station high has reached the bucket, but final CLI is not trusted yet.
- `CROSSED_BUCKET`: rounded high has moved above a bounded bucket.
- `IMPOSSIBLE_BY_OBSERVED_HIGH`: rounded high has moved above an open-ended below bucket.
- `UNRESOLVED_BUCKET`: live/forecast data has not resolved the bucket.

Temperature convention: `raw_high_so_far_f` preserves station observation precision; `high_so_far_f` is rounded with half-up behavior to match integer market buckets. Example: `73.9F -> 74F`.

## Chicago Miss Regression

Important historical failure: Chicago May 24, 2026 used KMDW/CLIMDW. Earlier data showed about `69.8F`; later KMDW observation history reached raw `73.9F`, rounded market high `74F`, making `74F to 75F` the relevant bucket. The scanner must not show `NO 74F to 75F` as a normal LEAN/WATCH or ordinary near-miss after the rounded official-station high has touched `74F`.

Regression coverage to preserve:

- KMDW observation history with raw `73.9F` yields rounded `74.0F`.
- YES probability for `74F to 75F` beats NO after `74F` has been observed.
- NO for that bucket is blocked from LEAN/WATCH and normal near-misses.
- Forecast-only NO signals are blocked/downgraded during active heating windows.
- Final same-day CLI overrides live/forecast; stale or unverified CLI does not.
- Stale station observations keep heating-window risk active.

## Report Reading

Primary outputs:

- `reports/today.md`: scored market rows.
- `reports/signals.md`: side-level YES/NO signal scan. If no WATCH/LEAN exists, normal near-misses are shown, but blocked/danger SKIPs are counted separately.
- `reports/temperature-confidence.md`: source confidence view.

Fields future AI should check first in reports:

- official station id/location
- market date and market-local time
- settlement/source safety state
- bucket state
- active heating window
- latest observation timestamp
- raw high and rounded market high
- CLI source URL and forecast source URL
- warnings

## Common Safe Changes

- Add tests first for scoring/weather/report behavior.
- Add new weather evidence fields to dict payloads; JSON snapshots tolerate this.
- Keep scoring conservative when data is missing, stale, forecast-only, or live.
- Update `config.py` if official station mapping is wrong, and document why in the city notes.

## Common Unsafe Changes

- Calling Kalshi account/trade/order APIs.
- Adding paid weather providers.
- Treating forecast.gov or Open-Meteo as settlement truth.
- Treating same-day preliminary observations as final CLI.
- Showing forecast-only or active-heating-window NO signals as actionable.
- Hiding source uncertainty from reports.
