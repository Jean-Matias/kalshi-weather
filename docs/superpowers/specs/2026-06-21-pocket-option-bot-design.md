# Pocket Option RSI Bot — Design

## Purpose

A standalone trading bot for Pocket Option, separate from the Kalshi weather
project (different platform, different risk profile, no shared state).
Trades a single OTC synthetic pair using an RSI-based signal, on a demo
account first, with a daily loss kill switch.

## Scope

- One OTC pair, one indicator (RSI), one expiry (1 min), fixed stake size.
- Demo account only for this iteration — no real-money trading until the
  user explicitly asks for it.
- No backtesting: OTC price history isn't published anywhere outside Pocket
  Option, so this can only be forward-tested live (with fake demo money).
- No multi-asset support, no martingale/stake scaling, no UI/dashboard.

## Known risk (carried from brainstorming, not re-litigated here)

OTC pairs are a broker-generated synthetic feed with no independent
reference price. There is no way to verify the feed is fair. Demo-only scope
exists specifically to de-risk this before any real money is involved.

## Architecture

New top-level directory `pocket_bot/`, independent of the existing
`weather_bot/` / Kalshi code:

- `pocket_bot/client.py` — thin wrapper around a reverse-engineered Pocket
  Option WebSocket client library (third-party pip package). Responsibilities:
  - Authenticate using a session ID (SSID) string the user copies from a
    logged-in browser tab (no username/password flow exists for this).
  - Subscribe to 1-minute candle stream for the configured pair.
  - Expose `place_trade(direction: "call"|"put", amount: float, expiry_s: int) -> trade_id`.
  - Expose a way to poll/await the trade result (win/loss/amount).
- `pocket_bot/signals.py` — pure function, no I/O:
  - `rsi(closes: list[float], period: int = 14) -> float`
  - `signal(rsi_value: float, overbought: float = 70, oversold: float = 30) -> "call" | "put" | None`
- `pocket_bot/runner.py` — main loop:
  - Maintain rolling window of closed candles for the configured pair.
  - On each new candle, compute RSI and signal.
  - On a signal, place a trade for the configured stake amount and expiry.
  - Log every trade (timestamp, pair, direction, stake, result, RSI value) to
    a local SQLite file (`pocket_bot/pocket_bot.db`), same lightweight
    pattern as the existing `database.py`.
  - Track cumulative daily P&L; once daily loss exceeds the configured cap,
    stop placing new trades until the next day (kill switch).
- `pocket_bot/config.py` — single place for: pair name, stake amount, RSI
  period/thresholds, expiry seconds, daily max-loss cap. All are config
  values the user can tune — no magic numbers buried in logic.

## Data flow

```
WS candle stream -> runner (rolling window) -> signals.rsi/signal
                                              -> client.place_trade (if signal)
                                              -> SQLite log + daily P&L tracker
```

## Error handling

- WS disconnects: client reconnects with backoff; runner pauses trading
  during disconnect rather than guessing stale prices.
- Trade placement failure (e.g. API rejects): logged as a skipped signal, not
  a crash — the loop continues to the next candle.
- Daily loss cap breach: hard stop for new entries; existing pending trade
  outcomes still get logged.

## Testing

- `pocket_bot/test_signals.py`: synthetic price series with a known RSI
  result, and known call/put/None outputs at the boundary thresholds. This is
  the only non-trivial logic in the system (everything else is I/O glue) so
  it's the only thing that gets a real test.
- No automated test for `client.py` (would require live WS/account) — verify
  it manually against the demo account on first run.

## Explicitly not building (this iteration)

- Backtesting (impossible for OTC data).
- Multiple pairs/indicators.
- Stake scaling / martingale.
- Dashboard or notifications beyond log/SQLite.
- Real-money trading (separate explicit decision later).
