# Weather Bot Handoff

Use this note when Claude or another AI assistant needs to pick up the weather bot project.

## Current Goal

Build a reusable weather-bot command center that can support future Kalshi weather bots, starting with low-temperature markets.

The current implementation is a paper/signal bot only. It must not place real orders, mutate the Kalshi account, import order-placement code, or turn on live trading from this workspace.

## Where To Read First

1. `AGENTS.md`
   - RTK command rule.
   - Research-only boundaries.
   - No paid APIs.
   - No real trading or account mutation.

2. `docs/AI_CONTEXT.md`
   - Existing high-temperature scanner architecture.
   - Weather source states and source safety rules.

3. `docs/BOT_HANDOFF.md`
   - This file.

4. `backtest/low_strategies.py`
   - Shared strategy functions used by the backtester and paper bot.

5. `weather_bot/core.py`
   - Bot definitions, snapshot builder, paper trade payloads, and risk gates.

6. `weather_bot/app.py`
   - FastAPI dashboard and JSON endpoints.

## Hard Safety Boundaries

- Keep the bot in paper mode unless the user explicitly asks for a separate live-trading project and accepts the risks.
- Do not place orders.
- Do not call Kalshi order, trade, portfolio, balance, or account-mutation endpoints.
- Do not print secrets.
- Do not copy credentials into this repo.
- Keep all reports and dashboards labeled research-only or paper-only.
- Treat NWS CLI as the best settlement-aligned source when it is date-matched.
- Treat station observations and forecasts as evidence, not final settlement truth.

## Current Bot

Default bot:

- Bot id: `vegas-low-confirmation`
- Name: `Vegas Low Confirmation`
- Market type: low temperature
- City: Las Vegas
- Strategy: `low_weather_confirmed`
- Decision hour: `3`
- Contracts: `3`
- Mode: `paper`
- Real order placement: blocked

The strategy is confirmation-style:

- It uses historical weather/settlement data to estimate the likely low bucket.
- It only paper-buys YES when the weather target and Kalshi favorite agree.
- It skips when they disagree, when price is outside the configured band, or when data is missing.

This is intentionally more conservative than the pure weather-prediction strategy, which tested poorly.

## Dashboard

Run the paper bot dashboard:

```powershell
rtk python -m uvicorn weather_bot.app:app --host 127.0.0.1 --port 8092
```

Open:

```text
http://127.0.0.1:8092
```

API endpoints:

```text
GET /api/bots
GET /api/bots/vegas-low-confirmation/snapshot?days=60
```

The dashboard shows:

- active paper bot
- current signal label
- 60-day backtest summary
- paper trade blotter
- risk gates
- weather-vs-Kalshi confirmation explanation

Screenshot from the last verification:

```text
reports/weather-bot-dashboard.png
```

## Current Backtest Snapshot

Latest verified Vegas low-weather confirmation result:

- Window: 60 event-days
- Strategy: `low_weather_confirmed`
- Decision hour: `3`
- Contracts: `3`
- Trades: `12`
- Skips: `48`
- Win rate: `83.3%`
- EV per trade: `+66.50c`
- Total simulated P&L: `+$7.98`
- Worst drawdown: `-154c`
- Older half EV: `+70.00c`
- Newer half EV: `+63.00c`

Interpretation:

- The result is promising but small-sample.
- It should stay paper-only until we collect more cities and more days.
- A future live bot needs stricter bankroll limits, max daily loss, max open exposure, and manual enablement.

## Strategy Findings So Far

Confirmation style is the current leader.

`low_weather_confirmed` on Las Vegas, 60 days:

- h3: 12 trades, 83.3% win rate, `+66.50c` EV/trade, `+$7.98`
- h6: 13 trades, 76.9% win rate, `+39.15c` EV/trade, `+$5.09`
- h9: 11 trades, 81.8% win rate, `+50.27c` EV/trade, `+$5.53`
- h12: 9 trades, 66.7% win rate, `+8.33c` EV/trade, `+$0.75`

San Antonio (tested 2026-06-10, 60 event-days, series `KXLOWTSATX`) behaves opposite to Vegas:

- The market favorite is badly calibrated early: at h3 it was priced ~39c but settled YES only 25% of the time.
- Settlement skews hotter than the favorite (favorite colder than settlement 47% of days at h3), the reverse of the "market bets hotter" hypothesis.
- `low_weather_confirmed` (the Vegas winner) fails there early: h3 = 10 trades, 20% win, `-53.50c` EV/trade. It only turns positive late (h9 `+54.80c`, h12 `+65.67c`) once the favorite becomes reliable.
- New strategy `low_fade_favorite` (buy NO on the favorite when priced 20-60c) exploits the early miscalibration:
  - San Antonio h3: 56 trades, 73.2% win, `+25.41c` EV/trade, `+$14.23`, worst drawdown `-772c`, older/newer halves `+32.21c` / `+18.61c`.
  - San Antonio h6: 55 trades, 69.1% win, `+16.62c` EV/trade.
  - Las Vegas h3 control: `-34.83c` EV/trade — the fade is city-specific, do not deploy it blindly across cities.
- Diagnostics tool: `python -m backtest.low_skew --city "San Antonio" --days 60` prints favorite-vs-settlement skew, favorite calibration, and naive fade EV per decision hour. Run it on any newly cached city before picking a strategy.
- Caveats: ~60 days of one season, execution uses hourly candle close (no bid/ask spread modeled), and early-hour books may be thin. Paper-only until it survives more days and live spread checks.

Pure weather prediction performed poorly and should not be promoted without major changes.

`low_weather_prediction` on Las Vegas, 60 days:

- h3: 35 trades, 31.4% win rate, `-20.20c` EV/trade
- h6: 32 trades, 37.5% win rate, `-12.81c` EV/trade
- h9: 30 trades, 36.7% win rate, `-15.70c` EV/trade
- h12: 28 trades, 35.7% win rate, `-9.36c` EV/trade

## Important Lookahead Fix

The low-weather strategy had a no-lookahead bug during development.

`_prior_lows()` must only use completed weather days before `decision_local_iso`. It must not use same-day final low data at decision time.

Preserve tests that prove:

- decision hour cannot read later bucket prices
- strategy cannot use same-day final low before it would have been known
- cached data is reused safely

## Data Status

Las Vegas and San Antonio (67 settled event-days, `KXLOWTSATX`) have usable cached low-market history in this workspace.

Other low-weather cities are configured but still need historical Kalshi/cache collection before they can be compared honestly in the bot backtester.

Configured low-weather cities:

- Atlanta
- Austin
- Chicago
- Dallas
- Denver
- Las Vegas
- Minneapolis
- NYC
- Oklahoma City
- Philadelphia
- Phoenix
- San Antonio
- Washington DC

## Minneapolis Test Result

Minneapolis was the first non-Vegas low-weather city tested.

Data collection:

- Command: `rtk python -m backtest.low_data --city "Minneapolis" --target-events 90`
- Cached historical event-days: `67`
- Newly fetched candle sets: `402`

`low_weather_confirmed` over 60 event-days:

- h3: 14 trades, 42.9% win rate, `-39.57c` EV/trade, `-$5.54`, worst drawdown `-$9.83`
- h6: 12 trades, 58.3% win rate, `+18.50c` EV/trade, `+$2.22`, worst drawdown `-$4.11`
- h9: 12 trades, 50.0% win rate, `-8.00c` EV/trade, `-$0.96`, worst drawdown `-$6.45`
- h12: 15 trades, 46.7% win rate, `-10.00c` EV/trade, `-$1.50`, worst drawdown `-$7.21`

Verdict:

- Do not promote Minneapolis to the dashboard as an active paper bot yet.
- The only positive entry point was h6, and its newer half turned negative.
- The city may be useful later for strategy research, but it does not resemble the Vegas confirmation edge.

Reports:

- `reports/low-backtest-minneapolis-confirmed-60d-h3.md`
- `reports/low-backtest-minneapolis-confirmed-60d-h6.md`
- `reports/low-backtest-minneapolis-confirmed-60d-h9.md`
- `reports/low-backtest-minneapolis-confirmed-60d-h12.md`

## Next City To Explore

Explore Phoenix next.

Reason:

- Minneapolis was tested and should not be promoted.
- Phoenix ranked second in the low-weather scout reliability report at `65/100`.
- Phoenix had weather confidence `84/100`.
- Phoenix is a better Vegas-like comparison because it is also a hot, drier market with airport-station settlement.

Recommended follow-up order:

1. Phoenix
2. Denver
3. San Antonio
4. Dallas
5. Minneapolis strategy variants only, not dashboard promotion

Important caveat:

- The reliability report is a live same-day source-quality snapshot from `2026-06-03`, not a profitability result.
- Before adding a Phoenix bot, collect historical market data and run the same `low_weather_confirmed` tests used for Vegas.

Suggested command:

```powershell
rtk python -m backtest.low_data --city "Phoenix" --target-events 90
rtk python -m backtest.low_run --city "Phoenix" --days 60 --strategy low_weather_confirmed --decision-hour 3
```

Then compare Phoenix against Vegas using:

- trades taken
- skip reasons
- win rate
- EV per trade
- total simulated P&L
- worst drawdown
- older-half vs newer-half stability

## Useful Commands

Run all tests:

```powershell
rtk python -m unittest discover tests
```

Compile check:

```powershell
rtk python -m compileall .
```

Run Vegas low confirmation backtest:

```powershell
rtk python -m backtest.low_run --city "Las Vegas" --days 60 --strategy low_weather_confirmed --decision-hour 3
```

Run the dashboard:

```powershell
rtk python -m uvicorn weather_bot.app:app --host 127.0.0.1 --port 8092
```

Check bot API:

```powershell
rtk python -c "from urllib.request import urlopen; print(urlopen('http://127.0.0.1:8092/api/bots').read().decode())"
```

## Current Verification

Last verified:

- `rtk python -m unittest discover tests`
- `rtk python -m compileall .`
- dashboard API at `http://127.0.0.1:8092/api/bots`
- dashboard screenshot at `reports/weather-bot-dashboard.png`

Known note:

- Node Playwright was not available, but Python Playwright successfully rendered the dashboard screenshot.

## Near-Term TODO

1. Collect low historical data for Minneapolis.
2. Run `low_weather_confirmed` for h3, h6, h9, and h12.
3. Compare Minneapolis vs Vegas with the same risk metrics.
4. Add a second paper bot definition only if Minneapolis has positive EV and stable older/newer halves.
5. Add dashboard city/bot selector support if more than one bot is enabled.
6. Add bankroll guardrails before any future trading discussion:
   - max contracts per event
   - max daily loss
   - max open exposure
   - cooldown after loss
   - manual arming switch
   - dry-run audit log
