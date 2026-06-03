from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from config import CITY_CONFIGS
from decision_layer import enrich_decision_layer
from kalshi_api import fetch_kalshi_api_observation
from scoring import score_market
from weather_sources import fetch_weather

LIVE_CITY_NAMES = ("Phoenix", "Las Vegas", "San Antonio")
DEFAULT_CACHE_TTL_SECONDS = 60


def selected_live_city_configs() -> list[dict[str, Any]]:
    wanted = set(LIVE_CITY_NAMES)
    return [config for config in CITY_CONFIGS if config["city"] in wanted]


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
    return {
        "city": city_config["city"],
        "station_id": weather.get("station_id"),
        "market_date": scored.get("market_date"),
        "market_title": scored.get("market_title"),
        "winning_bucket": _bucket_payload(top),
        "second_bucket": _bucket_payload(second),
        "current_temp_f": scored.get("current_temp_f"),
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


def collect_live_payload() -> dict[str, Any]:
    generated_at = _now_utc()
    cities = []
    for city_config in selected_live_city_configs():
        weather = fetch_weather(city_config)
        market = fetch_kalshi_api_observation(city_config)
        cities.append(build_city_payload(city_config, weather, market))
    return {
        "generated_at": generated_at.isoformat(),
        "last_updated": generated_at.isoformat(),
        "cities": cities,
        "research_only": True,
        "refresh_seconds": DEFAULT_CACHE_TTL_SECONDS,
    }


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class LiveDashboardCache:
    def __init__(
        self,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        fetcher: Callable[[], dict[str, Any]] = collect_live_payload,
        clock: Callable[[], datetime] = _now_utc,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.fetcher = fetcher
        self.clock = clock
        self.value: dict[str, Any] | None = None
        self.fetched_at: datetime | None = None

    def get(self) -> dict[str, Any]:
        now = self.clock()
        if self.value is not None and self.fetched_at is None:
            return self.value
        if self.value is None or self.fetched_at is None or now - self.fetched_at >= timedelta(seconds=self.ttl_seconds):
            self.value = self.fetcher()
            self.fetched_at = now
        return self._with_cache_metadata(now)

    def _with_cache_metadata(self, now: datetime) -> dict[str, Any]:
        payload = dict(self.value or {})
        next_refresh = (self.fetched_at or now) + timedelta(seconds=self.ttl_seconds)
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
