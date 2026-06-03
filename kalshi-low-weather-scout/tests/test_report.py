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
                "low_so_far_f": 68.0,
                "forecast_low_f": 70.0,
                "kalshi_price": None,
                "estimated_probability": None,
                "weather_confidence_score": 55,
                "volatility_risk_score": 40,
                "cooling_risk_score": 35,
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
                "bucket_state": "LOCKED_BY_OBSERVED_LOW",
                "blocked_from_near_misses": True,
                "reasoning": ["NO is unsafe after the bucket was touched."],
                "warnings": ["Blocked because official-station low has touched this bucket."],
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
                "cooling_risk_score": 70,
                "active_low_window": True,
                "source_safety_state": "CLI_STALE",
                "settlement_source_status": "cli_wrong_date",
                "forecast_source_status": "same_day_hourly_forecast",
            },
            {
                "city": "Stable City",
                "weather_confidence_score": 95,
                "volatility_risk_score": 10,
                "cooling_risk_score": 5,
                "active_low_window": False,
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
        self.assertIn("YES 70F to 71F", markdown)

    def test_city_reliability_report_labels_live_nws_tracking(self):
        rows = [
            {
                "city": "Dallas",
                "weather_confidence_score": 80,
                "volatility_risk_score": 34,
                "cooling_risk_score": 35,
                "active_low_window": True,
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

    def test_dashboard_report_ranks_city_reliability_and_hides_volatile_rows(self):
        rows = [
            {
                "city": "Seattle",
                "final_label": "WAIT",
                "weather_confidence_score": 65,
                "volatility_risk_score": 35,
                "cooling_risk_score": 30,
                "source_safety_state": "LIVE_OBS_PRELIMINARY",
                "forecast_source_status": "same_day_hourly_forecast",
                "active_low_window": True,
                "range_low_f": 62.0,
                "range_high_f": 63.0,
                "kalshi_price": 37.0,
                "estimated_probability": 7,
                "low_so_far_f": 61.0,
                "forecast_low_f": 60.0,
                "forecast_low_time": "2026-05-25T05:00:00-07:00",
                "latest_observation_time": "2026-05-25T16:00:00+00:00",
                "market_data_source": "kalshi_api",
                "api_crowd_favorite": "62F to 63F",
                "api_crowd_price": 64.0,
                "kalshi_url": "https://kalshi.example/seattle",
                "cli_source_url": "https://nws.example/cli",
                "forecast_source_url": "https://nws.example/hourly",
                "forecast_graph_url": "https://nws.example/graph",
                "official_location": "Seattle-Tacoma, WA",
                "station_id": "KSEA",
                "official_climate_product": "CLISEA",
            },
            {
                "city": "Volatile City",
                "final_label": "AVOID",
                "weather_confidence_score": 48,
                "volatility_risk_score": 82,
                "cooling_risk_score": 75,
                "source_safety_state": "LIVE_OBS_PRELIMINARY",
                "forecast_source_status": "forecast_unavailable",
                "active_low_window": True,
                "range_low_f": 70.0,
                "range_high_f": 71.0,
                "kalshi_price": 50.0,
                "estimated_probability": 50,
                "low_so_far_f": 82.0,
                "forecast_low_f": None,
                "latest_observation_time": "2026-05-25T16:00:00+00:00",
            }
        ]
        signals = [
            {
                "city": "Austin",
                "side": "YES",
                "contract_title": "66F to 67F",
                "side_price": 40.0,
                "estimated_probability": 82,
                "weather_confidence_score": 95,
                "volatility_risk_score": 10,
                "cooling_risk_score": 5,
                "source_safety_state": "FINAL_CLI_AVAILABLE",
                "bucket_state": "FINAL_YES",
                "blocked_from_near_misses": False,
                "low_so_far_f": 66.0,
                "forecast_low_f": 66.0,
                "latest_observation_time": "2026-05-25T16:00:00+00:00",
            },
            {
                "city": "Seattle",
                "side": "NO",
                "contract_title": "62F to 63F",
                "side_price": 64.0,
                "estimated_probability": 93,
                "weather_confidence_score": 65,
                "volatility_risk_score": 35,
                "cooling_risk_score": 30,
                "low_so_far_f": 61.0,
                "forecast_low_f": 60.0,
                "latest_observation_time": "2026-05-25T16:00:00+00:00",
                "active_low_window": True,
                "source_safety_state": "LIVE_OBS_PRELIMINARY",
                "bucket_state": "PRELIMINARY_OBSERVED_LOW_IN_BUCKET",
                "blocked_from_near_misses": True,
                "warnings": ["Low-temperature window is active."],
            },
            {
                "city": "Seattle",
                "side": "YES",
                "contract_title": "62F to 63F",
                "side_price": 37.0,
                "estimated_probability": 7,
                "weather_confidence_score": 65,
                "volatility_risk_score": 35,
                "cooling_risk_score": 30,
            },
        ]

        html = build_dashboard_report(rows, signals)

        self.assertIn("Most Reliable Cities", html)
        self.assertIn("Show Avoided / Volatile Cities", html)
        self.assertIn("Sources used", html)
        self.assertIn("Seattle-Tacoma, WA", html)
        self.assertIn("CLISEA", html)
        self.assertIn("Best Side", html)
        self.assertIn("Crowd Favorite", html)
        self.assertIn("API Market Data", html)
        self.assertIn("Low Time", html)
        self.assertIn("05:00", html)
        self.assertIn("NO 93%", html)
        self.assertIn("Hidden: low reliability score", html)
        self.assertLess(html.index("Seattle"), html.index("Volatile City"))
        self.assertIn("62F to 63F", html)
        self.assertIn("All City Rank", html)

    def test_dashboard_report_has_single_target_date_without_tomorrow_tab(self):
        rows = [
            {
                "city": "Austin",
                "market_date": "2026-05-28",
                "final_label": "WAIT",
                "weather_confidence_score": 78,
                "volatility_risk_score": 25,
                "cooling_risk_score": 20,
                "source_safety_state": "FUTURE_FORECAST",
                "market_day_state": "future",
                "forecast_source_status": "future_hourly_forecast",
                "range_low_f": 68.0,
                "range_high_f": 69.0,
                "kalshi_price": 41.0,
                "estimated_probability": 74,
                "low_so_far_f": None,
                "forecast_low_f": 69.0,
                "forecast_low_time": "2026-05-28T07:00:00-05:00",
                "latest_observation_time": None,
            }
        ]
        signals = [
            {
                "city": "Austin",
                "side": "YES",
                "contract_title": "68F to 69F",
                "side_price": 41.0,
                "estimated_probability": 74,
                "weather_confidence_score": 78,
                "volatility_risk_score": 25,
                "cooling_risk_score": 20,
                "source_safety_state": "FUTURE_FORECAST",
                "market_day_state": "future",
                "forecast_low_f": 69.0,
            }
        ]

        html = build_dashboard_report(rows, signals)

        self.assertIn("Target Kalshi market date: 2026-05-28", html)
        self.assertIn("Forecast Only", html)
        self.assertNotIn('id="tab-tomorrow"', html)
        self.assertNotIn("Most Reliable Forecast Cities", html)
        self.assertNotIn("All Tomorrow City Rank", html)
        self.assertIn("Most Reliable Cities", html)
        self.assertIn("All City Rank", html)
        self.assertIn("TOMORROW_FORECAST", html)
        self.assertIn("forecast-only rows are watchlist data", html)
        self.assertIn("Show Avoided / Volatile Cities (1)", html)


if __name__ == "__main__":
    unittest.main()
