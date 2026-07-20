# hotscout data sources

Historical data lives in `data/hotscout.sqlite3`. Four independent pullers
(`hotscout/data/{cli_history,forecast_history,obs_history,kalshi_history}.py`)
populate the five source tables defined in `hotscout/schema.py`. Run
`python -m hotscout.data.build --all --days N` to (re)backfill, or
`--probe --city "<city>"` to hit each endpoint once without bulk-downloading.

## cli_daily — settlement truth

- **Endpoint**: IEM `https://mesonet.agron.iastate.edu/json/cli.py?station=<ICAO>&year=<YYYY>`
  (NWS Climatological Report Daily, mirrored by Iowa Environmental Mesonet).
  This is what Kalshi's daily-high markets actually settle against.
- **Coverage** (as of this check): 183 rows per city, 2026-01-01 to 2026-07-02,
  for all three cities (Las Vegas / KLAS, Phoenix / KPHX, San Antonio / KSAT).
- **Quirks**: IEM returns `"M"` for missing highs (skipped, not stored as
  0/None-in-DB — those dates just have no row). Backfill is resumable per
  year: a year already at >=300 rows is skipped without a new HTTP call
  (current year is never treated as complete).

## forecast_daily — model forecast highs

- **lead_days=0** — `historical-forecast-api.open-meteo.com/v1/forecast`,
  `daily=temperature_2m_max`, model `ncep_nbm_conus` only (NWS's National
  Blend of Models). `best_match` was dropped 2026-07-20: it only existed as
  a pre-2025 coverage fallback (`ncep_nbm_conus` has no data before ~2025),
  which hotscout's 2026 backtest window never needed, and — since Kalshi
  settles against a specific NWS station product — every temperature input
  should be attributable to NWS, not Open-Meteo's separately-blended,
  not-necessarily-NWS `best_match` model. `ncep_nbm_conus` only returns
  non-null values from ~2025 onward; older requests come back null and are
  skipped, but that's outside hotscout's window anyway.
- **lead_days=1/2/3** — `previous-runs-api.open-meteo.com/v1/forecast`,
  `hourly=temperature_2m_previous_dayN`, model `ncep_nbm_conus` only. This is
  the forecast for a given hour as it stood N days before that hour occurred;
  reduced to one high per local calendar date by taking the max across that
  date's hours.
- **Coverage**: 905 rows per city, 2026-01-04 to 2026-07-03 (both models at
  lead 0 plus leads 1-3, so up to 5 rows/date; not every date has all 5 since
  `best_match`/`ncep_nbm_conus` and the previous-run leads can each fail
  independently per HTTP call).
- **Forecast skill check** (MAE vs. cli_daily, this DB): lead_days=0 is
  consistently the most accurate (LV 0.94F, Phoenix 1.46F, SATX 1.28F),
  degrading smoothly through lead_days=1/2/3 (LV up to 1.69F at lead 3).
  This gradient is what you'd expect from real forecast skill decay, not a
  same-day-conditions leak: NBM's runs for a given calendar date are
  available hours before local sunrise in all three timezones (UTC-6/7/8),
  well before the 9/11/13-local decision hours the backtest uses.
- **Quirk**: `forecast_daily` has no forecast-issue timestamp, only
  `lead_days`. `backtest._forecast_high_f` picks `MIN(lead_days)` per date,
  i.e. it always prefers lead_days=0 when present.

## obs_hourly — intraday observations (for "high so far")

- **Endpoint**: IEM ASOS archive,
  `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=<3-letter, K dropped>&data=tmpf&...&tz=<city tz>&format=onlycomma`.
  Returns 5-minute-resolution readings (`"M"` for missing); downsampled here
  to hourly-max per local hour.
- **Coverage**: ~4,300+ rows per city (LV 4306, Phoenix 4311, SATX 4318),
  2026-01-04 to 2026-07-02.

## kalshi_events / kalshi_candles — market history

- **Source**: NOT fetched directly by hotscout. `hotscout/data/kalshi_history.py`
  delegates to the pre-existing `backtest/data.py` disk cache
  (`ensure_cached`/`load_dataset`), which talks to the Kalshi API and caches
  events.json + per-bucket candlestick files on disk; hotscout only ingests
  that cache into sqlite (`kalshi_events`, `kalshi_candles`).
- **Coverage**: 91 settled event-days per city (one Kalshi daily-high market
  each), 2026-04-02 to 2026-07-01 — this is the real limit: Kalshi's
  `KXHIGHTLV`/`KXHIGHTPHX`/`KXHIGHTSATX` series and/or the disk cache don't
  go back further than early April 2026, so ~3 months / 91 event-days is
  the entire available window, not a puller-side cap.
- **Candle depth**: 21,565 (LV) / 21,407 (Phoenix) / 20,111 (SATX) candle
  rows across all buckets and events, hourly cadence (occasional 3-hour
  gaps), spanning the same window as the events.
- **Quirk**: bucket labels ("76 to 77", "75 or below", "84 or above") are
  parsed into `{low_f, high_f}` by regex in `kalshi_history.parse_bucket_label`;
  an unrecognized label shape silently becomes `(None, None)` (fully
  open-ended), which would make that bucket's model probability meaningless
  — no such case was observed in this dataset, but a future label variant
  could break silently rather than raising.

## Settlement cross-check

For every city, over every settled Kalshi event-day where `cli_daily` also
has a same-date row, checked whether `cli_high_f` falls inside the bucket
that actually settled `"yes"` (parsed low/high bounds, open ends treated as
+/-infinity):

| city | checked | matched | pct |
|---|---|---|---|
| Las Vegas | 91 | 91 | 100.0% |
| Phoenix | 91 | 91 | 100.0% |
| San Antonio | 91 | 91 | 100.0% |

No mismatches in any city — station selection, date alignment, and bucket
parsing all agree with Kalshi's own settlement. Re-run via
`hotscout.data.build.run_cross_check(CITIES)`.
