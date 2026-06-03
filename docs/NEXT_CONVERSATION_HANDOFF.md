# Next Conversation Handoff

Use this note to continue work on the high-temperature Kalshi dashboard in a fresh chat.

## What Tool We Are Using

The tool is `kalshi-weather-scout`, a research-only Python scanner/dashboard for Kalshi daily high-temperature markets.

Canonical command:

```powershell
rtk python scanner.py
```

That command refreshes:

- `reports/dashboard.html` - primary browser dashboard with Today and Tomorrow tabs.
- `reports/today.md` - city-level scored rows for the current Kalshi market date.
- `reports/signals.md` - side-level YES/NO signals.
- `reports/temperature-confidence.md` - weather source confidence.
- `reports/city-reliability.md` - city/source reliability.
- `data/snapshots.sqlite3` - same-day SQLite snapshots.

Open the dashboard directly in a browser. No web server is required:

```text
C:\Users\jeanm\OneDrive\Documents\kalshi weather\reports\dashboard.html
```

## Current Dashboard Behavior

- Today tab: uses live same-day NWS station observations, NWS hourly forecast, Kalshi visible page data, and CLI settlement status when available.
- Tomorrow tab: uses the next market date and forecast-only evidence. If Kalshi prices are posted, it shows price/gap calls. If prices are not posted yet, it shows likely-bucket watchlist cards.
- Tomorrow forecast rows are not saved into SQLite snapshots, to avoid mixing future forecasts with today live history.
- The tool is read-only toward Kalshi. It scrapes visible market pages only and never places trades.

## Where To Read First

Read these files before making changes:

1. `AGENTS.md`
   - RTK command rule.
   - Research-only boundaries.
   - No trading, order placement, account mutation, or paid APIs.

2. `docs/AI_CONTEXT.md`
   - Project map.
   - Safety states.
   - Data-source meanings.
   - Chicago regression context.

3. `docs/WORKSPACE_MAP.md`
   - Folder/file roles and cleanup policy.

4. `README.md`
   - Basic project usage.

## Important Source Documentation

Primary public/free data sources:

- NWS CLI settlement-style reports:
  `https://forecast.weather.gov/product.php?site=...&product=CLI&issuedby=...&format=TXT`

- NWS hourly forecast XML/DWML:
  `https://forecast.weather.gov/MapClick.php?lat=...&lon=...&unit=0&lg=english&FcstType=digitalDWML`

- NWS hourly forecast graph for human inspection:
  `https://forecast.weather.gov/MapClick.php?lat=...&lon=...&unit=0&lg=english&FcstType=graphical`

- NWS station observations:
  `https://api.weather.gov/stations/{station_id}/observations/latest`
  and station observation history.

- Open-Meteo fallback/comparison:
  `https://api.open-meteo.com/v1/forecast`

Kalshi rule text should be checked from the visible market page. Use the station and climate product stated by Kalshi rules as the authority when mappings need correction.

## Main Code Files

- `scanner.py`: entrypoint. Runs today and tomorrow passes and writes reports.
- `config.py`: city, station, market URL, ticker, and market-date config.
- `weather_sources.py`: NWS CLI, station observations/history, forecast.gov XML, Open-Meteo, derived weather state.
- `kalshi_browser.py`: Playwright visible-page scraper and contract parser.
- `scoring.py`: probabilities, source safety, bucket state, signal labels, and live-risk gating.
- `report.py`: Markdown and static HTML dashboard builders.
- `database.py`: SQLite JSON snapshot persistence.
- `tests/`: regression tests.

## Safe Verification Commands

```powershell
rtk python -m unittest discover tests
rtk python -m compileall .
rtk python scanner.py
```

Use `BeautifulSoup` for a fast dashboard structure check when needed:

```powershell
rtk python -c "from bs4 import BeautifulSoup; from pathlib import Path; s=BeautifulSoup(Path('reports/dashboard.html').read_text(encoding='utf-8'),'html.parser'); print(len(s.select('.today-panel .call-card')), len(s.select('.tomorrow-panel .call-card')), len(s.select('.tomorrow-panel tbody tr')))"
```

## Hard Boundaries

- Do not add trading, order placement, account mutation, portfolio logic, or Kalshi account APIs.
- Do not add paid weather APIs.
- Do not treat forecast.gov or Open-Meteo as settlement truth.
- Do not hide source uncertainty.
- Keep the MVP runnable with `rtk python scanner.py`.

