# tests/test_pocket_runner.py
import datetime as dt
import unittest

from pocket_bot import config, runner, storage


class FakeClient:
    def __init__(self):
        self.calls = []

    def buy(self, pair, amount, expiry):
        self.calls.append(("buy", pair, amount, expiry))
        return "trade-1"

    def sell(self, pair, amount, expiry):
        self.calls.append(("sell", pair, amount, expiry))
        return "trade-1"


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.conn = storage.init_db(":memory:")
        self.client = FakeClient()
        self.runner = runner.Runner(self.client, config, self.conn)

    def test_no_trade_until_window_full(self):
        for close in [10.0, 10.1, 10.2]:
            result = self.runner.on_candle(close)
            self.assertIsNone(result)
        self.assertEqual(self.client.calls, [])

    def test_oversold_streak_triggers_call(self):
        closes = [20.0 - i for i in range(config.RSI_PERIOD + 2)]
        last_result = None
        for close in closes:
            last_result = self.runner.on_candle(close)
        self.assertEqual(last_result, "call")
        self.assertEqual(self.client.calls[-1][0], "buy")

    def test_daily_loss_cap_stops_new_trades(self):
        today_ts = dt.datetime.combine(dt.date.today(), dt.time()).isoformat()
        storage.log_trade(
            self.conn, today_ts, config.PAIR, "call",
            config.STAKE_AMOUNT, 25.0, result="loss", pnl=-config.DAILY_MAX_LOSS,
        )
        closes = [20.0 - i for i in range(config.RSI_PERIOD + 2)]
        for close in closes:
            self.runner.on_candle(close)
        self.assertEqual(self.client.calls, [])


if __name__ == "__main__":
    unittest.main()
