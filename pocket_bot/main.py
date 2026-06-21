# pocket_bot/main.py
"""Entrypoint: python -m pocket_bot.main

Polls Pocket Option for new closed candles on the configured pair and feeds
each one to Runner. Ctrl+C to stop.
"""
from __future__ import annotations

import time

from pocket_bot import config, storage
from pocket_bot.client import PocketOptionClient
from pocket_bot.runner import Runner


def main() -> None:
    client = PocketOptionClient(config.get_ssid(), demo=config.DEMO)
    conn = storage.init_db(str(storage.DB_PATH))
    runner = Runner(client, config, conn)

    last_time: int | None = None
    print(f"Starting pocket_bot on {config.PAIR}, demo={config.DEMO}")
    while True:
        candles = client.get_recent_candles(config.PAIR, period=60, count=config.CANDLE_WINDOW)
        for candle_time, close in candles:
            if last_time is not None and candle_time <= last_time:
                continue
            last_time = candle_time
            direction = runner.on_candle(close)
            if direction:
                print(f"{direction.upper()} signal placed on {config.PAIR}")
        time.sleep(5)


if __name__ == "__main__":
    main()
