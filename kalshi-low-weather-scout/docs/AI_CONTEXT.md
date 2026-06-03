# AI Context Guide: kalshi-low-weather-scout

Purpose: research-only scanner for Kalshi daily low-temperature markets. It collects free public weather data, scrapes visible Kalshi page content with Playwright, scores heuristic risk, saves SQLite JSON snapshots, and writes Markdown/HTML reports. It must never place trades or use paid APIs.

Fast start:

```powershell
rtk python scanner.py
rtk python -m unittest discover tests
rtk python -m pytest
rtk python -m compileall .
```

Use `rtk` before shell commands in this workspace.

Target a specific market date explicitly:

```powershell
$env:KALSHI_MARKET_DATE="2026-06-03"; rtk python scanner.py
```

The scanner now runs one selected market date only. It does not auto-add a
Tomorrow dashboard tab. For LOW markets, daytime research usually targets the
next morning's market date because the current calendar day's lowest
temperature often already happened near sunrise.

## Hard Boundaries

- No order placement, auto-trading, account mutation, portfolio logic, or Kalshi trading API behavior.
- No paid APIs. Allowed data sources are NWS/weather.gov, forecast.weather.gov DWML/XML, NWS station observations, and Open-Meteo fallback/comparison.
- Missing weather or Kalshi data should add warnings and degrade confidence, not crash the scan.
- Final same-day, date-matched NWS CLI minimum temperature is the strongest settlement-aligned source.
- Stale, wrong-date, inconsistent, or unparseable-date CLI must not override same-day station observations.
- Forecast-only signals during active low-window conditions must be treated conservatively.
- Forecast-only future-date rows are watchlist data, not top reliable signals, until live observations or final CLI evidence exists.

## File Map

- `scanner.py`: entrypoint. Loops through `CITY_CONFIGS`, fetches weather and visible Kalshi market data, scores rows/signals, writes reports and snapshots.
- `config.py`: low-market URL/ticker and official station configuration. Update this when Kalshi rules specify a different station/sensor.
- `weather_sources.py`: free weather collection and derived low-temperature state. Owns CLI minimum parsing, station observation low-so-far, forecast lows, Open-Meteo comparison, latest observation time, and active low-window logic.
- `kalshi_browser.py`: Playwright visible-text scraper and contract parser. Read-only browser collection only.
- `scoring.py`: low-temperature probabilities, source safety state, bucket state, signal labels, and blocked near-miss gating.
- `report.py`: Markdown and HTML report builders. Reports must stay blunt about data source quality and research-only status.
- `database.py`: SQLite snapshot persistence. Snapshots store JSON payloads; schema changes are rarely needed.
- `tests/`: unittest-style tests, also collected by `python -m pytest`.

## Core States

Source states:

- `FINAL_CLI_AVAILABLE`: date-matched CLI low is available and trusted.
- `CLI_STALE`: CLI exists but is wrong-date, inconsistent, or has unverified date.
- `LIVE_OBS_PRELIMINARY`: station observations exist but final CLI is not trusted.
- `FORECAST_ONLY`: no station observation/low-so-far is available.

Bucket states:

- `FINAL_YES` / `FINAL_NO`: final CLI resolves the bucket.
- `PRELIMINARY_OBSERVED_LOW_IN_BUCKET`: rounded official-station low has touched a bounded bucket, but the final low can still fall below it.
- `LOCKED_BY_OBSERVED_LOW`: rounded official-station low has touched an open-ended bottom bucket.
- `CROSSED_BELOW_BUCKET`: rounded official-station low has fallen below a bounded or open-ended-top bucket, making YES impossible.
- `UNRESOLVED_BUCKET`: live/forecast data has not resolved the bucket.

Temperature convention: `raw_low_so_far_f` preserves station observation precision; `low_so_far_f` is rounded with half-up behavior to match integer market buckets.

## Report Checks

Check these fields first:

- official station id/location
- market date and market-local time
- settlement/source safety state
- bucket state
- active low-temperature window
- latest observation timestamp
- raw low and rounded market low
- forecast low
- CLI source URL and forecast source URL
- warnings

## Common Unsafe Changes

- Calling Kalshi account/trade/order APIs.
- Adding paid weather providers.
- Treating forecast.gov or Open-Meteo as settlement truth.
- Treating preliminary observations as final CLI.
- Showing forecast-only or active-low-window signals as actionable.
- Hiding source uncertainty from reports.
