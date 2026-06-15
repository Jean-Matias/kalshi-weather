"""Weather-OBSERVATION-driven strategies for KXHIGHTLV (Las Vegas daily-high
multi-bucket markets) — decisions are made from REAL recent/prior weather data
(persistence, multi-day trend), not from market price action.

A weather strategy has signature:

    strategy(event, buckets, weather_history) -> dict | None

- `event`/`buckets`: same shape as backtest.engine (buckets carry `prices`
  for the chosen entry hour — see `run_weather_backtest`).
- `weather_history`: dict {date_str: day_dict} from
  weather_cache.load_history_for_event(event), where day_dict["summary"]
  has "high_f"/"low_f"/"avg_pressure_hpa" and day_dict["observations"] is
  the hourly trajectory for that LOCAL calendar date.

Returns `None` to skip, or `{"side": "yes"|"no", "bucket": <ticker>,
"limit_price": <cents>}` — `limit_price` is read from the bucket's price at
the chosen entry hour (the strategy doesn't choose it; see runner).

We reuse `Trade`/`Report`/`split_chronological`/`FEE_CENTS_PER_CONTRACT`
from backtest.engine and only replace the *decision* step with one driven by
weather_history instead of price action.
"""
from __future__ import annotations

import re
import statistics
from datetime import timedelta
from typing import Callable, Optional

from backtest import weather_cache
from backtest.engine import (
    FEE_CENTS_PER_CONTRACT,
    Report,
    Trade,
    _build_buckets,
)

WeatherStrategy = Callable[[dict, list[dict], dict], Optional[dict]]

_RANGE_RE = re.compile(r"(\d+)\D+to\D+(\d+)")
_BELOW_RE = re.compile(r"(\d+)\D+or below")
_ABOVE_RE = re.compile(r"(\d+)\D+or above")


def bucket_range(label: str) -> tuple[float, float]:
    """Parse a bucket label like '82° to 83°' / '75° or below'
    / '84° or above' into an inclusive (low, high) °F range. Open-ended
    tails get a synthetic 6° half-width so they have a finite "center"."""
    m = _RANGE_RE.search(label)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = _BELOW_RE.search(label)
    if m:
        hi = float(m.group(1))
        return hi - 6, hi
    m = _ABOVE_RE.search(label)
    if m:
        lo = float(m.group(1))
        return lo, lo + 6
    return float("nan"), float("nan")


def bucket_center(label: str) -> float:
    lo, hi = bucket_range(label)
    return (lo + hi) / 2.0


def _bucket_for_temp(buckets: list[dict], temp: float):
    """Return the bucket whose [low, high] range contains `temp`, or the
    closest one by center distance if none contains it exactly."""
    contains = [b for b in buckets if bucket_range(b["label"])[0] <= temp <= bucket_range(b["label"])[1]]
    if contains:
        return contains[0]
    if not buckets:
        return None
    return min(buckets, key=lambda b: abs(bucket_center(b["label"]) - temp))


def _recent_highs(weather_history: dict, measure_date, lookback_days: int) -> list[float]:
    """Actual daily highs for the `lookback_days` days strictly BEFORE the
    measurement day, oldest-first, skipping any missing days."""
    highs = []
    for delta in range(lookback_days, 0, -1):
        d = (measure_date - timedelta(days=delta)).isoformat()
        day = weather_history.get(d)
        if day and day["summary"]["high_f"] is not None:
            highs.append(day["summary"]["high_f"])
    return highs


def _avg_pressure(weather_history: dict, measure_date, lookback_days: int) -> list[float]:
    out = []
    for delta in range(lookback_days, 0, -1):
        d = (measure_date - timedelta(days=delta)).isoformat()
        day = weather_history.get(d)
        if day and day["summary"].get("avg_pressure_hpa") is not None:
            out.append(day["summary"]["avg_pressure_hpa"])
    return out


def _price_at(bucket: dict, idx: int):
    if idx < len(bucket["prices"]):
        return bucket["prices"][idx]
    return None


# --------------------------------------------------------------------------
# Strategy 1: persistence — bet YES on the bucket containing the recent
# average actual high (optionally only if price offers a minimum margin).
# --------------------------------------------------------------------------
def persistence_yes(lookback_days: int = 1, min_price: int = 1, max_price: int = 95):
    def strategy(event, buckets, weather_history):
        measure_date = weather_cache.measurement_date(event)
        highs = _recent_highs(weather_history, measure_date, lookback_days)
        if not highs:
            return None
        target = statistics.mean(highs)
        bucket = _bucket_for_temp(buckets, target)
        if bucket is None:
            return None
        return {"side": "yes", "bucket": bucket["ticker"], "limit_price": None,
                "_target_temp": target, "_bucket_ref": bucket}
    return strategy


# --------------------------------------------------------------------------
# Strategy 2: fade the tails — bet NO on whichever extreme bucket is FAR
# (beyond `min_distance` °F) from the recent average actual high.
# --------------------------------------------------------------------------
def persistence_fade_tails(lookback_days: int = 2, min_distance: float = 6.0):
    def strategy(event, buckets, weather_history):
        if len(buckets) < 2:
            return None
        measure_date = weather_cache.measurement_date(event)
        highs = _recent_highs(weather_history, measure_date, lookback_days)
        if not highs:
            return None
        target = statistics.mean(highs)
        for tail in (buckets[0], buckets[-1]):
            center = bucket_center(tail["label"])
            if abs(center - target) >= min_distance:
                return {"side": "no", "bucket": tail["ticker"], "limit_price": None,
                        "_bucket_ref": tail}
        return None
    return strategy


# --------------------------------------------------------------------------
# Strategy 3: multi-day trend — shift target up/down from the recent average
# based on a warming/cooling trend (and optionally pressure trend).
# --------------------------------------------------------------------------
def trend_shift(lookback_days: int = 3, shift_per_degree: float = 0.5,
                min_trend: float = 1.5, use_pressure: bool = False):
    """If the last `lookback_days` actual highs show a warming (cooling)
    trend of at least `min_trend` °F (oldest vs newest), bet YES on the
    bucket centered at (recent average + trend * shift_per_degree); skip if
    the trend is too small to be meaningful."""
    def strategy(event, buckets, weather_history):
        measure_date = weather_cache.measurement_date(event)
        highs = _recent_highs(weather_history, measure_date, lookback_days)
        if len(highs) < 2:
            return None
        trend = highs[-1] - highs[0]
        if abs(trend) < min_trend:
            return None
        if use_pressure:
            pressures = _avg_pressure(weather_history, measure_date, lookback_days)
            if len(pressures) >= 2:
                p_trend = pressures[-1] - pressures[0]
                # rising pressure historically correlates with clearer/hotter
                # LV days; require trend agreement to act
                if (trend > 0) != (p_trend > 0):
                    return None
        target = statistics.mean(highs) + trend * shift_per_degree
        bucket = _bucket_for_temp(buckets, target)
        if bucket is None:
            return None
        return {"side": "yes", "bucket": bucket["ticker"], "limit_price": None,
                "_target_temp": target, "_bucket_ref": bucket}
    return strategy


# --------------------------------------------------------------------------
# Strategy 4: persistence + price-margin filter — only take the persistence
# bet when the market's own price for that bucket isn't already a near-lock
# or a longshot (so there's real payout margin if the weather signal is
# right and the market hasn't fully converged on it yet).
# --------------------------------------------------------------------------
def persistence_with_margin(lookback_days: int = 1, min_price: int = 30, max_price: int = 80):
    base = persistence_yes(lookback_days=lookback_days)

    def strategy(event, buckets, weather_history):
        decision = base(event, buckets, weather_history)
        if decision is None:
            return None
        return {**decision, "_min_price": min_price, "_max_price": max_price}
    return strategy


REGISTRY = {
    "persistence_yes": persistence_yes,
    "persistence_fade_tails": persistence_fade_tails,
    "trend_shift": trend_shift,
    "persistence_with_margin": persistence_with_margin,
}


# --------------------------------------------------------------------------
# Runner: thin wrapper around the engine's P&L machinery. Decision (which
# bucket/side) comes from the weather strategy; the executable price is read
# from the bucket's market price at `decision_hour` (what you'd actually pay
# to enter), exactly like engine.run() does for price-driven strategies.
# --------------------------------------------------------------------------
def run_weather_backtest(
    dataset: list[dict],
    strategy: WeatherStrategy,
    contracts: int = 3,
    label: str = "weather-strategy",
    decision_hour: int = 6,
) -> Report:
    report = Report(label=label)
    for entry in dataset:
        event = entry["event"]
        buckets = _build_buckets(event, entry["bucket_candles"])
        if not buckets:
            continue
        max_idx = min(len(b["prices"]) for b in buckets) - 1
        if max_idx < 0:
            continue
        idx = min(decision_hour, max_idx)
        if any(b["prices"][idx] is None for b in buckets):
            continue

        weather_history = weather_cache.load_history_for_event(event, lookback_days=3)
        decision = strategy(event, buckets, weather_history)
        if decision is None:
            continue

        side = decision["side"]
        bucket_ticker = decision["bucket"]
        bucket = next((b for b in buckets if b["ticker"] == bucket_ticker), None)
        if bucket is None:
            continue

        market_price = _price_at(bucket, idx)
        if market_price is None:
            continue
        # executable price: pay yes_ask for "yes", or (100 - yes_ask) for "no"
        exec_price = market_price if side == "yes" else (100 - market_price)
        exec_price = max(1, min(99, int(exec_price)))

        min_price = decision.get("_min_price")
        max_price = decision.get("_max_price")
        if min_price is not None and not (min_price <= exec_price <= max_price):
            continue

        bucket_is_yes = bucket["result"] == "yes"
        won = bucket_is_yes if side == "yes" else not bucket_is_yes
        if won:
            gross = (100 - exec_price) * contracts
        else:
            gross = -exec_price * contracts
        net = gross - int(FEE_CENTS_PER_CONTRACT * contracts)

        report.trades.append(Trade(
            event_ticker=event["event_ticker"],
            open_ts=event["open_ts"],
            bucket=bucket_ticker,
            side=side,
            limit_price=exec_price,
            won=won,
            net_cents=net,
        ))
    return report
