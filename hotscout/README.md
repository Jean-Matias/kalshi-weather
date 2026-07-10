# hotscout

A daily-high-temperature Kalshi trading tool: pulls historical weather/market
data, fits a forecast-error ("residual") model per city/decision-hour/month,
backtests a threshold-edge trading rule against real Kalshi settlement
history, and serves a live dashboard that only recommends trades where the
backtest cleared a validation gate.

Cities: Las Vegas, Phoenix, San Antonio (`hotscout/config.py:CITIES`).

## Runbook

All commands run from the repo root.

**Refresh historical data** (cli_daily, forecast_daily, obs_hourly,
kalshi_events/candles):
```
python -m hotscout.data.build --all --days 180
python -m hotscout.data.build --probe --city "Las Vegas"   # spot-check one endpoint, no bulk pull
```
This also runs a settlement cross-check at the end (does `cli_daily`'s high
fall inside the bucket that actually settled "yes"?). See
`hotscout/data/SOURCES.md` for per-source endpoint docs, coverage, and the
current cross-check numbers (100% match, all three cities, as of this
writing).

**Recalibrate** the residual-distribution model (persists to
`residual_models`, used by the live dashboard):
```
python -m hotscout.calibration --all
```

**Rerun the backtest** (persists to `backtest_results`, writes
`reports/hotscout_backtest.md`):
```
python -m hotscout.backtest --all --thresholds 0.03,0.05,0.08
```

**Launch the dashboard**:
```
uvicorn hotscout.app:app --port 8801
```
`/` renders the board (`hotscout/ui.py`), `/api/board` returns the JSON
payload, `/api/backtest?city=...` and `/api/picks` expose the underlying
tables. The board still returns (with a `warnings` entry) if today's Kalshi
event or live weather fetch fails — it does not 500.

## Badges and the validation gate

Each city's card shows a `backtest_badge` (win rate / ROI / n_trades /
window) and is tinted green ("Validated") or red ("NOT VALIDATED"). A
city/decision-hour is validated only if, in the backtest's chronological
**validation split** (last 30% of event-days by date):

```
n_trades >= MIN_VALIDATION_TRADES (30)   AND   roi > 0
```

(`hotscout/config.py`, enforced in `hotscout/live.py`). Recommendations
("BUY YES"/"BUY NO") only ever appear when the badge is validated **and**
the live edge-after-fees clears `EDGE_THRESHOLD_DEFAULT` (0.05); otherwise
the board shows `PASS` and, if unvalidated, an explicit
`"NOT VALIDATED: recommendations disabled for this city/hour"` warning. This
gate is intentionally strict — with only ~91 Kalshi event-days of history
per city (see below), it is entirely possible, and was expected, for some
or all city/hour combos to fail it.

## Current status (as of this backfill: ~91 event-days/city, 2026-04-02 to
## 2026-07-01)

- Kalshi history is the hard limit on backtest depth: the `KXHIGHTLV` /
  `KXHIGHTPHX` / `KXHIGHTSATX` series (or at least the disk cache hotscout
  reads from) only go back to early April 2026, giving ~91 settled
  event-days per city — a 70/30 split leaves roughly 27 validation days per
  city/hour, each with multiple tradeable buckets.
- After fixing a look-ahead bug in the backtest (see below), 21 of 27
  city x decision-hour x threshold combinations for Las Vegas and Phoenix
  clear the validation gate (n>=30, roi>0); San Antonio does not clear it at
  any threshold (win rate ~37-46%, ROI ranges from slightly negative to
  barely positive, and the one qualifying-by-n_trades combo has ROI too
  close to noise to trust with real money).
- Read this as "there is a directionally promising signal for Las Vegas and
  Phoenix worth more data before trusting it," not "this is a proven edge."
  91 event-days is one Vegas/Phoenix/San Antonio spring-into-summer window;
  there's no cross-year validation, and the sample sizes (40-90 trades)
  are small enough that win rates in the 45-55% range with a handful of bad
  weeks could flip the ROI sign. Do not size real trades off these numbers
  without a longer backtest window once more Kalshi history accumulates.

## A real bug found and fixed during integration

`hotscout/calibration.fit()` pools forecast-error residuals from a city's
**entire** history into one distribution per (decision_hour, month); that's
correct for live trading (today really is the most recent day). But the
backtest was originally calling `calibration.load_residual_dist()` — the
same globally-fit table — to score **validation-split** trades too. That
means the model being graded against "future" (validation-period) event-days
had already seen residuals from those same days baked into its fitted
distribution: classic look-ahead bias, and the likely explanation for
suspiciously strong pre-fix ROI numbers (e.g. Las Vegas @ 9am,
threshold 0.03: ROI 0.419 pre-fix vs. 0.357 post-fix — smaller but still
real changes across the board once the leak was closed).

Fix: `hotscout/backtest.py` now fits a train-only residual distribution (via
the new `calibration.compute_residual_dist()` / `calibration.load_date_maps()`
helpers, restricted to dates strictly before the validation window's start)
whenever the caller doesn't inject its own `load_residual_dist_fn` — i.e.
whenever `backtest.main()` runs for real. Unit tests that inject a fake
calibration function are unaffected. See `hotscout/backtest.py`'s
`_train_only_residual_dist_fn` docstring for the full reasoning.

No other look-ahead issues were found: decision-hour candle selection only
uses candles with `ts >= decision_ts` (first candle at/after, never
before); `high_so_far_f` only pools `obs_hourly` rows with
`ts_local <= decision_hour`; and the lead_days=0 forecast (an NWS National
Blend of Models run) is available hours before local sunrise in all three
timezones, well before the 9/11/13-local decision hours used, so it isn't a
same-day-conditions leak either (see `hotscout/data/SOURCES.md` for the
MAE-by-lead-time check that supports this).

## Tests

```
python -m pytest tests/test_hotscout_fees.py tests/test_hotscout_data.py \
    tests/test_hotscout_model.py tests/test_hotscout_backtest.py \
    tests/test_hotscout_app.py -q
python -m pytest tests -q
```
Full-suite baseline: 160 passed. Two pre-existing collection errors
(`tests/test_robinhood_bot.py`, `tests/test_robinhood_keygen.py`) are
unrelated to hotscout — they fail because the `nacl` package isn't
installed in this environment.
