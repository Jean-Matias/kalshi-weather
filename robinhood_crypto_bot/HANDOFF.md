# Robinhood Crypto Agent/Bot Handoff

## Purpose

This subproject is a training and research bot for the official Robinhood
Crypto Trading API. It is separate from the Kalshi weather dashboard.

Current operating mode is read-only and dry-run. Do not place orders or enable
live trading unless the user explicitly requests it after the strategy and risk
controls have been tested.

## Current Status

- The Ed25519 key pair has been generated locally.
- `robinhood_crypto_bot/.env` contains the API key and private key.
- `.env` is ignored by Git. Never print, commit, paste, or include its values in
  reports or handoffs.
- A signed read-only `BTC-USD` quote request completed successfully on
  2026-06-21.
- `BOT_DRY_RUN=true`.
- `BOT_ALLOW_LIVE_ORDERS=false`.
- No order-placement method is implemented in the client.
- SQLite quote logging is implemented locally for dry-run captures.

## Important Files

- `bot.py`: CLI watcher and dry-run loop.
- `rh_client.py`: signed official Robinhood Crypto API client.
- `strategy.py`: simple observation-only momentum signal.
- `generate_keys.py`: creates an Ed25519 key pair and stores only the private
  key in `.env`; refuses to overwrite an existing key.
- `.env.example`: non-secret configuration template.
- `.env`: local credentials and runtime settings; ignored by Git.
- `requirements.txt`: Python dependencies.
- `README.md`: human setup instructions.
- `../tests/test_robinhood_keygen.py`: key-generation regression tests.

## Run Commands

From the repository root:

```powershell
rtk python -m pip install -r robinhood_crypto_bot/requirements.txt
rtk python robinhood_crypto_bot/bot.py --symbol BTC-USD --once
rtk python robinhood_crypto_bot/bot.py --symbol BTC-USD
```

Run verification:

```powershell
rtk python -m unittest tests.test_robinhood_keygen
rtk python -m compileall robinhood_crypto_bot
```

## Safety Rules

1. Never expose or log `ROBINHOOD_PRIVATE_KEY_BASE64` or the API key.
2. Keep `.env` ignored by Git and out of screenshots or generated reports.
3. Keep `BOT_DRY_RUN=true` and `BOT_ALLOW_LIVE_ORDERS=false` during research.
4. Use read-only API calls for quotes, products, accounts, holdings, and order
   history.
5. Do not add order submission until position sizing, daily loss limits,
   duplicate-order protection, kill switches, and tests exist.
6. Do not mix this bot's credentials or trading logic into the Kalshi weather
   dashboard.

## Suggested Next Steps

1. Collect several days of dry-run observations before evaluating a strategy.
3. Add spread, slippage, and fee-aware simulated fills.
4. Add a simulated portfolio with strict exposure and daily-loss limits.
5. Backtest the exact strategy against stored data before considering live use.

## Starting Prompt For The Next Agent

```text
Work only inside robinhood_crypto_bot unless a shared test must be added under
tests. Read robinhood_crypto_bot/HANDOFF.md and README.md first. Preserve the
read-only, dry-run defaults and never print or commit credentials. Inspect the
existing code and tests before making changes, use RTK for every command, and
verify with the focused unit tests plus compileall. Do not implement or enable
live order placement without an explicit user request and tested risk controls.
```
