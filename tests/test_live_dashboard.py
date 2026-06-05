import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

import live_dashboard
from live_dashboard import (
    LiveDashboardCache,
    LiveTempMeterCache,
    build_city_payload,
    current_live_city_configs,
    favorite_buckets,
    live_city_config,
    market_date_label,
    normalize_live_day,
    parse_metar_max_temp_f,
    recent_observation_feed_summary,
    selected_live_city_configs,
)


class LiveDashboardServiceTests(unittest.TestCase):
    def test_selected_live_city_configs_only_returns_three_pattern_cities(self):
        cities = [config["city"] for config in selected_live_city_configs()]

        self.assertEqual(cities, ["Phoenix", "Las Vegas", "San Antonio"])

    def test_selected_live_city_configs_ignores_tomorrow_and_returns_today_cities(self):
        configs = selected_live_city_configs("tomorrow")
        cities = [config["city"] for config in configs]

        self.assertEqual(cities, ["Phoenix", "Las Vegas", "San Antonio"])
        self.assertEqual(len({config["market_date"] for config in configs}), 1)

    def test_current_live_city_configs_recomputes_stale_startup_dates(self):
        configs = current_live_city_configs()
        vegas = next(config for config in configs if config["city"] == "Las Vegas")
        suffix = datetime.fromisoformat(vegas["market_date"]).strftime("%y%b%d").lower()

        self.assertNotEqual(vegas["market_date"], "2026-05-24")
        self.assertIn(suffix, vegas["kalshi_url"])

    def test_live_city_config_matches_allowed_city_case_insensitive(self):
        config = live_city_config("san antonio")

        self.assertIsNotNone(config)
        self.assertEqual(config["city"], "San Antonio")

    def test_market_date_label_collapses_single_date(self):
        self.assertEqual(market_date_label([{"market_date": "2026-06-04"}]), "2026-06-04")

    def test_normalize_live_day_forces_today_only(self):
        self.assertEqual(normalize_live_day("tomorrow"), "today")
        self.assertEqual(normalize_live_day("weird"), "today")

    def test_favorite_buckets_returns_winner_and_second_by_yes_price(self):
        market = {
            "contracts": [
                {"label": "106F to 107F", "yes_price": 40},
                {"label": "107F to 108F", "yes_price": 65},
                {"label": "105F or below", "yes_price": 20},
            ]
        }

        top, second = favorite_buckets(market)

        self.assertEqual(top["label"], "107F to 108F")
        self.assertEqual(second["label"], "106F to 107F")

    def test_build_city_payload_includes_weather_market_and_decision_fields(self):
        config = {"city": "Phoenix"}
        weather = {
            "city": "Phoenix",
            "station_id": "KPHX",
            "station_name": "Phoenix Sky Harbor",
            "official_location": "Phoenix, AZ",
            "official_climate_product": "CLIPHX",
            "market_date": "2026-06-03",
            "settlement_source_status": "cli_wrong_date",
            "analysis_source_status": "same_day_station_observations",
            "forecast_source_status": "same_day_hourly_forecast",
            "forecast_source_url": "forecast-url",
            "forecast_graph_url": "graph-url",
            "forecast_generated_at": "2026-06-03T04:00:00-07:00",
            "forecast_high_time": "2026-06-03T17:00:00-07:00",
            "market_day_state": "today",
            "cli_high_f": None,
            "cli_report_issued": None,
            "cli_source_url": "cli-url",
            "latest_observation_time": "2026-06-03T18:00:00+00:00",
            "observation_time": "2026-06-03T17:55:00+00:00",
            "recent_observation_points": [
                {"time": "2026-06-03T17:50:00+00:00", "temp_f": 99.2},
                {"time": "2026-06-03T18:00:00+00:00", "temp_f": 100.4},
            ],
            "market_local_time": "2026-06-03T12:00:00-07:00",
            "active_heating_window": True,
            "current_temp_f": 100.0,
            "fast_metar_temp_f": 101.0,
            "fast_metar_time": "2026-06-03T18:01:00.000Z",
            "fast_metar_raw": "KPHX 031801Z AUTO 00000KT 10SM CLR 38/02 A2992",
            "fast_feed_source": "AviationWeather METAR",
            "raw_high_so_far_f": 100.4,
            "raw_high_so_far_time": "2026-06-03T18:00:00+00:00",
            "high_so_far_f": 100.0,
            "heating_rate_f_per_hour": 2.0,
            "forecast_high_f": 106.0,
            "threshold_f": 100.0,
            "warnings": ["weather warning"],
        }
        market = {
            "market_title": "Highest temperature in Phoenix",
            "contract_title": "107F to 108F",
            "range_low_f": 107.0,
            "range_high_f": 108.0,
            "kalshi_price": 68,
            "implied_probability": 0.68,
            "bid": 67,
            "ask": 68,
            "contracts": [
                {"label": "107F to 108F", "yes_price": 68, "yes_bid": 67},
                {"label": "105F to 106F", "yes_price": 30, "yes_bid": 28},
            ],
            "api_crowd_favorite": "107F to 108F",
            "api_crowd_price": 68,
            "market_data_source": "kalshi_api",
            "warnings": ["market warning"],
        }

        payload = build_city_payload(config, weather, market)

        self.assertEqual(payload["city"], "Phoenix")
        self.assertEqual(payload["winning_bucket"]["label"], "107F to 108F")
        self.assertEqual(payload["second_bucket"]["label"], "105F to 106F")
        self.assertEqual(payload["current_temp_f"], 100.0)
        self.assertEqual(payload["forecast_high_f"], 106.0)
        self.assertEqual(payload["latest_endpoint_temp_f"], 100.0)
        self.assertEqual(payload["fast_metar_temp_f"], 101.0)
        self.assertEqual(payload["fast_metar_time"], "2026-06-03T18:01:00.000Z")
        self.assertEqual(payload["fast_feed_source"], "AviationWeather METAR")
        self.assertEqual(payload["recent_observation_max_f"], 100.4)
        self.assertEqual(payload["raw_high_so_far_time"], "2026-06-03T18:00:00+00:00")
        self.assertEqual(payload["latest_history_time"], "2026-06-03T18:00:00+00:00")
        self.assertTrue(payload["latest_feed_lag_warning"])
        self.assertIn("heating_status_score", payload)
        self.assertIn("heating_status_label", payload)
        self.assertIsInstance(payload["heating_status_reasons"], list)
        self.assertEqual(payload["station_truth_label"], "Official station KPHX")
        self.assertEqual(payload["rounding_risk_label"], "Next bucket danger")
        self.assertEqual(payload["six_hour_lock_label"], "No 6h max yet")
        self.assertEqual(payload["market_confirmation_label"], "Market hotter than weather")
        self.assertEqual(payload["reachability_label"], "UNLIKELY")
        self.assertTrue(payload["false_pump_warning"])
        self.assertEqual(payload["warnings"], ["weather warning", "market warning"])

    def test_parse_metar_max_temp_f_reads_six_hour_max_group(self):
        raw = "KLAS 042256Z 21010G15KT 10SM CLR 40/M06 A2975 RMK AO2 10411 T04001061"

        self.assertAlmostEqual(parse_metar_max_temp_f(raw), 106.0, places=1)

    def test_parse_metar_max_temp_f_reads_24_hour_group_when_six_hour_missing(self):
        raw = "KLAS 050456Z 21010KT 10SM CLR 35/M04 A2978 RMK AO2 404110283"

        self.assertAlmostEqual(parse_metar_max_temp_f(raw), 106.0, places=1)

    def test_recent_observation_feed_summary_flags_newer_history(self):
        weather = {
            "current_temp_f": 84.2,
            "observation_time": "2026-06-03T19:25:00+00:00",
            "recent_observation_points": [
                {"time": "2026-06-03T19:25:00+00:00", "temp_f": 84.2},
                {"time": "2026-06-03T19:35:00+00:00", "temp_f": 87.8},
            ],
        }

        summary = recent_observation_feed_summary(weather)

        self.assertEqual(summary["recent_observation_max_f"], 87.8)
        self.assertEqual(summary["latest_history_temp_f"], 87.8)
        self.assertTrue(summary["latest_feed_lag_warning"])

    def test_recent_observation_feed_summary_includes_hotter_latest_endpoint(self):
        weather = {
            "current_temp_f": 89.6,
            "observation_time": "2026-06-04T19:30:00+00:00",
            "recent_observation_points": [
                {"time": "2026-06-04T19:20:00+00:00", "temp_f": 87.8},
                {"time": "2026-06-04T19:25:00+00:00", "temp_f": 87.8},
            ],
        }

        summary = recent_observation_feed_summary(weather)

        self.assertEqual(summary["recent_observation_max_f"], 89.6)
        self.assertTrue(summary["latest_feed_lag_warning"])

    def test_temp_meter_promotes_hotter_latest_endpoint_to_high_so_far(self):
        with (
            patch(
                "live_dashboard.fetch_nws_latest_observation",
                return_value={
                    "current_temp_f": 89.6,
                    "observation_time": "2026-06-04T19:30:00+00:00",
                },
            ),
            patch("live_dashboard.fetch_fast_metar_observation", return_value={}),
            patch(
                "live_dashboard.fetch_nws_observation_history",
                return_value={
                    "raw_high_so_far_f": 87.8,
                    "high_so_far_f": 88.0,
                    "recent_observation_points": [
                        {"time": "2026-06-04T19:20:00+00:00", "temp_f": 87.8},
                        {"time": "2026-06-04T19:25:00+00:00", "temp_f": 87.8},
                    ],
                },
            ),
        ):
            payload = live_dashboard.collect_live_temp_meter("San Antonio")

        self.assertEqual(payload["raw_high_so_far_f"], 89.6)
        self.assertEqual(payload["high_so_far_f"], 90.0)
        self.assertEqual(payload["recent_observation_max_f"], 89.6)

    def test_cache_prevents_refetch_inside_ttl(self):
        calls = {"count": 0}

        def fetcher(day):
            calls["count"] += 1
            return {"cities": [], "active_day": day, "generated": calls["count"]}

        now = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
        cache = LiveDashboardCache(ttl_seconds=60, fetcher=fetcher, clock=lambda: now)

        first = cache.get("today")
        second = cache.get("today")

        self.assertEqual(first["generated"], 1)
        self.assertEqual(second["generated"], 1)
        self.assertEqual(calls["count"], 1)

        tomorrow = cache.get("tomorrow")
        self.assertEqual(tomorrow["active_day"], "today")
        self.assertEqual(tomorrow["generated"], 1)

        later = now + timedelta(seconds=61)
        cache.clock = lambda: later
        third = cache.get("today")

        self.assertEqual(third["generated"], 2)
        self.assertEqual(calls["count"], 2)

    def test_temp_meter_cache_uses_three_second_city_cache(self):
        calls = {"count": 0}

        def fetcher(city_name):
            calls["count"] += 1
            return {"city": city_name, "generated": calls["count"]}

        now = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
        cache = LiveTempMeterCache(ttl_seconds=3, fetcher=fetcher, clock=lambda: now)

        first = cache.get("Phoenix")
        second = cache.get("Phoenix")

        self.assertEqual(first["generated"], 1)
        self.assertEqual(second["generated"], 1)
        self.assertEqual(calls["count"], 1)

        cache.clock = lambda: now + timedelta(seconds=3)
        third = cache.get("Phoenix")

        self.assertEqual(third["generated"], 2)
        self.assertEqual(calls["count"], 2)


class LiveDashboardAppTests(unittest.TestCase):
    def test_dashboard_and_api_are_public(self):
        import live_app

        live_app.live_cache.values = {
            "today": {"cities": [], "active_day": "today", "last_updated": "now", "next_refresh_eta": "soon"}
        }
        live_app.live_cache.fetched_at = {}
        client = TestClient(live_app.app)

        self.assertEqual(client.get("/").status_code, 200)
        response = client.get("/api/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cities"], [])
        self.assertEqual(response.json()["active_day"], "today")

    def test_api_live_tomorrow_param_returns_today_payload(self):
        import live_app

        live_app.live_cache.values = {
            "today": {"cities": [], "active_day": "today", "market_date_label": "2026-06-04"}
        }
        live_app.live_cache.fetched_at = {}
        client = TestClient(live_app.app)

        response = client.get("/api/live?day=tomorrow")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["active_day"], "today")

    def test_api_live_includes_public_polling_metadata(self):
        import live_app

        live_app.live_cache.values = {
            "today": {
                "cities": [],
                "active_day": "today",
                "browser_poll_seconds": 60,
                "temp_meter_browser_poll_seconds": 10,
            }
        }
        live_app.live_cache.fetched_at = {}
        client = TestClient(live_app.app)

        response = client.get("/api/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["browser_poll_seconds"], 60)
        self.assertEqual(response.json()["temp_meter_browser_poll_seconds"], 10)

    def test_temp_meter_api_returns_city_payload(self):
        import live_app

        live_app.temp_meter_cache.values = {
            "phoenix": {
                "city": "Phoenix",
                "ok": True,
                "current_temp_f": 100.0,
                "fast_metar_temp_f": 101.0,
                "fast_feed_source": "AviationWeather METAR",
                "recent_observation_max_f": 101.0,
            }
        }
        live_app.temp_meter_cache.fetched_at = {
            "phoenix": datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
        }
        live_app.temp_meter_cache.clock = lambda: datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
        client = TestClient(live_app.app)

        response = client.get("/api/temp-meter?city=Phoenix")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["city"], "Phoenix")
        self.assertEqual(response.json()["fast_metar_temp_f"], 101.0)
        self.assertEqual(response.json()["cache_ttl_seconds"], 10)

    def test_history_api_returns_three_day_payload(self):
        import live_app

        client = TestClient(live_app.app)
        with patch(
            "live_app.load_kalshi_candle_history",
            return_value={"city": "Las Vegas", "days": [{"market_date": "2026-06-03"}]},
        ) as loader:
            response = client.get("/api/history?city=Las%20Vegas")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["city"], "Las Vegas")
        self.assertEqual(len(response.json()["days"]), 1)
        loader.assert_called_once_with("Las Vegas", days=3)

    def test_dashboard_script_auto_refreshes_when_countdown_expires(self):
        import live_app

        html = live_app._dashboard_html()

        self.assertIn("let refreshInFlight = false", html)
        self.assertIn("seconds <= 0 && !refreshInFlight", html)
        self.assertIn("load();", html)

    def test_dashboard_has_main_page_live_temp_graph(self):
        import live_app

        html = live_app._dashboard_html()

        self.assertIn("dateBanner", html)
        self.assertIn("Today", html)
        self.assertIn("forecastOnly", html)
        self.assertIn("fetch('/api/live'", html)
        self.assertIn("NWS live temperature graph", html)
        self.assertIn("tempGraph", html)
        self.assertIn("High so far", html)
        self.assertIn("tempGraphHighPath", html)
        self.assertIn("NWS points often post around 5 min", html)
        self.assertIn("Still heating?", html)
        self.assertIn("heating_status_score", html)
        self.assertIn("heating_status_label", html)
        self.assertIn("marketChecklist", html)
        self.assertIn("6h clue", html)
        self.assertIn("Rounding", html)
        self.assertIn("Market check", html)
        self.assertIn("High So Far Raw", html)
        self.assertIn("High Time ET", html)
        self.assertIn("dayHigh", html)
        self.assertIn("fast_metar_temp_f", html)
        self.assertIn("tempMeterPollSeconds", html)
        self.assertIn("syncPollTimers", html)
        self.assertIn("/api/temp-meter?city=", html)
        self.assertIn("refreshVisibleTempMeters", html)
        self.assertIn("updateLiveTempGraph", html)
        self.assertIn("/api/history?city=", html)
        self.assertIn("historic", html.lower())
        self.assertIn("Recent NWS station feed", html)
        self.assertIn("latest_feed_lag_warning", html)
        self.assertNotIn("Open Live Temp Meter", html)
        self.assertNotIn("openFinalCities", html)
        self.assertNotIn("Degrees Needed", html)
        self.assertNotIn("Needed Rate", html)
        self.assertNotIn("Market vs Weather", html)
        self.assertNotIn("Tomorrow", html)
        self.assertNotIn("tabButton", html)

    def test_health_route_is_public(self):
        import live_app

        client = TestClient(live_app.app)
        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
