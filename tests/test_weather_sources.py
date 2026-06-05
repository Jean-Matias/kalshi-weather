import unittest
from datetime import datetime
from unittest.mock import patch

from weather_sources import fetch_fast_metar_observation, fetch_nws_observation_history, parse_cli_report_text, parse_digital_dwml_forecast
from weather_sources import _fill_derived_weather
from weather_sources import _market_day_utc_window
from weather_sources import _round_official_temp
from weather_sources import _wind_shift


class WeatherSourcesTests(unittest.TestCase):
    def test_parse_cli_report_maximum_temperature(self):
        text = """
CLIMATE REPORT
NATIONAL WEATHER SERVICE LOS ANGELES/OXNARD CA

...THE LOS ANGELES AIRPORT CLIMATE SUMMARY FOR MAY 24 2026...

TEMPERATURE (F)
TODAY
MAXIMUM         69
MINIMUM         58
AVERAGE         64
"""

        parsed = parse_cli_report_text(text)

        self.assertEqual(parsed["cli_high_f"], 69.0)
        self.assertEqual(parsed["cli_report_date"], "2026-05-24")
        self.assertEqual(parsed["settlement_source_status"], "cli_available")

    def test_parse_cli_report_ignores_missing_maximum(self):
        parsed = parse_cli_report_text("CLIMATE REPORT\nTEMPERATURE (F)\n")

        self.assertIsNone(parsed["cli_high_f"])
        self.assertEqual(parsed["settlement_source_status"], "cli_unavailable")

    def test_fill_derived_weather_flags_cli_lower_than_observed_high(self):
        weather = {
            "cli_high_f": 69.0,
            "current_temp_f": 75.0,
            "high_so_far_f": 75.0,
            "forecast_high_f": 80.0,
            "open_meteo_high_f": None,
            "model_disagreement_f": None,
            "cloud_cover_change": None,
            "open_meteo_cloud_change": None,
            "settlement_source_status": "cli_available",
            "warnings": [],
        }
        _fill_derived_weather(weather, {"notes": ""})

        self.assertEqual(weather["settlement_source_status"], "cli_inconsistent")
        self.assertEqual(weather["high_so_far_f"], 75.0)
        self.assertEqual(weather["forecast_high_f"], 80.0)

    def test_fill_derived_weather_flags_cli_wrong_report_date(self):
        weather = {
            "cli_high_f": 70.0,
            "cli_report_date": "2026-05-23",
            "current_temp_f": 60.0,
            "high_so_far_f": 70.0,
            "forecast_high_f": 74.0,
            "open_meteo_high_f": None,
            "model_disagreement_f": None,
            "cloud_cover_change": None,
            "open_meteo_cloud_change": None,
            "settlement_source_status": "cli_available",
            "warnings": [],
        }
        _fill_derived_weather(weather, {"market_date": "2026-05-24", "notes": ""})

        self.assertEqual(weather["settlement_source_status"], "cli_wrong_date")
        self.assertEqual(weather["analysis_source_status"], "same_day_station_observations")
        self.assertEqual(weather["high_so_far_f"], 70.0)
        self.assertEqual(weather["forecast_high_f"], 74.0)

    def test_fill_derived_weather_rejects_cli_high_without_report_date(self):
        weather = {
            "cli_high_f": 74.0,
            "cli_report_date": None,
            "current_temp_f": 73.0,
            "high_so_far_f": 73.0,
            "forecast_high_f": 75.0,
            "latest_observation_time": "2026-05-24T20:00:00+00:00",
            "open_meteo_high_f": None,
            "model_disagreement_f": None,
            "cloud_cover_change": None,
            "open_meteo_cloud_change": None,
            "settlement_source_status": "cli_available",
            "warnings": [],
        }

        _fill_derived_weather(
            weather,
            {
                "market_date": "2026-05-24",
                "timezone": "America/Chicago",
                "notes": "",
            },
            now=datetime.fromisoformat("2026-05-24T20:30:00+00:00"),
        )

        self.assertEqual(weather["settlement_source_status"], "cli_unverified_date")
        self.assertEqual(weather["high_so_far_f"], 73.0)
        self.assertEqual(weather["forecast_high_f"], 75.0)
        self.assertIn("NWS CLI report date could not be parsed", "\n".join(weather["warnings"]))

    def test_fill_derived_weather_treats_same_day_cli_as_preliminary_while_day_open(self):
        weather = {
            "cli_high_f": 60.0,
            "cli_report_date": "2026-05-25",
            "current_temp_f": 55.0,
            "high_so_far_f": 61.0,
            "forecast_high_f": 82.0,
            "latest_observation_time": "2026-05-25T12:00:00+00:00",
            "open_meteo_high_f": 83.0,
            "model_disagreement_f": None,
            "cloud_cover_change": None,
            "open_meteo_cloud_change": None,
            "settlement_source_status": "cli_available",
            "warnings": [],
        }

        _fill_derived_weather(
            weather,
            {
                "market_date": "2026-05-25",
                "timezone": "America/Denver",
                "notes": "",
            },
            now=datetime.fromisoformat("2026-05-25T12:30:00+00:00"),
        )

        self.assertEqual(weather["settlement_source_status"], "cli_preliminary")
        self.assertEqual(weather["high_so_far_f"], 61.0)
        self.assertEqual(weather["forecast_high_f"], 82.0)
        self.assertTrue(weather["active_heating_window"])
        self.assertIn("local weather day is still open", "\n".join(weather["warnings"]))

    def test_fill_derived_weather_accepts_same_day_cli_after_day_closes(self):
        weather = {
            "cli_high_f": 60.0,
            "cli_report_date": "2026-05-25",
            "current_temp_f": 55.0,
            "high_so_far_f": 61.0,
            "forecast_high_f": 82.0,
            "latest_observation_time": "2026-05-26T03:30:00+00:00",
            "open_meteo_high_f": 83.0,
            "model_disagreement_f": None,
            "cloud_cover_change": None,
            "open_meteo_cloud_change": None,
            "settlement_source_status": "cli_available",
            "warnings": [],
        }

        _fill_derived_weather(
            weather,
            {
                "market_date": "2026-05-25",
                "timezone": "America/Denver",
                "notes": "",
            },
            now=datetime.fromisoformat("2026-05-26T04:30:00+00:00"),
        )

        self.assertEqual(weather["settlement_source_status"], "cli_available")
        self.assertEqual(weather["high_so_far_f"], 60.0)
        self.assertFalse(weather["active_heating_window"])

    def test_parse_digital_dwml_forecast_uses_target_day_only(self):
        xml = """
<dwml>
  <head>
    <product>
      <creation-date>2026-05-24T08:00:00-05:00</creation-date>
    </product>
  </head>
  <time-layout>
    <layout-key>k-p1h</layout-key>
    <start-valid-time>2026-05-24T12:00:00-05:00</start-valid-time>
    <start-valid-time>2026-05-24T13:00:00-05:00</start-valid-time>
    <start-valid-time>2026-05-25T12:00:00-05:00</start-valid-time>
  </time-layout>
  <parameters>
    <temperature type="hourly" time-layout="k-p1h">
      <value>60</value><value>62</value><value>88</value>
    </temperature>
    <cloud-amount type="total" time-layout="k-p1h">
      <value>30</value><value>10</value><value>90</value>
    </cloud-amount>
    <humidity type="relative" time-layout="k-p1h">
      <value>80</value><value>70</value><value>20</value>
    </humidity>
  </parameters>
</dwml>
"""
        parsed = parse_digital_dwml_forecast(xml, "2026-05-24")

        self.assertEqual(parsed["forecast_high_f"], 62.0)
        self.assertEqual(parsed["forecast_high_time"], "2026-05-24T13:00:00-05:00")
        self.assertEqual(parsed["forecast_hourly_temps_f"], [60.0, 62.0])
        self.assertEqual(parsed["forecast_source_status"], "same_day_hourly_forecast")
        self.assertEqual(parsed["forecast_generated_at"], "2026-05-24T08:00:00-05:00")

    def test_market_day_utc_window_uses_city_timezone(self):
        start, end = _market_day_utc_window(
            {"market_date": "2026-05-24", "timezone": "America/Chicago"}
        )

        self.assertEqual(start, "2026-05-24T05:00:00Z")
        self.assertEqual(end, "2026-05-25T04:59:59Z")

    def test_round_official_temp_matches_integer_market_buckets(self):
        self.assertEqual(_round_official_temp(73.9), 74.0)
        self.assertEqual(_round_official_temp(73.4), 73.0)

    def test_wind_shift_handles_zero_degree_wraparound(self):
        self.assertFalse(_wind_shift([350.0, 355.0, 5.0, 10.0]))
        self.assertTrue(_wind_shift([350.0, 10.0, 40.0, 80.0]))

    def test_kmdw_history_rounds_raw_high_and_tracks_latest_observation_time(self):
        payload = {
            "features": [
                {
                    "properties": {
                        "timestamp": "2026-05-24T18:53:00+00:00",
                        "temperature": {"value": 21.0},
                    }
                },
                {
                    "properties": {
                        "timestamp": "2026-05-24T20:53:00+00:00",
                        "temperature": {"value": 23.2777777778},
                    }
                },
            ]
        }

        with patch("weather_sources._get_json", return_value=payload):
            weather = fetch_nws_observation_history(
                {
                    "station_id": "KMDW",
                    "market_date": "2026-05-24",
                    "timezone": "America/Chicago",
                }
            )

        self.assertEqual(weather["raw_high_so_far_f"], 73.9)
        self.assertEqual(weather["high_so_far_f"], 74.0)
        self.assertEqual(weather["raw_high_so_far_time"], "2026-05-24T20:53:00+00:00")
        self.assertEqual(weather["latest_observation_time"], "2026-05-24T20:53:00+00:00")

    def test_history_includes_recent_points_and_heating_rate(self):
        payload = {
            "features": [
                {
                    "properties": {
                        "timestamp": "2026-06-03T19:00:00+00:00",
                        "temperature": {"value": 30.0},
                    }
                },
                {
                    "properties": {
                        "timestamp": "2026-06-03T19:30:00+00:00",
                        "temperature": {"value": 31.0},
                    }
                },
                {
                    "properties": {
                        "timestamp": "2026-06-03T20:00:00+00:00",
                        "temperature": {"value": 32.0},
                    }
                },
            ]
        }

        with patch("weather_sources._get_json", return_value=payload):
            weather = fetch_nws_observation_history(
                {
                    "station_id": "KSAT",
                    "market_date": "2026-06-03",
                    "timezone": "America/Chicago",
                }
            )

        self.assertEqual(len(weather["recent_observation_points"]), 3)
        self.assertAlmostEqual(weather["heating_rate_f_per_hour"], 3.6, places=1)

    def test_fetch_fast_metar_observation_uses_aviationweather_feed(self):
        payload = [
            {
                "temp": 30.0,
                "reportTime": "2026-06-04T15:40:00.000Z",
                "rawOb": "KLAS 041540Z 00000KT 10SM CLR 30/08 A2992",
            }
        ]

        with patch("weather_sources._get_json", return_value=payload) as get_json:
            weather = fetch_fast_metar_observation("KLAS")

        self.assertIn("aviationweather.gov/api/data/metar", get_json.call_args.args[0])
        self.assertEqual(weather["fast_feed_source"], "AviationWeather METAR")
        self.assertEqual(weather["fast_metar_temp_f"], 86.0)
        self.assertEqual(weather["fast_metar_time"], "2026-06-04T15:40:00.000Z")
        self.assertIn("KLAS 041540Z", weather["fast_metar_raw"])

    def test_stale_latest_observation_keeps_heating_window_active(self):
        weather = {
            "cli_high_f": None,
            "cli_report_date": None,
            "current_temp_f": 70.0,
            "high_so_far_f": 74.0,
            "forecast_high_f": 72.0,
            "latest_observation_time": "2026-05-24T16:00:00+00:00",
            "open_meteo_high_f": None,
            "model_disagreement_f": None,
            "cloud_cover_change": None,
            "open_meteo_cloud_change": None,
            "settlement_source_status": "cli_unavailable",
            "warnings": [],
        }

        _fill_derived_weather(
            weather,
            {
                "market_date": "2026-05-24",
                "timezone": "America/Chicago",
                "notes": "",
            },
            now=datetime.fromisoformat("2026-05-24T20:00:00+00:00"),
        )

        self.assertTrue(weather["active_heating_window"])
        self.assertIn("Latest station observation is stale", "\n".join(weather["warnings"]))

    def test_fill_derived_weather_promotes_latest_temp_above_lagging_history_high(self):
        weather = {
            "cli_high_f": None,
            "cli_report_date": None,
            "current_temp_f": 89.6,
            "raw_high_so_far_f": 87.8,
            "high_so_far_f": 88.0,
            "forecast_high_f": 87.0,
            "latest_observation_time": "2026-06-04T19:30:00+00:00",
            "open_meteo_high_f": None,
            "model_disagreement_f": None,
            "cloud_cover_change": None,
            "open_meteo_cloud_change": None,
            "settlement_source_status": "cli_unavailable",
            "market_day_state": "today",
            "warnings": [],
        }

        _fill_derived_weather(
            weather,
            {
                "market_date": "2026-06-04",
                "timezone": "America/Chicago",
                "notes": "",
            },
            now=datetime.fromisoformat("2026-06-04T19:35:00+00:00"),
        )

        self.assertEqual(weather["raw_high_so_far_f"], 89.6)
        self.assertEqual(weather["high_so_far_f"], 90.0)

    def test_future_market_uses_forecast_without_observed_high(self):
        weather = {
            "cli_high_f": None,
            "cli_report_date": None,
            "current_temp_f": 93.0,
            "high_so_far_f": None,
            "forecast_high_f": 81.0,
            "latest_observation_time": None,
            "open_meteo_high_f": 82.0,
            "model_disagreement_f": None,
            "cloud_cover_change": None,
            "open_meteo_cloud_change": None,
            "settlement_source_status": "cli_not_checked",
            "market_day_state": "future",
            "warnings": [],
        }

        _fill_derived_weather(
            weather,
            {
                "market_date": "2026-05-28",
                "timezone": "America/Chicago",
                "notes": "",
            },
            now=datetime.fromisoformat("2026-05-27T15:00:00+00:00"),
        )

        self.assertEqual(weather["market_day_state"], "future")
        self.assertIsNone(weather["high_so_far_f"])
        self.assertEqual(weather["analysis_source_status"], "future_hourly_forecast")
        self.assertEqual(weather["settlement_source_status"], "cli_unavailable")


if __name__ == "__main__":
    unittest.main()
