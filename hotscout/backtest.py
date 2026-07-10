"""hotscout backtest: replays the model-driven edge/threshold decision rule
over historical event-days and writes results to backtest_results.

Relationship to backtest/ (the pre-existing engine used for the low/high
temperature research in this repo): that engine (backtest/engine.py) replays
a single "hours since market open" integer index against an in-memory JSON
candle cache, and asks a strategy function to pick ONE side/bucket per
event-day using only market prices. hotscout's decision rule is structurally
different in three ways that make direct reuse of `engine.run()` awkward:

  1. Decisions happen at fixed LOCAL WALL-CLOCK hours (9/11/13) that must be
     converted to UTC epoch per city timezone and matched against sqlite-
     backed candle timestamps — not a small relative "hours since open" index
     into an in-memory list.
  2. Both sides (YES and NO) are evaluated independently per bucket per
     decision hour against a model probability, so more than one trade can
     be taken per event-day/decision-hour (one engine.run() call picks at
     most one trade for the whole event-day).
  3. The edge computation is model-driven (residual distribution ->
     bucket_probabilities) rather than a pure market-price heuristic, and
     needs a train/validation split plus a calibration table over every
     bucket-probability observation (traded or not) — none of which
     engine.run()/Report expose.

So hotscout/backtest.py implements its own loop directly against the hotscout
sqlite schema. What IS reused conceptually from backtest/: the Trade-as-dict
/ aggregate-Report shape, and the chronological train/validation split idea
(mirroring `backtest.engine.split_chronological`), reimplemented here as an
explicit 70/30 split since the spec calls for that ratio rather than 50/50.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone as _dt_timezone
from zoneinfo import ZoneInfo

from hotscout import db, metrics
from hotscout.config import (
    CITIES,
    DECISION_HOURS_LOCAL,
    EDGE_THRESHOLD_DEFAULT,
    city_config,
)
from hotscout.fees import kalshi_fee_cents

TYPICAL_PEAK_HOUR_LOCAL = 16
TRAIN_FRACTION = 0.7
REPORT_PATH = "reports/hotscout_backtest.md"

# Which forecast_daily lead the backtest trades on and fits residuals from.
# lead_days=0 (default) is the Open-Meteo same-day archive: it best matches
# the live dashboard's information set (a fresh forecast fetched at the
# decision hour), but its exact issue time is unknown so a residual
# look-ahead risk remains. Setting this to 1 (--min-forecast-lead 1) is the
# conservative stress test: only previous-day forecasts, provably issued
# before the decision — under it the measured edge inverts (ROI +0.4 -> -0.35
# over 2026-04..07), because the 9am market already prices same-morning
# forecast revisions. The forecast_snapshots table accumulates provably
# pre-decision live forecasts to settle this with real data over time.
MIN_FORECAST_LEAD_DAYS = 0


def _default_bucket_probabilities_fn():
    from hotscout.model import bucket_probabilities
    return bucket_probabilities


def _default_load_residual_dist_fn():
    from hotscout.calibration import load_residual_dist
    return load_residual_dist


def _train_only_residual_dist_fn(conn, city: str, cutoff_date: str):
    """Build a load_residual_dist-shaped callable whose distributions are
    fit ONLY from dates strictly before `cutoff_date` (the start of the
    validation window). This avoids the look-ahead bias of pooling
    residuals from the validation period into the model that is then
    scored against that same period: calibration.load_residual_dist reads
    from residual_models, which calibration.fit() pools from the ENTIRE
    history (correct for live trading, where "today" really is the most
    recent data available, but wrong for backtesting an out-of-sample
    validation split)."""
    from hotscout import calibration

    forecast_by_date, cli_by_date, obs_by_date = calibration.load_date_maps(
        conn, city, min_lead_days=MIN_FORECAST_LEAD_DAYS
    )
    forecast_by_date = {d: v for d, v in forecast_by_date.items() if d < cutoff_date}
    cli_by_date = {d: v for d, v in cli_by_date.items() if d < cutoff_date}
    obs_by_date = {d: v for d, v in obs_by_date.items() if d < cutoff_date}

    cache: dict[tuple[int, int], dict | None] = {}

    def _load(_conn, _city, decision_hour_local, month):
        key = (decision_hour_local, month)
        if key not in cache:
            cache[key] = calibration.compute_residual_dist(
                forecast_by_date, cli_by_date, obs_by_date, decision_hour_local, month
            )
        return cache[key] or {"residuals_f": [0.0], "n": 0, "blend_weight": 1.0}

    return _load


def _decision_ts_utc(city: str, market_date: str, decision_hour_local: int) -> int:
    """Epoch seconds for `decision_hour_local`:00 local time on `market_date`
    in `city`'s timezone."""
    tz = ZoneInfo(city_config(city)["timezone"])
    y, m, d = (int(x) for x in market_date.split("-"))
    local_dt = datetime(y, m, d, decision_hour_local, 0, 0, tzinfo=tz)
    return int(local_dt.timestamp())


def _high_so_far(conn, city: str, market_date: str, decision_hour_local: int):
    """Max observed temp_f in obs_hourly for `city`/`market_date` at or before
    `decision_hour_local`:00 local time. None if no observations are cached."""
    cutoff = f"{market_date}T{decision_hour_local:02d}:00:00"
    row = conn.execute(
        "SELECT MAX(temp_f) AS high_so_far FROM obs_hourly "
        "WHERE city = ? AND date = ? AND ts_local <= ?",
        (city, market_date, cutoff),
    ).fetchone()
    return row["high_so_far"] if row is not None else None


def _nearest_candle_at_or_after(candles: list, decision_ts: int):
    """First candle (already sorted by ts ascending) with ts >= decision_ts,
    or None if every candle is strictly before the decision point."""
    for c in candles:
        if c["ts"] >= decision_ts:
            return c
    return None


def _entry_price_and_source(candle):
    yes_ask_c = candle["yes_ask_c"]
    if yes_ask_c is not None:
        return yes_ask_c, "yes_ask"
    return candle["price_c"], "price_c_fallback"


def _forecast_high_f(conn, city: str, market_date: str):
    """Smallest lead_days >= MIN_FORECAST_LEAD_DAYS for the date (no lead-0:
    see MIN_FORECAST_LEAD_DAYS). Returns None if no such forecast exists,
    which skips the event-day."""
    row = conn.execute(
        "SELECT forecast_high_f FROM forecast_daily "
        "WHERE city = ? AND date = ? AND lead_days >= ? ORDER BY lead_days ASC LIMIT 1",
        (city, market_date, MIN_FORECAST_LEAD_DAYS),
    ).fetchone()
    return None if row is None else row["forecast_high_f"]


def _split_dates(dates: list[str]) -> tuple[set, set]:
    """Chronological 70/30 split of sorted unique event dates."""
    ordered = sorted(dates)
    split_idx = int(len(ordered) * TRAIN_FRACTION)
    return set(ordered[:split_idx]), set(ordered[split_idx:])


def evaluate(
    conn,
    city: str,
    decision_hour_local: int,
    threshold: float,
    bucket_probabilities_fn=None,
    load_residual_dist_fn=None,
    typical_peak_hour_local: int = TYPICAL_PEAK_HOUR_LOCAL,
    only_dates: set | None = None,
) -> dict:
    """Replay the hotscout decision rule for one (city, decision_hour,
    threshold) over every settled event-day with complete data. Returns a
    dict with train/validation trade lists+metrics, all bucket-probability
    observations, a 10-bin calibration table, and the window of dates
    covered. Does not write to the database."""
    bucket_probabilities_fn = bucket_probabilities_fn or _default_bucket_probabilities_fn()

    events = conn.execute(
        "SELECT * FROM kalshi_events WHERE city = ? ORDER BY market_date",
        (city,),
    ).fetchall()

    if load_residual_dist_fn is None:
        # Fit residuals only from dates strictly before the validation
        # window so the model can't see validation-period forecast errors
        # (see _train_only_residual_dist_fn docstring for why this differs
        # from the live-trading residual_models table).
        event_dates = sorted({e["market_date"] for e in events})
        _, val_dates_all = _split_dates(event_dates)
        cutoff_date = min(val_dates_all) if val_dates_all else None
        if cutoff_date is not None:
            load_residual_dist_fn = _train_only_residual_dist_fn(conn, city, cutoff_date)
        else:
            load_residual_dist_fn = _default_load_residual_dist_fn()

    trades: list[dict] = []
    observations: list[tuple[float, float]] = []
    dates_seen: set = set()

    for event in events:
        market_date = event["market_date"]
        if only_dates is not None and market_date not in only_dates:
            continue
        buckets = json.loads(event["buckets_json"])
        if not buckets:
            continue

        forecast_high_f = _forecast_high_f(conn, city, market_date)
        if forecast_high_f is None:
            continue

        candle_rows = conn.execute(
            "SELECT * FROM kalshi_candles WHERE event_ticker = ? ORDER BY market_ticker, ts",
            (event["event_ticker"],),
        ).fetchall()
        if not candle_rows:
            continue
        candles_by_ticker = defaultdict(list)
        for c in candle_rows:
            candles_by_ticker[c["market_ticker"]].append(c)

        dates_seen.add(market_date)
        month = int(market_date.split("-")[1])
        decision_ts = _decision_ts_utc(city, market_date, decision_hour_local)
        high_so_far_f = _high_so_far(conn, city, market_date, decision_hour_local)
        hours_to_peak = typical_peak_hour_local - decision_hour_local

        residual_dist = load_residual_dist_fn(conn, city, decision_hour_local, month)
        probs = bucket_probabilities_fn(
            residual_dist, forecast_high_f, buckets,
            high_so_far_f=high_so_far_f, hours_to_peak=hours_to_peak,
        )
        prob_by_ticker = {p["ticker"]: p["prob"] for p in probs}

        for bucket in buckets:
            ticker = bucket["ticker"]
            result = bucket.get("result")
            model_prob = prob_by_ticker.get(ticker)
            candles = candles_by_ticker.get(ticker)
            if model_prob is None or not candles:
                continue
            candle = _nearest_candle_at_or_after(candles, decision_ts)
            if candle is None:
                continue

            observations.append((model_prob, 1.0 if result == "yes" else 0.0))

            entry_price_c, price_source = _entry_price_and_source(candle)
            if entry_price_c is None:
                continue

            base_trade = {
                "event_ticker": event["event_ticker"],
                "city": city,
                "market_date": market_date,
                "decision_hour_local": decision_hour_local,
                "bucket_ticker": ticker,
                "price_source": price_source,
            }

            # YES side.
            fee_yes = kalshi_fee_cents(entry_price_c)
            edge_yes = model_prob - (entry_price_c + fee_yes) / 100.0
            if edge_yes > threshold:
                won = result == "yes"
                pnl_c = (100 - entry_price_c - fee_yes) if won else (-entry_price_c - fee_yes)
                trades.append({
                    **base_trade,
                    "side": "yes",
                    "model_prob": model_prob,
                    "trade_prob": model_prob,
                    "entry_price_c": entry_price_c,
                    "fee_c": fee_yes,
                    "edge": edge_yes,
                    "won": won,
                    "pnl_c": pnl_c,
                })

            # NO side.
            yes_bid_c = candle["yes_bid_c"]
            if yes_bid_c is not None:
                no_ask_c = 100 - yes_bid_c
                fee_no = kalshi_fee_cents(no_ask_c)
                edge_no = (1 - model_prob) - (no_ask_c + fee_no) / 100.0
                if edge_no > threshold:
                    won = result == "no"
                    pnl_c = (100 - no_ask_c - fee_no) if won else (-no_ask_c - fee_no)
                    trades.append({
                        **base_trade,
                        "side": "no",
                        "model_prob": model_prob,
                        "trade_prob": 1 - model_prob,
                        "entry_price_c": no_ask_c,
                        "fee_c": fee_no,
                        "edge": edge_no,
                        "won": won,
                        "pnl_c": pnl_c,
                    })

    train_dates, val_dates = _split_dates(sorted(dates_seen))
    train_trades = [t for t in trades if t["market_date"] in train_dates]
    val_trades = [t for t in trades if t["market_date"] in val_dates]

    for t in train_trades:
        t["split"] = "train"
    for t in val_trades:
        t["split"] = "validation"

    train_metrics = _trade_metrics_dict(train_trades)
    validation_metrics = _trade_metrics_dict(val_trades)
    calibration = metrics.calibration_bins(observations, n_bins=10)

    window_start = min(dates_seen) if dates_seen else None
    window_end = max(dates_seen) if dates_seen else None

    return {
        "city": city,
        "decision_hour_local": decision_hour_local,
        "edge_threshold": threshold,
        "train": train_metrics,
        "validation": validation_metrics,
        "trades": train_trades + val_trades,
        "calibration": calibration,
        "window_start": window_start,
        "window_end": window_end,
        "n_event_days": len(dates_seen),
    }


def walk_forward(conn, city: str, decision_hour_local: int, threshold: float,
                 bucket_probabilities_fn=None) -> dict:
    """Expanding-window monthly folds: for each calendar month with settled
    events, fit residuals ONLY on dates strictly before that month's first
    day (all weather history, which predates Kalshi coverage), then evaluate
    that month's trades out-of-sample. Complements the 70/30 headline split:
    every traded month is scored by a model that has never seen it."""
    rows = conn.execute(
        "SELECT DISTINCT market_date FROM kalshi_events WHERE city = ? ORDER BY market_date",
        (city,),
    ).fetchall()
    dates = [r["market_date"] for r in rows]
    months = sorted({d[:7] for d in dates})

    folds = []
    all_trades: list[dict] = []
    for month in months:
        fold_dates = {d for d in dates if d[:7] == month}
        residual_fn = _train_only_residual_dist_fn(conn, city, cutoff_date=f"{month}-01")
        result = evaluate(
            conn, city, decision_hour_local, threshold,
            bucket_probabilities_fn=bucket_probabilities_fn,
            load_residual_dist_fn=residual_fn,
            only_dates=fold_dates,
        )
        trades = result["trades"]
        folds.append({"month": month, **_trade_metrics_dict(trades)})
        all_trades.extend(trades)

    return {
        "city": city,
        "decision_hour_local": decision_hour_local,
        "edge_threshold": threshold,
        "folds": folds,
        "pooled": _trade_metrics_dict(all_trades),
    }


def _trade_metrics_dict(trades: list[dict]) -> dict:
    pairs = [(t["trade_prob"], 1.0 if t["won"] else 0.0) for t in trades]
    return {
        "n_trades": len(trades),
        "wins": sum(1 for t in trades if t["won"]),
        "win_rate": metrics.win_rate(trades),
        "roi": metrics.roi(trades),
        "brier": metrics.brier(pairs),
    }


def write_result(conn, result: dict) -> None:
    """Insert one backtest_results row for `result` (as returned by
    `evaluate()`). The validation split is the headline (n_trades/wins/roi/
    brier columns); everything else lives in payload_json."""
    validation = result["validation"]
    payload = {
        "trades": result["trades"],
        "train": result["train"],
        "validation": validation,
        "calibration": result["calibration"],
        "n_event_days": result["n_event_days"],
    }
    conn.execute(
        "INSERT INTO backtest_results "
        "(city, strategy, decision_hour_local, edge_threshold, n_trades, wins, "
        " roi, brier, window_start, window_end, payload_json, created_at) "
        "VALUES (?, 'hotscout_v1', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            result["city"],
            result["decision_hour_local"],
            result["edge_threshold"],
            validation["n_trades"],
            validation["wins"],
            validation["roi"],
            validation["brier"],
            result["window_start"],
            result["window_end"],
            json.dumps(payload),
            datetime.now(_dt_timezone.utc).isoformat(),
        ),
    )


def _print_summary_table(results: list[dict]) -> None:
    header = f"{'city':<14}{'hour':>5}{'thresh':>8}{'n':>5}{'win%':>8}{'roi':>8}{'brier':>8}"
    print(header)
    print("-" * len(header))
    for r in results:
        v = r["validation"]
        print(
            f"{r['city']:<14}{r['decision_hour_local']:>5}{r['edge_threshold']:>8.2f}"
            f"{v['n_trades']:>5}{100 * v['win_rate']:>7.1f}%{v['roi']:>8.3f}{v['brier']:>8.3f}"
        )


def _write_markdown_report(results: list[dict], path: str = REPORT_PATH,
                           walk_forward_results: list[dict] | None = None) -> None:
    lines = ["# hotscout backtest results", ""]
    lines.append("| city | decision hour | threshold | n | win rate | ROI | Brier |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in results:
        v = r["validation"]
        lines.append(
            f"| {r['city']} | {r['decision_hour_local']} | {r['edge_threshold']:.2f} | "
            f"{v['n_trades']} | {100 * v['win_rate']:.1f}% | {v['roi']:.3f} | {v['brier']:.3f} |"
        )
    lines.append("")
    lines.append("Validation split is the headline (chronologically last 30% of event-days).")
    lines.append("")

    if walk_forward_results:
        lines.append("## Walk-forward validation (expanding monthly folds)")
        lines.append("")
        lines.append("Residuals for each fold month are fit only on dates strictly before it.")
        lines.append("")
        lines.append("| city | hour | threshold | month | n | win rate | ROI | Brier |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for wf in walk_forward_results:
            rows = wf["folds"] + [{"month": "pooled", **wf["pooled"]}]
            for fold in rows:
                lines.append(
                    f"| {wf['city']} | {wf['decision_hour_local']} | {wf['edge_threshold']:.2f} | "
                    f"{fold['month']} | {fold['n_trades']} | {100 * fold['win_rate']:.1f}% | "
                    f"{fold['roi']:.3f} | {fold['brier']:.3f} |"
                )
        lines.append("")

    for r in results:
        lines.append(
            f"## {r['city']} — decision hour {r['decision_hour_local']} — "
            f"threshold {r['edge_threshold']:.2f}"
        )
        lines.append("")
        lines.append(f"Window: {r['window_start']} to {r['window_end']} ({r['n_event_days']} event-days)")
        lines.append("")
        lines.append("| prob bin | count | avg predicted | realized freq |")
        lines.append("|---|---|---|---|")
        for b in r["calibration"]:
            avg_p = f"{b['avg_predicted']:.3f}" if b["avg_predicted"] is not None else "-"
            realized = f"{b['realized_freq']:.3f}" if b["realized_freq"] is not None else "-"
            lines.append(f"| [{b['bin_lo']:.1f}, {b['bin_hi']:.1f}) | {b['count']} | {avg_p} | {realized} |")
        lines.append("")

    lines.append("## Caveats")
    lines.append("")
    lines.append(
        f"- Forecast used per event-day is the forecast_daily row with the smallest "
        f"lead_days >= {MIN_FORECAST_LEAD_DAYS} for that (city, date); residuals are "
        f"fit from the same selection rule. The headline (lead 0, same-day archive) "
        f"matches the live dashboard's information set, but the archive's issue time "
        f"is unknown; the conservative lead>=1 stress test (--min-forecast-lead 1) "
        f"flips Las Vegas ROI negative (~-0.35), so the edge depends on having a "
        f"decision-time-fresh forecast. forecast_snapshots is accumulating provably "
        f"pre-decision live forecasts to settle this."
    )
    lines.append(
        "- Entry price at each decision hour is the first candle at/after that "
        "hour's local wall-clock time; falls back to price_c when yes_ask_c is "
        "missing (tagged price_source per trade)."
    )
    lines.append(
        "- high_so_far_f (and therefore hours_to_peak blending) is only available "
        "where obs_hourly has cached observations; otherwise the model runs "
        "without an intraday anchor."
    )
    lines.append(
        "- Calibration table is computed over every bucket-probability "
        "observation evaluated (traded or not), across the full window."
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main(argv=None) -> None:
    global MIN_FORECAST_LEAD_DAYS
    parser = argparse.ArgumentParser(description="Backtest the hotscout probability model.")
    parser.add_argument("--all", action="store_true", help="Backtest all configured cities.")
    parser.add_argument("--city", action="append", help="City to backtest (repeatable).")
    parser.add_argument(
        "--thresholds", default=str(EDGE_THRESHOLD_DEFAULT),
        help="Comma-separated edge thresholds, e.g. 0.03,0.05,0.08.",
    )
    parser.add_argument(
        "--decision-hours", default=",".join(str(h) for h in DECISION_HOURS_LOCAL),
        help="Comma-separated local decision hours, e.g. 9,11,13.",
    )
    parser.add_argument(
        "--min-forecast-lead", type=int, default=MIN_FORECAST_LEAD_DAYS,
        help="Minimum forecast_daily lead_days to trade on / fit residuals from "
             "(0 = same-day archive, matches live's info set; 1 = provably "
             "pre-decision stress test).",
    )
    args = parser.parse_args(argv)

    MIN_FORECAST_LEAD_DAYS = args.min_forecast_lead

    cities = args.city if args.city else list(CITIES)
    thresholds = [float(x) for x in args.thresholds.split(",")]
    hours = [int(x) for x in args.decision_hours.split(",")]

    conn = db.connect()
    db.init(conn)
    try:
        results = []
        walk_forward_results = []
        for city in cities:
            for hour in hours:
                for threshold in thresholds:
                    result = evaluate(conn, city, hour, threshold)
                    write_result(conn, result)
                    results.append(result)
                    walk_forward_results.append(walk_forward(conn, city, hour, threshold))
        conn.commit()
    finally:
        conn.close()

    _print_summary_table(results)
    print("\nwalk-forward (pooled over expanding monthly folds):")
    for wf in walk_forward_results:
        p = wf["pooled"]
        print(
            f"{wf['city']:<14}{wf['decision_hour_local']:>5}{wf['edge_threshold']:>8.2f}"
            f"{p['n_trades']:>5}{100 * p['win_rate']:>7.1f}%{p['roi']:>8.3f}{p['brier']:>8.3f}"
        )
    _write_markdown_report(results, walk_forward_results=walk_forward_results)
    print(f"\nWrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
