import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal

# We will implement this module next.
from robinhood_crypto_bot.rh_database import init_db, insert_quote, get_recent_quotes

class RobinhoodDBTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_quotes.sqlite3"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_insert_and_retrieve_quotes(self):
        now = datetime.now(timezone.utc)
        
        insert_quote(
            self.db_path,
            timestamp=now,
            symbol="BTC-USD",
            bid=Decimal("60000.00"),
            ask=Decimal("60010.00"),
            mark=Decimal("60005.00"),
            spread=Decimal("10.00")
        )

        quotes = get_recent_quotes(self.db_path, limit=1)
        self.assertEqual(len(quotes), 1)
        q = quotes[0]
        self.assertEqual(q["symbol"], "BTC-USD")
        self.assertEqual(q["bid"], 60000.00)
        self.assertEqual(q["ask"], 60010.00)
        self.assertEqual(q["mark"], 60005.00)
        self.assertEqual(q["spread"], 10.00)
        self.assertEqual(q["timestamp"], now.isoformat())

    def test_insert_missing_optional_values(self):
        now = datetime.now(timezone.utc)
        
        insert_quote(
            self.db_path,
            timestamp=now,
            symbol="ETH-USD",
            bid=None,
            ask=None,
            mark=Decimal("3000.00"),
            spread=None
        )

        quotes = get_recent_quotes(self.db_path, limit=1)
        self.assertEqual(len(quotes), 1)
        q = quotes[0]
        self.assertEqual(q["symbol"], "ETH-USD")
        self.assertIsNone(q["bid"])
        self.assertIsNone(q["ask"])
        self.assertEqual(q["mark"], 3000.00)
        self.assertIsNone(q["spread"])

    def test_retrieves_newest_first(self):
        for i in range(3):
            insert_quote(
                self.db_path,
                timestamp=datetime(2026, 6, 21, 10, i, tzinfo=timezone.utc),
                symbol="BTC-USD",
                bid=Decimal("60000"),
                ask=Decimal("60010"),
                mark=Decimal(f"6000{i}"),
                spread=Decimal("10")
            )

        quotes = get_recent_quotes(self.db_path, limit=2)
        self.assertEqual(len(quotes), 2)
        self.assertEqual(quotes[0]["mark"], 60002.0)
        self.assertEqual(quotes[1]["mark"], 60001.0)

if __name__ == "__main__":
    unittest.main()
