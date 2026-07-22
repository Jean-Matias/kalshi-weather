import datetime
import sqlite3
import unittest

from hotscout import calibration, db
from hotscout.model import bucket_probabilities, edge_after_fees


def _buckets():
    return [
        {"ticker": "B1", "label": "80 or below", "low_f": None, "high_f": 80},
        {"ticker": "B2", "label": "81-85", "low_f": 81, "high_f": 85},
        {"ticker": "B3", "label": "86-90", "low_f": 86, "high_f": 90},
        {"ticker": "B4", "label": "91 or above", "low_f": 91, "high_f": None},
    ]


class BucketProbabilitiesTests(unittest.TestCase):
    def test_probs_sum_to_one(self):
        residual_dist = {"residuals_f": [-2.0, -1.0, 0.0, 1.0, 2.0], "n": 5, "blend_weight": 1.0}
        probs = bucket_probabilities(residual_dist, 83.0, _buckets())
        total = sum(p["prob"] for p in probs)
        self.assertAlmostEqual(total, 1.0, places=9)

    def test_degenerate_residuals_put_mass_in_forecast_bucket(self):
        residual_dist = {"residuals_f": [0.0] * 20, "n": 20, "blend_weight": 1.0}
        probs = bucket_probabilities(residual_dist, 83.0, _buckets())
        prob_map = {p["ticker"]: p["prob"] for p in probs}
        self.assertGreater(prob_map["B2"], 0.99)

    def test_open_ended_buckets_cover_tails(self):
        residual_dist = {"residuals_f": [-30.0, 0.0, 30.0], "n": 3, "blend_weight": 1.0}
        probs = bucket_probabilities(residual_dist, 83.0, _buckets())
        prob_map = {p["ticker"]: p["prob"] for p in probs}
        self.assertAlmostEqual(prob_map["B1"], 1.0 / 3, places=6)
        self.assertAlmostEqual(prob_map["B4"], 1.0 / 3, places=6)
        total = sum(p["prob"] for p in probs)
        self.assertAlmostEqual(total, 1.0, places=9)

    def test_truncation_zeroes_out_buckets_below_high_so_far(self):
        residual_dist = {"residuals_f": [-2.0, -1.0, 0.0, 1.0, 2.0], "n": 5, "blend_weight": 1.0}
        probs = bucket_probabilities(residual_dist, 83.0, _buckets(), high_so_far_f=90.0)
        prob_map = {p["ticker"]: p["prob"] for p in probs}
        self.assertLess(prob_map["B1"], 1e-9)
        self.assertLess(prob_map["B2"], 1e-9)

    def test_monotonic_raising_forecast_shifts_mass_upward(self):
        residual_dist = {"residuals_f": [-2.0, -1.0, 0.0, 1.0, 2.0], "n": 5, "blend_weight": 1.0}
        low_probs = bucket_probabilities(residual_dist, 82.0, _buckets())
        high_probs = bucket_probabilities(residual_dist, 88.0, _buckets())
        low_map = {p["ticker"]: p["prob"] for p in low_probs}
        high_map = {p["ticker"]: p["prob"] for p in high_probs}
        self.assertGreater(high_map["B3"] + high_map["B4"], low_map["B3"] + low_map["B4"])

    def test_blend_after_peak_collapses_toward_high_so_far(self):
        residual_dist = {"residuals_f": [-5.0, 0.0, 5.0], "n": 3, "blend_weight": 0.0}
        probs = bucket_probabilities(
            residual_dist, 83.0, _buckets(), high_so_far_f=83.0, hours_to_peak=-1
        )
        prob_map = {p["ticker"]: p["prob"] for p in probs}
        # blend_weight=0.0 -> pure point mass at high_so_far_f (83 -> bucket B2)
        self.assertGreater(prob_map["B2"], 0.99)

    def test_empty_residuals_still_normalizes(self):
        residual_dist = {"residuals_f": [], "n": 0, "blend_weight": 1.0}
        probs = bucket_probabilities(residual_dist, 83.0, _buckets())
        total = sum(p["prob"] for p in probs)
        self.assertAlmostEqual(total, 1.0, places=9)


class EdgeAfterFeesTests(unittest.TestCase):
    def test_positive_edge_when_model_prob_beats_price_plus_fee(self):
        edge = edge_after_fees(0.80, 50)
        # fee at 50c/1 contract = ceil(7*50*50/10000) = 2c
        self.assertAlmostEqual(edge, 0.80 - 0.52, places=9)

    def test_negative_edge_when_price_exceeds_model_prob(self):
        edge = edge_after_fees(0.10, 90)
        self.assertLess(edge, 0)


class CalibrationEndToEndTests(unittest.TestCase):
    CITY = "Phoenix"
    DECISION_HOUR = 11

    def _seed(self, conn):
        base = datetime.date(2023, 6, 1)
        for i in range(40):
            d = base + datetime.timedelta(days=i)
            date_str = d.isoformat()
            forecast_high = 100.0 + (i % 5) - 2
            cli_high = forecast_high + ((-1) ** i) * 1.0
            conn.execute(
                "INSERT INTO forecast_daily(city, date, lead_days, forecast_high_f, model, source) "
                "VALUES (?, ?, 0, ?, 'best_match', 'test')",
                (self.CITY, date_str, forecast_high),
            )
            conn.execute(
                "INSERT INTO cli_daily(city, date, cli_high_f, source, raw_json) "
                "VALUES (?, ?, ?, 'test', '{}')",
                (self.CITY, date_str, cli_high),
            )
            morning_temp = cli_high - 5.0
            conn.execute(
                "INSERT INTO obs_hourly(city, date, ts_local, temp_f, source) VALUES (?, ?, ?, ?, 'test')",
                (self.CITY, date_str, f"{date_str} 09:00:00", morning_temp),
            )
            conn.execute(
                "INSERT INTO obs_hourly(city, date, ts_local, temp_f, source) VALUES (?, ?, ?, ?, 'test')",
                (self.CITY, date_str, f"{date_str} 11:00:00", morning_temp + 1.0),
            )
        conn.commit()

    def test_fit_then_load_then_bucket_probabilities(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            db.init(conn)
            self._seed(conn)

            sample_counts = calibration.fit(conn, cities=[self.CITY])
            self.assertIn(self.CITY, sample_counts)
            self.assertGreater(sample_counts[self.CITY], 0)

            residual_dist = calibration.load_residual_dist(
                conn, self.CITY, self.DECISION_HOUR, month=6
            )
            self.assertIsNotNone(residual_dist)
            self.assertIn("residuals_f", residual_dist)
            self.assertIn("blend_weight", residual_dist)
            self.assertIn("remaining_rise_f", residual_dist)

            probs = bucket_probabilities(residual_dist, 100.0, _buckets())
            self.assertAlmostEqual(sum(p["prob"] for p in probs), 1.0, places=9)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
