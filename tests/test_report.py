import unittest


from report import (
    build_city_reliability_report,
    build_dashboard_report,
    build_markdown_report,
    build_signal_report,
)


class ReportTests(unittest.TestCase):
    def test_report_includes_missing_market_warning(self):
        rows = [
            {
                "city": "San Francisco",
                "market_title": None,
                "current_temp_f": 67.2,
                "high_so_far_f": 68.0,
                "forecast_high_f": 70.0,
                "kalshi_price": None,
                "estimated_probability": None,
                "weather_confidence_score": 55,
                "volatility_risk_score": 40,
                "rebound_risk_score": 35,
                "liquidity_risk_score": 85,
                "estimated_edge_score": 0,
                "final_label": "WAIT",
                "reasoning": ["Kalshi market data unavailable"],
                "warnings": ["Missing Kalshi data; do not treat as a trading signal."],
            }
        ]

        markdown = build_markdown_report(rows)

        self.assertIn("San Francisco", markdown)
        self.assertIn("WAIT", markdown)
        self.assertIn("Missing Kalshi data", markdown)

    def test_signal_report_keeps_blocked_skip_out_of_normal_near_misses(self):
        signals = [
            {
                "city": "Chicago",
                "side": "NO",
                "signal_label": "SKIP",
                "contract_title": "74° to 75°",
                "range_low_f": 74.0,
                "range_high_f": 75.0,
                "side_price": 6.0,
                "estimated_probability": 13,
                "estimated_edge_score": 33,
                "official_location": "Chicago Midway, IL",
                "settlement_source_status": "cli_wrong_date",
                "source_safety_state": "CLI_STALE",
                "bucket_state": "LOCKED_BY_OBSERVED_HIGH",
                "blocked_from_near_misses": True,
                "reasoning": ["NO is unsafe after the bucket was touched."],
                "warnings": ["Blocked because official-station high has reached this bucket."],
            },
            {
                "city": "Seattle",
                "side": "YES",
                "signal_label": "SKIP",
                "contract_title": "70° to 71°",
                "range_low_f": 70.0,
                "range_high_f": 71.0,
                "side_price": 40.0,
                "estimated_probability": 42,
                "estimated_edge_score": 12,
                "official_location": "Seattle-Tacoma, WA",
                "settlement_source_status": "cli_wrong_date",
                "reasoning": ["Normal near miss."],
                "warnings": [],
            },
        ]

        markdown = build_signal_report(signals)

        self.assertIn("Top near-misses", markdown)
        self.assertIn("Seattle YES - SKIP", markdown)
        self.assertNotIn("Chicago NO - SKIP", markdown)
        self.assertIn("Blocked/danger signals hidden from near-misses", markdown)

    def test_city_reliability_report_ranks_stable_sources_first(self):
        rows = [
            {
                "city": "Coast City",
                "weather_confidence_score": 58,
                "volatility_risk_score": 80,
                "rebound_risk_score": 70,
                "active_heating_window": True,
                "source_safety_state": "CLI_STALE",
                "settlement_source_status": "cli_wrong_date",
                "forecast_source_status": "same_day_hourly_forecast",
            },
            {
                "city": "Stable City",
                "weather_confidence_score": 95,
                "volatility_risk_score": 10,
                "rebound_risk_score": 5,
                "active_heating_window": False,
                "source_safety_state": "FINAL_CLI_AVAILABLE",
                "settlement_source_status": "cli_available",
                "forecast_source_status": "same_day_hourly_forecast",
                "forecast_generated_at": "2026-05-25T08:00:00-05:00",
            },
        ]
        signals = [
            {
                "city": "Stable City",
                "side": "YES",
                "contract_title": "70F to 71F",
                "signal_label": "SKIP",
                "estimated_edge_score": 8,
                "blocked_from_near_misses": False,
            }
        ]

        markdown = build_city_reliability_report(rows, signals)

        self.assertLess(markdown.index("Stable City"), markdown.index("Coast City"))
        self.assertIn("HIGH_SOURCE_CONFIDENCE", markdown)
        self.assertIn("Hourly forecast generated: 2026-05-25T08:00:00-05:00", markdown)
        self.assertIn("Weather-only rank", markdown)
        self.assertNotIn("Best reviewable side signal", markdown)

    def test_city_reliability_report_labels_live_nws_tracking(self):
        rows = [
            {
                "city": "Dallas",
                "weather_confidence_score": 80,
                "volatility_risk_score": 34,
                "rebound_risk_score": 35,
                "active_heating_window": True,
                "source_safety_state": "LIVE_OBS_PRELIMINARY",
                "settlement_source_status": "cli_wrong_date",
                "analysis_source_status": "same_day_station_observations",
                "forecast_source_status": "same_day_hourly_forecast",
            }
        ]

        markdown = build_city_reliability_report(rows, [])

        self.assertIn("LIVE_NWS_TRACKING", markdown)
        self.assertIn("Analysis data status: same_day_station_observations", markdown)
        self.assertIn("Hourly forecast status: same_day_hourly_forecast", markdown)

    def test_dashboard_report_shows_good_bad_and_city_rows(self):
        rows = [
            {
                "city": "Seattle",
                "final_label": "WAIT",
                "weather_confidence_score": 65,
                "volatility_risk_score": 35,
                "rebound_risk_score": 30,
                "source_safety_state": "LIVE_OBS_PRELIMINARY",
                "forecast_source_status": "same_day_hourly_forecast",
                "active_heating_window": True,
                "range_low_f": 62.0,
                "range_high_f": 63.0,
                "kalshi_price": 37.0,
                "estimated_probability": 7,
                "high_so_far_f": 61.0,
                "forecast_high_f": 60.0,
                "forecast_high_time": "2026-05-25T17:00:00-07:00",
                "latest_observation_time": "2026-05-25T16:00:00+00:00",
                "market_data_source": "kalshi_api",
                "api_crowd_favorite": "62F to 63F",
                "api_crowd_price": 64.0,
            }
        ]
        signals = [
            {
                "city": "Seattle",
                "side": "NO",
                "contract_title": "62F to 63F",
                "side_price": 64.0,
                "estimated_probability": 93,
                "weather_confidence_score": 65,
                "volatility_risk_score": 35,
                "rebound_risk_score": 30,
                "high_so_far_f": 61.0,
                "forecast_high_f": 60.0,
                "latest_observation_time": "2026-05-25T16:00:00+00:00",
                "active_heating_window": True,
                "warnings": ["Heating window is active."],
            },
            {
                "city": "Seattle",
                "side": "YES",
                "contract_title": "62F to 63F",
                "side_price": 37.0,
                "estimated_probability": 7,
                "weather_confidence_score": 65,
                "volatility_risk_score": 35,
                "rebound_risk_score": 30,
            },
        ]

        html = build_dashboard_report(rows, signals)

        self.assertIn("Most Weather-Reliable Cities", html)
        self.assertIn("All City Rank", html)
        self.assertIn("Show Remaining Cities", html)
        self.assertIn("Source Confidence", html)
        self.assertIn("Rebound Risk", html)
        self.assertIn("62F to 63F", html)
        self.assertIn("Market note", html)
        self.assertIn("API Market Data", html)
        self.assertIn("High Time", html)
        self.assertIn("17:00", html)
        self.assertIn("Current High", html)

    def test_dashboard_report_has_tomorrow_forecast_tab(self):
        tomorrow_rows = [
            {
                "city": "Austin",
                "market_date": "2026-05-28",
                "final_label": "WAIT",
                "weather_confidence_score": 78,
                "volatility_risk_score": 25,
                "rebound_risk_score": 20,
                "source_safety_state": "FUTURE_FORECAST",
                "market_day_state": "future",
                "forecast_source_status": "future_hourly_forecast",
                "range_low_f": 88.0,
                "range_high_f": 89.0,
                "kalshi_price": 41.0,
                "estimated_probability": 74,
                "high_so_far_f": None,
                "forecast_high_f": 89.0,
                "latest_observation_time": None,
            }
        ]
        tomorrow_signals = [
            {
                "city": "Austin",
                "side": "YES",
                "contract_title": "88F to 89F",
                "side_price": 41.0,
                "estimated_probability": 74,
                "weather_confidence_score": 78,
                "volatility_risk_score": 25,
                "rebound_risk_score": 20,
                "source_safety_state": "FUTURE_FORECAST",
                "market_day_state": "future",
                "forecast_high_f": 89.0,
            }
        ]

        html = build_dashboard_report([], [], tomorrow_rows, tomorrow_signals)

        self.assertIn('id="tab-tomorrow"', html)
        self.assertIn("Most Weather-Reliable Forecast Cities", html)
        self.assertIn("All Tomorrow City Rank", html)
        self.assertIn("TOMORROW_FORECAST", html)
        self.assertIn("Forecast-only tomorrow rows", html)


if __name__ == "__main__":
    unittest.main()
