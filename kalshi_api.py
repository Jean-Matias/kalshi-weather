from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import USER_AGENT
from scoring import weather_confidence

KALSHI_API_BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
KALSHI_API_TIMEOUT_SECONDS = 15


def should_fetch_api_observation(weather: dict[str, Any], min_confidence: int = 70) -> bool:
    confidence = weather.get("weather_confidence_score")
    if confidence is None:
        confidence = weather_confidence(weather)
    if int(confidence) < min_confidence:
        return False
    if weather.get("forecast_high_f") is None:
        return False
    if weather.get("market_day_state") == "future":
        return True
    return weather.get("analysis_source_status") in {
        "same_day_station_observations",
        "final_cli",
        "cli_available",
    } or weather.get("settlement_source_status") == "cli_available"


def fetch_kalshi_api_observation(city_config: dict[str, Any]) -> dict[str, Any]:
    event_ticker = city_config.get("kalshi_event_ticker")
    if not event_ticker:
        return {
            "city": city_config.get("city"),
            "market_data_source": "kalshi_api_unavailable",
            "warnings": ["No Kalshi event ticker configured for API observation."],
        }

    url = f"{KALSHI_API_BASE_URL}/events/{event_ticker}"
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=KALSHI_API_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "city": city_config.get("city"),
            "url": city_config.get("kalshi_url"),
            "api_url": url,
            "market_data_source": "kalshi_api_unavailable",
            "warnings": [f"Kalshi public market API unavailable: {exc}"],
        }

    parsed = parse_event_response(payload, city_config)
    parsed["api_url"] = url
    parsed["url"] = city_config.get("kalshi_url")
    return parsed


def parse_event_response(payload: dict[str, Any], city_config: dict[str, Any]) -> dict[str, Any]:
    event = payload.get("event") or {}
    contracts = [_contract_from_api_market(market) for market in payload.get("markets", [])]
    contracts = [contract for contract in contracts if contract is not None]
    contracts.sort(
        key=lambda contract: (
            float("-inf") if contract.get("low_f") is None else contract["low_f"],
            float("inf") if contract.get("high_f") is None else contract["high_f"],
        )
    )
    selected = _select_api_contract(contracts)
    crowd_price = selected.get("yes_price") if selected else None
    return {
        "city": city_config.get("city"),
        "market_title": event.get("title"),
        "contract_title": selected.get("label") if selected else None,
        "kalshi_price": crowd_price,
        "implied_probability": crowd_price / 100 if crowd_price is not None else None,
        "bid": selected.get("yes_bid") if selected else None,
        "ask": selected.get("yes_price") if selected else None,
        "volume": _sum_numeric(contract.get("volume") for contract in contracts),
        "recent_move_cents": None,
        "contracts": contracts,
        "range_low_f": selected.get("low_f") if selected else None,
        "range_high_f": selected.get("high_f") if selected else None,
        "api_crowd_favorite": selected.get("label") if selected else None,
        "api_crowd_price": crowd_price,
        "api_contract_count": len(contracts),
        "api_event_ticker": event.get("event_ticker") or city_config.get("kalshi_event_ticker"),
        "market_data_source": "kalshi_api",
        "warnings": [],
    }


def merge_api_observation(
    browser_market: dict[str, Any],
    api_market: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(browser_market)
    for key, value in api_market.items():
        if key in {"official_source_text", "official_source_url", "raw_text_excerpt", "warnings"}:
            continue
        if value is not None:
            merged[key] = value
    for preserved_key in ("official_source_text", "official_source_url", "raw_text_excerpt"):
        if browser_market.get(preserved_key) is not None:
            merged[preserved_key] = browser_market[preserved_key]
    merged["warnings"] = list(browser_market.get("warnings", [])) + list(api_market.get("warnings", []))
    return merged


def _contract_from_api_market(market: dict[str, Any]) -> dict[str, Any] | None:
    low, high = _range_from_api_market(market)
    if low is None and high is None:
        return None
    yes_price = _dollars_to_cents(market.get("yes_ask_dollars") or market.get("last_price_dollars"))
    no_price = _dollars_to_cents(market.get("no_ask_dollars"))
    return {
        "label": _format_range(low, high),
        "low_f": low,
        "high_f": high,
        "yes_price": yes_price,
        "no_price": no_price,
        "yes_bid": _dollars_to_cents(market.get("yes_bid_dollars")),
        "ticker": market.get("ticker"),
        "api_title": market.get("title"),
        "last_price": _dollars_to_cents(market.get("last_price_dollars")),
        "liquidity": _dollars_to_cents(market.get("liquidity_dollars")),
        "volume": _numeric(market.get("volume")),
    }


def _range_from_api_market(market: dict[str, Any]) -> tuple[float | None, float | None]:
    strike_type = str(market.get("strike_type") or "").lower()
    floor = _numeric(market.get("floor_strike"))
    cap = _numeric(market.get("cap_strike"))
    if strike_type == "less" and cap is not None:
        return None, cap - 1
    if strike_type == "greater" and floor is not None:
        return floor + 1, None
    if strike_type == "between":
        return floor, cap
    return floor, cap


def _select_api_contract(contracts: list[dict[str, Any]]) -> dict[str, Any] | None:
    priced = [contract for contract in contracts if contract.get("yes_price") is not None]
    if not priced:
        return None
    return max(priced, key=lambda contract: contract["yes_price"])


def _dollars_to_cents(value: Any) -> float | None:
    numeric = _numeric(value)
    if numeric is None:
        return None
    return round(numeric * 100)


def _numeric(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _sum_numeric(values: Any) -> float | None:
    numeric_values = [value for value in values if value is not None]
    if not numeric_values:
        return None
    return sum(float(value) for value in numeric_values)


def _format_range(low: float | None, high: float | None) -> str:
    if low is None and high is not None:
        return f"{high:.0f}F or below"
    if high is None and low is not None:
        return f"{low:.0f}F or above"
    if low is not None and high is not None:
        return f"{low:.0f}F to {high:.0f}F"
    return "unknown"
