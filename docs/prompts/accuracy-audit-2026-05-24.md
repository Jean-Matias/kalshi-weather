# Next Chat Prompt: Kalshi Weather Scout Accuracy Audit

I am working in `C:\Users\jeanm\OneDrive\Documents\kalshi weather` on a Python project called `kalshi-weather-scout`.

This is a research-only tool for Kalshi daily high-temperature markets. It must never place trades or use paid APIs. It runs with:

```powershell
python scanner.py
```

The goal is to make the tool as accurate and honest as possible with the free data available, so I can make my own betting decisions with better information behind them. Do not give financial advice and do not build auto-trading behavior.

Important context:

- We had a real miss on Chicago May 24, 2026.
- Kalshi's Chicago market used Chicago Midway, IL / `KMDW`.
- The `74F to 75F` bucket ended up winning.
- The tool initially treated high-so-far as about `69.8F`, but later KMDW observations reached `73.9F`, which should be treated as `74F` for integer market buckets.
- The failure mode was live same-day overconfidence: the heating window was still active, the CLI report for May 24 was not final yet, and the scanner relied too much on forecast/high-so-far snapshots.

Your workflow for this conversation:

1. Inspect the code, tests, reports, and current behavior first.
2. Create a proposed accuracy-improvement plan. Do not implement code yet.
3. Use Claude and Gemini to review the proposed plan before presenting it to me.
4. When Claude and Gemini return feedback, validate their feedback yourself. Keep what is technically sound, reject anything unsafe, irrelevant, overbuilt, paid-API-based, or trade-execution-related.
5. Present me the revised plan plus a short note summarizing what Claude and Gemini contributed and what you accepted or rejected.
6. Wait for me to accept the plan before implementing.
7. After implementation, run verification.
8. Then use Claude and Gemini again to review the changed code and tests.
9. Validate their code-review feedback yourself, implement repairs if needed, and rerun verification.
10. Only then summarize the final result for me.

Use Claude and Gemini as reviewers, not as unquestioned authorities. The chat is responsible for deciding whether their input is correct.

Accuracy problems to hunt aggressively:

- wrong official station
- wrong local market date
- stale CLI report from yesterday
- forecast.weather.gov coordinates that point to downtown instead of the official Kalshi station
- using forecast data as if it were settlement data
- failing to round observed highs the same way the market bucket resolves
- treating a still-active heating window as settled
- generating LEAN/WATCH signals before a bucket is actually locked or final CLI is available
- bad YES/NO inversion, especially when a bucket has already been crossed
- market rows scraped from Kalshi but matched to the wrong station or wrong date
- stale browser/session data
- late-day rebounds, cloud breaks, wind shifts, or marine-layer effects
- liquidity/price signals that look attractive only because the market is thin or already resolved

Data-source rules:

- Use only free sources:
  - NWS/weather.gov
  - forecast.weather.gov hourly XML / digitalDWML
  - NWS station observations API
  - Open-Meteo only as a comparison/fallback
- No paid APIs.
- No trading APIs.
- No order placement.
- If final same-day NWS CLI is available and date-matched, it overrides forecast and live observations.
- If final CLI is not available, live station observations are preliminary and the report must say so clearly.

Testing and reliability tools already installed:

- `pytest`
- `responses`
- `vcrpy`
- `requests-cache`
- `beautifulsoup4`

The plan should include tests that reproduce the Chicago miss:

- KMDW observations include `73.9F`
- official/market high-so-far should become `74F`
- `74F to 75F` YES should be favored over NO after that observation
- `NO 74F to 75F` must not appear as a LEAN/WATCH after `74F` has been hit
- before the heating window is over, forecast-only NO signals must be downgraded or explicitly blocked

Consider adding explicit source/safety states:

- `FINAL_CLI_AVAILABLE`
- `CLI_STALE`
- `LIVE_OBS_PRELIMINARY`
- `FORECAST_ONLY`
- `ACTIVE_HEATING_WINDOW`
- `LOCKED_BY_OBSERVED_HIGH`
- `CROSSED_BUCKET`
- `UNRESOLVED_BUCKET`

Reports should become brutally clear about:

- final CLI vs preliminary station observations vs forecast
- official station and station source URL
- latest observation timestamp
- market local date and local time
- time remaining before likely high-temperature window ends
- raw high and rounded/market high
- bucket state: already crossed, still possible, impossible, or final
- explicit "do not bet from forecast-only signal" warnings
- why each signal can still be dangerous

Verification commands:

```powershell
python -m compileall .
python -m unittest discover tests
pytest
python scanner.py
```

Rules:

- This is not financial advice and not a trading bot.
- Never add order placement or Kalshi trading API behavior.
- Prefer conservative labels when data is not final.
- Missing data must degrade confidence and add warnings, not crash.
- If a bucket has already been crossed by rounded official-station high-so-far, that bucket state must dominate forecast estimates.
- If Claude or Gemini suggests anything involving paid APIs, automatic trading, or ignoring Kalshi's official station/rules, reject that suggestion.
