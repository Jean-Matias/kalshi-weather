"""hotscout live board builder.

Assembles the frozen BoardPayload (see hotscout.schema) from live Kalshi
market data, live weather observations, and (when available) the fitted
residual model. Degraded mode is a hard requirement: if the model or
backtest history is unavailable, the board still renders with
model_prob=None, edge_after_fees=None, "PASS" recommendations, and a
"NOT VALIDATED" backtest badge.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable

import config as root_config
from kalshi_api import fetch_kalshi_api_observation
from weather_sources import fetch_weather

from hotscout import config as hs_config
from hotscout import db as hs_db
from hotscout.fees import kalshi_fee_cents

try:  # pragma: no cover - exercised indirectly via degraded-mode tests
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore


CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"


def city_config_for_now(city: str, market_date: str | None = None) -> dict[str, Any]:
    """Return the root CITY_CONFIGS entry for `city` with a fresh market_date
    (and matching Kalshi URL/ticker date suffix) instead of whatever date was
    frozen in at process import time."""
    base = deepcopy(hs_config.city_config(city))
    if market_date is None:
        tz = base.get("timezone", "UTC")
        market_date = datetime.now(ZoneInfo(tz)).date().isoformat()
    base["market_date"] = market_date
    base["kalshi_url"] = root_config._with_market_date_suffix(base["kalshi_url"], market_date, uppercase=False)
    base["kalshi_event_ticker"] = root_config._with_market_date_suffix(
        base["kalshi_event_ticker"], market_date, uppercase=True
    )
    return base


def nearest_decision_hour(city_timezone: str, now: datetime | None = None) -> int:
    """Return the decision hour (local, from hs_config.DECISION_HOURS_LOCAL)
    closest to the current local time for this city."""
    local_now = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(city_timezone))
    hour = local_now.hour + local_now.minute / 60.0
    return min(hs_config.DECISION_HOURS_LOCAL, key=lambda h: abs(h - hour))


def _bucket_from_contract(contract: dict[str, Any]) -> dict[str, Any] | None:
    ticker = contract.get("ticker")
    if not ticker:
        return None
    return {
        "ticker": ticker,
        "label": contract.get("label") or "unknown",
        "low_f": contract.get("low_f"),
        "high_f": contract.get("high_f"),
        "yes_bid_c": _to_int(contract.get("yes_bid")),
        "yes_ask_c": _to_int(contract.get("yes_price")),
    }


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _load_model_probs(
    conn,
    city: str,
    decision_hour_local: int,
    month: int,
    forecast_high_f: float | None,
    buckets: list[dict[str, Any]],
    high_so_far_f: float | None,
    hours_to_peak: float | None,
    warnings: list[str],
) -> dict[str, float]:
    """Return {ticker: prob}, or {} in degraded mode (model/backtest tables
    unavailable or empty). Never raises."""
    if forecast_high_f is None or not buckets:
        return {}
    try:
        from hotscout.calibration import load_residual_dist
        from hotscout.model import bucket_probabilities
    except Exception as exc:
        warnings.append(f"model unavailable: {exc}")
        return {}

    try:
        residual_dist = load_residual_dist(conn, city, decision_hour_local, month)
        if not residual_dist or not residual_dist.get("residuals_f"):
            warnings.append("model unavailable: no residual distribution for this city/hour/month")
            return {}
        model_buckets = [
            {
                "ticker": bucket["ticker"],
                "label": bucket["label"],
                "low_f": bucket.get("low_f"),
                "high_f": bucket.get("high_f"),
            }
            for bucket in buckets
        ]
        probs = bucket_probabilities(
            residual_dist,
            forecast_high_f,
            model_buckets,
            high_so_far_f=high_so_far_f,
            hours_to_peak=hours_to_peak,
        )
        return {entry["ticker"]: entry["prob"] for entry in probs}
    except Exception as exc:
        warnings.append(f"model unavailable: {exc}")
        return {}


def _load_backtest_badge(conn, city: str, decision_hour_local: int) -> dict[str, Any]:
    """Latest backtest_results row for this city/decision hour. Degrades to
    an unvalidated badge if the table is empty or unreachable."""
    default_badge = {
        "win_rate": None,
        "roi": None,
        "n_trades": 0,
        "window": "n/a",
        "validated": False,
    }
    try:
        row = conn.execute(
            """
            SELECT wins, n_trades, roi, window_start, window_end
            FROM backtest_results
            WHERE city = ? AND decision_hour_local = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (city, decision_hour_local),
        ).fetchone()
    except Exception:
        return default_badge
    if row is None:
        return default_badge
    n_trades = row["n_trades"] or 0
    wins = row["wins"] or 0
    roi = row["roi"]
    win_rate = (wins / n_trades) if n_trades else None
    validated = n_trades >= hs_config.MIN_VALIDATION_TRADES and roi is not None and roi > 0
    window = f"{row['window_start']} to {row['window_end']} @ {decision_hour_local}:00"
    return {
        "win_rate": win_rate,
        "roi": roi,
        "n_trades": n_trades,
        "window": window,
        "validated": validated,
    }


def _confidence(edge: float | None, n_trades: int, validated: bool) -> str:
    if edge is None or not validated:
        return CONFIDENCE_LOW
    if edge > 2 * hs_config.EDGE_THRESHOLD_DEFAULT and n_trades >= 2 * hs_config.MIN_VALIDATION_TRADES:
        return CONFIDENCE_HIGH
    if edge > hs_config.EDGE_THRESHOLD_DEFAULT:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW


def _build_city_board(
    conn,
    city: str,
    market_date: str | None,
    now: datetime,
    kalshi_fetcher: Callable[[dict[str, Any]], dict[str, Any]],
    weather_fetcher: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    warnings: list[str] = []
    city_cfg = city_config_for_now(city, market_date)

    try:
        weather = weather_fetcher(city_cfg)
    except Exception as exc:
        warnings.append(f"weather unavailable: {exc}")
        weather = {}

    try:
        market = kalshi_fetcher(city_cfg)
    except Exception as exc:
        warnings.append(f"kalshi unavailable: {exc}")
        market = {}
    warnings.extend(weather.get("warnings") or [])
    warnings.extend(market.get("warnings") or [])

    contracts = market.get("contracts") or []
    if not contracts:
        warnings.append("no candles: Kalshi contracts unavailable for this event")

    buckets_raw = [b for b in (_bucket_from_contract(c) for c in contracts) if b is not None]

    forecast_high_f = weather.get("forecast_high_f")
    high_so_far_f = weather.get("high_so_far_f")
    hours_to_peak = _hours_to_peak(weather.get("forecast_high_time"), now)

    decision_hour_local = nearest_decision_hour(city_cfg["timezone"], now)
    month = now.astimezone(ZoneInfo(city_cfg["timezone"])).month

    # Snapshot the live forecast the first time we see each (city, date,
    # decision hour): a provably pre-decision forecast record that future
    # backtests can use instead of archive forecasts of unknown issue time.
    # Only capture at-or-before the decision hour — a later capture would
    # reintroduce exactly the look-ahead this table exists to rule out.
    local_now = now.astimezone(ZoneInfo(city_cfg["timezone"]))
    if forecast_high_f is not None and local_now.hour <= decision_hour_local:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO forecast_snapshots"
                "(city, date, decision_hour_local, captured_at, forecast_high_f, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (city, city_cfg["market_date"], decision_hour_local,
                 now.isoformat(), forecast_high_f, "live_board"),
            )
            conn.commit()
        except Exception as exc:
            warnings.append(f"forecast snapshot not recorded: {exc}")

    model_probs = _load_model_probs(
        conn,
        city,
        decision_hour_local,
        month,
        forecast_high_f,
        buckets_raw,
        high_so_far_f,
        hours_to_peak,
        warnings,
    )

    badge = _load_backtest_badge(conn, city, decision_hour_local)
    if not badge["validated"]:
        warnings.append("NOT VALIDATED: recommendations disabled for this city/hour")

    buckets = []
    for bucket in buckets_raw:
        model_prob = model_probs.get(bucket["ticker"])
        recommendation = "PASS"
        edge_after_fees: float | None = None
        confidence = CONFIDENCE_LOW

        yes_ask_c = bucket["yes_ask_c"]
        yes_bid_c = bucket["yes_bid_c"]
        if model_prob is not None and yes_ask_c is not None and yes_bid_c is not None:
            no_ask_c = 100 - yes_bid_c
            edge_yes = model_prob - (yes_ask_c + kalshi_fee_cents(yes_ask_c)) / 100
            edge_no = (1 - model_prob) - (no_ask_c + kalshi_fee_cents(no_ask_c)) / 100
            if edge_yes >= edge_no:
                edge_after_fees = edge_yes
                side_edge = edge_yes
                candidate_side = "BUY YES"
            else:
                edge_after_fees = edge_no
                side_edge = edge_no
                candidate_side = "BUY NO"

            if side_edge > hs_config.EDGE_THRESHOLD_DEFAULT and badge["validated"]:
                recommendation = candidate_side
            confidence = _confidence(side_edge, badge["n_trades"], badge["validated"])

        buckets.append(
            {
                "ticker": bucket["ticker"],
                "label": bucket["label"],
                "model_prob": model_prob,
                "yes_bid_c": yes_bid_c,
                "yes_ask_c": yes_ask_c,
                "edge_after_fees": edge_after_fees,
                "recommendation": recommendation,
                "confidence": confidence,
                "decision_hour_local": decision_hour_local,
            }
        )

    return {
        "city": city,
        "market_date": city_cfg["market_date"],
        "forecast_high_f": forecast_high_f,
        "high_so_far_f": high_so_far_f,
        "heating_rate": weather.get("heating_rate_f_per_hour"),
        "buckets": buckets,
        "backtest_badge": badge,
        "warnings": warnings,
    }


def _hours_to_peak(forecast_high_time: Any, now: datetime) -> float | None:
    if not forecast_high_time:
        return None
    try:
        text = str(forecast_high_time).replace("Z", "+00:00")
        peak = datetime.fromisoformat(text)
    except ValueError:
        return None
    if peak.tzinfo is None:
        peak = peak.replace(tzinfo=timezone.utc)
    delta_hours = (peak.astimezone(timezone.utc) - now.astimezone(timezone.utc)).total_seconds() / 3600
    return max(0.0, delta_hours)


def build_board(
    market_date: str | None = None,
    conn=None,
    kalshi_fetcher: Callable[[dict[str, Any]], dict[str, Any]] = fetch_kalshi_api_observation,
    weather_fetcher: Callable[[dict[str, Any]], dict[str, Any]] = fetch_weather,
) -> dict[str, Any]:
    """Build the full BoardPayload across all hotscout cities. Never raises:
    every external dependency (network, model, backtest history) degrades to
    warnings rather than a failure."""
    now = datetime.now(timezone.utc)
    owns_conn = conn is None
    if owns_conn:
        conn = hs_db.connect()
        hs_db.init(conn)
    try:
        cities = [
            _build_city_board(conn, city, market_date, now, kalshi_fetcher, weather_fetcher)
            for city in hs_config.CITIES
        ]
    finally:
        if owns_conn:
            conn.close()

    return {
        "generated_at": now.isoformat(),
        "cities": cities,
    }
