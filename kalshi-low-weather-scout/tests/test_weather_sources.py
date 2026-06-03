import unittest
from datetime import datetime
from unittest.mock import patch

from weather_sources import (
    _fill_derived_weather,
    _market_day_utc_window,
    _open_meteo_market_day_values,
    _round_official_temp,
    _trend,
    _wind_shift,
    fetch_nws_observation_history,
    parse_cli_report_text,
    parse_digital_dwml_forecast,
)


class WeatherSourcesTests(unittest.TestCase):
    def test_parse_cli_report_minimum_temperature(self):
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

        self.assertEqual(parsed["cli_low_f"], 58.0)
        self.assertEqual(parsed["cli_report_date"], "2026-05-24")
        self.assertEqual(parsed["settlement_source_status"], "cli_available")

    def test_parse_cli_report_minimum_from_same_line_max_min(self):
        text = """
...THE CHICAGO MIDWAY CLIMATE SUMMARY FOR MAY 24 2026...
TEMPERATURE (F)
MAXIMUM 74 MINIMUM 52 AVERAGE 63
"""

        parsed = parse_cli_report_text(text)

        self.assertEqual(parsed["cli_low_f"], 52.0)

    def test_parse_cli_report_ignores_missing_minimum(self):
        parsed = parse_cli_report_text("CLIMATE REPORT\nTEMPERATURE (F)\nMAXIMUM 74\n")

        self.assertIsNone(parsed["cli_low_f"])
        self.assertEqual(parsed["settlement_source_status"], "cli_unavailable")

    def test_fill_derived_weather_flags_cli_above_observed_low(self):
        weather = {
            "cli_low_f": 58.0,
            "current_temp_f": 55.0,
            "low_so_far_f": 55.0,
            "forecast_low_f": 54.0,
            "open_meteo_low_f": None,
            "model_disagreement_f": None,
            "cloud_cover_change": None,
            "open_meteo_cloud_change": None,
            "settlement_source_status": "cli_available",
            "warnings": [],
        }
        _fill_derived_weather(weather, {"notes": ""})

        self.assertEqual(weather["settlement_source_status"], "cli_inconsistent")
        self.assertEqual(weather["low_so_far_f"], 55.0)
        self.assertEqual(weather["forecast_low_f"], 54.0)

    def test_fill_derived_weather_flags_cli_wrong_report_date(self):
        weather = {
            "cli_low_f": 58.0,
            "cli_report_date": "2026-05-23",
            "current_temp_f": 60.0,
            "low_so_far_f": 58.0,
            "forecast_low_f": 57.0,
            "open_meteo_low_f": None,
            "model_disagreement_f": None,
            "cloud_cover_change": None,
            "open_meteo_cloud_change": None,
            "settlement_source_status": "cli_available",
            "warnings": [],
        }
        _fill_derived_weather(weather, {"market_date": "2026-05-24", "notes": ""})

        self.assertEqual(weather["settlement_source_status"], "cli_wrong_date")
        self.assertEqual(weather["analysis_source_status"], "same_day_station_observations")
        self.assertEqual(weather["low_so_far_f"], 58.0)
        self.assertEqual(weather["forecast_low_f"], 57.0)

    def test_fill_derived_weather_rejects_cli_low_without_report_date(self):
        weather = {
            "cli_low_f": 52.0,
            "cli_report_date": None,
            "current_temp_f": 54.0,
            "low_so_far_f": 53.0,
            "forecast_low_f": 51.0,
            "latest_observation_time": "2026-05-24T20:00:00+00:00",
            "open_meteo_low_f": None,
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
        self.assertEqual(weather["low_so_far_f"], 53.0)
        self.assertEqual(weather["forecast_low_f"], 51.0)
        self.assertIn("NWS CLI report date could not be parsed", "\n".join(weather["warnings"]))

    def test_fill_derived_weather_treats_same_day_cli_as_preliminary_while_day_open(self):
        weather = {
            "cli_low_f": 52.0,
            "cli_report_date": "2026-05-25",
            "current_temp_f": 61.0,
            "low_so_far_f": 53.0,
            "forecast_low_f": 50.0,
            "latest_observation_time": "2026-05-25T12:00:00+00:00",
            "open_meteo_low_f": 49.0,
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
        self.assertEqual(weather["low_so_far_f"], 53.0)
        self.assertEqual(weather["forecast_low_f"], 50.0)
        self.assertTrue(weather["active_low_window"])

    def test_parse_digital_dwml_forecast_uses_target_day_low_only(self):
        xml = """
<dwml>
  <head>
    <product>
      <creation-date>2026-05-24T08:00:00-05:00</creation-date>
    </product>
  </head>
  <time-layout>
    <layout-key>k-p1h</layout-key>
    <start-valid-time>2026-05-24T00:00:00-05:00</start-valid-time>
    <start-valid-time>2026-05-24T01:00:00-05:00</start-valid-time>
    <start-valid-time>2026-05-25T00:00:00-05:00</start-valid-time>
  </time-layout>
  <parameters>
    <temperature type="hourly" time-layout="k-p1h">
      <value>60</value><value>52</value><value>38</value>
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

        self.assertEqual(parsed["forecast_low_f"], 52.0)
        self.assertEqual(parsed["forecast_low_time"], "2026-05-24T01:00:00-05:00")
        self.assertEqual(parsed["forecast_hourly_temps_f"], [60.0, 52.0])
        self.assertEqual(parsed["forecast_source_status"], "same_day_hourly_forecast")
        self.assertEqual(parsed["forecast_generated_at"], "2026-05-24T08:00:00-05:00")

    def test_open_meteo_values_use_market_local_date_only(self):
        values = _open_meteo_market_day_values(
            ["2026-05-24T23:00", "2026-05-25T00:00"],
            [51, 38],
            "2026-05-24",
            "America/Chicago",
        )

        self.assertEqual(values, [51.0])

    def test_market_day_utc_window_uses_city_timezone(self):
        start, end = _market_day_utc_window(
            {"market_date": "2026-05-24", "timezone": "America/Chicago"}
        )

        self.assertEqual(start, "2026-05-24T05:00:00Z")
        self.assertEqual(end, "2026-05-25T04:59:59Z")

    def test_round_official_temp_matches_integer_market_buckets(self):
        self.assertEqual(_round_official_temp(52.5), 53.0)
        self.assertEqual(_round_official_temp(52.4), 52.0)

    def test_wind_shift_handles_zero_degree_wraparound(self):
        self.assertFalse(_wind_shift([350.0, 355.0, 5.0, 10.0]))
        self.assertTrue(_wind_shift([350.0, 10.0, 40.0, 80.0]))

    def test_trend_treats_first_values_as_recent_nws_order(self):
        self.assertEqual(_trend([103.0, 102.0, 101.0, 96.0, 95.0, 94.0]), "rising")
        self.assertEqual(_trend([94.0, 95.0, 96.0, 101.0, 102.0, 103.0]), "falling")

    def test_history_rounds_raw_low_and_tracks_latest_observation_time(self):
        payload = {
            "features": [
                {
                    "properties": {
                        "timestamp": "2026-05-24T18:53:00+00:00",
                        "temperature": {"value": 12.0},
                    }
                },
                {
                    "properties": {
                        "timestamp": "2026-05-24T20:53:00+00:00",
                        "temperature": {"value": 11.3888888889},
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

        self.assertEqual(weather["raw_low_so_far_f"], 52.5)
        self.assertEqual(weather["low_so_far_f"], 53.0)
        self.assertEqual(weather["latest_observation_time"], "2026-05-24T20:53:00+00:00")

    def test_stale_latest_observation_keeps_low_window_active(self):
        weather = {
            "cli_low_f": None,
            "cli_report_date": None,
            "current_temp_f": 70.0,
            "low_so_far_f": 54.0,
            "forecast_low_f": 52.0,
            "latest_observation_time": "2026-05-24T16:00:00+00:00",
            "open_meteo_low_f": None,
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

        self.assertTrue(weather["active_low_window"])
        self.assertIn("Latest station observation is stale", "\n".join(weather["warnings"]))

    def test_future_market_uses_forecast_without_observed_low(self):
        weather = {
            "cli_low_f": None,
            "cli_report_date": None,
            "current_temp_f": 55.0,
            "low_so_far_f": None,
            "forecast_low_f": 61.0,
            "latest_observation_time": None,
            "open_meteo_low_f": 62.0,
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
        self.assertIsNone(weather["low_so_far_f"])
        self.assertEqual(weather["analysis_source_status"], "future_hourly_forecast")
        self.assertEqual(weather["forecast_source_status"], "future_hourly_forecast")
        self.assertEqual(weather["settlement_source_status"], "cli_unavailable")


if __name__ == "__main__":
    unittest.main()
