from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from config import CITY_CONFIGS, _with_market_date_suffix, city_configs_for_date, next_market_date
from decision_layer import enrich_decision_layer
from kalshi_api import fetch_kalshi_api_observation
from scoring import score_market
from weather_sources import fetch_nws_latest_observation, fetch_nws_observation_history, fetch_weather


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


LIVE_CITY_NAMES = ("Phoenix", "Las Vegas", "San Antonio")
PUBLIC_TRAFFIC_MODE = os.environ.get("PUBLIC_TRAFFIC_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
DEFAULT_CACHE_TTL_SECONDS = _env_int("LIVE_DASHBOARD_CACHE_SECONDS", 60)
LIVE_TEMP_METER_TTL_SECONDS = _env_int("LIVE_TEMP_METER_CACHE_SECONDS", 5 if PUBLIC_TRAFFIC_MODE else 3)
BROWSER_POLL_SECONDS = _env_int("LIVE_DASHBOARD_BROWSER_POLL_SECONDS", 60 if PUBLIC_TRAFFIC_MODE else 15)
TEMP_METER_BROWSER_POLL_SECONDS = _env_int("LIVE_TEMP_METER_BROWSER_POLL_SECONDS", 10 if PUBLIC_TRAFFIC_MODE else 3)


def selected_live_city_configs(day: str = "today") -> list[dict[str, Any]]:
    wanted = set(LIVE_CITY_NAMES)
    configs = current_live_city_configs() if day != "tomorrow" else city_configs_for_date(next_market_date())
    return [config for config in configs if config["city"] in wanted]


def current_live_city_configs() -> list[dict[str, Any]]:
    configs = deepcopy(CITY_CONFIGS)
    for config in configs:
        market_date = datetime.now(ZoneInfo(config["timezone"])).date().isoformat()
        config["market_date"] = market_date
        config["kalshi_url"] = _with_market_date_suffix(config["kalshi_url"], market_date, uppercase=False)
        config["kalshi_event_ticker"] = _with_market_date_suffix(
            config["kalshi_event_ticker"],
            market_date,
            uppercase=True,
        )
    return configs


def live_city_config(city_name: str, day: str = "today") -> dict[str, Any] | None:
    normalized = city_name.strip().lower()
    for config in selected_live_city_configs(day):
        if config["city"].lower() == normalized:
            return config
    return None


def favorite_buckets(market: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    contracts = [
        contract
        for contract in market.get("contracts", [])
        if contract.get("yes_price") is not None
    ]
    contracts.sort(key=lambda contract: float(contract.get("yes_price") or 0), reverse=True)
    top = contracts[0] if contracts else None
    second = contracts[1] if len(contracts) > 1 else None
    return top, second


def build_city_payload(
    city_config: dict[str, Any],
    weather: dict[str, Any],
    market: dict[str, Any],
) -> dict[str, Any]:
    scored = enrich_decision_layer(score_market(city_config["city"], weather, market))
    top, second = favorite_buckets(market)
    warnings = list(weather.get("warnings") or []) + list(market.get("warnings") or [])
    feed_summary = recent_observation_feed_summary(weather)
    return {
        "city": city_config["city"],
        "station_id": weather.get("station_id"),
        "market_date": scored.get("market_date"),
        "market_title": scored.get("market_title"),
        "winning_bucket": _bucket_payload(top),
        "second_bucket": _bucket_payload(second),
        "current_temp_f": scored.get("current_temp_f"),
        "latest_endpoint_temp_f": weather.get("current_temp_f"),
        "latest_endpoint_time": weather.get("observation_time"),
        "latest_history_temp_f": feed_summary["latest_history_temp_f"],
        "latest_history_time": feed_summary["latest_history_time"],
        "recent_observation_points": feed_summary["recent_observation_points"],
        "recent_observation_max_f": feed_summary["recent_observation_max_f"],
        "latest_feed_lag_warning": feed_summary["latest_feed_lag_warning"],
        "latest_feed_lag_note": feed_summary["latest_feed_lag_note"],
        "raw_high_so_far_f": scored.get("raw_high_so_far_f"),
        "high_so_far_f": scored.get("high_so_far_f"),
        "latest_observation_time": scored.get("latest_observation_time"),
        "forecast_high_f": scored.get("forecast_high_f"),
        "forecast_high_time": scored.get("forecast_high_time"),
        "critical_window_et": scored.get("critical_window_et"),
        "heating_rate_f_per_hour": scored.get("heating_rate_f_per_hour"),
        "required_rate_f_per_hour": scored.get("required_rate_f_per_hour"),
        "degrees_needed_to_reach_bucket": scored.get("degrees_needed_to_reach_bucket"),
        "reachability_label": scored.get("reachability_label"),
        "market_weather_alignment": scored.get("market_weather_alignment"),
        "false_pump_warning": scored.get("false_pump_warning"),
        "decision_note": scored.get("decision_note"),
        "source_safety_state": scored.get("source_safety_state"),
        "settlement_source_status": scored.get("settlement_source_status"),
        "weather_confidence_score": scored.get("weather_confidence_score"),
        "forecast_graph_url": scored.get("forecast_graph_url"),
        "kalshi_url": scored.get("kalshi_url"),
        "warnings": warnings,
    }


def market_date_label(cities: list[dict[str, Any]]) -> str:
    dates = sorted({str(city.get("market_date")) for city in cities if city.get("market_date")})
    if not dates:
        return "unknown"
    if len(dates) == 1:
        return dates[0]
    return f"{dates[0]} to {dates[-1]}"


def recent_observation_feed_summary(weather: dict[str, Any]) -> dict[str, Any]:
    points = [
        point
        for point in weather.get("recent_observation_points") or []
        if point.get("time") and point.get("temp_f") is not None
    ]
    recent_max = None
    if points:
        recent_max = round(max(float(point["temp_f"]) for point in points), 1)
    latest_point = points[-1] if points else {}
    latest_history_time = latest_point.get("time")
    latest_history_temp = latest_point.get("temp_f")
    endpoint_time = weather.get("observation_time")
    endpoint_temp = weather.get("current_temp_f")
    history_ahead = _history_is_ahead(endpoint_time, latest_history_time)
    recent_max_hotter = _recent_max_is_hotter(endpoint_temp, recent_max)
    warning = history_ahead or recent_max_hotter
    note = None
    if history_ahead:
        note = "Latest endpoint may be behind the recent observation list. Use recent max in final minutes."
    elif recent_max_hotter:
        note = "Recent observation history has a hotter official reading than the latest endpoint. Use recent max for bucket checks."
    return {
        "recent_observation_points": points,
        "recent_observation_max_f": recent_max,
        "latest_history_time": latest_history_time,
        "latest_history_temp_f": latest_history_temp,
        "latest_feed_lag_warning": warning,
        "latest_feed_lag_note": note,
    }


def collect_live_payload(day: str = "today") -> dict[str, Any]:
    day = normalize_live_day(day)
    generated_at = _now_utc()
    configs = selected_live_city_configs(day)
    cities = []
    for city_config in configs:
        weather = fetch_weather(city_config)
        market = fetch_kalshi_api_observation(city_config)
        cities.append(build_city_payload(city_config, weather, market))
    return {
        "generated_at": generated_at.isoformat(),
        "last_updated": generated_at.isoformat(),
        "active_day": day,
        "market_date_label": market_date_label(configs),
        "cities": cities,
        "research_only": True,
        "refresh_seconds": DEFAULT_CACHE_TTL_SECONDS,
        "browser_poll_seconds": BROWSER_POLL_SECONDS,
        "temp_meter_browser_poll_seconds": TEMP_METER_BROWSER_POLL_SECONDS,
        "public_traffic_mode": PUBLIC_TRAFFIC_MODE,
    }


def collect_live_temp_meter(city_name: str) -> dict[str, Any]:
    city_config = live_city_config(city_name)
    generated_at = _now_utc()
    if not city_config:
        return {
            "generated_at": generated_at.isoformat(),
            "city": city_name,
            "ok": False,
            "error": "City is not available on this live dashboard.",
            "refresh_seconds": LIVE_TEMP_METER_TTL_SECONDS,
            "browser_poll_seconds": TEMP_METER_BROWSER_POLL_SECONDS,
            "public_traffic_mode": PUBLIC_TRAFFIC_MODE,
        }

    warnings: list[str] = []
    weather: dict[str, Any] = {"station_id": city_config.get("station_id")}
    try:
        weather.update(fetch_nws_latest_observation(city_config["station_id"]))
    except Exception as exc:
        warnings.append(f"NWS latest observation unavailable: {exc}")
    try:
        weather.update(fetch_nws_observation_history(city_config))
    except Exception as exc:
        warnings.append(f"NWS observation history unavailable: {exc}")

    feed_summary = recent_observation_feed_summary(weather)
    raw_high = weather.get("raw_high_so_far_f")
    rounded_high = weather.get("high_so_far_f")
    return {
        "generated_at": generated_at.isoformat(),
        "city": city_config["city"],
        "station_id": city_config.get("station_id"),
        "ok": True,
        "current_temp_f": weather.get("current_temp_f"),
        "latest_endpoint_time": weather.get("observation_time"),
        "raw_high_so_far_f": raw_high,
        "high_so_far_f": rounded_high,
        "rounded_if_final_now_f": rounded_high,
        "recent_observation_points": feed_summary["recent_observation_points"],
        "recent_observation_max_f": feed_summary["recent_observation_max_f"],
        "latest_history_temp_f": feed_summary["latest_history_temp_f"],
        "latest_history_time": feed_summary["latest_history_time"],
        "latest_feed_lag_warning": feed_summary["latest_feed_lag_warning"],
        "latest_feed_lag_note": feed_summary["latest_feed_lag_note"],
        "warnings": warnings,
        "refresh_seconds": LIVE_TEMP_METER_TTL_SECONDS,
        "browser_poll_seconds": TEMP_METER_BROWSER_POLL_SECONDS,
        "public_traffic_mode": PUBLIC_TRAFFIC_MODE,
    }


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class LiveDashboardCache:
    def __init__(
        self,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        fetcher: Callable[[str], dict[str, Any]] = collect_live_payload,
        clock: Callable[[], datetime] = _now_utc,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.fetcher = fetcher
        self.clock = clock
        self.values: dict[str, dict[str, Any]] = {}
        self.fetched_at: dict[str, datetime] = {}

    def get(self, day: str = "today") -> dict[str, Any]:
        now = self.clock()
        key = normalize_live_day(day)
        if key in self.values and key not in self.fetched_at:
            return self.values[key]
        fetched_at = self.fetched_at.get(key)
        if key not in self.values or fetched_at is None or now - fetched_at >= timedelta(seconds=self.ttl_seconds):
            self.values[key] = self.fetcher(key)
            self.fetched_at[key] = now
        return self._with_cache_metadata(key, now)

    def _with_cache_metadata(self, key: str, now: datetime) -> dict[str, Any]:
        payload = dict(self.values.get(key) or {})
        next_refresh = self.fetched_at.get(key, now) + timedelta(seconds=self.ttl_seconds)
        payload["cache_ttl_seconds"] = self.ttl_seconds
        payload["next_refresh_eta"] = next_refresh.isoformat()
        return payload


class LiveTempMeterCache:
    def __init__(
        self,
        ttl_seconds: int = LIVE_TEMP_METER_TTL_SECONDS,
        fetcher: Callable[[str], dict[str, Any]] = collect_live_temp_meter,
        clock: Callable[[], datetime] = _now_utc,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.fetcher = fetcher
        self.clock = clock
        self.values: dict[str, dict[str, Any]] = {}
        self.fetched_at: dict[str, datetime] = {}

    def get(self, city_name: str) -> dict[str, Any]:
        now = self.clock()
        key = city_name.strip().lower()
        fetched_at = self.fetched_at.get(key)
        if key not in self.values or fetched_at is None or now - fetched_at >= timedelta(seconds=self.ttl_seconds):
            self.values[key] = self.fetcher(city_name)
            self.fetched_at[key] = now
        payload = dict(self.values[key])
        next_refresh = self.fetched_at[key] + timedelta(seconds=self.ttl_seconds)
        payload["cache_ttl_seconds"] = self.ttl_seconds
        payload["next_refresh_eta"] = next_refresh.isoformat()
        return payload


def _bucket_payload(contract: dict[str, Any] | None) -> dict[str, Any] | None:
    if not contract:
        return None
    return {
        "label": contract.get("label"),
        "yes_price": contract.get("yes_price"),
        "yes_bid": contract.get("yes_bid"),
        "no_price": contract.get("no_price"),
        "low_f": contract.get("low_f"),
        "high_f": contract.get("high_f"),
        "ticker": contract.get("ticker"),
    }


def normalize_live_day(day: str) -> str:
    return "tomorrow" if str(day).strip().lower() == "tomorrow" else "today"


def _history_is_ahead(endpoint_time: Any, history_time: Any) -> bool:
    endpoint = _parse_iso_time(endpoint_time)
    history = _parse_iso_time(history_time)
    if endpoint is None or history is None:
        return False
    return history - endpoint >= timedelta(minutes=3)


def _recent_max_is_hotter(endpoint_temp: Any, recent_max: Any) -> bool:
    try:
        if endpoint_temp is None or recent_max is None:
            return False
        return float(recent_max) - float(endpoint_temp) >= 0.5
    except (TypeError, ValueError):
        return False


def _parse_iso_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
