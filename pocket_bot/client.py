# pocket_bot/client.py
"""Thin wrapper around the BinaryOptionsToolsV2 PocketOption client.

ponytail: this is the one file that absorbs drift in the underlying
library's method names/signatures (confirmed in Task 5 Step 2) — if a
future version renames buy/sell/get_candles, fix it here only.
"""
from __future__ import annotations

from BinaryOptionsToolsV2 import PocketOption


class PocketOptionClient:
    def __init__(self, ssid: str, demo: bool = True):
        self._client = PocketOption(ssid, demo=demo)

    def get_recent_candles(self, pair: str, period: int, count: int) -> list[tuple[int, float]]:
        candles = self._client.get_candles(pair, period, count * period)
        return [(c["time"], c["close"]) for c in candles[-count:]]

    def buy(self, pair: str, amount: float, expiry_seconds: int) -> str:
        trade_id, _deal = self._client.buy(pair, amount, expiry_seconds)
        return trade_id

    def sell(self, pair: str, amount: float, expiry_seconds: int) -> str:
        trade_id, _deal = self._client.sell(pair, amount, expiry_seconds)
        return trade_id

    def check_result(self, trade_id: str) -> dict:
        return self._client.check_win(trade_id)
