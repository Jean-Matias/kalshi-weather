import unittest

from scoring import bucket_state, estimate_range_probability, score_contract_signals, score_market


class ScoringTests(unittest.TestCase):
    def test_score_market_uses_cli_low_for_range_probability(self):
        weather = {
            "current_temp_f": 61.0,
            "low_so_far_f": 53.0,
            "forecast_low_f": 52.0,
            "cli_low_f": 53.0,
            "threshold_f": 53.0,
            "humidity_trend": "steady",
            "pressure_trend": "steady",
            "wind_shift": False,
            "cloud_cover_change": 0,
            "coastal_risk": False,
            "model_disagreement_f": 1.0,
            "settlement_source_status": "cli_available",
        }
        market = {
            "implied_probability": 0.46,
            "bid": 45,
            "ask": 46,
            "volume": 1000,
            "range_low_f": 52.0,
            "range_high_f": 53.0,
        }

        scored = score_market("San Francisco", weather, market)

        self.assertGreaterEqual(scored["estimated_probability"], 60)
        self.assertGreater(scored["estimated_edge_score"], 0)
        self.assertLessEqual(scored["cooling_risk_score"], 5)
        self.assertGreaterEqual(scored["weather_confidence_score"], 90)

    def test_score_market_does_not_treat_inconsistent_cli_as_final(self):
        weather = {
            "current_temp_f": 50.0,
            "low_so_far_f": 50.0,
            "forecast_low_f": 49.0,
            "cli_low_f": 58.0,
            "threshold_f": 58.0,
            "humidity_trend": "steady",
            "pressure_trend": "steady",
            "wind_shift": False,
            "cloud_cover_change": 0,
            "coastal_risk": False,
            "model_disagreement_f": 1.0,
            "settlement_source_status": "cli_inconsistent",
        }
        market = {
            "implied_probability": 0.46,
            "bid": 45,
            "ask": 46,
            "volume": 1000,
            "range_low_f": 57.0,
            "range_high_f": 58.0,
        }

        scored = score_market("Los Angeles", weather, market)

        self.assertLess(scored["estimated_probability"], 50)
        self.assertLess(scored["weather_confidence_score"], 90)

    def test_observed_low_inside_bounded_bucket_favors_yes_but_is_preliminary(self):
        weather = {
            "current_temp_f": 57.0,
            "raw_low_so_far_f": 54.4,
            "low_so_far_f": 54.0,
            "forecast_low_f": 56.0,
            "threshold_f": 54.0,
            "humidity_trend": "steady",
            "pressure_trend": "steady",
            "wind_shift": False,
            "cloud_cover_change": 0,
            "coastal_risk": False,
            "model_disagreement_f": 1.0,
            "settlement_source_status": "cli_wrong_date",
            "active_low_window": True,
            "warnings": [],
        }
        market = {
            "market_title": "Lowest temperature in Chicago today?",
            "url": "https://kalshi.com/example",
            "contracts": [
                {
                    "label": "54° to 55°",
                    "low_f": 54.0,
                    "high_f": 55.0,
                    "yes_price": 70.0,
                    "no_price": 32.0,
                }
            ],
            "warnings": [],
        }

        signals = score_contract_signals("Chicago", weather, market)

        yes_signal = next(signal for signal in signals if signal["side"] == "YES")
        no_signal = next(signal for signal in signals if signal["side"] == "NO")
        self.assertGreater(yes_signal["estimated_probability"], no_signal["estimated_probability"])
        self.assertNotIn(no_signal["signal_label"], {"LEAN", "WATCH"})
        self.assertEqual(yes_signal["bucket_state"], "PRELIMINARY_OBSERVED_LOW_IN_BUCKET")
        self.assertEqual(no_signal["source_safety_state"], "LIVE_OBS_PRELIMINARY")
        self.assertTrue(no_signal["blocked_from_near_misses"])

    def test_observed_low_below_bounded_bucket_makes_yes_impossible(self):
        weather = {
            "current_temp_f": 53.0,
            "low_so_far_f": 53.0,
            "forecast_low_f": 56.0,
            "threshold_f": 54.0,
            "humidity_trend": "steady",
            "pressure_trend": "steady",
            "wind_shift": False,
            "cloud_cover_change": 0,
            "coastal_risk": False,
            "model_disagreement_f": 1.0,
            "settlement_source_status": "cli_wrong_date",
            "active_low_window": True,
        }
        market = {"range_low_f": 54.0, "range_high_f": 55.0}

        self.assertEqual(bucket_state(weather, market), "CROSSED_BELOW_BUCKET")
        self.assertEqual(estimate_range_probability(weather, market), 0)

    def test_open_ended_bottom_bucket_locks_yes_when_touched(self):
        weather = {
            "current_temp_f": 53.0,
            "low_so_far_f": 53.0,
            "forecast_low_f": 56.0,
            "settlement_source_status": "cli_wrong_date",
        }
        market = {"range_low_f": None, "range_high_f": 54.0}

        self.assertEqual(bucket_state(weather, market), "LOCKED_BY_OBSERVED_LOW")
        self.assertGreaterEqual(estimate_range_probability(weather, market), 90)

    def test_open_ended_top_bucket_crossed_below_makes_yes_impossible(self):
        weather = {
            "current_temp_f": 53.0,
            "low_so_far_f": 53.0,
            "forecast_low_f": 56.0,
            "settlement_source_status": "cli_wrong_date",
        }
        market = {"range_low_f": 54.0, "range_high_f": None}

        self.assertEqual(bucket_state(weather, market), "CROSSED_BELOW_BUCKET")
        self.assertEqual(estimate_range_probability(weather, market), 0)

    def test_open_ended_top_bucket_touched_remains_preliminary_and_blocks_no(self):
        weather = {
            "current_temp_f": 57.0,
            "low_so_far_f": 57.0,
            "forecast_low_f": 58.0,
            "humidity_trend": "steady",
            "pressure_trend": "steady",
            "wind_shift": False,
            "cloud_cover_change": 0,
            "coastal_risk": False,
            "model_disagreement_f": 1.0,
            "settlement_source_status": "cli_wrong_date",
            "active_low_window": False,
            "warnings": [],
        }
        market = {
            "contracts": [
                {
                    "label": "54° or above",
                    "low_f": 54.0,
                    "high_f": None,
                    "yes_price": 80.0,
                    "no_price": 22.0,
                }
            ],
            "warnings": [],
        }

        signals = score_contract_signals("Chicago", weather, market)
        no_signal = next(signal for signal in signals if signal["side"] == "NO")

        self.assertEqual(bucket_state(weather, {"range_low_f": 54.0, "range_high_f": None}), "PRELIMINARY_OBSERVED_LOW_IN_BUCKET")
        self.assertNotIn(no_signal["signal_label"], {"LEAN", "WATCH"})
        self.assertTrue(no_signal["blocked_from_near_misses"])

    def test_forecast_only_no_signal_is_blocked_during_active_low_window(self):
        weather = {
            "current_temp_f": None,
            "low_so_far_f": None,
            "forecast_low_f": 56.0,
            "threshold_f": 54.0,
            "humidity_trend": "steady",
            "pressure_trend": "steady",
            "wind_shift": False,
            "cloud_cover_change": 0,
            "coastal_risk": False,
            "model_disagreement_f": 1.0,
            "settlement_source_status": "cli_unavailable",
            "active_low_window": True,
            "warnings": [],
        }
        market = {
            "contracts": [
                {
                    "label": "54° to 55°",
                    "low_f": 54.0,
                    "high_f": 55.0,
                    "yes_price": 20.0,
                    "no_price": 10.0,
                }
            ],
            "warnings": [],
        }

        signals = score_contract_signals("Chicago", weather, market)
        no_signal = next(signal for signal in signals if signal["side"] == "NO")

        self.assertNotIn(no_signal["signal_label"], {"LEAN", "WATCH"})
        self.assertEqual(no_signal["source_safety_state"], "FORECAST_ONLY")
        self.assertTrue(no_signal["blocked_from_near_misses"])


if __name__ == "__main__":
    unittest.main()
