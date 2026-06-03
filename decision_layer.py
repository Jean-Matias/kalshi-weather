from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def enrich_decision_layer(row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    now = _parse_time(row.get("market_local_time"))
    peak = _parse_time(row.get("forecast_high_time"))
    time_to_peak = _minutes_between(now, peak)
    critical_window = _critical_window_et(peak)

    raw_high = _first_number(
        row.get("raw_high_so_far_f"),
        row.get("high_so_far_f"),
        row.get("current_temp_f"),
    )
    low = _to_float(row.get("range_low_f"))
    high = _to_float(row.get("range_high_f"))
    forecast = _to_float(row.get("forecast_high_f"))
    heating_rate = _to_float(row.get("heating_rate_f_per_hour"))

    degrees_needed = _degrees_needed(raw_high, low)
    required_rate = _required_rate(degrees_needed, time_to_peak)
    reachability = _reachability_label(
        raw_high=raw_high,
        low=low,
        high=high,
        forecast=forecast,
        degrees_needed=degrees_needed,
        required_rate=required_rate,
        heating_rate=heating_rate,
        time_to_peak=time_to_peak,
    )
    alignment = _market_weather_alignment(low, high, forecast)
    false_pump = _false_pump_warning(row, alignment, reachability)

    enriched.update(
        {
            "critical_window_et": critical_window,
            "time_to_peak_minutes": time_to_peak,
            "degrees_needed_to_reach_bucket": _round_optional(degrees_needed),
            "required_rate_f_per_hour": _round_optional(required_rate),
            "heating_rate_f_per_hour": _round_optional(heating_rate),
            "reachability_label": reachability,
            "market_weather_alignment": alignment,
            "false_pump_warning": false_pump,
            "decision_note": _decision_note(
                row,
                reachability=reachability,
                alignment=alignment,
                false_pump=false_pump,
                degrees_needed=degrees_needed,
                required_rate=required_rate,
                heating_rate=heating_rate,
            ),
        }
    )
    return enriched


def _critical_window_et(peak: datetime | None) -> str:
    if peak is None:
        return "n/a"
    peak_et = peak.astimezone(ET)
    start_et = peak_et - timedelta(hours=1)
    if ("AM" if start_et.hour < 12 else "PM") == ("AM" if peak_et.hour < 12 else "PM"):
        return f"{_clock(start_et, suffix=False)}-{_clock(peak_et)} ET"
    return f"{_clock(start_et)}-{_clock(peak_et)} ET"


def _clock(value: datetime, *, suffix: bool = True) -> str:
    hour = value.hour % 12 or 12
    suffix_text = "AM" if value.hour < 12 else "PM"
    return f"{hour}:{value.minute:02d} {suffix_text}" if suffix else f"{hour}:{value.minute:02d}"


def _minutes_between(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    return int(round((end.astimezone(ET) - start.astimezone(ET)).total_seconds() / 60))


def _degrees_needed(raw_high: float | None, low: float | None) -> float | None:
    if raw_high is None:
        return None
    if low is None:
        return 0.0
    return max(0.0, (low - 0.5) - raw_high)


def _required_rate(degrees_needed: float | None, time_to_peak: int | None) -> float | None:
    if degrees_needed is None:
        return None
    if degrees_needed <= 0:
        return 0.0
    if time_to_peak is None or time_to_peak <= 0:
        return None
    return degrees_needed / (time_to_peak / 60)


def _reachability_label(
    *,
    raw_high: float | None,
    low: float | None,
    high: float | None,
    forecast: float | None,
    degrees_needed: float | None,
    required_rate: float | None,
    heating_rate: float | None,
    time_to_peak: int | None,
) -> str:
    if raw_high is None:
        return "UNLIKELY"
    if high is not None and raw_high >= high + 0.5:
        return "CROSSED_ABOVE"
    if low is not None and raw_high >= low - 0.5:
        if high is not None and time_to_peak is not None and time_to_peak > 45:
            if forecast is not None and forecast > high:
                return "OVERSHOOT_RISK"
        return "REACHED"
    if high is None and low is not None and raw_high >= low - 0.5:
        return "REACHED"
    if low is None:
        if high is not None and forecast is not None and forecast <= high:
            return "REACHABLE"
        return "STRETCH"
    if time_to_peak is not None and time_to_peak <= 0:
        return "UNLIKELY"
    if forecast is not None and forecast <= low - 1.0:
        return "UNLIKELY"
    if required_rate is None:
        return "STRETCH"
    live_support = heating_rate if heating_rate is not None else 1.5
    if forecast is not None and forecast >= low and required_rate <= max(2.0, live_support + 0.75):
        return "REACHABLE"
    if forecast is not None and forecast >= low - 1.0 and required_rate <= max(3.0, live_support + 1.25):
        return "STRETCH"
    return "UNLIKELY"


def _market_weather_alignment(low: float | None, high: float | None, forecast: float | None) -> str:
    if forecast is None or (low is None and high is None):
        return "NO_MARKET"
    if low is None and high is not None:
        return "ALIGNED" if forecast <= high else "MARKET_COLDER"
    if high is None and low is not None:
        return "ALIGNED" if forecast >= low else "MARKET_HOTTER"
    if low is not None and high is not None:
        if low <= forecast <= high:
            return "ALIGNED"
        if forecast < low:
            return "MARKET_HOTTER"
        return "MARKET_COLDER"
    return "NO_MARKET"


def _false_pump_warning(row: dict[str, Any], alignment: str, reachability: str) -> bool:
    price = _first_number(row.get("api_crowd_price"), row.get("kalshi_price"))
    return bool(
        alignment == "MARKET_HOTTER"
        and price is not None
        and price >= 60
        and reachability in {"UNLIKELY", "STRETCH"}
    )


def _decision_note(
    row: dict[str, Any],
    *,
    reachability: str,
    alignment: str,
    false_pump: bool,
    degrees_needed: float | None,
    required_rate: float | None,
    heating_rate: float | None,
) -> str:
    bucket = row.get("api_crowd_favorite") or row.get("contract_title") or "market bucket"
    if false_pump:
        return f"Kalshi favors {bucket}, but weather pace does not confirm the hotter move yet."
    if reachability == "REACHED":
        return f"{bucket} has been reached by the official-station high so far."
    if reachability == "CROSSED_ABOVE":
        return f"The official-station high has already moved above {bucket}."
    if reachability == "OVERSHOOT_RISK":
        return f"{bucket} is reached, but there is still overshoot risk before peak."
    if reachability == "REACHABLE":
        if required_rate is not None and heating_rate is not None and heating_rate >= required_rate:
            return f"{bucket} is reachable if live heating stays near the current pace."
        return f"{bucket} is reachable because the NWS forecast supports that bucket."
    if reachability == "STRETCH":
        return f"{bucket} is a stretch; watch for stronger live heating confirmation."
    needed = "unknown" if degrees_needed is None else f"{degrees_needed:.1f}F"
    req = "unknown" if required_rate is None else f"{required_rate:.1f}F/hr"
    pace = "unknown" if heating_rate is None else f"{heating_rate:.1f}F/hr"
    return f"{bucket} looks unlikely before peak: needs {needed} at {req}, current pace {pace}."


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_number(*values: Any) -> float | None:
    for value in values:
        number = _to_float(value)
        if number is not None:
            return number
    return None


def _round_optional(value: float | None) -> float | None:
    return None if value is None else round(value, 1)
