"""Look-ahead protections in the hotscout backtest: with
MIN_FORECAST_LEAD_DAYS=1 (the --min-forecast-lead 1 stress test) trades and
residual fitting must only use forecasts issued at-or-before the decision
hour (lead_days >= 1); walk-forward folds must never fit residuals on dates
inside (or after) the fold month regardless of lead policy."""

import json
import sqlite3
import unittest
from unittest import mock

from hotscout import backtest, calibration, db

CITY = "Las Vegas"
DECISION_HOUR = 11
THRESHOLD = 0.05

# Two calendar months so walk_forward produces two folds.
JUNE_DATES = [f"2024-06-{d:02d}" for d in range(1, 6)]
JULY_DATES = [f"2024-07-{d:02d}" for d in range(1, 6)]
DATES = JUNE_DATES + JULY_DATES

# A deliberately absurd lead-0 forecast: if any code path picks it up, the
# captured forecast_high_f below makes the test fail loudly.
POISON_LEAD0_HIGH = 200.0
LEAD1_HIGH = 88.0


def _fake_bucket_probabilities_factory(captured):
    def fake(residual_dist, forecast_high_f, buckets, high_so_far_f=None, hours_to_peak=None):
        captured.append(forecast_high_f)
        table = {"BLOW": 0.75, "BHIGH": 0.25}
        return [{"ticker": b["ticker"], "prob": table[b["ticker"]]} for b in buckets]
    return fake


def _fake_load_residual_dist(conn, city, decision_hour_local, month):
    return {"residuals_f": [0.0], "n": 1, "blend_weight": 1.0}


def _build_fixture_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init(conn)
    for i, date in enumerate(DATES):
        event_ticker = f"EVT-{date}"
        blow_result = "yes" if i % 2 == 0 else "no"
        buckets_json = json.dumps([
            {"ticker": "BLOW", "label": "89 or below", "low_f": None, "high_f": 89, "result": blow_result},
            {"ticker": "BHIGH", "label": "90 or above", "low_f": 90, "high_f": None,
             "result": "no" if blow_result == "yes" else "yes"},
        ])
        conn.execute(
            "INSERT INTO kalshi_events (city, market_date, event_ticker, close_ts, "
            "settled_bucket_ticker, settled_bucket_label, buckets_json) VALUES (?,?,?,?,?,?,?)",
            (CITY, date, event_ticker, 0, "BLOW", "", buckets_json),
        )
        # Poisoned same-day forecast plus a legitimate day-ahead one.
        conn.execute(
            "INSERT INTO forecast_daily (city, date, lead_days, forecast_high_f, model, source) "
            "VALUES (?,?,?,?,?,?)",
            (CITY, date, 0, POISON_LEAD0_HIGH, "ncep_nbm_conus", "test"),
        )
        conn.execute(
            "INSERT INTO forecast_daily (city, date, lead_days, forecast_high_f, model, source) "
            "VALUES (?,?,?,?,?,?)",
            (CITY, date, 1, LEAD1_HIGH, "ncep_nbm_conus", "test"),
        )
        decision_ts = backtest._decision_ts_utc(CITY, date, DECISION_HOUR)
        for ticker, (yes_bid_c, yes_ask_c) in {"BLOW": (45, 50), "BHIGH": (30, 35)}.items():
            conn.execute(
                "INSERT INTO kalshi_candles (event_ticker, market_ticker, ts, yes_bid_c, yes_ask_c, price_c, volume) "
                "VALUES (?,?,?,?,?,?,?)",
                (event_ticker, ticker, decision_ts, yes_bid_c, yes_ask_c, yes_ask_c - 2, 10),
            )
    conn.commit()
    return conn


class ForecastLeadSelectionTests(unittest.TestCase):
    def setUp(self):
        self.conn = _build_fixture_conn()

    def tearDown(self):
        self.conn.close()

    def test_default_lead_policy_is_same_day(self):
        # Default (lead 0): the same-day archive forecast is used, matching
        # the live dashboard's information set.
        self.assertEqual(backtest.MIN_FORECAST_LEAD_DAYS, 0)
        self.assertEqual(
            backtest._forecast_high_f(self.conn, CITY, DATES[0]), POISON_LEAD0_HIGH
        )

    def test_stress_mode_trades_never_use_lead0_forecast(self):
        captured = []
        with mock.patch.object(backtest, "MIN_FORECAST_LEAD_DAYS", 1):
            result = backtest.evaluate(
                self.conn, CITY, DECISION_HOUR, THRESHOLD,
                bucket_probabilities_fn=_fake_bucket_probabilities_factory(captured),
                load_residual_dist_fn=_fake_load_residual_dist,
            )
        self.assertGreater(len(result["trades"]), 0)
        self.assertTrue(all(f == LEAD1_HIGH for f in captured))

    def test_stress_mode_forecast_high_f_requires_min_lead(self):
        conn = self.conn
        conn.execute(
            "INSERT INTO forecast_daily (city, date, lead_days, forecast_high_f, model, source) "
            "VALUES (?,?,?,?,?,?)",
            (CITY, "2024-08-01", 0, POISON_LEAD0_HIGH, "ncep_nbm_conus", "test"),
        )
        with mock.patch.object(backtest, "MIN_FORECAST_LEAD_DAYS", 1):
            self.assertEqual(backtest._forecast_high_f(conn, CITY, DATES[0]), LEAD1_HIGH)
            # A date with only a lead-0 row must be skipped entirely.
            self.assertIsNone(backtest._forecast_high_f(conn, CITY, "2024-08-01"))

    def test_residual_maps_respect_min_lead(self):
        forecast_by_date = calibration._select_forecast_by_date(
            self.conn, CITY, min_lead_days=1
        )
        self.assertTrue(all(v == LEAD1_HIGH for v in forecast_by_date.values()))
        # Default (live) behavior still sees the lead-0 rows.
        live_map = calibration._select_forecast_by_date(self.conn, CITY)
        self.assertTrue(all(v == POISON_LEAD0_HIGH for v in live_map.values()))


class WalkForwardTests(unittest.TestCase):
    def setUp(self):
        self.conn = _build_fixture_conn()

    def tearDown(self):
        self.conn.close()

    def test_folds_are_monthly_and_pooled_matches(self):
        wf = backtest.walk_forward(
            self.conn, CITY, DECISION_HOUR, THRESHOLD,
            bucket_probabilities_fn=_fake_bucket_probabilities_factory([]),
        )
        self.assertEqual([f["month"] for f in wf["folds"]], ["2024-06", "2024-07"])
        self.assertEqual(
            wf["pooled"]["n_trades"], sum(f["n_trades"] for f in wf["folds"])
        )

    def test_fold_residuals_fit_strictly_before_fold_month(self):
        cutoffs = []
        real_fn = backtest._train_only_residual_dist_fn

        def spy(conn, city, cutoff_date):
            cutoffs.append(cutoff_date)
            return real_fn(conn, city, cutoff_date)

        with mock.patch.object(backtest, "_train_only_residual_dist_fn", side_effect=spy):
            backtest.walk_forward(
                self.conn, CITY, DECISION_HOUR, THRESHOLD,
                bucket_probabilities_fn=_fake_bucket_probabilities_factory([]),
            )
        self.assertEqual(cutoffs, ["2024-06-01", "2024-07-01"])

    def test_train_only_maps_exclude_cutoff_and_later(self):
        # cli rows so residuals actually form, spanning both months.
        for date in DATES:
            self.conn.execute(
                "INSERT INTO cli_daily (city, date, cli_high_f, source, raw_json) VALUES (?,?,?,?,?)",
                (CITY, date, 90.0, "test", "{}"),
            )
        self.conn.commit()
        from hotscout import calibration as cal
        fmap, cmap, _ = cal.load_date_maps(self.conn, CITY, min_lead_days=1)
        cutoff = "2024-07-01"
        fmap = {d: v for d, v in fmap.items() if d < cutoff}
        cmap = {d: v for d, v in cmap.items() if d < cutoff}
        self.assertTrue(all(d < cutoff for d in fmap))
        dist = cal.compute_residual_dist(fmap, cmap, {}, DECISION_HOUR, 6)
        self.assertEqual(dist["n"], len(JUNE_DATES))
        self.assertTrue(all(r == 90.0 - LEAD1_HIGH for r in dist["residuals_f"]))


if __name__ == "__main__":
    unittest.main()
