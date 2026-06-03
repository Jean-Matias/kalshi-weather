import unittest

from kalshi_browser import _parse_visible_market_text


class KalshiBrowserTests(unittest.TestCase):
    def test_parse_bucket_contracts_and_select_highest_yes_price(self):
        text = """
Lowest temperature in San Francisco today?
76%
61° or below
Yes 1¢
No
62° to 63°
Yes 6¢
No 95¢
64° to 65°
Yes 33¢
No 68¢
66° to 67°
Yes 47¢
No 55¢
68° to 69°
Yes 14¢
No 87¢
70° or above
Yes 2¢
No
Market Rules
If the minimum temperature recorded at San Francisco for May 24, 2026, is between 66-67° fahrenheit according to the National Weather Service's Climatological Report (Daily), then the market resolves to Yes.
"""
        parsed = _parse_visible_market_text(text, {"city": "San Francisco"})

        self.assertEqual(len(parsed["contracts"]), 6)
        self.assertEqual(parsed["contract_title"], "66° to 67°")
        self.assertEqual(parsed["kalshi_price"], 47)
        self.assertEqual(parsed["implied_probability"], 0.47)
        self.assertEqual(parsed["range_low_f"], 66)
        self.assertEqual(parsed["range_high_f"], 67)


if __name__ == "__main__":
    unittest.main()
