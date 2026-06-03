import unittest

from scoring import score_contract_signals


class SignalGenerationTests(unittest.TestCase):
    def test_scores_yes_and_no_sides_for_all_buckets(self):
        weather = {
            "city": "Los Angeles",
            "cli_high_f": 69.0,
            "forecast_high_f": 69.0,
            "high_so_far_f": 69.0,
            "current_temp_f": 61.0,
            "settlement_source_status": "cli_available",
            "official_climate_product": "CLILAX",
            "official_location": "Los Angeles Airport, CA",
            "warnings": [],
        }
        market = {
            "market_title": "Highest temperature in LA today?",
            "url": "https://kalshi.com/example",
            "contracts": [
                {"label": "66° to 67°", "low_f": 66.0, "high_f": 67.0, "yes_price": 35.0, "no_price": 66.0},
                {"label": "68° to 69°", "low_f": 68.0, "high_f": 69.0, "yes_price": 55.0, "no_price": 46.0},
            ],
            "warnings": [],
        }

        signals = score_contract_signals("Los Angeles", weather, market)

        yes_signal = next(signal for signal in signals if signal["contract_title"] == "68° to 69°" and signal["side"] == "YES")
        no_signal = next(signal for signal in signals if signal["contract_title"] == "66° to 67°" and signal["side"] == "NO")
        self.assertGreaterEqual(yes_signal["estimated_probability"], 60)
        self.assertGreater(no_signal["estimated_edge_score"], 0)


if __name__ == "__main__":
    unittest.main()
