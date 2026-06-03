import unittest


from scoring import estimate_range_probability, score_contract_signals, score_market


class ScoringTests(unittest.TestCase):
    def test_score_market_flags_clear_buy_watch(self):
        weather = {
            "current_temp_f": 72.0,
            "high_so_far_f": 73.0,
            "forecast_high_f": 74.0,
            "threshold_f": 76.0,
            "humidity_trend": "steady",
            "pressure_trend": "rising",
            "wind_shift": False,
            "cloud_cover_change": 5,
            "coastal_risk": False,
            "model_disagreement_f": 1.0,
        }
        market = {
            "implied_probability": 0.35,
            "bid": 32,
            "ask": 38,
            "volume": 1800,
            "recent_move_cents": 2,
        }

        scored = score_market("San Francisco", weather, market)

        self.assertEqual(scored["final_label"], "BUY WATCH")
        self.assertGreaterEqual(scored["estimated_edge_score"], 60)
        self.assertGreaterEqual(scored["weather_confidence_score"], 70)

    def test_score_market_avoids_fragile_rebound_and_thin_liquidity(self):
        weather = {
            "current_temp_f": 75.0,
            "high_so_far_f": 75.0,
            "forecast_high_f": 78.0,
            "threshold_f": 76.0,
            "humidity_trend": "falling",
            "pressure_trend": "falling",
            "wind_shift": True,
            "cloud_cover_change": -35,
            "coastal_risk": True,
            "model_disagreement_f": 5.0,
        }
        market = {
            "implied_probability": 0.82,
            "bid": 60,
            "ask": 92,
            "volume": 24,
            "recent_move_cents": 18,
        }

        scored = score_market("San Francisco", weather, market)

        self.assertEqual(scored["final_label"], "AVOID")
        self.assertGreaterEqual(scored["rebound_risk_score"], 70)
        self.assertGreaterEqual(scored["liquidity_risk_score"], 70)

    def test_score_market_waits_when_market_data_is_missing(self):
        weather = {
            "current_temp_f": 64.0,
            "high_so_far_f": 67.0,
            "forecast_high_f": 70.0,
            "threshold_f": 76.0,
            "humidity_trend": "steady",
            "pressure_trend": "steady",
            "wind_shift": False,
            "cloud_cover_change": 0,
            "coastal_risk": False,
            "model_disagreement_f": 1.0,
        }
        market = {"warnings": ["Kalshi scrape failed"]}

        scored = score_market("San Francisco", weather, market)

        self.assertEqual(scored["final_label"], "WAIT")
        self.assertIn("Missing Kalshi data; do not treat as a trading signal.", scored["warnings"])

    def test_score_market_uses_cli_high_for_range_probability(self):
        weather = {
            "current_temp_f": 64.0,
            "high_so_far_f": 67.0,
            "forecast_high_f": 72.0,
            "cli_high_f": 67.0,
            "threshold_f": 67.0,
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
            "range_low_f": 66.0,
            "range_high_f": 67.0,
        }

        scored = score_market("San Francisco", weather, market)

        self.assertGreaterEqual(scored["estimated_probability"], 60)
        self.assertGreater(scored["estimated_edge_score"], 0)
        self.assertLessEqual(scored["rebound_risk_score"], 5)
        self.assertGreaterEqual(scored["weather_confidence_score"], 90)

    def test_score_market_does_not_treat_inconsistent_cli_as_final(self):
        weather = {
            "current_temp_f": 75.0,
            "high_so_far_f": 75.0,
            "forecast_high_f": 80.0,
            "cli_high_f": 69.0,
            "threshold_f": 69.0,
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
            "range_low_f": 68.0,
            "range_high_f": 69.0,
        }

        scored = score_market("Los Angeles", weather, market)

        self.assertLess(scored["estimated_probability"], 50)
        self.assertLess(scored["weather_confidence_score"], 90)

    def test_range_probability_respects_already_hit_integer_bucket(self):
        weather = {
            "current_temp_f": 73.4,
            "high_so_far_f": 74.0,
            "forecast_high_f": 72.0,
            "threshold_f": 77.0,
            "humidity_trend": "steady",
            "pressure_trend": "steady",
            "wind_shift": False,
            "cloud_cover_change": 0,
            "coastal_risk": False,
            "model_disagreement_f": 1.0,
            "settlement_source_status": "cli_wrong_date",
        }
        market = {"range_low_f": 74.0, "range_high_f": 75.0}

        self.assertGreaterEqual(estimate_range_probability(weather, market), 60)

    def test_chicago_hit_bucket_favors_yes_over_no_and_marks_states(self):
        weather = {
            "current_temp_f": 73.4,
            "raw_high_so_far_f": 73.9,
            "high_so_far_f": 74.0,
            "forecast_high_f": 72.0,
            "threshold_f": 77.0,
            "humidity_trend": "steady",
            "pressure_trend": "steady",
            "wind_shift": False,
            "cloud_cover_change": 0,
            "coastal_risk": False,
            "model_disagreement_f": 1.0,
            "settlement_source_status": "cli_wrong_date",
            "active_heating_window": True,
            "warnings": [],
        }
        market = {
            "market_title": "Highest temperature in Chicago today?",
            "url": "https://kalshi.com/example",
            "contracts": [
                {
                    "label": "74° to 75°",
                    "low_f": 74.0,
                    "high_f": 75.0,
                    "yes_price": 96.0,
                    "no_price": 6.0,
                }
            ],
            "warnings": [],
        }

        signals = score_contract_signals("Chicago", weather, market)

        yes_signal = next(signal for signal in signals if signal["side"] == "YES")
        no_signal = next(signal for signal in signals if signal["side"] == "NO")
        self.assertGreater(yes_signal["estimated_probability"], no_signal["estimated_probability"])
        self.assertNotIn(no_signal["signal_label"], {"LEAN", "WATCH"})
        self.assertEqual(yes_signal["bucket_state"], "LOCKED_BY_OBSERVED_HIGH")
        self.assertEqual(no_signal["source_safety_state"], "LIVE_OBS_PRELIMINARY")
        self.assertTrue(no_signal["blocked_from_near_misses"])

    def test_observed_high_above_bucket_makes_yes_impossible(self):
        weather = {
            "current_temp_f": 76.0,
            "high_so_far_f": 76.0,
            "forecast_high_f": 72.0,
            "threshold_f": 77.0,
            "humidity_trend": "steady",
            "pressure_trend": "steady",
            "wind_shift": False,
            "cloud_cover_change": 0,
            "coastal_risk": False,
            "model_disagreement_f": 1.0,
            "settlement_source_status": "cli_wrong_date",
            "active_heating_window": True,
        }
        market = {"range_low_f": 74.0, "range_high_f": 75.0}

        self.assertEqual(estimate_range_probability(weather, market), 0)

    def test_forecast_only_no_signal_is_blocked_during_active_heating_window(self):
        weather = {
            "current_temp_f": None,
            "high_so_far_f": None,
            "forecast_high_f": 72.0,
            "threshold_f": 77.0,
            "humidity_trend": "steady",
            "pressure_trend": "steady",
            "wind_shift": False,
            "cloud_cover_change": 0,
            "coastal_risk": False,
            "model_disagreement_f": 1.0,
            "settlement_source_status": "cli_unavailable",
            "active_heating_window": True,
            "warnings": [],
        }
        market = {
            "contracts": [
                {
                    "label": "74° to 75°",
                    "low_f": 74.0,
                    "high_f": 75.0,
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

    def test_future_market_does_not_use_current_temp_as_today_observation(self):
        weather = {
            "current_temp_f": 100.0,
            "high_so_far_f": None,
            "forecast_high_f": 71.0,
            "threshold_f": 77.0,
            "humidity_trend": "steady",
            "pressure_trend": "steady",
            "wind_shift": False,
            "cloud_cover_change": 0,
            "coastal_risk": False,
            "model_disagreement_f": 1.0,
            "settlement_source_status": "cli_unavailable",
            "market_day_state": "future",
            "active_heating_window": True,
            "warnings": [],
        }
        market = {
            "contracts": [
                {
                    "label": "70° to 71°",
                    "low_f": 70.0,
                    "high_f": 71.0,
                    "yes_price": 38.0,
                    "no_price": 65.0,
                }
            ],
            "warnings": [],
        }

        signals = score_contract_signals("Seattle", weather, market)
        yes_signal = next(signal for signal in signals if signal["side"] == "YES")

        self.assertEqual(yes_signal["source_safety_state"], "FUTURE_FORECAST")
        self.assertGreater(yes_signal["estimated_probability"], 20)


if __name__ == "__main__":
    unittest.main()
