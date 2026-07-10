import unittest
from decimal import Decimal
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path

_rb_path = str(Path(__file__).parent.parent / "robinhood_crypto_bot")
sys.path.insert(0, _rb_path)
from bot import parse_args, extract_quote_details
sys.path.remove(_rb_path)

class RobinhoodBotTests(unittest.TestCase):
    def test_extract_quote_details_full(self):
        quote = {
            "results": [{
                "bid_price": "60000.00",
                "ask_price": "60010.00",
                "mark_price": "60005.00"
            }]
        }
        bid, ask, mark, spread = extract_quote_details(quote)
        self.assertEqual(bid, Decimal("60000.00"))
        self.assertEqual(ask, Decimal("60010.00"))
        self.assertEqual(mark, Decimal("60005.00"))
        self.assertEqual(spread, Decimal("10.00"))

    def test_extract_quote_details_live_keys(self):
        quote = {
            "results": [{
                "ask_inclusive_of_buy_spread": "60010.00",
                "bid_inclusive_of_sell_spread": "60000.00",
                "buy_spread": "0.1",
                "price": "60005.00",
                "sell_spread": "0.1",
                "symbol": "BTC-USD",
                "timestamp": "2026-06-21T00:00:00Z"
            }]
        }
        bid, ask, mark, spread = extract_quote_details(quote)
        self.assertEqual(bid, Decimal("60000.00"))
        self.assertEqual(ask, Decimal("60010.00"))
        self.assertEqual(mark, Decimal("60005.00"))
        self.assertEqual(spread, Decimal("10.00"))
        quote = {
            "results": [{
                "bid_price": "60000.00",
                "mark_price": "60005.00"
            }]
        }
        bid, ask, mark, spread = extract_quote_details(quote)
        self.assertEqual(bid, Decimal("60000.00"))
        self.assertIsNone(ask)
        self.assertEqual(mark, Decimal("60005.00"))
        self.assertIsNone(spread)

    @patch("sys.argv", ["bot.py", "--recent", "5"])
    def test_parse_args_recent(self):
        args = parse_args()
        self.assertEqual(args.recent, 5)

    @patch("sys.argv", ["bot.py", "--recent", "0"])
    def test_parse_args_rejects_zero(self):
        with self.assertRaises(SystemExit):
            parse_args()

    @patch("sys.argv", ["bot.py", "--recent", "-1"])
    def test_parse_args_rejects_negative(self):
        with self.assertRaises(SystemExit):
            parse_args()

    @patch("sys.argv", ["bot.py", "--recent", "2"])
    @patch("bot.RobinhoodCryptoClient")
    @patch("bot.database.get_recent_quotes")
    def test_main_recent_offline_path(self, mock_get_recent, mock_client_class):
        # Ensure we don't accidentally do network calls
        mock_get_recent.return_value = []
        
        # main() returns 0 when exiting the recent path
        import bot
        result = bot.main()
        
        self.assertEqual(result, 0)
        # Verify RobinhoodCryptoClient was never constructed
        mock_client_class.assert_not_called()
        mock_get_recent.assert_called_once()

if __name__ == "__main__":
    unittest.main()
