import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from hotscout import db as hs_db
from hotscout import live as hs_live
from hotscout import picks as hs_picks
from hotscout.app import create_app


def fake_weather(city_config):
    return {
        "forecast_high_f": 100.0,
        "high_so_far_f": 92.0,
        "heating_rate_f_per_hour": 1.5,
        "forecast_high_time": None,
        "warnings": [],
    }


def fake_kalshi(city_config):
    return {
        "contracts": [
            {
                "ticker": f"{city_config['city'].replace(' ', '')}-99",
                "label": "99F or above",
                "low_f": 99,
                "high_f": None,
                "yes_bid": 40,
                "yes_price": 45,
            },
            {
                "ticker": f"{city_config['city'].replace(' ', '')}-95-98",
                "label": "95F to 98F",
                "low_f": 95,
                "high_f": 98,
                "yes_bid": 20,
                "yes_price": 25,
            },
        ],
        "warnings": [],
    }


def make_temp_db():
    tmp_dir = tempfile.TemporaryDirectory()
    db_path = Path(tmp_dir.name) / "hotscout_test.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    hs_db.init(conn)
    return tmp_dir, conn


class HealthAndIndexTests(unittest.TestCase):
    def test_health_ok(self):
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_index_returns_html(self):
        app = create_app()
        client = TestClient(app)
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Hotscout", response.text)


class BuildBoardDegradedModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir, self.conn = make_temp_db()

    def tearDown(self):
        self.conn.close()
        self.tmp_dir.cleanup()

    def test_board_shape_matches_payload(self):
        board = hs_live.build_board(
            market_date="2026-07-03",
            conn=self.conn,
            kalshi_fetcher=fake_kalshi,
            weather_fetcher=fake_weather,
        )
        self.assertIn("generated_at", board)
        self.assertIn("cities", board)
        self.assertEqual(len(board["cities"]), 1)
        city = board["cities"][0]
        for key in (
            "city",
            "market_date",
            "forecast_high_f",
            "high_so_far_f",
            "heating_rate",
            "buckets",
            "backtest_badge",
            "warnings",
        ):
            self.assertIn(key, city)
        bucket = city["buckets"][0]
        for key in (
            "ticker",
            "label",
            "model_prob",
            "yes_bid_c",
            "yes_ask_c",
            "edge_after_fees",
            "recommendation",
            "confidence",
        ):
            self.assertIn(key, bucket)

    def test_degraded_mode_all_pass_and_not_validated(self):
        board = hs_live.build_board(
            market_date="2026-07-03",
            conn=self.conn,
            kalshi_fetcher=fake_kalshi,
            weather_fetcher=fake_weather,
        )
        for city in board["cities"]:
            self.assertFalse(city["backtest_badge"]["validated"])
            for bucket in city["buckets"]:
                self.assertEqual(bucket["recommendation"], "PASS")
                self.assertIsNone(bucket["model_prob"])

    def test_kalshi_and_weather_failures_produce_warnings_not_500(self):
        def broken_weather(city_config):
            raise RuntimeError("weather feed down")

        def broken_kalshi(city_config):
            raise RuntimeError("kalshi feed down")

        board = hs_live.build_board(
            market_date="2026-07-03",
            conn=self.conn,
            kalshi_fetcher=broken_kalshi,
            weather_fetcher=broken_weather,
        )
        for city in board["cities"]:
            self.assertTrue(any("weather unavailable" in w for w in city["warnings"]))
            self.assertTrue(any("kalshi unavailable" in w for w in city["warnings"]))
            self.assertEqual(city["buckets"], [])


class BuildBoardValidatedModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir, self.conn = make_temp_db()

    def tearDown(self):
        self.conn.close()
        self.tmp_dir.cleanup()

    def _insert_backtest_row(self, city, decision_hour_local):
        self.conn.execute(
            """
            INSERT INTO backtest_results(
                city, strategy, decision_hour_local, edge_threshold, n_trades,
                wins, roi, brier, window_start, window_end, payload_json, created_at
            ) VALUES (?, 'baseline', ?, 0.05, 50, 33, 0.18, 0.1, '2025-01-01', '2025-06-01', '{}', '2026-01-01T00:00:00Z')
            """,
            (city, decision_hour_local),
        )
        self.conn.commit()

    def test_validated_high_edge_bucket_gets_buy_yes(self):
        city = "Las Vegas"
        decision_hour_local = hs_live.nearest_decision_hour("America/Los_Angeles")
        self._insert_backtest_row(city, decision_hour_local)

        fake_probs = {f"{city.replace(' ', '')}-99": 0.9, f"{city.replace(' ', '')}-95-98": 0.1}

        class FakeModelModule:
            @staticmethod
            def bucket_probabilities(residual_dist, forecast_high_f, buckets, high_so_far_f=None, hours_to_peak=None):
                return [{"ticker": b["ticker"], "prob": fake_probs.get(b["ticker"], 0.0)} for b in buckets]

        class FakeCalibrationModule:
            @staticmethod
            def load_residual_dist(conn, city, decision_hour_local, month):
                return {"residuals_f": [0.1, -0.2, 0.3], "n": 3, "blend_weight": 1.0}

        with mock.patch.dict(
            "sys.modules",
            {"hotscout.model": FakeModelModule, "hotscout.calibration": FakeCalibrationModule},
        ):
            board = hs_live.build_board(
                market_date="2026-07-03",
                conn=self.conn,
                kalshi_fetcher=fake_kalshi,
                weather_fetcher=fake_weather,
            )

        city_board = next(c for c in board["cities"] if c["city"] == city)
        self.assertTrue(city_board["backtest_badge"]["validated"])
        high_bucket = next(b for b in city_board["buckets"] if b["ticker"].endswith("-99"))
        self.assertEqual(high_bucket["recommendation"], "BUY YES")
        self.assertIsNotNone(high_bucket["model_prob"])


class PicksTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir, self.conn = make_temp_db()

    def tearDown(self):
        self.conn.close()
        self.tmp_dir.cleanup()

    def _board_with_buy(self):
        return {
            "generated_at": "2026-07-03T00:00:00Z",
            "cities": [
                {
                    "city": "Las Vegas",
                    "market_date": "2026-07-03",
                    "forecast_high_f": 100.0,
                    "high_so_far_f": 92.0,
                    "heating_rate": 1.5,
                    "buckets": [
                        {
                            "ticker": "LASVEGAS-99",
                            "label": "99F or above",
                            "model_prob": 0.9,
                            "yes_bid_c": 40,
                            "yes_ask_c": 45,
                            "edge_after_fees": 0.4,
                            "recommendation": "BUY YES",
                            "confidence": "high",
                            "decision_hour_local": 11,
                        }
                    ],
                    "backtest_badge": {"win_rate": 0.6, "roi": 0.1, "n_trades": 50, "window": "n/a", "validated": True},
                    "warnings": [],
                }
            ],
        }

    def test_record_from_board_inserts_and_dedups(self):
        board = self._board_with_buy()
        inserted_first = hs_picks.record_from_board(self.conn, board)
        inserted_second = hs_picks.record_from_board(self.conn, board)
        self.assertEqual(inserted_first, 1)
        self.assertEqual(inserted_second, 0)
        rows = self.conn.execute("SELECT * FROM picks").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["market_ticker"], "LASVEGAS-99")
        self.assertEqual(rows[0]["side"], "yes")
        self.assertEqual(rows[0]["market_price_c"], 45)

    def test_resolve_open_settles_win_and_loss(self):
        board = self._board_with_buy()
        hs_picks.record_from_board(self.conn, board)

        self.conn.execute(
            """
            INSERT INTO kalshi_events(city, market_date, event_ticker, close_ts, settled_bucket_ticker, settled_bucket_label, buckets_json)
            VALUES ('Las Vegas', '2026-07-03', 'EVT-1', 0, 'LASVEGAS-99', '99F or above', '[]')
            """
        )
        self.conn.commit()

        resolved = hs_picks.resolve_open(self.conn, today="2026-07-04")
        self.assertEqual(resolved, 1)
        row = self.conn.execute("SELECT outcome, pnl_c FROM picks").fetchone()
        self.assertEqual(row["outcome"], "win")
        self.assertEqual(row["pnl_c"], 100 - 45 - 2)

    def test_resolve_open_leaves_unsettled_market_open(self):
        board = self._board_with_buy()
        hs_picks.record_from_board(self.conn, board)
        resolved = hs_picks.resolve_open(self.conn, today="2026-07-04")
        self.assertEqual(resolved, 0)
        row = self.conn.execute("SELECT outcome FROM picks").fetchone()
        self.assertIsNone(row["outcome"])


class ApiEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "hotscout_test.sqlite3"
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        hs_db.init(conn)
        conn.close()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _fresh_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_api_board_and_picks_shape(self):
        def fast_builder():
            conn = self._fresh_conn()
            try:
                return hs_live.build_board(
                    market_date="2026-07-03",
                    conn=conn,
                    kalshi_fetcher=fake_kalshi,
                    weather_fetcher=fake_weather,
                )
            finally:
                conn.close()

        with mock.patch("hotscout.app.hs_db.connect", side_effect=self._fresh_conn), \
             mock.patch("hotscout.app.hs_db.init"):
            app = create_app(board_builder=fast_builder)
            client = TestClient(app)

            board_response = client.get("/api/board")
            self.assertEqual(board_response.status_code, 200)
            board_payload = board_response.json()
            self.assertEqual(len(board_payload["cities"]), 1)
            self.assertIn("cache_ttl_seconds", board_payload)

            picks_response = client.get("/api/picks")
            self.assertEqual(picks_response.status_code, 200)
            picks_payload = picks_response.json()
            self.assertIn("picks", picks_payload)
            self.assertIn("record", picks_payload)

            backtest_response = client.get("/api/backtest", params={"city": "Las Vegas"})
            self.assertEqual(backtest_response.status_code, 200)
            self.assertIn("results", backtest_response.json())


if __name__ == "__main__":
    unittest.main()
