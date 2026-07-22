# hotscout backtest results

| city | decision hour | threshold | n | win rate | ROI | Brier |
|---|---|---|---|---|---|---|
| Las Vegas | 9 | 0.03 | 36 | 63.9% | 0.117 | 0.137 |
| Las Vegas | 9 | 0.05 | 32 | 62.5% | 0.140 | 0.136 |
| Las Vegas | 9 | 0.08 | 28 | 57.1% | 0.127 | 0.150 |
| Las Vegas | 11 | 0.03 | 43 | 53.5% | 0.019 | 0.136 |
| Las Vegas | 11 | 0.05 | 40 | 52.5% | 0.024 | 0.146 |
| Las Vegas | 11 | 0.08 | 30 | 46.7% | -0.015 | 0.165 |
| Las Vegas | 13 | 0.03 | 44 | 61.4% | 0.128 | 0.134 |
| Las Vegas | 13 | 0.05 | 38 | 55.3% | 0.107 | 0.148 |
| Las Vegas | 13 | 0.08 | 21 | 57.1% | 0.290 | 0.157 |

Validation split is the headline (chronologically last 30% of event-days).

## Walk-forward validation (expanding monthly folds)

Residuals for each fold month are fit only on dates strictly before it.

| city | hour | threshold | month | n | win rate | ROI | Brier |
|---|---|---|---|---|---|---|---|
| Las Vegas | 9 | 0.03 | 2026-05 | 39 | 79.5% | 0.342 | 0.173 |
| Las Vegas | 9 | 0.03 | 2026-06 | 49 | 71.4% | 0.357 | 0.149 |
| Las Vegas | 9 | 0.03 | 2026-07 | 33 | 63.6% | 0.134 | 0.124 |
| Las Vegas | 9 | 0.03 | pooled | 121 | 71.9% | 0.291 | 0.150 |
| Las Vegas | 9 | 0.05 | 2026-05 | 34 | 79.4% | 0.390 | 0.195 |
| Las Vegas | 9 | 0.05 | 2026-06 | 37 | 70.3% | 0.514 | 0.137 |
| Las Vegas | 9 | 0.05 | 2026-07 | 32 | 62.5% | 0.140 | 0.128 |
| Las Vegas | 9 | 0.05 | pooled | 103 | 70.9% | 0.349 | 0.153 |
| Las Vegas | 9 | 0.08 | 2026-05 | 27 | 77.8% | 0.311 | 0.190 |
| Las Vegas | 9 | 0.08 | 2026-06 | 23 | 78.3% | 0.757 | 0.151 |
| Las Vegas | 9 | 0.08 | 2026-07 | 26 | 61.5% | 0.153 | 0.142 |
| Las Vegas | 9 | 0.08 | pooled | 76 | 72.4% | 0.371 | 0.162 |
| Las Vegas | 11 | 0.03 | 2026-05 | 31 | 80.6% | 0.299 | 0.180 |
| Las Vegas | 11 | 0.03 | 2026-06 | 40 | 62.5% | 0.340 | 0.154 |
| Las Vegas | 11 | 0.03 | 2026-07 | 43 | 58.1% | 0.075 | 0.123 |
| Las Vegas | 11 | 0.03 | pooled | 114 | 65.8% | 0.226 | 0.149 |
| Las Vegas | 11 | 0.05 | 2026-05 | 29 | 79.3% | 0.311 | 0.191 |
| Las Vegas | 11 | 0.05 | 2026-06 | 30 | 70.0% | 0.496 | 0.156 |
| Las Vegas | 11 | 0.05 | 2026-07 | 35 | 60.0% | 0.112 | 0.133 |
| Las Vegas | 11 | 0.05 | pooled | 94 | 69.1% | 0.288 | 0.158 |
| Las Vegas | 11 | 0.08 | 2026-05 | 23 | 78.3% | 0.324 | 0.171 |
| Las Vegas | 11 | 0.08 | 2026-06 | 23 | 69.6% | 0.483 | 0.150 |
| Las Vegas | 11 | 0.08 | 2026-07 | 27 | 55.6% | 0.087 | 0.146 |
| Las Vegas | 11 | 0.08 | pooled | 73 | 67.1% | 0.284 | 0.155 |
| Las Vegas | 13 | 0.03 | 2026-05 | 30 | 83.3% | 0.522 | 0.200 |
| Las Vegas | 13 | 0.03 | 2026-06 | 41 | 68.3% | 0.358 | 0.185 |
| Las Vegas | 13 | 0.03 | 2026-07 | 41 | 58.5% | 0.090 | 0.127 |
| Las Vegas | 13 | 0.03 | pooled | 112 | 68.8% | 0.304 | 0.167 |
| Las Vegas | 13 | 0.05 | 2026-05 | 25 | 88.0% | 0.615 | 0.176 |
| Las Vegas | 13 | 0.05 | 2026-06 | 34 | 64.7% | 0.312 | 0.185 |
| Las Vegas | 13 | 0.05 | 2026-07 | 31 | 61.3% | 0.207 | 0.122 |
| Las Vegas | 13 | 0.05 | pooled | 90 | 70.0% | 0.366 | 0.161 |
| Las Vegas | 13 | 0.08 | 2026-05 | 18 | 83.3% | 0.643 | 0.199 |
| Las Vegas | 13 | 0.08 | 2026-06 | 24 | 66.7% | 0.424 | 0.205 |
| Las Vegas | 13 | 0.08 | 2026-07 | 21 | 57.1% | 0.278 | 0.146 |
| Las Vegas | 13 | 0.08 | pooled | 63 | 68.3% | 0.445 | 0.184 |

## Las Vegas — decision hour 9 — threshold 0.03

Window: 2026-05-13 to 2026-07-19 (68 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 275 | 0.008 | 0.004 |
| [0.1, 0.2) | 25 | 0.157 | 0.080 |
| [0.2, 0.3) | 18 | 0.252 | 0.333 |
| [0.3, 0.4) | 10 | 0.363 | 0.300 |
| [0.4, 0.5) | 13 | 0.452 | 0.385 |
| [0.5, 0.6) | 14 | 0.548 | 0.643 |
| [0.6, 0.7) | 12 | 0.656 | 0.667 |
| [0.7, 0.8) | 25 | 0.756 | 0.760 |
| [0.8, 0.9) | 14 | 0.813 | 0.929 |
| [0.9, 1.0) | 2 | 0.980 | 1.000 |

## Las Vegas — decision hour 9 — threshold 0.05

Window: 2026-05-13 to 2026-07-19 (68 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 275 | 0.008 | 0.004 |
| [0.1, 0.2) | 25 | 0.157 | 0.080 |
| [0.2, 0.3) | 18 | 0.252 | 0.333 |
| [0.3, 0.4) | 10 | 0.363 | 0.300 |
| [0.4, 0.5) | 13 | 0.452 | 0.385 |
| [0.5, 0.6) | 14 | 0.548 | 0.643 |
| [0.6, 0.7) | 12 | 0.656 | 0.667 |
| [0.7, 0.8) | 25 | 0.756 | 0.760 |
| [0.8, 0.9) | 14 | 0.813 | 0.929 |
| [0.9, 1.0) | 2 | 0.980 | 1.000 |

## Las Vegas — decision hour 9 — threshold 0.08

Window: 2026-05-13 to 2026-07-19 (68 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 275 | 0.008 | 0.004 |
| [0.1, 0.2) | 25 | 0.157 | 0.080 |
| [0.2, 0.3) | 18 | 0.252 | 0.333 |
| [0.3, 0.4) | 10 | 0.363 | 0.300 |
| [0.4, 0.5) | 13 | 0.452 | 0.385 |
| [0.5, 0.6) | 14 | 0.548 | 0.643 |
| [0.6, 0.7) | 12 | 0.656 | 0.667 |
| [0.7, 0.8) | 25 | 0.756 | 0.760 |
| [0.8, 0.9) | 14 | 0.813 | 0.929 |
| [0.9, 1.0) | 2 | 0.980 | 1.000 |

## Las Vegas — decision hour 11 — threshold 0.03

Window: 2026-05-13 to 2026-07-19 (68 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 275 | 0.008 | 0.004 |
| [0.1, 0.2) | 25 | 0.157 | 0.080 |
| [0.2, 0.3) | 18 | 0.252 | 0.333 |
| [0.3, 0.4) | 10 | 0.363 | 0.300 |
| [0.4, 0.5) | 13 | 0.452 | 0.385 |
| [0.5, 0.6) | 14 | 0.548 | 0.643 |
| [0.6, 0.7) | 12 | 0.656 | 0.667 |
| [0.7, 0.8) | 25 | 0.756 | 0.760 |
| [0.8, 0.9) | 14 | 0.813 | 0.929 |
| [0.9, 1.0) | 2 | 0.980 | 1.000 |

## Las Vegas — decision hour 11 — threshold 0.05

Window: 2026-05-13 to 2026-07-19 (68 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 275 | 0.008 | 0.004 |
| [0.1, 0.2) | 25 | 0.157 | 0.080 |
| [0.2, 0.3) | 18 | 0.252 | 0.333 |
| [0.3, 0.4) | 10 | 0.363 | 0.300 |
| [0.4, 0.5) | 13 | 0.452 | 0.385 |
| [0.5, 0.6) | 14 | 0.548 | 0.643 |
| [0.6, 0.7) | 12 | 0.656 | 0.667 |
| [0.7, 0.8) | 25 | 0.756 | 0.760 |
| [0.8, 0.9) | 14 | 0.813 | 0.929 |
| [0.9, 1.0) | 2 | 0.980 | 1.000 |

## Las Vegas — decision hour 11 — threshold 0.08

Window: 2026-05-13 to 2026-07-19 (68 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 275 | 0.008 | 0.004 |
| [0.1, 0.2) | 25 | 0.157 | 0.080 |
| [0.2, 0.3) | 18 | 0.252 | 0.333 |
| [0.3, 0.4) | 10 | 0.363 | 0.300 |
| [0.4, 0.5) | 13 | 0.452 | 0.385 |
| [0.5, 0.6) | 14 | 0.548 | 0.643 |
| [0.6, 0.7) | 12 | 0.656 | 0.667 |
| [0.7, 0.8) | 25 | 0.756 | 0.760 |
| [0.8, 0.9) | 14 | 0.813 | 0.929 |
| [0.9, 1.0) | 2 | 0.980 | 1.000 |

## Las Vegas — decision hour 13 — threshold 0.03

Window: 2026-05-13 to 2026-07-19 (68 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 276 | 0.007 | 0.004 |
| [0.1, 0.2) | 24 | 0.156 | 0.042 |
| [0.2, 0.3) | 18 | 0.253 | 0.333 |
| [0.3, 0.4) | 9 | 0.361 | 0.333 |
| [0.4, 0.5) | 13 | 0.446 | 0.385 |
| [0.5, 0.6) | 15 | 0.548 | 0.600 |
| [0.6, 0.7) | 12 | 0.656 | 0.667 |
| [0.7, 0.8) | 24 | 0.757 | 0.792 |
| [0.8, 0.9) | 14 | 0.815 | 0.929 |
| [0.9, 1.0) | 3 | 0.987 | 1.000 |

## Las Vegas — decision hour 13 — threshold 0.05

Window: 2026-05-13 to 2026-07-19 (68 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 276 | 0.007 | 0.004 |
| [0.1, 0.2) | 24 | 0.156 | 0.042 |
| [0.2, 0.3) | 18 | 0.253 | 0.333 |
| [0.3, 0.4) | 9 | 0.361 | 0.333 |
| [0.4, 0.5) | 13 | 0.446 | 0.385 |
| [0.5, 0.6) | 15 | 0.548 | 0.600 |
| [0.6, 0.7) | 12 | 0.656 | 0.667 |
| [0.7, 0.8) | 24 | 0.757 | 0.792 |
| [0.8, 0.9) | 14 | 0.815 | 0.929 |
| [0.9, 1.0) | 3 | 0.987 | 1.000 |

## Las Vegas — decision hour 13 — threshold 0.08

Window: 2026-05-13 to 2026-07-19 (68 event-days)

| prob bin | count | avg predicted | realized freq |
|---|---|---|---|
| [0.0, 0.1) | 276 | 0.007 | 0.004 |
| [0.1, 0.2) | 24 | 0.156 | 0.042 |
| [0.2, 0.3) | 18 | 0.253 | 0.333 |
| [0.3, 0.4) | 9 | 0.361 | 0.333 |
| [0.4, 0.5) | 13 | 0.446 | 0.385 |
| [0.5, 0.6) | 15 | 0.548 | 0.600 |
| [0.6, 0.7) | 12 | 0.656 | 0.667 |
| [0.7, 0.8) | 24 | 0.757 | 0.792 |
| [0.8, 0.9) | 14 | 0.815 | 0.929 |
| [0.9, 1.0) | 3 | 0.987 | 1.000 |

## Caveats

- Forecast used per event-day is the forecast_daily row with the smallest lead_days >= 0 for that (city, date); residuals are fit from the same selection rule. The headline (lead 0, same-day archive) matches the live dashboard's information set, but the archive's issue time is unknown; the conservative lead>=1 stress test (--min-forecast-lead 1) flips Las Vegas ROI negative (~-0.35), so the edge depends on having a decision-time-fresh forecast. forecast_snapshots is accumulating provably pre-decision live forecasts to settle this.
- Entry price at each decision hour is the first candle at/after that hour's local wall-clock time; falls back to price_c when yes_ask_c is missing (tagged price_source per trade).
- high_so_far_f (and therefore hours_to_peak blending) is only available where obs_hourly has cached observations; otherwise the model runs without an intraday anchor.
- Calibration table is computed over every bucket-probability observation evaluated (traded or not), across the full window.
