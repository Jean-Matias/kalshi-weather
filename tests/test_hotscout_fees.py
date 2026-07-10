import sqlite3
import tempfile
import unittest
from pathlib import Path

from hotscout import db
from hotscout.config import CITIES, city_config
from hotscout.fees import kalshi_fee_cents
from hotscout.schema import DDL


class HotscoutFeesTests(unittest.TestCase):
    def test_fee_50_cents_1_contract(self):
        self.assertEqual(kalshi_fee_cents(50, 1), 2)

    def test_fee_99_cents_1_contract(self):
        self.assertEqual(kalshi_fee_cents(99, 1), 1)

    def test_fee_1_cent_1_contract(self):
        self.assertEqual(kalshi_fee_cents(1, 1), 1)

    def test_fee_50_cents_10_contracts(self):
        self.assertEqual(kalshi_fee_cents(50, 10), 18)


class HotscoutDbInitTests(unittest.TestCase):
    def test_init_creates_all_tables(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_hotscout.sqlite3"
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                db.init(conn)

                tables = {
                    row["name"]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
            finally:
                conn.close()

        self.assertEqual(len(DDL), 9)
        expected_tables = {
            "cli_daily",
            "forecast_daily",
            "obs_hourly",
            "kalshi_events",
            "kalshi_candles",
            "residual_models",
            "backtest_results",
            "forecast_snapshots",
            "picks",
        }
        self.assertTrue(expected_tables.issubset(tables))


class HotscoutConfigTests(unittest.TestCase):
    def test_three_cities_resolve_via_city_config(self):
        self.assertEqual(len(CITIES), 1)
        self.assertEqual(
            set(CITIES), {"Las Vegas"}
        )
        for name in CITIES:
            config = city_config(name)
            self.assertEqual(config["city"], name)


if __name__ == "__main__":
    unittest.main()
