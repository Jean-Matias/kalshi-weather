import unittest

from kalshi_api import (
    merge_api_observation,
    parse_event_response,
    should_fetch_api_observation,
)


class KalshiApiTests(unittest.TestCase):
    def test_parse_event_response_ranks_crowd_favorite_from_public_market_data(self):
        payload = {
            "event": {
                "event_ticker": "KXHIGHTPHX-26MAY28",
                "title": "Highest temperature in Phoenix on May 28, 2026?",
            },
            "markets": [
                {
                    "ticker": "KXHIGHTPHX-26MAY28-T91",
                    "title": "Will the maximum temperature be  <91° on May 28, 2026?",
                    "yes_ask_dollars": "0.0100",
                    "no_ask_dollars": "0.9900",
                    "last_price_dollars": "0.0100",
                    "floor_strike": None,
                    "cap_strike": 91,
                    "strike_type": "less",
                },
                {
                    "ticker": "KXHIGHTPHX-26MAY28-B91.5",
                    "title": "Will the maximum temperature be  91-92° on May 28, 2026?",
                    "yes_ask_dollars": "0.3700",
                    "no_ask_dollars": "0.6400",
                    "last_price_dollars": "0.3700",
                    "floor_strike": 91,
                    "cap_strike": 92,
                    "strike_type": "between",
                },
                {
                    "ticker": "KXHIGHTPHX-26MAY28-B93.5",
                    "title": "Will the maximum temperature be  93-94° on May 28, 2026?",
                    "yes_ask_dollars": "0.5800",
                    "no_ask_dollars": "0.4300",
                    "last_price_dollars": "0.5800",
                    "floor_strike": 93,
                    "cap_strike": 94,
                    "strike_type": "between",
                },
            ],
        }

        parsed = parse_event_response(payload, {"city": "Phoenix"})

        self.assertEqual(parsed["market_data_source"], "kalshi_api")
        self.assertEqual(parsed["contract_title"], "93F to 94F")
        self.assertEqual(parsed["kalshi_price"], 58)
        self.assertEqual(parsed["api_crowd_favorite"], "93F to 94F")
        self.assertEqual(parsed["api_crowd_price"], 58)
        self.assertEqual(parsed["contracts"][0]["label"], "90F or below")
        self.assertEqual(parsed["contracts"][1]["label"], "91F to 92F")

    def test_should_fetch_api_observation_only_for_reliable_weather_rows(self):
        reliable_weather = {
            "weather_confidence_score": 78,
            "forecast_high_f": 92.0,
            "analysis_source_status": "same_day_station_observations",
        }
        unreliable_weather = {
            "weather_confidence_score": 50,
            "forecast_high_f": 92.0,
            "analysis_source_status": "same_day_station_observations",
        }

        self.assertTrue(should_fetch_api_observation(reliable_weather))
        self.assertFalse(should_fetch_api_observation(unreliable_weather))

    def test_merge_api_observation_preserves_browser_rule_text(self):
        browser_market = {
            "city": "Phoenix",
            "market_title": "Highest temperature in Phoenix today?",
            "official_source_text": "If the maximum temperature recorded at Phoenix...",
            "raw_text_excerpt": "Market Rules...",
            "warnings": ["browser warning"],
        }
        api_market = {
            "market_title": "Highest temperature in Phoenix on May 28, 2026?",
            "contract_title": "93F to 94F",
            "contracts": [{"label": "93F to 94F"}],
            "warnings": ["api warning"],
        }

        merged = merge_api_observation(browser_market, api_market)

        self.assertEqual(merged["market_title"], api_market["market_title"])
        self.assertEqual(merged["official_source_text"], browser_market["official_source_text"])
        self.assertEqual(merged["raw_text_excerpt"], browser_market["raw_text_excerpt"])
        self.assertEqual(merged["warnings"], ["browser warning", "api warning"])


if __name__ == "__main__":
    unittest.main()
