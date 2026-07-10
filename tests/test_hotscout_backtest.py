import json
import sqlite3
import unittest

from hotscout import backtest, db, metrics
from hotscout.fees import kalshi_fee_cents


CITY = "Las Vegas"
DECISION_HOUR = 11
THRESHOLD = 0.05

# 10 sequential event-days. Each has two mutually exclusive buckets:
#   BLOW  ("89 or below"): fake model always says prob=0.75
#   BHIGH ("90 or above"): fake model always says prob=0.25
# BLOW settles "yes" on even-indexed days, BHIGH settles "yes" on odd-indexed
# days. Both buckets quote yes_ask_c=50/yes_bid_c=45 every day.
DATES = [f"2024-06-{d:02d}" for d in range(1, 11)]


def _fake_bucket_probabilities_factory(captured_calls):
    def fake_bucket_probabilities(residual_dist, forecast_high_f, buckets, high_so_far_f=None, hours_to_peak=None):
        captured_calls.append((forecast_high_f, high_so_far_f, hours_to_peak))
        table = {"BLOW": 0.75, "BHIGH": 0.25}
        return [{"ticker": b["ticker"], "prob": table[b["ticker"]]} for b in buckets]
    return fake_bucket_probabilities


def _fake_load_residual_dist(conn, city, decision_hour_local, month):
    return {"residuals_f": [0.0], "n": 1, "blend_weight": 1.0}


def _build_fixture_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init(conn)

    for i, date in enumerate(DATES):
        event_ticker = f"EVT-{date}"
        blow_result = "yes" if i % 2 == 0 else "no"
        bhigh_result = "no" if i % 2 == 0 else "yes"
        buckets_json = json.dumps([
            {"ticker": "BLOW", "label": "89 or below", "low_f": None, "high_f": 89, "result": blow_result},
            {"ticker": "BHIGH", "label": "90 or above", "low_f": 90, "high_f": None, "result": bhigh_result},
        ])
        conn.execute(
            "INSERT INTO kalshi_events (city, market_date, event_ticker, close_ts, "
            "settled_bucket_ticker, settled_bucket_label, buckets_json) VALUES (?,?,?,?,?,?,?)",
            (CITY, date, event_ticker, 0, "BLOW" if blow_result == "yes" else "BHIGH", "", buckets_json),
        )
        conn.execute(
            "INSERT INTO forecast_daily (city, date, lead_days, forecast_high_f, model, source) "
            "VALUES (?,?,?,?,?,?)",
            (CITY, date, 1, 88.0 + i, "fake", "test"),
        )
        # Decision-hour candle: ts computed the same way backtest._decision_ts_utc
        # would, but we just need SOMETHING at/after 11:00 local; use the exact
        # decision timestamp so the "nearest at/after" lookup is exact.
        decision_ts = backtest._decision_ts_utc(CITY, date, DECISION_HOUR)
        # BLOW: market at 50/45 vs fake model's 0.75 -> big YES edge, trades.
        # BHIGH: market at 35/30 vs fake model's 0.25 -> both sides' edges
        # stay under THRESHOLD (see arithmetic in module docstring / tests
        # below), so BHIGH never trades. This isolates every trade to a
        # single, easy-to-hand-compute case (BLOW YES).
        candle_prices = {"BLOW": (45, 50), "BHIGH": (30, 35)}
        for ticker, (yes_bid_c, yes_ask_c) in candle_prices.items():
            conn.execute(
                "INSERT INTO kalshi_candles (event_ticker, market_ticker, ts, yes_bid_c, yes_ask_c, price_c, volume) "
                "VALUES (?,?,?,?,?,?,?)",
                (event_ticker, ticker, decision_ts, yes_bid_c, yes_ask_c, yes_ask_c - 2, 10),
            )

    # obs_hourly for the first date only, to exercise high_so_far_f.
    first_date = DATES[0]
    for ts_local, temp_f in [
        (f"{first_date}T06:00:00", 70.0),
        (f"{first_date}T09:00:00", 75.0),
        (f"{first_date}T10:59:00", 78.0),
        (f"{first_date}T12:00:00", 95.0),  # after the decision hour: must be excluded
    ]:
        conn.execute(
            "INSERT INTO obs_hourly (city, date, ts_local, temp_f, source) VALUES (?,?,?,?,?)",
            (CITY, first_date, ts_local, temp_f, "test"),
        )

    conn.commit()
    return conn


class HotscoutBacktestEvaluateTests(unittest.TestCase):
    def setUp(self):
        self.conn = _build_fixture_conn()
        self.captured_calls = []
        self.fake_model = _fake_bucket_probabilities_factory(self.captured_calls)

    def tearDown(self):
        self.conn.close()

    def _evaluate(self):
        return backtest.evaluate(
            self.conn, CITY, DECISION_HOUR, THRESHOLD,
            bucket_probabilities_fn=self.fake_model,
            load_residual_dist_fn=_fake_load_residual_dist,
        )

    def test_only_blow_side_trades_every_day(self):
        result = self._evaluate()
        # BHIGH never clears the edge threshold on either side (see module
        # docstring math); every trade should be a YES on BLOW.
        self.assertEqual(len(result["trades"]), 10)
        for t in result["trades"]:
            self.assertEqual(t["bucket_ticker"], "BLOW")
            self.assertEqual(t["side"], "yes")
            self.assertEqual(t["entry_price_c"], 50)

    def test_exact_fee_and_pnl_arithmetic(self):
        result = self._evaluate()
        fee = kalshi_fee_cents(50, 1)
        self.assertEqual(fee, 2)  # ceil(7*50*50/10000) = ceil(1.75) = 2
        wins = [t for t in result["trades"] if t["won"]]
        losses = [t for t in result["trades"] if not t["won"]]
        self.assertEqual(len(wins), 5)
        self.assertEqual(len(losses), 5)
        for t in wins:
            self.assertEqual(t["fee_c"], 2)
            self.assertEqual(t["pnl_c"], 100 - 50 - 2)  # +48
        for t in losses:
            self.assertEqual(t["fee_c"], 2)
            self.assertEqual(t["pnl_c"], -50 - 2)  # -52
        edge = 0.75 - (50 + 2) / 100.0
        self.assertAlmostEqual(edge, 0.23)
        for t in result["trades"]:
            self.assertAlmostEqual(t["edge"], edge)
            self.assertEqual(t["model_prob"], 0.75)
            self.assertEqual(t["trade_prob"], 0.75)

    def test_chronological_70_30_split(self):
        result = self._evaluate()
        train_trades = [t for t in result["trades"] if t["split"] == "train"]
        val_trades = [t for t in result["trades"] if t["split"] == "validation"]
        self.assertEqual(len(train_trades), 7)
        self.assertEqual(len(val_trades), 3)
        self.assertEqual({t["market_date"] for t in train_trades}, set(DATES[:7]))
        self.assertEqual({t["market_date"] for t in val_trades}, set(DATES[7:]))

    def test_train_and_validation_metrics(self):
        result = self._evaluate()
        train = result["train"]
        validation = result["validation"]

        self.assertEqual(train["n_trades"], 7)
        self.assertEqual(train["wins"], 4)
        self.assertAlmostEqual(train["roi"], (4 * 48 + 3 * -52) / (7 * 50))
        self.assertAlmostEqual(train["brier"], (4 * (0.75 - 1) ** 2 + 3 * (0.75 - 0) ** 2) / 7)

        self.assertEqual(validation["n_trades"], 3)
        self.assertEqual(validation["wins"], 1)
        self.assertAlmostEqual(validation["roi"], (1 * 48 + 2 * -52) / (3 * 50))
        self.assertAlmostEqual(validation["brier"], (1 * (0.75 - 1) ** 2 + 2 * (0.75 - 0) ** 2) / 3)

    def test_calibration_over_all_observations_not_just_trades(self):
        result = self._evaluate()
        calibration = result["calibration"]
        self.assertEqual(len(calibration), 10)

        bin_075 = next(b for b in calibration if b["bin_lo"] <= 0.75 < b["bin_hi"])
        self.assertEqual(bin_075["count"], 10)
        self.assertAlmostEqual(bin_075["avg_predicted"], 0.75)
        self.assertAlmostEqual(bin_075["realized_freq"], 0.5)

        bin_025 = next(b for b in calibration if b["bin_lo"] <= 0.25 < b["bin_hi"])
        self.assertEqual(bin_025["count"], 10)
        self.assertAlmostEqual(bin_025["avg_predicted"], 0.25)
        self.assertAlmostEqual(bin_025["realized_freq"], 0.5)

        empty_bins = [b for b in calibration if b["bin_lo"] not in (0.7000000000000001, 0.2)]
        # every other bin should be empty
        nonzero = [b for b in calibration if b["count"] > 0]
        self.assertEqual(len(nonzero), 2)

    def test_high_so_far_and_hours_to_peak_passed_to_model(self):
        self._evaluate()
        first_call = self.captured_calls[0]
        forecast_high_f, high_so_far_f, hours_to_peak = first_call
        self.assertEqual(forecast_high_f, 88.0)
        self.assertEqual(high_so_far_f, 78.0)  # excludes the 12:00 (post-decision) obs
        self.assertEqual(hours_to_peak, backtest.TYPICAL_PEAK_HOUR_LOCAL - DECISION_HOUR)

    def test_window_and_event_day_count(self):
        result = self._evaluate()
        self.assertEqual(result["window_start"], DATES[0])
        self.assertEqual(result["window_end"], DATES[-1])
        self.assertEqual(result["n_event_days"], 10)

    def test_write_result_inserts_backtest_results_row(self):
        result = self._evaluate()
        backtest.write_result(self.conn, result)
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM backtest_results WHERE city = ? AND strategy = 'hotscout_v1'", (CITY,)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["decision_hour_local"], DECISION_HOUR)
        self.assertAlmostEqual(row["edge_threshold"], THRESHOLD)
        self.assertEqual(row["n_trades"], 3)
        self.assertEqual(row["wins"], 1)
        self.assertAlmostEqual(row["roi"], result["validation"]["roi"])
        self.assertAlmostEqual(row["brier"], result["validation"]["brier"])
        self.assertEqual(row["window_start"], DATES[0])
        self.assertEqual(row["window_end"], DATES[-1])

        payload = json.loads(row["payload_json"])
        self.assertEqual(len(payload["trades"]), 10)
        self.assertEqual(payload["train"]["n_trades"], 7)
        self.assertEqual(payload["validation"]["n_trades"], 3)
        self.assertEqual(len(payload["calibration"]), 10)
        self.assertEqual(payload["n_event_days"], 10)

    def test_incomplete_data_is_skipped(self):
        # An event-day with no forecast row should be silently skipped.
        conn = _build_fixture_conn()
        conn.execute(
            "INSERT INTO kalshi_events (city, market_date, event_ticker, close_ts, "
            "settled_bucket_ticker, settled_bucket_label, buckets_json) VALUES (?,?,?,?,?,?,?)",
            (CITY, "2024-06-20", "EVT-2024-06-20", 0, "BLOW", "",
             json.dumps([{"ticker": "BLOW", "label": "x", "low_f": None, "high_f": 89, "result": "yes"}])),
        )
        conn.commit()
        result = backtest.evaluate(
            conn, CITY, DECISION_HOUR, THRESHOLD,
            bucket_probabilities_fn=self.fake_model,
            load_residual_dist_fn=_fake_load_residual_dist,
        )
        # No forecast/candles for 2024-06-20 -> it must not appear in the window.
        self.assertEqual(result["n_event_days"], 10)
        conn.close()


class HotscoutMetricsTests(unittest.TestCase):
    def test_win_rate_roi_brier_empty(self):
        self.assertEqual(metrics.win_rate([]), 0.0)
        self.assertEqual(metrics.roi([]), 0.0)
        self.assertEqual(metrics.brier([]), 0.0)

    def test_win_rate(self):
        trades = [{"won": True}, {"won": False}, {"won": True}]
        self.assertAlmostEqual(metrics.win_rate(trades), 2 / 3)

    def test_roi(self):
        trades = [
            {"entry_price_c": 50, "pnl_c": 32},
            {"entry_price_c": 50, "pnl_c": -68},
        ]
        self.assertAlmostEqual(metrics.roi(trades), (32 - 68) / 100)

    def test_brier(self):
        pairs = [(0.75, 1.0), (0.75, 0.0)]
        self.assertAlmostEqual(metrics.brier(pairs), ((0.25) ** 2 + (0.75) ** 2) / 2)

    def test_calibration_bins_shapes_and_empty_bins(self):
        bins = metrics.calibration_bins([(0.05, 1.0)], n_bins=10)
        self.assertEqual(len(bins), 10)
        self.assertEqual(bins[0]["count"], 1)
        self.assertEqual(bins[0]["avg_predicted"], 0.05)
        self.assertEqual(bins[0]["realized_freq"], 1.0)
        for b in bins[1:]:
            self.assertEqual(b["count"], 0)
            self.assertIsNone(b["avg_predicted"])
            self.assertIsNone(b["realized_freq"])

    def test_calibration_bins_prob_one_lands_in_last_bin(self):
        bins = metrics.calibration_bins([(1.0, 1.0)], n_bins=10)
        self.assertEqual(bins[-1]["count"], 1)


class HotscoutBacktestCliTests(unittest.TestCase):
    def test_help_exits_zero(self):
        with self.assertRaises(SystemExit) as ctx:
            backtest.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)


class BacktestEnginePluggableFeeTests(unittest.TestCase):
    """backtest/engine.py's run() gained an optional fee_fn parameter; the
    default (no fee_fn passed) must reproduce the exact prior flat-fee
    behavior, and a real fee schedule must be usable as an override."""

    def _dataset(self):
        event = {
            "event_ticker": "E1",
            "open_ts": 0,
            "close_ts": 100,
            "buckets": [
                {"ticker": "T1", "label": "L1", "result": "yes"},
                {"ticker": "T2", "label": "L2", "result": "no"},
            ],
        }
        candle = {"end_period_ts": 0, "yes_ask": {"close_dollars": 0.5}, "yes_bid": {"close_dollars": 0.45}}
        bucket_candles = {"T1": [candle], "T2": [candle]}
        return [{"event": event, "bucket_candles": bucket_candles}]

    def _strategy(self, event, buckets, idx):
        return {"side": "yes", "bucket": "T1", "limit_price": 50}

    def test_default_fee_unchanged(self):
        from backtest.engine import run
        report = run(self._dataset(), self._strategy, contracts=1)
        self.assertEqual(len(report.trades), 1)
        # gross = (100-50)*1 = 50; default flat fee = int(1.5*1) = 1
        self.assertEqual(report.trades[0].net_cents, 49)

    def test_pluggable_real_fee(self):
        from backtest.engine import run
        report = run(self._dataset(), self._strategy, contracts=1, fee_fn=kalshi_fee_cents)
        self.assertEqual(len(report.trades), 1)
        # gross = 50; real fee = kalshi_fee_cents(50, 1) = 2
        self.assertEqual(report.trades[0].net_cents, 48)


if __name__ == "__main__":
    unittest.main()
