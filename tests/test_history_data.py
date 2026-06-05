import json
import sqlite3
import unittest

from datetime import datetime
from zoneinfo import ZoneInfo

from history_data import load_historical_payload, load_kalshi_candle_history


def insert_snapshot(conn, table, captured_at, city, payload):
    if table == "market_snapshots":
        conn.execute(
            """
            insert into market_snapshots (run_id, captured_at, city, url, payload_json)
            values (?, ?, ?, ?, ?)
            """,
            ("run", captured_at, city, "https://kalshi.example", json.dumps(payload)),
        )
    else:
        conn.execute(
            """
            insert into weather_snapshots (run_id, captured_at, city, station_id, payload_json)
            values (?, ?, ?, ?, ?)
            """,
            ("run", captured_at, city, "KLAS", json.dumps(payload)),
        )


class HistoryDataTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(
            """
            create table market_snapshots (
                id integer primary key autoincrement,
                run_id text not null,
                captured_at text not null,
                city text not null,
                url text,
                payload_json text not null
            );
            create table weather_snapshots (
                id integer primary key autoincrement,
                run_id text not null,
                captured_at text not null,
                city text not null,
                station_id text,
                payload_json text not null
            );
            """
        )

    def test_load_historical_payload_returns_three_days_with_bucket_and_weather_lines(self):
        for date, favorite_price in [
            ("2026-06-03", 70),
            ("2026-06-02", 55),
            ("2026-06-01", 40),
            ("2026-05-31", 30),
        ]:
            for hour, price_offset in [("14:00:00", 0), ("18:00:00", 5)]:
                captured_at = f"{date}T{hour}+00:00"
                insert_snapshot(
                    self.conn,
                    "market_snapshots",
                    captured_at,
                    "Las Vegas",
                    {
                        "market_date": date,
                        "contracts": [
                            {
                                "label": "103F to 104F",
                                "low_f": 103,
                                "high_f": 104,
                                "yes_price": 20 + price_offset,
                            },
                            {
                                "label": "105F to 106F",
                                "low_f": 105,
                                "high_f": 106,
                                "yes_price": favorite_price + price_offset,
                            },
                        ],
                    },
                )
                insert_snapshot(
                    self.conn,
                    "weather_snapshots",
                    captured_at,
                    "Las Vegas",
                    {
                        "market_date": date,
                        "raw_high_so_far_f": 100 + price_offset,
                        "current_temp_f": 99 + price_offset,
                        "forecast_high_f": 105,
                    },
                )
        self.conn.commit()

        payload = load_historical_payload("Las Vegas", conn=self.conn, days=3)

        self.assertEqual(payload["city"], "Las Vegas")
        self.assertEqual([day["market_date"] for day in payload["days"]], ["2026-06-03", "2026-06-02", "2026-06-01"])
        first_day = payload["days"][0]
        self.assertEqual(first_day["point_count"], 2)
        self.assertIn("105F to 106F", first_day["bucket_labels"])
        self.assertEqual(first_day["series"][0]["favorite_bucket"], "105F to 106F")
        self.assertEqual(first_day["series"][0]["kalshi_forecast_f"], 105.5)
        self.assertEqual(first_day["series"][1]["actual_temp_f"], 105)
        self.assertEqual(first_day["series"][1]["forecast_temp_f"], 105)

    def test_load_historical_payload_handles_missing_database_rows(self):
        payload = load_historical_payload("Phoenix", conn=self.conn, days=3)

        self.assertEqual(payload["city"], "Phoenix")
        self.assertEqual(payload["days"], [])

    def test_load_historical_payload_handles_missing_tables(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)

        payload = load_historical_payload("Phoenix", conn=conn, days=3)

        self.assertEqual(payload["city"], "Phoenix")
        self.assertEqual(payload["days"], [])

    def test_load_kalshi_candle_history_builds_crowd_forecast_line(self):
        def fake_fetch(url):
            if "/events/" in url and "/candlesticks" not in url:
                return {
                    "markets": [
                        {
                            "ticker": "KXHIGHTLV-26JUN05-B104.5",
                            "strike_type": "between",
                            "floor_strike": 105,
                            "cap_strike": 106,
                        },
                        {
                            "ticker": "KXHIGHTLV-26JUN05-B106.5",
                            "strike_type": "between",
                            "floor_strike": 107,
                            "cap_strike": 108,
                        },
                    ]
                }
            return {
                "market_tickers": ["KXHIGHTLV-26JUN05-B104.5", "KXHIGHTLV-26JUN05-B106.5"],
                "market_candlesticks": [
                    [
                        {
                            "end_period_ts": 1780603200,
                            "price": {"close_dollars": "0.7000"},
                            "yes_ask": {"close_dollars": "0.7100"},
                        }
                    ],
                    [
                        {
                            "end_period_ts": 1780603200,
                            "price": {"close_dollars": "0.3000"},
                            "yes_ask": {"close_dollars": "0.3100"},
                        }
                    ],
                ],
            }

        payload = load_kalshi_candle_history(
            "Las Vegas",
            days=1,
            now=datetime(2026, 6, 5, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles")),
            fetch_json=fake_fetch,
        )

        self.assertEqual(payload["city"], "Las Vegas")
        day = payload["days"][0]
        self.assertEqual(day["event_ticker"], "KXHIGHTLV-26JUN05")
        self.assertEqual(day["point_count"], 1)
        point = day["series"][0]
        self.assertEqual(point["favorite_bucket"], "105F to 106F")
        self.assertEqual(point["favorite_price"], 70.0)
        self.assertEqual(point["kalshi_forecast_f"], 106.1)
        self.assertEqual(day["latest_buckets"][0]["label"], "105F to 106F")


if __name__ == "__main__":
    unittest.main()
