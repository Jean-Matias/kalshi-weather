import unittest

from pocket_bot import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.conn = storage.init_db(":memory:")

    def test_daily_pnl_with_no_trades_is_zero(self):
        self.assertEqual(storage.daily_pnl(self.conn, "2026-06-21"), 0.0)

    def test_daily_pnl_sums_same_day_only(self):
        storage.log_trade(
            self.conn, "2026-06-21T10:00:00", "EURUSD_otc", "call", 1.0, 25.0,
            result="win", pnl=0.85,
        )
        storage.log_trade(
            self.conn, "2026-06-21T10:05:00", "EURUSD_otc", "put", 1.0, 75.0,
            result="loss", pnl=-1.0,
        )
        storage.log_trade(
            self.conn, "2026-06-20T10:00:00", "EURUSD_otc", "call", 1.0, 20.0,
            result="win", pnl=0.85,
        )
        self.assertAlmostEqual(storage.daily_pnl(self.conn, "2026-06-21"), -0.15, places=6)

    def test_log_trade_without_result_is_excluded_from_pnl(self):
        storage.log_trade(
            self.conn, "2026-06-21T10:00:00", "EURUSD_otc", "call", 1.0, 25.0,
        )
        self.assertEqual(storage.daily_pnl(self.conn, "2026-06-21"), 0.0)


if __name__ == "__main__":
    unittest.main()
