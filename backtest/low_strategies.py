from __future__ import annotations

import re
import statistics
from datetime import timedelta
from typing import Any, Callable

from backtest import low_weather


LowStrategy = Callable[[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]], dict[str, Any]]

_RANGE_RE = re.compile(r"(\d+)\D+to\D+(\d+)")
_BELOW_RE = re.compile(r"(\d+)\D+or below")
_ABOVE_RE = re.compile(r"(\d+)\D+or above")


def normalized_trade(
    side: str,
    bucket: str,
    *,
    limit_price: int | None = None,
    reason: str,
    features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "side": side,
        "bucket": bucket,
        "limit_price": limit_price,
        "reason": reason,
        "features": features or {},
        "skip_reason": None,
    }


def normalized_skip(reason: str, *, features: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "side": None,
        "bucket": None,
        "limit_price": None,
        "reason": None,
        "features": features or {},
        "skip_reason": reason,
    }


def bucket_range(label: str) -> tuple[float, float]:
    normalized = label.replace("\u00b0", "F")
    match = _RANGE_RE.search(normalized)
    if match:
        return float(match.group(1)), float(match.group(2))
    match = _BELOW_RE.search(normalized)
    if match:
        high = float(match.group(1))
        return high - 6, high
    match = _ABOVE_RE.search(normalized)
    if match:
        low = float(match.group(1))
        return low, low + 6
    return float("nan"), float("nan")


def bucket_center(label: str) -> float:
    low, high = bucket_range(label)
    return (low + high) / 2.0


def low_persistence(lookback_days: int = 1):
    def strategy(event, buckets, weather_history):
        lows = _prior_lows(event, weather_history, lookback_days)
        if not lows:
            return normalized_skip("no prior lows")
        target = statistics.mean(lows)
        bucket = _bucket_for_temp(buckets, target)
        if bucket is None:
            return normalized_skip("no bucket for target", features={"target_low_f": target})
        return normalized_trade(
            "yes",
            bucket["ticker"],
            reason=f"{lookback_days}-day low persistence",
            features={"target_low_f": target, "prior_lows": lows},
        )
    return strategy


def low_trend_shift(lookback_days: int = 3, shift_per_degree: float = 0.5, min_trend: float = 1.5):
    def strategy(event, buckets, weather_history):
        lows = _prior_lows(event, weather_history, lookback_days)
        if len(lows) < 2:
            return normalized_skip("not enough prior lows")
        trend = lows[-1] - lows[0]
        if abs(trend) < min_trend:
            return normalized_skip("low trend too small", features={"trend_f": trend})
        target = statistics.mean(lows) + trend * shift_per_degree
        bucket = _bucket_for_temp(buckets, target)
        if bucket is None:
            return normalized_skip("no bucket for trend target", features={"target_low_f": target})
        return normalized_trade(
            "yes",
            bucket["ticker"],
            reason="recent low trend shift",
            features={"target_low_f": target, "trend_f": trend, "prior_lows": lows},
        )
    return strategy


def low_fade_far_tail(lookback_days: int = 2, min_distance: float = 6.0):
    def strategy(event, buckets, weather_history):
        if len(buckets) < 2:
            return normalized_skip("not enough buckets")
        lows = _prior_lows(event, weather_history, lookback_days)
        if not lows:
            return normalized_skip("no prior lows")
        target = statistics.mean(lows)
        tails = [buckets[0], buckets[-1]]
        tail = max(tails, key=lambda bucket: abs(bucket_center(bucket["label"]) - target))
        distance = abs(bucket_center(tail["label"]) - target)
        if distance < min_distance:
            return normalized_skip("tails not far enough", features={"target_low_f": target, "distance_f": distance})
        return normalized_trade(
            "no",
            tail["ticker"],
            reason="fade far low-temperature tail",
            features={"target_low_f": target, "distance_f": distance, "prior_lows": lows},
        )
    return strategy


def low_fade_favorite(min_price: int = 20, max_price: int = 60):
    """Buy NO on the current market favorite when it trades inside the band.

    Motivated by San Antonio early-hour calibration: the favorite was priced
    ~39c at h3 but settled YES only ~25% of the time, so fading it was +EV.
    """

    def strategy(event, buckets, weather_history):
        favorite = _favorite_bucket(buckets)
        if favorite is None:
            return normalized_skip("no market favorite")
        price = _latest_price(favorite)
        if price is None or not (min_price <= price <= max_price):
            return normalized_skip("favorite price outside fade band", features={"favorite_price": price})
        return normalized_trade(
            "no",
            favorite["ticker"],
            reason="fade overconfident low favorite",
            features={"favorite_price": price},
        )
    return strategy


def low_market_confirmed(lookback_days: int = 1, min_price: int = 25, max_price: int = 80):
    base = low_persistence(lookback_days=lookback_days)

    def strategy(event, buckets, weather_history):
        decision = base(event, buckets, weather_history)
        if decision.get("skip_reason"):
            return decision
        favorite = _favorite_bucket(buckets)
        if favorite is None:
            return normalized_skip("no market favorite")
        if favorite["ticker"] != decision["bucket"]:
            return normalized_skip(
                "weather target disagrees with market favorite",
                features={**decision.get("features", {}), "favorite_bucket": favorite["ticker"]},
            )
        price = _latest_price(favorite)
        if price is None or not (min_price <= price <= max_price):
            return normalized_skip(
                "favorite price outside entry band",
                features={**decision.get("features", {}), "favorite_price": price},
            )
        return {**decision, "reason": "weather persistence confirmed by market favorite"}
    return strategy


def low_weather_confirmed(
    lookback_days: int = 1,
    min_price: int = 25,
    max_price: int = 80,
    projection_hours: float = 4.0,
):
    def strategy(event, buckets, weather_history):
        prior_lows = _prior_lows(event, weather_history, lookback_days)
        if not prior_lows:
            return normalized_skip("no prior lows")
        visible_observations = _visible_observations(event, weather_history)
        if len(visible_observations) < 2:
            return normalized_skip("not enough visible weather observations")

        recent = visible_observations[-4:]
        latest_temp = recent[-1]["temp_f"]
        hours = max(1.0, (_observation_minutes(recent[-1]) - _observation_minutes(recent[0])) / 60.0)
        cooling_rate = (recent[-1]["temp_f"] - recent[0]["temp_f"]) / hours
        persistence_target = statistics.mean(prior_lows)
        projected_low = latest_temp + min(0.0, cooling_rate) * projection_hours
        target = min(persistence_target, projected_low) if cooling_rate < -0.2 else persistence_target
        bucket = _bucket_for_temp(buckets, target)
        if bucket is None:
            return normalized_skip("no bucket for weather target", features={"target_low_f": target})

        favorite = _favorite_bucket(buckets)
        if favorite is None:
            return normalized_skip("no market favorite")
        if favorite["ticker"] != bucket["ticker"]:
            return normalized_skip(
                "weather target disagrees with market favorite",
                features={
                    "target_low_f": target,
                    "target_bucket": bucket["ticker"],
                    "favorite_bucket": favorite["ticker"],
                    "latest_temp_f": latest_temp,
                    "cooling_rate_f_per_hour": cooling_rate,
                    "prior_lows": prior_lows,
                },
            )

        price = _latest_price(favorite)
        if price is None or not (min_price <= price <= max_price):
            return normalized_skip(
                "favorite price outside entry band",
                features={"target_low_f": target, "favorite_price": price},
            )
        return normalized_trade(
            "yes",
            bucket["ticker"],
            reason="weather observations confirmed by market favorite",
            features={
                "target_low_f": target,
                "latest_temp_f": latest_temp,
                "cooling_rate_f_per_hour": cooling_rate,
                "prior_lows": prior_lows,
                "source_note": "historical archive proxy for live NWS observations",
            },
        )
    return strategy


def low_weather_prediction(
    lookback_days: int = 1,
    min_price: int = 10,
    max_price: int = 80,
    projection_hours: float = 4.0,
):
    def strategy(event, buckets, weather_history):
        target = _weather_target_low(event, weather_history, lookback_days, projection_hours)
        if target.get("skip_reason"):
            return target
        bucket = _bucket_for_temp(buckets, target["target_low_f"])
        if bucket is None:
            return normalized_skip("no bucket for weather target", features=target)
        price = _latest_price(bucket)
        if price is None or not (min_price <= price <= max_price):
            return normalized_skip(
                "weather bucket price outside entry band",
                features={**target, "target_bucket": bucket["ticker"], "target_price": price},
            )
        favorite = _favorite_bucket(buckets)
        return normalized_trade(
            "yes",
            bucket["ticker"],
            reason="weather prediction selected bucket",
            features={
                **target,
                "target_bucket": bucket["ticker"],
                "target_price": price,
                "favorite_bucket": favorite["ticker"] if favorite else None,
                "favorite_price": _latest_price(favorite) if favorite else None,
                "source_note": "historical archive proxy for live NWS observations",
            },
        )
    return strategy


REGISTRY = {
    "low_persistence": low_persistence,
    "low_trend_shift": low_trend_shift,
    "low_fade_far_tail": low_fade_far_tail,
    "low_fade_favorite": low_fade_favorite,
    "low_market_confirmed": low_market_confirmed,
    "low_weather_confirmed": low_weather_confirmed,
    "low_weather_prediction": low_weather_prediction,
}


def _prior_lows(event: dict[str, Any], weather_history: dict[str, dict[str, Any]], lookback_days: int) -> list[float]:
    cutoff_date = _prior_low_cutoff_date(event)
    lows = []
    for date_str in sorted(weather_history):
        if date_str >= cutoff_date:
            continue
        low = ((weather_history.get(date_str) or {}).get("summary") or {}).get("low_f")
        if low is not None:
            lows.append(float(low))
    return lows[-lookback_days:]


def _prior_low_cutoff_date(event: dict[str, Any]) -> str:
    decision_local = event.get("decision_local_iso")
    if decision_local:
        return str(decision_local).split("T", 1)[0]
    return low_weather.measurement_date(event).isoformat()


def _weather_target_low(
    event: dict[str, Any],
    weather_history: dict[str, dict[str, Any]],
    lookback_days: int,
    projection_hours: float,
) -> dict[str, Any]:
    prior_lows = _prior_lows(event, weather_history, lookback_days)
    if not prior_lows:
        return normalized_skip("no prior lows")
    visible_observations = _visible_observations(event, weather_history)
    if len(visible_observations) < 2:
        return normalized_skip("not enough visible weather observations", features={"prior_lows": prior_lows})
    recent = visible_observations[-4:]
    latest_temp = recent[-1]["temp_f"]
    hours = max(1.0, (_observation_minutes(recent[-1]) - _observation_minutes(recent[0])) / 60.0)
    cooling_rate = (recent[-1]["temp_f"] - recent[0]["temp_f"]) / hours
    persistence_target = statistics.mean(prior_lows)
    projected_low = latest_temp + min(0.0, cooling_rate) * projection_hours
    target_low = min(persistence_target, projected_low) if cooling_rate < -0.2 else persistence_target
    return {
        "target_low_f": target_low,
        "latest_temp_f": latest_temp,
        "cooling_rate_f_per_hour": cooling_rate,
        "prior_lows": prior_lows,
        "visible_observation_count": len(visible_observations),
    }


def _bucket_for_temp(buckets: list[dict[str, Any]], temp: float) -> dict[str, Any] | None:
    contains = [bucket for bucket in buckets if bucket_range(bucket["label"])[0] <= temp <= bucket_range(bucket["label"])[1]]
    if contains:
        return contains[0]
    if not buckets:
        return None
    return min(buckets, key=lambda bucket: abs(bucket_center(bucket["label"]) - temp))


def _favorite_bucket(buckets: list[dict[str, Any]]) -> dict[str, Any] | None:
    priced = [(bucket, _latest_price(bucket)) for bucket in buckets]
    priced = [(bucket, price) for bucket, price in priced if price is not None]
    if not priced:
        return None
    return max(priced, key=lambda item: item[1])[0]


def _latest_price(bucket: dict[str, Any]) -> int | None:
    prices = bucket.get("prices") or []
    for price in reversed(prices):
        if price is not None:
            return int(price)
    return None


def _visible_observations(event: dict[str, Any], weather_history: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    cutoff = event.get("decision_local_iso")
    observations = []
    for day in weather_history.values():
        for observation in day.get("observations") or []:
            timestamp = observation.get("timestamp")
            temp = observation.get("temp_f")
            if timestamp is None or temp is None:
                continue
            if cutoff is not None and str(timestamp) > str(cutoff):
                continue
            observations.append({"timestamp": str(timestamp), "temp_f": float(temp)})
    observations.sort(key=lambda item: item["timestamp"])
    return observations


def _observation_minutes(observation: dict[str, Any]) -> int:
    _, _, clock = observation["timestamp"].partition("T")
    hour, _, minute = clock.partition(":")
    return int(hour) * 60 + int(minute or 0)
