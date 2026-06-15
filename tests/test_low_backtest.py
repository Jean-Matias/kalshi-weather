import json
import tempfile
import unittest
from pathlib import Path


class LowBacktestSpecTests(unittest.TestCase):
    def test_load_low_market_specs_reads_low_weather_config(self):
        from backtest.market_specs import load_low_market_specs

        specs = load_low_market_specs()
        las_vegas = next(spec for spec in specs if spec.city == "Las Vegas")

        self.assertEqual(las_vegas.market_type, "low")
        self.assertEqual(las_vegas.series_ticker, "KXLOWTLV")
        self.assertEqual(las_vegas.station_id, "KLAS")
        self.assertEqual(las_vegas.cli_product, "CLILAS")
        self.assertEqual(las_vegas.timezone, "America/Los_Angeles")


class LowKalshiDataTests(unittest.TestCase):
    def test_ensure_cached_uses_historical_markets_fallback_and_reuses_candles(self):
        from backtest.low_data import ensure_cached, load_dataset

        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            calls = []

            def fake_fetch(path, query=""):
                calls.append((path, query))
                if path == "/markets":
                    return {"markets": []}
                if path == "/historical/markets":
                    return {
                        "markets": [
                            {
                                "event_ticker": "KXLOWTLV-26JUN01",
                                "ticker": "KXLOWTLV-26JUN01-B58.5",
                                "open_time": "2026-05-31T14:00:00Z",
                                "close_time": "2026-06-02T08:00:00Z",
                                "result": "yes",
                                "strike_type": "between",
                                "floor_strike": 58,
                                "cap_strike": 59,
                            },
                            {
                                "event_ticker": "KXLOWTLV-26JUN01",
                                "ticker": "KXLOWTLV-26JUN01-T60",
                                "open_time": "2026-05-31T14:00:00Z",
                                "close_time": "2026-06-02T08:00:00Z",
                                "result": "no",
                                "strike_type": "greater",
                                "floor_strike": 59,
                            },
                        ],
                    }
                if path.endswith("/candlesticks"):
                    return {
                        "candlesticks": [
                            {
                                "end_period_ts": 1780332000,
                                "yes_ask": {"close_dollars": "0.42"},
                                "yes_bid": {"close_dollars": "0.39"},
                            }
                        ]
                    }
                raise AssertionError(f"unexpected fetch {path}")

            first = ensure_cached("Las Vegas", target_events=1, cache_root=cache_root, fetch_json=fake_fetch, sleep_seconds=0)
            first_candle_calls = [call for call in calls if call[0].endswith("/candlesticks")]
            second = ensure_cached("Las Vegas", target_events=1, cache_root=cache_root, fetch_json=fake_fetch, sleep_seconds=0)
            second_candle_calls = [call for call in calls if call[0].endswith("/candlesticks")]
            dataset = load_dataset("Las Vegas", cache_root=cache_root)

            self.assertEqual(first["total_events"], 1)
            self.assertEqual(first["newly_fetched_candle_sets"], 2)
            self.assertEqual(second["newly_fetched_candle_sets"], 0)
            self.assertEqual(len(first_candle_calls), len(second_candle_calls))
            self.assertEqual(dataset[0]["event"]["event_ticker"], "KXLOWTLV-26JUN01")
            self.assertEqual(dataset[0]["event"]["buckets"][0]["label"], "58F to 59F")


class LowWeatherCacheTests(unittest.TestCase):
    def test_select_low_settlement_prefers_date_matched_cli_and_rejects_stale_cli(self):
        from backtest.low_weather import select_low_settlement

        archive_day = {
            "summary": {"date": "2026-06-01", "low_f": 61.4},
            "source": "open-meteo-archive",
        }

        matched = select_low_settlement(
            {"cli_low_f": 58, "cli_report_date": "2026-06-01"},
            archive_day,
            "2026-06-01",
        )
        stale = select_low_settlement(
            {"cli_low_f": 57, "cli_report_date": "2026-05-31"},
            archive_day,
            "2026-06-01",
        )

        self.assertEqual(matched["actual_low_f"], 58)
        self.assertEqual(matched["actual_source"], "nws_cli")
        self.assertEqual(stale["actual_low_f"], 61.4)
        self.assertEqual(stale["actual_source"], "open-meteo-archive")
        self.assertIn("Stale CLI", stale["warnings"][0])


class LowReplayTests(unittest.TestCase):
    def test_run_low_backtest_truncates_prices_before_strategy_call(self):
        from backtest.low_engine import run_low_backtest
        from backtest.low_strategies import normalized_trade

        seen_lengths = []
        dataset = [
            {
                "city": "Las Vegas",
                "event": {
                    "event_ticker": "KXLOWTLV-26JUN01",
                    "open_ts": 1780293600,
                    "buckets": [
                        {"ticker": "A", "label": "58F to 59F", "result": "yes"},
                        {"ticker": "B", "label": "60F or above", "result": "no"},
                    ],
                },
                "bucket_candles": {
                    "A": [
                        {"end_period_ts": 1, "yes_ask": {"close_dollars": "0.20"}},
                        {"end_period_ts": 2, "yes_ask": {"close_dollars": "0.30"}},
                        {"end_period_ts": 3, "yes_ask": {"close_dollars": "0.99"}},
                    ],
                    "B": [
                        {"end_period_ts": 1, "yes_ask": {"close_dollars": "0.80"}},
                        {"end_period_ts": 2, "yes_ask": {"close_dollars": "0.70"}},
                        {"end_period_ts": 3, "yes_ask": {"close_dollars": "0.01"}},
                    ],
                },
            }
        ]

        def strategy(event, buckets, weather_history):
            seen_lengths.extend(len(bucket["prices"]) for bucket in buckets)
            return normalized_trade("yes", "A", reason="test", features={"target_low_f": 58})

        result = run_low_backtest(dataset, strategy, weather_loader=lambda event: {}, decision_hour=1, contracts=1)

        self.assertEqual(seen_lengths, [2, 2])
        self.assertEqual(result.report.n, 1)
        self.assertEqual(result.report.trades[0].limit_price, 30)
        self.assertEqual(result.report.trades[0].won, True)

    def test_low_weather_confirmed_ignores_observations_after_decision_time(self):
        from backtest.low_strategies import low_weather_confirmed

        event = {
            "event_ticker": "KXLOWTLV-26JUN01",
            "decision_local_iso": "2026-05-31T12:00",
        }
        buckets = [
            {"ticker": "WARM", "label": "74F to 75F", "prices": [55]},
            {"ticker": "COLD", "label": "58F to 59F", "prices": [70]},
        ]
        weather_history = {
            "2026-05-30": {
                "summary": {"low_f": 74.0},
                "observations": [
                    {"timestamp": "2026-05-30T06:00", "temp_f": 74.0},
                    {"timestamp": "2026-05-30T12:00", "temp_f": 90.0},
                ],
            },
            "2026-05-31": {
                "summary": {"low_f": 58.0},
                "observations": [
                    {"timestamp": "2026-05-31T11:00", "temp_f": 89.0},
                    {"timestamp": "2026-05-31T23:00", "temp_f": 58.0},
                ],
            },
        }

        decision = low_weather_confirmed(lookback_days=1, projection_hours=1)(event, buckets, weather_history)

        self.assertEqual(decision["skip_reason"], "weather target disagrees with market favorite")
        self.assertEqual(decision["features"]["target_bucket"], "WARM")

    def test_low_weather_prediction_trades_weather_bucket_without_favorite_confirmation(self):
        from backtest.low_strategies import low_weather_prediction

        event = {
            "event_ticker": "KXLOWTLV-26JUN01",
            "decision_local_iso": "2026-05-31T12:00",
        }
        buckets = [
            {"ticker": "WEATHER", "label": "74F to 75F", "prices": [45]},
            {"ticker": "FAVORITE", "label": "58F to 59F", "prices": [70]},
        ]
        weather_history = {
            "2026-05-30": {
                "summary": {"low_f": 74.0},
                "observations": [
                    {"timestamp": "2026-05-30T06:00", "temp_f": 74.0},
                    {"timestamp": "2026-05-31T11:00", "temp_f": 89.0},
                ],
            }
        }

        decision = low_weather_prediction(lookback_days=1, projection_hours=1)(event, buckets, weather_history)

        self.assertIsNone(decision["skip_reason"])
        self.assertEqual(decision["side"], "yes")
        self.assertEqual(decision["bucket"], "WEATHER")
        self.assertEqual(decision["features"]["favorite_bucket"], "FAVORITE")

    def test_low_fade_favorite_buys_no_on_favorite_inside_band(self):
        from backtest.low_strategies import low_fade_favorite

        event = {"event_ticker": "KXLOWTSATX-26JUN01"}
        buckets = [
            {"ticker": "COLD", "label": "58F to 59F", "prices": [20]},
            {"ticker": "FAVORITE", "label": "60F to 61F", "prices": [45]},
            {"ticker": "WARM", "label": "62F or above", "prices": [30]},
        ]

        decision = low_fade_favorite(min_price=20, max_price=60)(event, buckets, {})

        self.assertIsNone(decision["skip_reason"])
        self.assertEqual(decision["side"], "no")
        self.assertEqual(decision["bucket"], "FAVORITE")
        self.assertEqual(decision["features"]["favorite_price"], 45)

    def test_low_fade_favorite_skips_when_favorite_price_outside_band(self):
        from backtest.low_strategies import low_fade_favorite

        event = {"event_ticker": "KXLOWTSATX-26JUN01"}
        buckets = [
            {"ticker": "COLD", "label": "58F to 59F", "prices": [10]},
            {"ticker": "FAVORITE", "label": "60F to 61F", "prices": [75]},
        ]

        decision = low_fade_favorite(min_price=20, max_price=60)(event, buckets, {})

        self.assertEqual(decision["skip_reason"], "favorite price outside fade band")

    def test_render_low_backtest_report_includes_required_sections(self):
        from backtest.engine import Report, Trade
        from backtest.low_engine import LowBacktestResult
        from backtest.low_report import render_low_backtest_report

        result = LowBacktestResult(
            label="low_persistence",
            report=Report(
                label="low_persistence",
                trades=[
                    Trade(
                        event_ticker="KXLOWTLV-26JUN01",
                        open_ts=1780293600,
                        bucket="A",
                        side="yes",
                        limit_price=30,
                        won=True,
                        net_cents=68,
                    )
                ],
            ),
            total_event_days=2,
            skipped=[{"city": "Las Vegas", "reason": "no prior lows"}],
            city_results={"Las Vegas": Report(label="Las Vegas")},
        )

        markdown = render_low_backtest_report([result])

        self.assertIn("Research-only", markdown)
        self.assertIn("Win rate", markdown)
        self.assertIn("EV/trade", markdown)
        self.assertIn("Worst drawdown", markdown)
        self.assertIn("Stability", markdown)
        self.assertIn("Skip reasons", markdown)


if __name__ == "__main__":
    unittest.main()
