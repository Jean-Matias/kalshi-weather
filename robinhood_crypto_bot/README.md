# Robinhood Crypto Bot

Research/training bot for the official Robinhood Crypto Trading API.

This starts in **read-only + dry-run** mode. Do not enable live orders until the
watcher has been running cleanly and you understand the strategy/risk limits.

## Setup

1. Create a Robinhood Crypto API key in Robinhood web classic crypto settings.
2. Start with read-only permissions. Do not enable order placement yet.
3. Copy `.env.example` to `.env`.
4. Fill in:

```text
ROBINHOOD_API_KEY=...
ROBINHOOD_PRIVATE_KEY_BASE64=...
```

5. Install dependencies:

```powershell
rtk python -m pip install -r robinhood_crypto_bot/requirements.txt
```

6. Run the live dry-run observer (logs to SQLite):

```powershell
rtk python robinhood_crypto_bot/bot.py --symbol BTC-USD
```

7. View offline recent history directly from SQLite (no API keys needed):

```powershell
rtk python robinhood_crypto_bot/bot.py --recent 10
```

## Safety Defaults

- `BOT_DRY_RUN=true` by default.
- `BOT_ALLOW_LIVE_ORDERS=false` by default.
- Live order code refuses to run unless both settings are deliberately changed.
- Default strategy is observation-only and logs a simple momentum read.

## Official API Notes

Robinhood Crypto authenticated requests use:

- `x-api-key`
- `x-signature`
- `x-timestamp`

The signature message format used here is:

```text
api_key + timestamp + path + method + body
```

Base URL:

```text
https://trading.robinhood.com
```

