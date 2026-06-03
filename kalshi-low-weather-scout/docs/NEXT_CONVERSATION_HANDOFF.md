# Next Conversation Handoff

This project is `kalshi-low-weather-scout`, a research-only scanner for Kalshi
daily LOW-temperature markets.

Workspace:

```powershell
C:\Users\jeanm\OneDrive\Documents\kalshi weather\kalshi-low-weather-scout
```

Run commands from that folder and prefix shell commands with `rtk`.

## Main Command

Refresh all data, reports, dashboard, and SQLite snapshots:

```powershell
rtk python scanner.py
```

Target the market date the user is actually aiming for:

```powershell
$env:KALSHI_MARKET_DATE="2026-06-03"; rtk python scanner.py
```

LOW-temperature workflow note: if the user asks during the day, the current
date's low may already have happened in the morning. In that case the
actionable research target is often the next morning's market date. Ask for or
set `KALSHI_MARKET_DATE`; do not rely on an automatic Tomorrow dashboard.

Main dashboard:

```powershell
reports\dashboard.html
```

Other generated reports:

```powershell
reports\today.md
reports\signals.md
reports\temperature-confidence.md
reports\city-reliability.md
```

Database snapshot:

```powershell
data\snapshots.sqlite3
```

Preferred user-facing report format:

```powershell
docs\LOW_TEMP_REPORT_FORMAT.md
```

Use that file whenever the user asks for a report. The user expects top 4
reliable cities, confidence for the expected low, the low time in Eastern Time,
and a plain-English Kalshi market read.

## Required Reading

Read these first before making changes:

```powershell
AGENTS.md
docs\AI_CONTEXT.md
docs\WORKSPACE_MAP.md
```

`AGENTS.md` has the hard rules and RTK command rule. `AI_CONTEXT.md` has the
low-temperature source states, bucket states, and file map.

## Hard Rules

- Research only. Not financial advice.
- Never add order placement, auto-trading, Kalshi trading API behavior,
  portfolio logic, or account mutation.
- Do not use paid APIs.
- Keep free sources only: NWS/weather.gov, forecast.weather.gov XML/DWML,
  NWS station observations/history, and Open-Meteo fallback/comparison.
- Keep Playwright for visible browser-based Kalshi page collection.
- Missing data should create warnings and conservative labels, not crashes.

## Dashboard Purpose

The dashboard was simplified to help decide which cities are worth inspecting
first. It should rank cities by stable data and low temperature reliability,
not by a direct bet recommendation.

Current dashboard design:

- Top section: `Most Reliable Cities`
- One selected target market date only. There is no automatic Today/Tomorrow
  dashboard split.
- Cities are ranked best to worst using source quality, volatility risk,
  cooling/low-window risk, forecast availability, and observation freshness.
- `FUTURE_FORECAST` rows are watchlist data and should stay out of the top
  reliable city cards. They can still appear in the hidden section and all-city
  table when the selected target date is in the future.
- Volatile or low-confidence cities are hidden by default under
  `Show Avoided / Volatile Cities`.
- Each city card shows:
  - reliability score
  - temperature bracket
  - whichever side has the higher modeled probability, `YES` or `NO`
  - current rounded low
  - forecast low
  - freshness timestamp
  - `Sources used` dropdown
- Each source dropdown should include Kalshi page, NWS CLI, NWS hourly forecast,
  forecast graph, official station, climate product, market date, and final CLI
  status when available.

## Important LOW-Market Notes

LOW markets are more fragile than HIGH markets while live because the daily low
often happens overnight or early morning and can still fall lower. Treat all
active low-window data as preliminary until final same-day NWS CLI posts.

For current-day markets:

- `FINAL_CLI_AVAILABLE` is strongest.
- `LIVE_OBS_PRELIMINARY` means observations are useful but not final.
- `CLI_STALE` usually means the CLI is for a previous date and must not
  override current same-day observations.
- `FORECAST_ONLY` should be conservative.

For San Antonio LOW markets, Kalshi points to NWS `CLISAT`. The visible NWS
Observed Weather page labels the location as `San Antonio`, with dropdown value
`SAT`. The station mapping found during investigation is:

- `CLISAT`
- `SAT`
- `KSAT`
- `SAN ANTONIO INTL AP`
- `USW00012921`

Use that as the working settlement station mapping unless Kalshi/NWS rules
prove otherwise.

## Key Files

- `scanner.py`: entrypoint, writes all reports.
- `config.py`: city configs, Kalshi URLs/tickers, official station mappings.
- `weather_sources.py`: NWS CLI low parsing, observations, forecasts,
  Open-Meteo fallback, active low-window logic.
- `kalshi_browser.py`: Playwright visible-page collection and bucket parsing.
- `scoring.py`: low probabilities, source safety, bucket states, labels.
- `report.py`: Markdown reports and HTML dashboard.
- `database.py`: SQLite snapshots.
- `tests/`: unittest/pytest tests.

## Verification

Use these after changes:

```powershell
rtk python -m compileall .
rtk python -m unittest discover tests
rtk python -m pytest
rtk python scanner.py
```

After dashboard changes, check that `reports\dashboard.html` contains:

- `Most Reliable Cities`
- `Show Avoided / Volatile Cities`
- `Sources used`
- `All City Rank`

and does not regress to the older primary layout:

- `Reliable Signals`
- `Needs Review`
- `Avoid / Bad Prices`
