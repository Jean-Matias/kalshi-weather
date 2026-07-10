# hotscout backtest results

| city | decision hour | threshold | n | win rate | ROI | Brier |
|---|---|---|---|---|---|---|
| Las Vegas | 9 | 0.03 | 57 | 49.1% | 0.385 | 0.155 |
| Las Vegas | 9 | 0.05 | 55 | 49.1% | 0.422 | 0.158 |
| Las Vegas | 11 | 0.03 | 59 | 45.8% | 0.349 | 0.149 |
| Las Vegas | 11 | 0.05 | 54 | 48.1% | 0.440 | 0.153 |
| Las Vegas | 13 | 0.03 | 56 | 42.9% | 0.267 | 0.149 |
| Las Vegas | 13 | 0.05 | 50 | 44.0% | 0.260 | 0.158 |

Validation split is the headline (chronologically last 30% of event-days).

## Walk-forward validation (expanding monthly folds)

Residuals for each fold month are fit only on dates strictly before it.

| city | hour | threshold | month | n | win rate | ROI | Brier |
|---|---|---|---|---|---|---|---|
| Las Vegas | 9 | 0.03 | 2026-04 | 79 | 67.1% | 0.368 | 0.116 |
| Las Vegas | 9 | 0.03 | 2026-05 | 62 | 54.8% | 0.360 | 0.162 |
| Las Vegas | 9 | 0.03 | 2026-06 | 59 | 52.5% | 0.467 | 0.140 |
| Las Vegas | 9 | 0.03 | 2026-07 | 2 | 0.0% | -1.041 | 0.411 |
| Las Vegas | 9 | 0.03 | pooled | 202 | 58.4% | 0.374 | 0.140 |
| Las Vegas | 9 | 0.05 | 2026-04 | 66 | 68.2% | 0.442 | 0.122 |
| Las Vegas | 9 | 0.05 | 2026-05 | 49 | 53.1% | 0.434 | 0.190 |
| Las Vegas | 9 | 0.05 | 2026-06 | 55 | 52.7% | 0.519 | 0.148 |
| Las Vegas | 9 | 0.05 | 2026-07 | 2 | 0.0% | -1.041 | 0.411 |
| Las Vegas | 9 | 0.05 | pooled | 172 | 58.1% | 0.439 | 0.153 |
| Las Vegas | 11 | 0.03 | 2026-04 | 69 | 68.1% | 0.462 | 0.136 |
| Las Vegas | 11 | 0.03 | 2026-05 | 48 | 60.4% | 0.525 | 0.166 |
| Las Vegas | 11 | 0.03 | 2026-06 | 58 | 46.6% | 0.434 | 0.138 |
| Las Vegas | 11 | 0.03 | 2026-07 | 2 | 0.0% | -1.035 | 0.411 |
| Las Vegas | 11 | 0.03 | pooled | 177 | 58.2% | 0.447 | 0.148 |
| Las Vegas | 11 | 0.05 | 2026-04 | 64 | 67.2% | 0.479 | 0.141 |
| Las Vegas | 11 | 0.05 | 2026-05 | 40 | 62.5% | 0.637 | 0.173 |
| Las Vegas | 11 | 0.05 | 2026-06 | 53 | 47.2% | 0.486 | 0.146 |
| Las Vegas | 11 | 0.05 | 2026-07 | 1 | 0.0% | -1.033 | 0.455 |
| Las Vegas | 11 | 0.05 | pooled | 158 | 58.9% | 0.505 | 0.153 |
| Las Vegas | 13 | 0.03 | 2026-04 | 68 | 70.6% | 0.343 | 0.128 |
| Las Vegas | 13 | 0.03 | 2026-05 | 59 | 52.5% | 0.512 | 0.173 |
| Las Vegas | 13 | 0.03 | 2026-06 | 60 | 43.3% | 0.275 | 0.146 |
| Las Vegas | 13 | 0.03 | 2026-07 | 0 | 0.0% | 0.000 | 0.000 |
| Las Vegas | 13 | 0.03 | pooled | 187 | 56.1% | 0.370 | 0.148 |
| Las Vegas | 13 | 0.05 | 2026-04 | 58 | 70.7% | 0.413 | 0.142 |
| Las Vegas | 13 | 0.05 | 2026-05 | 50 | 54.0% | 0.557 | 0.168 |
| Las Vegas | 13 | 0.05 | 2026-06 | 53 | 43.4% | 0.255 | 0.154 |
| Las Vegas | 13 | 0.05 | 2026-07 | 0 | 0.0% | 0.000 | 0.000 |
| Las Vegas | 13 | 0.05 | pooled | 161 | 56.5% | 0.407 | 0.154 |

## Las Vegas — decision hour 9 — threshold 0.03

Window: 2026-04-02 to 2026-07-01 (91 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 343 | 0.014 | 0.000 |
| [0.1, 0.2) | 39 | 0.145 | 0.026 |
| [0.2, 0.3) | 23 | 0.239 | 0.130 |
| [0.3, 0.4) | 27 | 0.337 | 0.333 |
| [0.4, 0.5) | 36 | 0.456 | 0.472 |
| [0.5, 0.6) | 25 | 0.553 | 0.760 |
| [0.6, 0.7) | 47 | 0.661 | 0.766 |
| [0.7, 0.8) | 4 | 0.706 | 1.000 |
| [0.8, 0.9) | 0 | - | - |
| [0.9, 1.0) | 2 | 0.953 | 1.000 |

## Las Vegas — decision hour 9 — threshold 0.05

Window: 2026-04-02 to 2026-07-01 (91 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 343 | 0.014 | 0.000 |
| [0.1, 0.2) | 39 | 0.145 | 0.026 |
| [0.2, 0.3) | 23 | 0.239 | 0.130 |
| [0.3, 0.4) | 27 | 0.337 | 0.333 |
| [0.4, 0.5) | 36 | 0.456 | 0.472 |
| [0.5, 0.6) | 25 | 0.553 | 0.760 |
| [0.6, 0.7) | 47 | 0.661 | 0.766 |
| [0.7, 0.8) | 4 | 0.706 | 1.000 |
| [0.8, 0.9) | 0 | - | - |
| [0.9, 1.0) | 2 | 0.953 | 1.000 |

## Las Vegas — decision hour 11 — threshold 0.03

Window: 2026-04-02 to 2026-07-01 (91 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 342 | 0.013 | 0.000 |
| [0.1, 0.2) | 40 | 0.144 | 0.025 |
| [0.2, 0.3) | 23 | 0.239 | 0.130 |
| [0.3, 0.4) | 27 | 0.337 | 0.333 |
| [0.4, 0.5) | 35 | 0.455 | 0.486 |
| [0.5, 0.6) | 26 | 0.551 | 0.731 |
| [0.6, 0.7) | 47 | 0.661 | 0.766 |
| [0.7, 0.8) | 4 | 0.706 | 1.000 |
| [0.8, 0.9) | 0 | - | - |
| [0.9, 1.0) | 2 | 0.953 | 1.000 |

## Las Vegas — decision hour 11 — threshold 0.05

Window: 2026-04-02 to 2026-07-01 (91 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 342 | 0.013 | 0.000 |
| [0.1, 0.2) | 40 | 0.144 | 0.025 |
| [0.2, 0.3) | 23 | 0.239 | 0.130 |
| [0.3, 0.4) | 27 | 0.337 | 0.333 |
| [0.4, 0.5) | 35 | 0.455 | 0.486 |
| [0.5, 0.6) | 26 | 0.551 | 0.731 |
| [0.6, 0.7) | 47 | 0.661 | 0.766 |
| [0.7, 0.8) | 4 | 0.706 | 1.000 |
| [0.8, 0.9) | 0 | - | - |
| [0.9, 1.0) | 2 | 0.953 | 1.000 |

## Las Vegas — decision hour 13 — threshold 0.03

Window: 2026-04-02 to 2026-07-01 (91 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 341 | 0.011 | 0.000 |
| [0.1, 0.2) | 42 | 0.142 | 0.024 |
| [0.2, 0.3) | 22 | 0.241 | 0.091 |
| [0.3, 0.4) | 27 | 0.337 | 0.333 |
| [0.4, 0.5) | 35 | 0.456 | 0.486 |
| [0.5, 0.6) | 26 | 0.551 | 0.731 |
| [0.6, 0.7) | 43 | 0.661 | 0.791 |
| [0.7, 0.8) | 7 | 0.724 | 0.857 |
| [0.8, 0.9) | 0 | - | - |
| [0.9, 1.0) | 3 | 0.967 | 1.000 |

## Las Vegas — decision hour 13 — threshold 0.05

Window: 2026-04-02 to 2026-07-01 (91 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 341 | 0.011 | 0.000 |
| [0.1, 0.2) | 42 | 0.142 | 0.024 |
| [0.2, 0.3) | 22 | 0.241 | 0.091 |
| [0.3, 0.4) | 27 | 0.337 | 0.333 |
| [0.4, 0.5) | 35 | 0.456 | 0.486 |
| [0.5, 0.6) | 26 | 0.551 | 0.731 |
| [0.6, 0.7) | 43 | 0.661 | 0.791 |
| [0.7, 0.8) | 7 | 0.724 | 0.857 |
| [0.8, 0.9) | 0 | - | - |
| [0.9, 1.0) | 3 | 0.967 | 1.000 |

## Caveats

- Forecast used per event-day is the forecast_daily row with the smallest lead_days >= 0 for that (city, date); residuals are fit from the same selection rule. The headline (lead 0, same-day archive) matches the live dashboard's information set, but the archive's issue time is unknown; the conservative lead>=1 stress test (--min-forecast-lead 1) flips Las Vegas ROI negative (~-0.35), so the edge depends on having a decision-time-fresh forecast. forecast_snapshots is accumulating provably pre-decision live forecasts to settle this.
- Entry price at each decision hour is the first candle at/after that hour's local wall-clock time; falls back to price_c when yes_ask_c is missing (tagged price_source per trade).
- high_so_far_f (and therefore hours_to_peak blending) is only available where obs_hourly has cached observations; otherwise the model runs without an intraday anchor.
- Calibration table is computed over every bucket-probability observation evaluated (traded or not), across the full window.