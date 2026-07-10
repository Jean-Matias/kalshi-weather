import os

PAIR = "EURUSD_otc"
CANDLE_PERIOD_SECONDS = 60
STAKE_AMOUNT = 1.0
EXPIRY_SECONDS = 60
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0
DAILY_MAX_LOSS = 20.0
CANDLE_WINDOW = RSI_PERIOD + 5
SSID_ENV_VAR = "POCKET_OPTION_SSID"
DEMO_ENV_VAR = "POCKET_OPTION_DEMO"

# ponytail: safe-by-default. Demo unless POCKET_OPTION_DEMO is explicitly set
# to "0"/"false" — going live is an opt-in env var, never a code default.
DEMO = os.environ.get(DEMO_ENV_VAR, "1").strip().lower() not in ("0", "false", "no")


def get_ssid() -> str:
    ssid = os.environ.get(SSID_ENV_VAR)
    if not ssid:
        raise RuntimeError(f"Set {SSID_ENV_VAR} env var with your Pocket Option session ID")
    return ssid
