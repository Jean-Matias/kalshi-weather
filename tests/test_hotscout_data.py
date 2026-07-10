import json
import sqlite3
import unittest

from hotscout import db
from hotscout.data import cli_history, forecast_history, kalshi_history, obs_history


def _memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init(conn)
    return conn


class CliHistoryTests(unittest.TestCase):
    def test_parse_cli_record_extracts_date_and_high(self):
        record = {"station": "KLAS", "valid": "2024-01-01", "high": 62}
        self.assertEqual(cli_history.parse_cli_record(record), ("2024-01-01", 62.0))

    def test_parse_cli_record_skips_missing_high(self):
        record = {"station": "KLAS", "valid": "2024-01-01", "high": "M"}
        self.assertIsNone(cli_history.parse_cli_record(record))

    def test_parse_cli_record_skips_missing_date(self):
        record = {"station": "KLAS", "high": 62}
        self.assertIsNone(cli_history.parse_cli_record(record))

    def test_upsert_cli_daily_is_resumable(self):
        conn = _memory_conn()
        records = [{"valid": "2024-01-01", "high": 62}, {"valid": "2024-01-02", "high": 61}]
        inserted_first = cli_history.upsert_cli_daily(conn, "Las Vegas", records)
        inserted_second = cli_history.upsert_cli_daily(conn, "Las Vegas", records)
        self.assertEqual(inserted_first, 2)
        self.assertEqual(inserted_second, 0)
        rows = conn.execute("SELECT * FROM cli_daily ORDER BY date").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["cli_high_f"], 62.0)


class ForecastHistoryTests(unittest.TestCase):
    def test_parse_lead0_response_skips_nulls(self):
        payload = {
            "daily": {
                "time": ["2025-06-01", "2025-06-02", "2025-06-03"],
                "temperature_2m_max": [96.8, None, 91.5],
            }
        }
        rows = forecast_history.parse_lead0_response(payload)
        self.assertEqual(rows, [("2025-06-01", 96.8), ("2025-06-03", 91.5)])

    def test_parse_previous_run_response_takes_daily_max(self):
        payload = {
            "hourly": {
                "time": ["2025-06-01T00:00", "2025-06-01T14:00", "2025-06-02T00:00"],
                "temperature_2m_previous_day1": [70.0, 96.8, 65.0],
            }
        }
        rows = forecast_history.parse_previous_run_response(payload, 1)
        self.assertEqual(rows, [("2025-06-01", 96.8), ("2025-06-02", 65.0)])

    def test_upsert_forecast_daily_is_resumable(self):
        conn = _memory_conn()
        rows = [("2025-06-01", 96.8), ("2025-06-02", 92.3)]
        inserted_first = forecast_history.upsert_forecast_daily(
            conn, "Las Vegas", rows, 0, "ncep_nbm_conus", "open_meteo_historical_forecast"
        )
        inserted_second = forecast_history.upsert_forecast_daily(
            conn, "Las Vegas", rows, 0, "ncep_nbm_conus", "open_meteo_historical_forecast"
        )
        self.assertEqual(inserted_first, 2)
        self.assertEqual(inserted_second, 0)


class ObsHistoryTests(unittest.TestCase):
    def test_iem_station_drops_leading_k(self):
        self.assertEqual(obs_history.iem_station("KLAS"), "LAS")
        self.assertEqual(obs_history.iem_station("LAS"), "LAS")

    def test_parse_asos_csv_downsamples_to_hourly_max(self):
        csv_text = (
            "station,valid,tmpf\n"
            "LAS,2024-06-01 00:56,90.00\n"
            "LAS,2024-06-01 00:36,88.00\n"
            "LAS,2024-06-01 01:15,85.00\n"
            "LAS,2024-06-01 01:20,M\n"
        )
        rows = obs_history.parse_asos_csv(csv_text)
        self.assertEqual(
            rows,
            [
                ("2024-06-01T00:00", 90.0),
                ("2024-06-01T01:00", 85.0),
            ],
        )

    def test_upsert_obs_hourly_is_resumable(self):
        conn = _memory_conn()
        rows = [("2024-06-01T00:00", 90.0), ("2024-06-01T01:00", 85.0)]
        inserted_first = obs_history.upsert_obs_hourly(conn, "Las Vegas", rows, "iem_asos")
        inserted_second = obs_history.upsert_obs_hourly(conn, "Las Vegas", rows, "iem_asos")
        self.assertEqual(inserted_first, 2)
        self.assertEqual(inserted_second, 0)


class KalshiHistoryTests(unittest.TestCase):
    def test_parse_bucket_label_between(self):
        self.assertEqual(kalshi_history.parse_bucket_label("76° to 77°"), (76.0, 77.0))

    def test_parse_bucket_label_below(self):
        self.assertEqual(kalshi_history.parse_bucket_label("75° or below"), (None, 75.0))

    def test_parse_bucket_label_above(self):
        self.assertEqual(kalshi_history.parse_bucket_label("84° or above"), (84.0, None))

    def test_parse_bucket_label_unknown_shape(self):
        self.assertEqual(kalshi_history.parse_bucket_label("nonsense"), (None, None))

    def test_market_date_from_ticker(self):
        self.assertEqual(kalshi_history.market_date_from_ticker("KXHIGHTLV-26APR02"), "2026-04-02")

    def test_settled_bucket_finds_yes_result(self):
        buckets = [
            {"ticker": "A", "label": "x", "low_f": None, "high_f": 75.0, "result": "no"},
            {"ticker": "B", "label": "y", "low_f": 76.0, "high_f": 77.0, "result": "yes"},
        ]
        self.assertEqual(kalshi_history.settled_bucket(buckets)["ticker"], "B")

    def test_bucket_to_frozen_shape(self):
        bucket = {"ticker": "KXHIGHTLV-26APR02-T76", "label": "75° or below", "result": "yes"}
        frozen = kalshi_history.bucket_to_frozen(bucket)
        self.assertEqual(
            frozen,
            {
                "ticker": "KXHIGHTLV-26APR02-T76",
                "label": "75° or below",
                "low_f": None,
                "high_f": 75.0,
                "result": "yes",
            },
        )

    def test_upsert_event_and_candles_row_shape(self):
        conn = _memory_conn()
        event = {
            "event_ticker": "KXHIGHTLV-26APR02",
            "close_ts": 1775203200,
            "buckets": [
                {"ticker": "KXHIGHTLV-26APR02-T76", "label": "75° or below", "result": "yes"},
                {"ticker": "KXHIGHTLV-26APR02-B76.5", "label": "76° to 77°", "result": "no"},
            ],
        }
        inserted = kalshi_history.upsert_event(conn, "Las Vegas", event)
        self.assertEqual(inserted, 1)
        row = conn.execute("SELECT * FROM kalshi_events WHERE event_ticker = ?", (event["event_ticker"],)).fetchone()
        self.assertEqual(row["market_date"], "2026-04-02")
        self.assertEqual(row["settled_bucket_ticker"], "KXHIGHTLV-26APR02-T76")
        buckets = json.loads(row["buckets_json"])
        self.assertEqual(len(buckets), 2)

        candles = [
            {
                "end_period_ts": 1775055600,
                "price": {"close_dollars": "0.2100"},
                "yes_ask": {"close_dollars": "0.2200"},
                "yes_bid": {"close_dollars": "0.1900"},
                "volume_fp": "93.00",
            }
        ]
        candles_inserted = kalshi_history.upsert_candles(conn, event["event_ticker"], "KXHIGHTLV-26APR02-T76", candles)
        self.assertEqual(candles_inserted, 1)
        candle_row = conn.execute("SELECT * FROM kalshi_candles").fetchone()
        self.assertEqual(candle_row["ts"], 1775055600)
        self.assertEqual(candle_row["yes_bid_c"], 19)
        self.assertEqual(candle_row["yes_ask_c"], 22)
        self.assertEqual(candle_row["price_c"], 21)
        self.assertEqual(candle_row["volume"], 93)

        # Re-running is a no-op (resumable).
        self.assertEqual(kalshi_history.upsert_event(conn, "Las Vegas", event), 0)
        self.assertEqual(
            kalshi_history.upsert_candles(conn, event["event_ticker"], "KXHIGHTLV-26APR02-T76", candles), 0
        )


class RetryTests(unittest.TestCase):
    def test_retries_transient_failures_then_succeeds(self):
        from urllib.error import URLError

        from hotscout.data.retry import retrying

        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise URLError("transient")
            return "ok"

        self.assertEqual(retrying(flaky, base_sleep_s=0)(), "ok")
        self.assertEqual(len(calls), 3)

    def test_reraises_after_final_attempt(self):
        from urllib.error import URLError

        from hotscout.data.retry import retrying

        def always_fails():
            raise URLError("down")

        with self.assertRaises(URLError):
            retrying(always_fails, base_sleep_s=0)()


class StrictBucketParsingTests(unittest.TestCase):
    def test_event_with_unparseable_bucket_label_is_skipped(self):
        conn = _memory_conn()
        event = {
            "event_ticker": "KXHIGHTLV-26APR02",
            "close_ts": 0,
            "buckets": [
                {"ticker": "T1", "label": "76° to 77°", "result": "no"},
                {"ticker": "T2", "label": "garbled ??? label", "result": "yes"},
            ],
        }
        with self.assertLogs("hotscout.data.kalshi_history", level="ERROR"):
            inserted = kalshi_history.upsert_event(conn, "Las Vegas", event)
        self.assertEqual(inserted, 0)
        n = conn.execute("SELECT COUNT(*) FROM kalshi_events").fetchone()[0]
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
