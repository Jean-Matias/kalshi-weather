import unittest

from decision_layer import enrich_decision_layer


def base_row(**overrides):
    row = {
        "city": "San Antonio",
        "current_temp_f": 90.0,
        "raw_high_so_far_f": 90.0,
        "high_so_far_f": 90.0,
        "forecast_high_f": 92.0,
        "forecast_high_time": "2026-06-03T16:00:00-05:00",
        "market_local_time": "2026-06-03T14:00:00-05:00",
        "range_low_f": 91.0,
        "range_high_f": 92.0,
        "api_crowd_favorite": "91F to 92F",
        "api_crowd_price": 65,
        "kalshi_price": 65,
        "market_day_state": "today",
        "active_heating_window": True,
    }
    row.update(overrides)
    return row


class DecisionLayerTests(unittest.TestCase):
    def test_critical_window_uses_eastern_hour_before_peak(self):
        row = enrich_decision_layer(
            base_row(
                forecast_high_time="2026-06-03T16:00:00-05:00",
                market_local_time="2026-06-03T14:00:00-05:00",
            )
        )

        self.assertEqual(row["critical_window_et"], "4:00-5:00 PM ET")
        self.assertEqual(row["time_to_peak_minutes"], 120)

    def test_range_bucket_uses_raw_rounding_to_enter_bucket(self):
        row = enrich_decision_layer(
            base_row(
                raw_high_so_far_f=90.0,
                forecast_high_f=92.0,
                range_low_f=93.0,
                range_high_f=94.0,
                api_crowd_favorite="93F to 94F",
                api_crowd_price=70,
            )
        )

        self.assertEqual(row["degrees_needed_to_reach_bucket"], 2.5)
        self.assertGreater(row["required_rate_f_per_hour"], 1.0)

    def test_reached_when_raw_high_has_entered_bucket_by_rounding(self):
        row = enrich_decision_layer(
            base_row(
                raw_high_so_far_f=92.5,
                high_so_far_f=93.0,
                range_low_f=93.0,
                range_high_f=94.0,
                forecast_high_f=93.0,
            )
        )

        self.assertEqual(row["reachability_label"], "REACHED")

    def test_crossed_above_when_raw_high_exceeds_upper_rounding_boundary(self):
        row = enrich_decision_layer(
            base_row(
                raw_high_so_far_f=94.5,
                high_so_far_f=95.0,
                range_low_f=93.0,
                range_high_f=94.0,
                forecast_high_f=94.0,
            )
        )

        self.assertEqual(row["reachability_label"], "CROSSED_ABOVE")

    def test_false_hotter_pump_when_market_hotter_without_weather_confirmation(self):
        row = enrich_decision_layer(
            base_row(
                raw_high_so_far_f=90.0,
                current_temp_f=90.0,
                forecast_high_f=92.0,
                range_low_f=93.0,
                range_high_f=94.0,
                api_crowd_favorite="93F to 94F",
                api_crowd_price=70,
                heating_rate_f_per_hour=0.2,
            )
        )

        self.assertEqual(row["market_weather_alignment"], "MARKET_HOTTER")
        self.assertTrue(row["false_pump_warning"])
        self.assertEqual(row["reachability_label"], "UNLIKELY")

    def test_no_false_pump_when_hotter_market_is_reachable_and_forecast_confirms(self):
        row = enrich_decision_layer(
            base_row(
                raw_high_so_far_f=92.0,
                current_temp_f=92.0,
                forecast_high_f=94.0,
                range_low_f=93.0,
                range_high_f=94.0,
                api_crowd_favorite="93F to 94F",
                api_crowd_price=70,
                heating_rate_f_per_hour=2.0,
            )
        )

        self.assertEqual(row["market_weather_alignment"], "ALIGNED")
        self.assertFalse(row["false_pump_warning"])
        self.assertIn(row["reachability_label"], {"REACHABLE", "STRETCH"})

    def test_heating_status_scores_clear_rising_pre_peak_weather_as_heating(self):
        row = enrich_decision_layer(
            base_row(
                city="Las Vegas",
                current_temp_f=103.0,
                raw_high_so_far_f=103.0,
                high_so_far_f=103.0,
                forecast_high_f=106.0,
                forecast_high_time="2026-06-05T17:00:00-07:00",
                market_local_time="2026-06-05T15:00:00-07:00",
                heating_rate_f_per_hour=2.1,
                cloud_text="Clear",
                humidity=6,
                humidity_trend=-2,
                wind_speed_mph=14,
                wind_direction_deg=220,
                forecast_hourly_temps_f=[103, 104, 105, 106],
            )
        )

        self.assertGreaterEqual(row["heating_status_score"], 80)
        self.assertEqual(row["heating_status_label"], "HEATING")
        self.assertIn("rising", row["heating_status_reasons"][0].lower())

    def test_heating_status_scores_post_peak_falling_weather_as_likely_done(self):
        row = enrich_decision_layer(
            base_row(
                current_temp_f=89.0,
                raw_high_so_far_f=91.4,
                high_so_far_f=91.0,
                forecast_high_f=91.0,
                forecast_high_time="2026-06-05T15:00:00-05:00",
                market_local_time="2026-06-05T16:30:00-05:00",
                heating_rate_f_per_hour=-1.2,
                cloud_text="Mostly Cloudy",
                humidity=58,
                humidity_trend=8,
                wind_speed_mph=5,
                forecast_hourly_temps_f=[91, 90, 89, 88],
            )
        )

        self.assertLessEqual(row["heating_status_score"], 25)
        self.assertEqual(row["heating_status_label"], "LIKELY DONE")
        self.assertIn("past peak", " ".join(row["heating_status_reasons"]).lower())


if __name__ == "__main__":
    unittest.main()
