"""hotscout database schema and frozen interface contracts.

All downstream hotscout modules (data pullers, model, backtest, dashboard)
import ONLY from `hotscout.config`, `hotscout.schema`, `hotscout.db`, and
`hotscout.fees`. The shapes documented below are FROZEN — do not change them
without updating every consumer.

Tables
------
cli_daily          -- one row per (city, date): the official NWS CLI daily high.
forecast_daily     -- one row per (city, date, lead_days, model): a forecast made
                      `lead_days` days before `date`, from a given model/source.
obs_hourly         -- one row per (city, ts_local, source): raw hourly observations,
                      used to compute "high so far" / heating rate intraday.
kalshi_events      -- one row per Kalshi daily market (city, market_date): the
                      event ticker, close time, settlement bucket, and the
                      bucket definitions as of settlement.
kalshi_candles     -- one row per (market_ticker, ts): time-series order book /
                      trade snapshots for a single bucket market within an event.
residual_models    -- one row per (city, decision_hour_local, month_center):
                      fitted forecast-error (residual) distribution parameters.
backtest_results   -- one row per backtest run: aggregate performance of a
                      strategy over a historical window.
picks              -- one row per recommended trade (live or backtested),
                      with realized outcome/pnl once known.
forecast_snapshots -- one row per (city, date, decision_hour_local): the live
                      forecast_high_f as first fetched at board-build time.
                      Provably pre-decision forecasts, accumulated so future
                      backtests can settle the lead-0-vs-lead-1 freshness
                      question with real decision-time data.

Frozen JSON / interface contracts
----------------------------------
Bucket = {"ticker": str, "label": str, "low_f": float|None, "high_f": float|None}
    # None = open-ended; inclusive integer-F bounds

buckets_json (kalshi_events) = JSON list[Bucket + {"result": "yes"|"no"|None}]

ResidualDist = {"residuals_f": list[float], "n": int, "blend_weight": float}

model.bucket_probabilities(residual_dist, forecast_high_f, buckets, high_so_far_f=None, hours_to_peak=None) -> list[{"ticker": str, "prob": float}]
    # probs sum to 1.0

calibration.load_residual_dist(conn, city, decision_hour_local, month) -> ResidualDist

backtest decision rule:
    edge_yes = model_prob - (yes_ask_c + fee_cents(yes_ask_c)) / 100
    recommend only if:
        edge > threshold
        AND validation n_trades >= MIN_VALIDATION_TRADES
        AND validation roi > 0

BoardPayload = {
    "generated_at": str,
    "cities": [
        {
            "city": str,
            "market_date": str,
            "forecast_high_f": float,
            "high_so_far_f": float | None,
            "heating_rate": float | None,
            "buckets": [
                {
                    "ticker": str,
                    "label": str,
                    "model_prob": float,
                    "yes_bid_c": int,
                    "yes_ask_c": int,
                    "edge_after_fees": float,
                    "recommendation": str,
                    "confidence": float,
                }
            ],
            "backtest_badge": {
                "win_rate": float,
                "roi": float,
                "n_trades": int,
                "window": str,
                "validated": bool,
            },
            "warnings": [str],
        }
    ],
}
"""

DDL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS cli_daily(
        city TEXT,
        date TEXT,
        cli_high_f REAL,
        source TEXT,
        raw_json TEXT,
        UNIQUE(city, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS forecast_daily(
        city TEXT,
        date TEXT,
        lead_days INTEGER,
        forecast_high_f REAL,
        model TEXT,
        source TEXT,
        UNIQUE(city, date, lead_days, model)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS obs_hourly(
        city TEXT,
        date TEXT,
        ts_local TEXT,
        temp_f REAL,
        source TEXT,
        UNIQUE(city, ts_local, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kalshi_events(
        city TEXT,
        market_date TEXT,
        event_ticker TEXT UNIQUE,
        close_ts INTEGER,
        settled_bucket_ticker TEXT,
        settled_bucket_label TEXT,
        buckets_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kalshi_candles(
        event_ticker TEXT,
        market_ticker TEXT,
        ts INTEGER,
        yes_bid_c INTEGER,
        yes_ask_c INTEGER,
        price_c INTEGER,
        volume INTEGER,
        UNIQUE(market_ticker, ts)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS residual_models(
        city TEXT,
        decision_hour_local INTEGER,
        month_center INTEGER,
        params_json TEXT,
        n_samples INTEGER,
        fitted_at TEXT,
        UNIQUE(city, decision_hour_local, month_center)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_results(
        city TEXT,
        strategy TEXT,
        decision_hour_local INTEGER,
        edge_threshold REAL,
        n_trades INTEGER,
        wins INTEGER,
        roi REAL,
        brier REAL,
        window_start TEXT,
        window_end TEXT,
        payload_json TEXT,
        created_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS forecast_snapshots(
        city TEXT,
        date TEXT,
        decision_hour_local INTEGER,
        captured_at TEXT,
        forecast_high_f REAL,
        source TEXT,
        UNIQUE(city, date, decision_hour_local)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS picks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city TEXT,
        market_date TEXT,
        decision_hour_local INTEGER,
        market_ticker TEXT,
        side TEXT,
        model_prob REAL,
        market_price_c INTEGER,
        edge_after_fees REAL,
        recommended_at TEXT,
        outcome TEXT,
        pnl_c INTEGER
    )
    """,
]
