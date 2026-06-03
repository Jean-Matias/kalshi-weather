# kalshi-weather-scout

Cheap MVP research tool for Kalshi daily high-temperature markets.

This is not an auto-trading bot. It only collects data, scores risk, stores
snapshots, and writes a Markdown report.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Run

```bash
python scanner.py
```

Outputs:

- SQLite snapshots: `data/snapshots.sqlite3`
- Daily report: `reports/today.md`
- Side-signal report: `reports/signals.md`
- Source-confidence report: `reports/temperature-confidence.md`

## AI Handoff

Future AI conversations should read `AGENTS.md` first, then
`docs/AI_CONTEXT.md`. The project is optimized for short-context handoff:
root files are the runnable app, `reports/` and `data/` are generated outputs,
and `docs/prompts/` stores historical prompts.

## Notes

- Weather data uses free sources only: weather.gov/NWS, forecast.weather.gov
  XML, and Open-Meteo fallback/model comparison.
- The scanner prefers the exact NWS Climatological Report Daily (`CLI...`)
  products cited in Kalshi rules. If a CLI high is available, it is treated as
  the strongest settlement-aligned source.
- Kalshi data is collected with Playwright from visible browser page content.
  Login-gated or layout-sensitive fields may be missing.
- Manual station config lives in `config.py` and maps the 20 visible Kalshi
  daily-temperature city markets to their official NWS stations/climate reports.
  Always verify the official station/sensor for each contract before using a
  signal.
- Scores are heuristic MVP research signals, not trading advice.

## Development Checks

```bash
python -m unittest discover tests
python -m pytest
python -m compileall .
python scanner.py
```
