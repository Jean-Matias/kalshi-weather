# Low-Temperature Accuracy Audit Prompt

Use this prompt when asking another model to review changes to `kalshi-low-weather-scout`.

This is a research-only tool for Kalshi daily low-temperature markets. It must never place trades, call Kalshi trading/account/order APIs, or use paid weather APIs. It runs with:

```powershell
rtk python scanner.py
rtk python -m unittest discover tests
rtk python -m pytest
rtk python -m compileall .
```

Review focus:

- CLI minimum temperature parsing, including same-line MAX/MIN formats.
- Wrong-date, stale, inconsistent, or unparseable-date CLI handling.
- Raw observed low and rounded market low behavior.
- Bounded bucket touched by observed low is preliminary, not final.
- Observed low below a bounded bucket lower bound makes YES impossible.
- Open-ended bottom buckets can lock YES once touched.
- Open-ended top buckets cannot lock YES from observations and become impossible once crossed below.
- NO signals are blocked from LEAN/WATCH after a bucket is touched or crossed.
- Forecast-only signals stay downgraded while the active low-temperature window is true.
- Reports clearly show research-only status, official station/source, raw/rounded low, forecast low, source safety state, bucket state, active low window, and warnings.

Reject any recommendation that adds trading behavior, paid APIs, or hides uncertainty.
