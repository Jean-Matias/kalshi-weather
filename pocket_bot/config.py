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
DEMO = True
SSID_ENV_VAR = "POCKET_OPTION_SSID"


def get_ssid() -> str:
    ssid = os.environ.get(SSID_ENV_VAR)
    if not ssid:
        raise RuntimeError(f"Set {SSID_ENV_VAR} env var with your Pocket Option session ID")
    return ssid
