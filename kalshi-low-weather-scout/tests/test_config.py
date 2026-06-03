import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from config import _market_date_for_timezone


class ConfigTests(unittest.TestCase):
    def test_default_market_date_uses_kalshi_date_not_city_local_date(self):
        now = datetime(2026, 5, 26, 6, 30, tzinfo=timezone.utc)

        self.assertEqual(_market_date_for_timezone("America/Los_Angeles", now=now), "2026-05-26")

    def test_market_date_override_wins(self):
        with patch.dict(os.environ, {"KALSHI_MARKET_DATE": "2026-05-24"}):
            self.assertEqual(_market_date_for_timezone("America/Los_Angeles"), "2026-05-24")


if __name__ == "__main__":
    unittest.main()
