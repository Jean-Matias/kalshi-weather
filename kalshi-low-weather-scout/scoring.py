from __future__ import annotations

import math
from typing import Any


def score_market(city: str, weather: dict[str, Any], market: dict[str, Any]) -> dict[str, Any]:
    warnings = list(weather.get("warnings", [])) + list(market.get("warnings", []))
    reasoning: list[str] = []

    estimated_probability = estimate_weather_probability(weather, market)
    confidence = weather_confidence(weather)
    volatility = volatility_risk(weather)
    cooling = cooling_risk(weather)
    crowding = market_crowding(market)
    liquidity = liquidity_risk(market)
    edge = estimated_edge(estimated_probability, market.get("implied_probability"), confidence)

    if market.get("implied_probability") is None:
        warnings.append("Missing Kalshi data; do not treat as a trading signal.")
        reasoning.append("Kalshi market data unavailable or login-gated.")
    if weather.get("market_day_state") != "future" and weather.get("current_temp_f") is None:
        warnings.append("Missing current NWS observation.")
    if weather.get("forecast_low_f") is None:
        warnings.append("Missing forecast low.")

    missing_market = market.get("implied_probability") is None
    label = final_label(edge, confidence, volatility, cooling, liquidity, crowding, warnings, missing_market)
    reasoning.extend(_reasoning(weather, market, estimated_probability, edge, label))

    return {
        "city": city,
        "station_id": weather.get("station_id"),
        "station_name": weather.get("station_name"),
        "official_location": weather.get("official_location"),
        "official_climate_product": weather.get("official_climate_product"),
        "market_date": weather.get("market_date"),
        "settlement_source_status": weather.get("settlement_source_status"),
        "analysis_source_status": weather.get("analysis_source_status"),
        "forecast_source_status": weather.get("forecast_source_status"),
        "forecast_source_url": weather.get("forecast_source_url"),
        "forecast_graph_url": weather.get("forecast_graph_url"),
        "forecast_generated_at": weather.get("forecast_generated_at"),
        "forecast_low_time": weather.get("forecast_low_time"),
        "market_day_state": weather.get("market_day_state"),
        "source_safety_state": source_safety_state(weather),
        "bucket_state": bucket_state(weather, market),
        "cli_low_f": weather.get("cli_low_f"),
        "cli_report_issued": weather.get("cli_report_issued"),
        "cli_source_url": weather.get("cli_source_url"),
        "latest_observation_time": weather.get("latest_observation_time"),
        "market_local_time": weather.get("market_local_time"),
        "active_low_window": weather.get("active_low_window"),
        "market_title": market.get("market_title"),
        "contract_title": market.get("contract_title"),
        "kalshi_url": market.get("url"),
        "current_temp_f": weather.get("current_temp_f"),
        "raw_low_so_far_f": weather.get("raw_low_so_far_f"),
        "low_so_far_f": weather.get("low_so_far_f"),
        "forecast_low_f": weather.get("forecast_low_f"),
        "threshold_f": weather.get("threshold_f"),
        "range_low_f": market.get("range_low_f"),
        "range_high_f": market.get("range_high_f"),
        "kalshi_price": market.get("kalshi_price"),
        "estimated_probability": estimated_probability,
        "implied_probability": market.get("implied_probability"),
        "market_data_source": market.get("market_data_source") or "kalshi_page",
        "api_crowd_favorite": market.get("api_crowd_favorite"),
        "api_crowd_price": market.get("api_crowd_price"),
        "api_contract_count": market.get("api_contract_count"),
        "api_event_ticker": market.get("api_event_ticker"),
        "weather_confidence_score": confidence,
        "volatility_risk_score": volatility,
        "cooling_risk_score": cooling,
        "market_crowding_score": crowding,
        "liquidity_risk_score": liquidity,
        "estimated_edge_score": edge,
        "final_label": label,
        "reasoning": reasoning,
        "warnings": warnings,
        "weather_snapshot": weather,
        "market_snapshot": market,
    }


def score_contract_signals(city: str, weather: dict[str, Any], market: dict[str, Any]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    contracts = market.get("contracts") or []
    confidence = weather_confidence(weather)
    volatility = volatility_risk(weather)
    cooling = cooling_risk(weather)
    warnings = list(weather.get("warnings", [])) + list(market.get("warnings", []))

    for contract in contracts:
        yes_price = contract.get("yes_price")
        no_price = contract.get("no_price")
        if yes_price is None and no_price is None and weather.get("market_day_state") != "future":
            continue

        contract_market = dict(market)
        contract_market.update(
            {
                "contract_title": contract.get("label"),
                "range_low_f": contract.get("low_f"),
                "range_high_f": contract.get("high_f"),
                "kalshi_price": yes_price,
                "implied_probability": yes_price / 100 if yes_price is not None else None,
                "bid": 100 - no_price if no_price is not None else None,
                "ask": yes_price,
            }
        )
        yes_probability = estimate_range_probability(weather, contract_market)
        yes_edge = estimated_edge(yes_probability, contract_market.get("implied_probability"), confidence)

        signals.append(
            _build_side_signal(
                city=city,
                weather=weather,
                market=contract_market,
                side="YES",
                contract_probability=yes_probability,
                side_price=yes_price,
                edge=yes_edge,
                confidence=confidence,
                volatility=volatility,
                cooling=cooling,
                warnings=warnings,
            )
        )

        if no_price is not None:
            no_probability = 100 - yes_probability
            no_implied = no_price / 100
            no_edge = estimated_edge(no_probability, no_implied, confidence)
            signals.append(
                _build_side_signal(
                    city=city,
                    weather=weather,
                    market=contract_market,
                    side="NO",
                    contract_probability=no_probability,
                    side_price=no_price,
                    edge=no_edge,
                    confidence=confidence,
                    volatility=volatility,
                    cooling=cooling,
                    warnings=warnings,
                )
            )

    return sorted(signals, key=lambda signal: signal.get("estimated_edge_score", 0), reverse=True)


def _build_side_signal(
    city: str,
    weather: dict[str, Any],
    market: dict[str, Any],
    side: str,
    contract_probability: int,
    side_price: float | None,
    edge: int,
    confidence: int,
    volatility: int,
    cooling: int,
    warnings: list[str],
) -> dict[str, Any]:
    liquidity = liquidity_risk(market)
    crowding = market_crowding({"implied_probability": side_price / 100 if side_price is not None else None})
    bucket = bucket_state(weather, market)
    source_state = source_safety_state(weather)
    label = signal_label(edge, confidence, volatility, cooling, liquidity, crowding, side_price)
    signal_warnings = list(warnings)
    blocked_from_near_misses = False
    if _live_signal_depends_on_forecast(weather, market, side):
        if label in {"WATCH", "LEAN"}:
            label = "SKIP"
        blocked_from_near_misses = True
        signal_warnings.append(
            "Live same-day low market is not final; this signal depends on forecast and should not be treated as a bet."
        )
    if side == "NO" and bucket in {"PRELIMINARY_OBSERVED_LOW_IN_BUCKET", "LOCKED_BY_OBSERVED_LOW"}:
        if label in {"WATCH", "LEAN"}:
            label = "SKIP"
        blocked_from_near_misses = True
        signal_warnings.append(
            "Official-station rounded low has touched this bucket; NO is blocked until final CLI proves otherwise."
        )
    if bucket == "CROSSED_BELOW_BUCKET":
        blocked_from_near_misses = True
        signal_warnings.append(
            "Official-station rounded low has already fallen below this bucket."
        )
    if source_state == "FORECAST_ONLY":
        blocked_from_near_misses = True
        signal_warnings.append("Forecast-only low signal; do not bet from this without station observations or final CLI.")
    if weather.get("active_low_window") and source_state not in {"FINAL_CLI_AVAILABLE", "FUTURE_FORECAST"}:
        blocked_from_near_misses = True
        signal_warnings.append("Low-temperature window is still active or observation data is stale; keep live signals conservative.")
    reasons = [
        f"{side} estimated probability is {contract_probability}% vs visible price {_format_price(side_price)}.",
        f"Bucket probability is based on {_source_phrase(weather)}.",
    ]
    if side == "NO":
        reasons.append("NO signal means the low-temperature bucket appears unlikely relative to the visible No price.")
    return {
        "city": city,
        "side": side,
        "signal_label": label,
        "final_label": label,
        "market_title": market.get("market_title"),
        "contract_title": market.get("contract_title"),
        "kalshi_url": market.get("url"),
        "official_location": weather.get("official_location"),
        "official_climate_product": weather.get("official_climate_product"),
        "settlement_source_status": weather.get("settlement_source_status"),
        "analysis_source_status": weather.get("analysis_source_status"),
        "forecast_source_status": weather.get("forecast_source_status"),
        "forecast_source_url": weather.get("forecast_source_url"),
        "forecast_graph_url": weather.get("forecast_graph_url"),
        "forecast_generated_at": weather.get("forecast_generated_at"),
        "forecast_low_time": weather.get("forecast_low_time"),
        "market_day_state": weather.get("market_day_state"),
        "source_safety_state": source_state,
        "bucket_state": bucket,
        "blocked_from_near_misses": blocked_from_near_misses,
        "cli_low_f": weather.get("cli_low_f"),
        "cli_source_url": weather.get("cli_source_url"),
        "current_temp_f": weather.get("current_temp_f"),
        "raw_low_so_far_f": weather.get("raw_low_so_far_f"),
        "low_so_far_f": weather.get("low_so_far_f"),
        "latest_observation_time": weather.get("latest_observation_time"),
        "market_local_time": weather.get("market_local_time"),
        "active_low_window": weather.get("active_low_window"),
        "forecast_low_f": weather.get("forecast_low_f"),
        "range_low_f": market.get("range_low_f"),
        "range_high_f": market.get("range_high_f"),
        "side_price": side_price,
        "kalshi_price": side_price,
        "market_data_source": market.get("market_data_source") or "kalshi_page",
        "api_crowd_favorite": market.get("api_crowd_favorite"),
        "api_crowd_price": market.get("api_crowd_price"),
        "api_contract_count": market.get("api_contract_count"),
        "estimated_probability": contract_probability,
        "weather_confidence_score": confidence,
        "volatility_risk_score": volatility,
        "cooling_risk_score": cooling,
        "liquidity_risk_score": liquidity,
        "market_crowding_score": crowding,
        "estimated_edge_score": edge,
        "reasoning": reasons,
        "warnings": signal_warnings,
    }


def _live_signal_depends_on_forecast(weather: dict[str, Any], market: dict[str, Any], side: str) -> bool:
    if weather.get("market_day_state") == "future":
        return False
    if weather.get("settlement_source_status") == "cli_available":
        return False
    if weather.get("active_low_window"):
        return True
    bucket = bucket_state(weather, market)
    if side == "YES":
        return bucket not in {"LOCKED_BY_OBSERVED_LOW", "CROSSED_BELOW_BUCKET"}
    if bucket in {"PRELIMINARY_OBSERVED_LOW_IN_BUCKET", "LOCKED_BY_OBSERVED_LOW", "CROSSED_BELOW_BUCKET"}:
        return False
    return True


def signal_label(
    edge: int,
    confidence: int,
    volatility: int,
    cooling: int,
    liquidity: int,
    crowding: int,
    side_price: float | None,
) -> str:
    if side_price is None:
        return "SKIP"
    if confidence < 60 or volatility >= 80 or cooling >= 75:
        return "AVOID"
    if liquidity >= 85:
        return "AVOID"
    if edge >= 45 and confidence >= 85 and liquidity < 75 and crowding < 85:
        return "WATCH"
    if edge >= 25 and confidence >= 75:
        return "LEAN"
    return "SKIP"


def estimate_weather_probability(weather: dict[str, Any], market: dict[str, Any] | None = None) -> int:
    if market and (market.get("range_low_f") is not None or market.get("range_high_f") is not None):
        return estimate_range_probability(weather, market)

    threshold = weather.get("threshold_f")
    forecast = weather.get("forecast_low_f")
    low_so_far = weather.get("low_so_far_f")
    current = None if weather.get("market_day_state") == "future" else weather.get("current_temp_f")
    side = weather.get("contract_side", "below")
    if threshold is None or forecast is None:
        return 50

    reference_low = min(v for v in [forecast, low_so_far, current] if v is not None)
    margin = reference_low - threshold
    probability_above = 50 + margin * 12
    probability_above -= max(0, cooling_risk(weather) - 50) * 0.25
    probability_above -= max(0, volatility_risk(weather) - 50) * 0.15
    probability_above = _clamp(probability_above)

    if side == "above":
        return probability_above
    return 100 - probability_above


def estimate_range_probability(weather: dict[str, Any], market: dict[str, Any]) -> int:
    cli_available = weather.get("settlement_source_status") == "cli_available"
    forecast = weather.get("cli_low_f") if cli_available else None
    if forecast is None:
        forecast = weather.get("forecast_low_f")
    low_so_far = weather.get("low_so_far_f")
    current = None if weather.get("market_day_state") == "future" else weather.get("current_temp_f")
    if forecast is None:
        return 50

    low = market.get("range_low_f")
    high = market.get("range_high_f")

    if cli_available:
        return 100 if _value_in_bucket(forecast, low, high) else 0

    bucket = bucket_state(weather, market)
    if bucket == "CROSSED_BELOW_BUCKET":
        return 0
    if bucket == "LOCKED_BY_OBSERVED_LOW":
        return 96
    if bucket == "PRELIMINARY_OBSERVED_LOW_IN_BUCKET":
        return _clamp(92 - _fall_below_lower_risk(weather, low))

    expected = min([value for value in [forecast, low_so_far, current] if value is not None], default=forecast)
    stdev = weather.get("station_temp_stdev_f") or 2.0
    disagreement = weather.get("model_disagreement_f") or 0
    sigma = max(0.8, min(6.0, stdev + disagreement * 0.6))

    if low is None and high is not None:
        probability = _normal_cdf((high - expected + 0.5) / sigma)
    elif high is None and low is not None:
        probability = 1 - _normal_cdf((low - expected - 0.5) / sigma)
    elif low is not None and high is not None:
        upper = _normal_cdf((high - expected + 0.5) / sigma)
        lower = _normal_cdf((low - expected - 0.5) / sigma)
        probability = max(0, upper - lower)
    else:
        probability = 0.5

    if cli_available or weather.get("market_day_state") == "future":
        risk_penalty = 0
    else:
        risk_penalty = (cooling_risk(weather) * 0.0015) + (volatility_risk(weather) * 0.001)
    return _clamp((probability - risk_penalty) * 100)


def source_safety_state(weather: dict[str, Any]) -> str:
    status = weather.get("settlement_source_status")
    if weather.get("market_day_state") == "future":
        return "FUTURE_FORECAST"
    if status == "cli_available" and weather.get("cli_low_f") is not None:
        return "FINAL_CLI_AVAILABLE"
    if weather.get("low_so_far_f") is not None or weather.get("current_temp_f") is not None:
        return "LIVE_OBS_PRELIMINARY"
    if status in {"cli_wrong_date", "cli_inconsistent", "cli_unverified_date"}:
        return "CLI_STALE"
    return "FORECAST_ONLY"


def bucket_state(weather: dict[str, Any], market: dict[str, Any]) -> str:
    low = market.get("range_low_f")
    high = market.get("range_high_f")
    if low is None and high is None:
        return "UNRESOLVED_BUCKET"

    if weather.get("settlement_source_status") == "cli_available" and weather.get("cli_low_f") is not None:
        return "FINAL_YES" if _value_in_bucket(weather["cli_low_f"], low, high) else "FINAL_NO"

    low_so_far = weather.get("low_so_far_f")
    if low_so_far is None:
        return "UNRESOLVED_BUCKET"
    if low is not None and low_so_far < low:
        return "CROSSED_BELOW_BUCKET"
    if low is None and high is not None and low_so_far <= high:
        return "LOCKED_BY_OBSERVED_LOW"
    if high is None and low is not None and low_so_far >= low:
        return "PRELIMINARY_OBSERVED_LOW_IN_BUCKET"
    if low is not None and high is not None and low_so_far <= high:
        return "PRELIMINARY_OBSERVED_LOW_IN_BUCKET"
    return "UNRESOLVED_BUCKET"


def _value_in_bucket(value: float, low: float | None, high: float | None) -> bool:
    if high is not None and value > high:
        return False
    if low is not None and value < low:
        return False
    return True


def _fall_below_lower_risk(weather: dict[str, Any], low: float | None) -> float:
    if low is None:
        return 0
    forecast = weather.get("forecast_low_f")
    current = weather.get("current_temp_f")
    risk = cooling_risk(weather) * 0.45 + volatility_risk(weather) * 0.25
    if forecast is not None:
        risk += max(0, low - forecast) * 18
    if current is not None:
        risk += max(0, low - current) * 4
    return risk


def weather_confidence(weather: dict[str, Any]) -> int:
    if weather.get("settlement_source_status") == "cli_available" and weather.get("cli_low_f") is not None:
        return 95

    score = 85
    if weather.get("market_day_state") != "future" and weather.get("current_temp_f") is None:
        score -= 20
    if weather.get("forecast_low_f") is None:
        score -= 25
    if weather.get("market_day_state") != "future" and weather.get("low_so_far_f") is None:
        score -= 15
    disagreement = weather.get("model_disagreement_f")
    if disagreement is not None:
        score -= min(25, disagreement * 5)
    elif weather.get("open_meteo_low_f") is None:
        score -= 8
    if weather.get("coastal_risk"):
        score -= 8
    if weather.get("station_temp_stdev_f") and weather["station_temp_stdev_f"] > 4:
        score -= 8
    return _clamp(score)


def volatility_risk(weather: dict[str, Any]) -> int:
    if weather.get("settlement_source_status") == "cli_available" and weather.get("cli_low_f") is not None:
        return 10

    score = 20
    stdev = weather.get("station_temp_stdev_f")
    if stdev is not None:
        score += min(35, stdev * 8)
    if weather.get("wind_shift"):
        score += 15
    if weather.get("cloud_cover_change") is not None and abs(weather["cloud_cover_change"]) > 25:
        score += 15
    if weather.get("model_disagreement_f") is not None:
        score += min(25, weather["model_disagreement_f"] * 5)
    return _clamp(score)


def cooling_risk(weather: dict[str, Any]) -> int:
    if weather.get("settlement_source_status") == "cli_available" and weather.get("cli_low_f") is not None:
        return 5

    score = 15
    threshold = weather.get("threshold_f")
    forecast = weather.get("forecast_low_f")
    low_so_far = weather.get("low_so_far_f")
    current = None if weather.get("market_day_state") == "future" else weather.get("current_temp_f")
    observed_floor = min([v for v in [low_so_far, current] if v is not None], default=None)
    if threshold is not None and observed_floor is not None and observed_floor <= threshold + 1:
        score += 25
    if forecast is not None and observed_floor is not None and observed_floor - forecast >= 5:
        score += 25
    if weather.get("pressure_trend") == "rising":
        score += 8
    if weather.get("humidity_trend") == "rising":
        score += 8
    if weather.get("cloud_cover_change") is not None and weather["cloud_cover_change"] > 20:
        score += 10
    if weather.get("coastal_risk"):
        score += 10
    if weather.get("wind_shift"):
        score += 10
    return _clamp(score)


def market_crowding(market: dict[str, Any]) -> int:
    probability = market.get("implied_probability")
    recent_move = abs(market.get("recent_move_cents") or 0)
    if probability is None:
        return 50
    score = 20
    if probability > 0.75 or probability < 0.25:
        score += 25
    score += min(35, recent_move * 2)
    return _clamp(score)


def liquidity_risk(market: dict[str, Any]) -> int:
    bid = market.get("bid")
    ask = market.get("ask")
    volume = market.get("volume")
    if bid is None and ask is None and volume is None:
        return 85
    score = 20
    if bid is not None and ask is not None:
        score += min(50, max(0, ask - bid) * 2)
    else:
        score += 20
    if volume is None:
        score += 25
    elif volume < 100:
        score += 35
    elif volume < 500:
        score += 18
    return _clamp(score)


def estimated_edge(estimated_probability: int, implied_probability: float | None, confidence: int) -> int:
    if implied_probability is None:
        return 0
    raw_edge = estimated_probability - implied_probability * 100
    confidence_factor = confidence / 100
    return _clamp(raw_edge * 2.2 * confidence_factor)


def final_label(
    edge: int,
    confidence: int,
    volatility: int,
    cooling: int,
    liquidity: int,
    crowding: int,
    warnings: list[str],
    missing_market: bool = False,
) -> str:
    if cooling >= 75 or volatility >= 80:
        return "AVOID"
    if liquidity >= 85 and not missing_market:
        return "AVOID"
    if confidence < 35:
        return "AVOID"
    if missing_market:
        return "WAIT"
    if warnings and edge < 55:
        return "WAIT"
    if edge >= 60 and confidence >= 70 and cooling < 55 and liquidity < 65 and crowding < 70:
        return "RESEARCH WATCH"
    if edge >= 35 and confidence >= 50 and liquidity < 80:
        return "WAIT"
    return "SKIP"


def _reasoning(
    weather: dict[str, Any],
    market: dict[str, Any],
    estimated_probability: int,
    edge: int,
    label: str,
) -> list[str]:
    reasons = [
        f"Estimated low-temperature probability is {estimated_probability}% with edge score {edge}.",
    ]
    if weather.get("settlement_source_status") == "cli_available" and weather.get("cli_low_f") is not None:
        reasons.append(
            f"NWS CLI report low is {weather['cli_low_f']:.1f}F "
            f"({weather.get('official_climate_product', 'CLI')})."
        )
    else:
        reasons.append("NWS CLI report low is not available yet; using observation/forecast fallback.")
    threshold = weather.get("threshold_f")
    low_so_far = weather.get("low_so_far_f")
    forecast = weather.get("forecast_low_f")
    if market.get("range_low_f") is not None or market.get("range_high_f") is not None:
        reasons.append(f"Scored visible Kalshi bucket: {_format_range(market)}.")
    if threshold is not None and low_so_far is not None:
        reasons.append(f"Low so far is {low_so_far:.1f}F vs threshold {threshold:.1f}F.")
    if threshold is not None and forecast is not None:
        reasons.append(f"Forecast low is {forecast:.1f}F vs threshold {threshold:.1f}F.")
    if market.get("implied_probability") is not None:
        reasons.append(f"Visible Kalshi implied probability is {market['implied_probability']:.0%}.")
    if weather.get("coastal_risk"):
        reasons.append("Coastal/marine-layer risk is enabled for this station.")
    if label == "RESEARCH WATCH":
        reasons.append("Research-only watch signal; verify official contract station before acting.")
    return reasons


def _normal_cdf(value: float) -> float:
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))


def _format_range(market: dict[str, Any]) -> str:
    low = market.get("range_low_f")
    high = market.get("range_high_f")
    if low is None and high is None:
        return "unknown"
    if low is None:
        return f"{high:.0f}F or below"
    if high is None:
        return f"{low:.0f}F or above"
    return f"{low:.0f}F to {high:.0f}F"


def _format_price(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f} cents"


def _source_phrase(weather: dict[str, Any]) -> str:
    if weather.get("settlement_source_status") == "cli_available" and weather.get("cli_low_f") is not None:
        return f"NWS CLI low {weather['cli_low_f']:.1f}F"
    if weather.get("low_so_far_f") is not None:
        return "NWS observation low-so-far plus forecast fallback"
    return "forecast fallback"


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return int(max(low, min(high, round(value))))
