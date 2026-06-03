import unittest

from kalshi_api import (
    merge_api_observation,
    parse_event_response,
    should_fetch_api_observation,
)


class KalshiApiTests(unittest.TestCase):
    def test_parse_event_response_ranks_low_market_crowd_favorite(self):
        payload = {
            "event": {
                "event_ticker": "KXLOWTPHX-26MAY28",
                "title": "Lowest temperature in Phoenix on May 28, 2026?",
            },
            "markets": [
                {
                    "ticker": "KXLOWTPHX-26MAY28-T71",
                    "title": "Will the minimum temperature be  <71° on May 28, 2026?",
                    "yes_ask_dollars": "0.0900",
                    "no_ask_dollars": "0.9200",
                    "floor_strike": None,
                    "cap_strike": 71,
                    "strike_type": "less",
                },
                {
                    "ticker": "KXLOWTPHX-26MAY28-B73.5",
                    "title": "Will the minimum temperature be  73-74° on May 28, 2026?",
                    "yes_ask_dollars": "0.5600",
                    "no_ask_dollars": "0.4500",
                    "floor_strike": 73,
                    "cap_strike": 74,
                    "strike_type": "between",
                },
            ],
        }

        parsed = parse_event_response(payload, {"city": "Phoenix"})

        self.assertEqual(parsed["market_data_source"], "kalshi_api")
        self.assertEqual(parsed["contract_title"], "73F to 74F")
        self.assertEqual(parsed["api_crowd_favorite"], "73F to 74F")
        self.assertEqual(parsed["api_crowd_price"], 56)
        self.assertEqual(parsed["contracts"][0]["label"], "70F or below")

    def test_should_fetch_api_observation_only_for_reliable_low_weather_rows(self):
        reliable_weather = {
            "weather_confidence_score": 78,
            "forecast_low_f": 72.0,
            "analysis_source_status": "same_day_station_observations",
        }
        unreliable_weather = {
            "weather_confidence_score": 50,
            "forecast_low_f": 72.0,
            "analysis_source_status": "same_day_station_observations",
        }

        self.assertTrue(should_fetch_api_observation(reliable_weather))
        self.assertFalse(should_fetch_api_observation(unreliable_weather))

    def test_merge_api_observation_preserves_browser_rule_text(self):
        browser_market = {
            "city": "Phoenix",
            "official_source_text": "If the minimum temperature recorded at Phoenix...",
            "raw_text_excerpt": "Market Rules...",
            "warnings": ["browser warning"],
        }
        api_market = {
            "market_title": "Lowest temperature in Phoenix on May 28, 2026?",
            "contract_title": "73F to 74F",
            "contracts": [{"label": "73F to 74F"}],
            "warnings": ["api warning"],
        }

        merged = merge_api_observation(browser_market, api_market)

        self.assertEqual(merged["market_title"], api_market["market_title"])
        self.assertEqual(merged["official_source_text"], browser_market["official_source_text"])
        self.assertEqual(merged["warnings"], ["browser warning", "api warning"])


if __name__ == "__main__":
    unittest.main()
