# pocket_bot/runner.py
from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Optional

from pocket_bot import signals, storage


class Runner:
    def __init__(self, client, cfg, conn: sqlite3.Connection):
        self.client = client
        self.cfg = cfg
        self.conn = conn
        self.closes: list[float] = []

    def on_candle(self, close: float) -> Optional[str]:
        self.closes.append(close)
        if len(self.closes) > self.cfg.CANDLE_WINDOW:
            self.closes = self.closes[-self.cfg.CANDLE_WINDOW:]
        if len(self.closes) < self.cfg.RSI_PERIOD + 1:
            return None

        today = dt.date.today().isoformat()
        if storage.daily_pnl(self.conn, today) <= -self.cfg.DAILY_MAX_LOSS:
            return None

        rsi_value = signals.rsi(self.closes, self.cfg.RSI_PERIOD)
        direction = signals.signal(rsi_value, self.cfg.RSI_OVERBOUGHT, self.cfg.RSI_OVERSOLD)
        if direction is None:
            return None

        if direction == "call":
            self.client.buy(self.cfg.PAIR, self.cfg.STAKE_AMOUNT, self.cfg.EXPIRY_SECONDS)
        else:
            self.client.sell(self.cfg.PAIR, self.cfg.STAKE_AMOUNT, self.cfg.EXPIRY_SECONDS)

        storage.log_trade(
            self.conn,
            dt.datetime.now().isoformat(),
            self.cfg.PAIR,
            direction,
            self.cfg.STAKE_AMOUNT,
            rsi_value,
        )
        return direction
