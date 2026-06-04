from __future__ import annotations

import json
import math
import re
import statistics
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from config import USER_AGENT


def fetch_weather(city_config: dict[str, Any]) -> dict[str, Any]:
    weather = _empty_weather(city_config)
    warnings: list[str] = []
    market_day_state = _market_day_state(city_config)
    weather["market_day_state"] = market_day_state

    if market_day_state != "future":
        try:
            cli = fetch_nws_cli_report(city_config)
            _merge_weather_update(weather, cli)
        except Exception as exc:
            warnings.append(f"NWS CLI settlement report unavailable: {exc}")

        try:
            latest = fetch_nws_latest_observation(city_config["station_id"])
            _merge_weather_update(weather, latest)
        except Exception as exc:
            warnings.append(f"NWS latest observation unavailable: {exc}")

        try:
            fast_metar = fetch_fast_metar_observation(city_config["station_id"])
            _merge_weather_update(weather, fast_metar)
        except Exception as exc:
            warnings.append(f"Fast METAR feed unavailable: {exc}")

        try:
            history = fetch_nws_observation_history(city_config)
            _merge_weather_update(weather, history)
        except Exception as exc:
            warnings.append(f"NWS observation history unavailable: {exc}")

    try:
        forecast = fetch_forecast_weather_gov_xml(city_config)
        _merge_weather_update(weather, forecast)
    except Exception as exc:
        warnings.append(f"forecast.weather.gov XML unavailable: {exc}")

    try:
        open_meteo = fetch_open_meteo(city_config)
        _merge_weather_update(weather, open_meteo)
    except Exception as exc:
        warnings.append(f"Open-Meteo fallback unavailable: {exc}")

    weather["warnings"].extend(warnings)
    _fill_derived_weather(weather, city_config)
    return weather

def _merge_weather_update(weather: dict[str, Any], update: dict[str, Any]) -> None:
    source_urls = list(weather.get("source_urls") or [])
    source_urls.extend(update.pop("source_urls", []) or [])
    weather.update(update)
    weather["source_urls"] = list(dict.fromkeys(source_urls))


def fetch_nws_latest_observation(station_id: str) -> dict[str, Any]:
    url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
    data = _get_json(url)
    props = data.get("properties", {})
    return {
        "current_temp_f": _c_to_f(_value(props, "temperature")),
        "humidity": _value(props, "relativeHumidity"),
        "pressure_pa": _value(props, "barometricPressure"),
        "wind_speed_mph": _ms_to_mph(_value(props, "windSpeed")),
        "wind_direction_deg": _value(props, "windDirection"),
        "cloud_text": props.get("textDescription"),
        "observation_time": props.get("timestamp"),
        "source_urls": [url],
    }


def fetch_fast_metar_observation(station_id: str) -> dict[str, Any]:
    url = f"https://aviationweather.gov/api/data/metar?ids={urllib.parse.quote(station_id)}&format=json"
    data = _get_json(url)
    if not isinstance(data, list) or not data:
        return {
            "fast_metar_temp_f": None,
            "fast_metar_time": None,
            "fast_metar_raw": None,
            "fast_feed_source": "AviationWeather METAR",
            "fast_feed_url": url,
            "source_urls": [url],
        }

    report = data[0]
    temp_c = _to_float(report.get("temp"))
    report_time = report.get("reportTime") or _epoch_to_iso(report.get("obsTime"))
    return {
        "fast_metar_temp_f": _c_to_f(temp_c),
        "fast_metar_time": report_time,
        "fast_metar_raw": report.get("rawOb"),
        "fast_feed_source": "AviationWeather METAR",
        "fast_feed_url": url,
        "source_urls": [url],
    }


def fetch_nws_cli_report(city_config: dict[str, Any]) -> dict[str, Any]:
    url = city_config.get("official_source_url")
    if not url:
        return {
            "cli_high_f": None,
            "settlement_source_status": "cli_not_configured",
            "cli_source_url": None,
        }
    text = _get_text(url)
    parsed = parse_cli_report_text(text)
    parsed["cli_source_url"] = url
    parsed["official_climate_product"] = city_config.get("official_climate_product")
    parsed["official_location"] = city_config.get("official_location")
    parsed["source_urls"] = [url]
    return parsed


def parse_cli_report_text(text: str) -> dict[str, Any]:
    high = None
    for pattern in [
        r"^\s*MAXIMUM\s+(-?\d{1,3})\b",
        r"^\s*MAX TEMP(?:ERATURE)?\s+(-?\d{1,3})\b",
        r"^\s*MAX\s+(-?\d{1,3})\b",
    ]:
        match = re.search(pattern, text, flags=re.I | re.M)
        if match:
            high = float(match.group(1))
            break

    issued_match = re.search(r"^\d{3,4}\s+[AP]M\s+\w+\s+.+$", text, flags=re.M)
    date_match = re.search(
        r"CLIMATE SUMMARY FOR ([A-Z]+)\s+(\d{1,2})\s+(\d{4})",
        text,
        flags=re.I,
    )
    return {
        "cli_high_f": high,
        "cli_report_date": _cli_date(date_match) if date_match else None,
        "cli_report_issued": issued_match.group(0).strip() if issued_match else None,
        "settlement_source_status": "cli_available" if high is not None else "cli_unavailable",
    }


def fetch_nws_observation_history(city_config: dict[str, Any]) -> dict[str, Any]:
    station_id = city_config["station_id"]
    start, end = _market_day_utc_window(city_config)
    url = (
        f"https://api.weather.gov/stations/{station_id}/observations?"
        f"start={urllib.parse.quote(start)}&end={urllib.parse.quote(end)}&limit=500"
    )
    data = _get_json(url)
    features = data.get("features", [])
    temps: list[float] = []
    humidities: list[float] = []
    pressures: list[float] = []
    wind_dirs: list[float] = []
    wind_speeds: list[float] = []
    observation_times: list[str] = []
    temp_points: list[tuple[str, float]] = []

    for feature in features:
        props = feature.get("properties", {})
        timestamp = props.get("timestamp")
        if timestamp:
            observation_times.append(timestamp)
        temp = _c_to_f(_value(props, "temperature"))
        if temp is not None:
            temps.append(temp)
            if timestamp:
                temp_points.append((timestamp, temp))
        humidity = _value(props, "relativeHumidity")
        if humidity is not None:
            humidities.append(humidity)
        pressure = _value(props, "barometricPressure")
        if pressure is not None:
            pressures.append(pressure)
        wind_dir = _value(props, "windDirection")
        if wind_dir is not None:
            wind_dirs.append(wind_dir)
        wind_speed = _ms_to_mph(_value(props, "windSpeed"))
        if wind_speed is not None:
            wind_speeds.append(wind_speed)

    raw_high_so_far = max(temps) if temps else None
    recent_points = _recent_temp_points(temp_points)
    return {
        "raw_high_so_far_f": raw_high_so_far,
        "high_so_far_f": _round_official_temp(raw_high_so_far),
        "latest_observation_time": _latest_time_text(observation_times),
        "recent_observation_points": recent_points,
        "heating_rate_f_per_hour": _heating_rate_f_per_hour(recent_points),
        "station_temp_stdev_f": statistics.pstdev(temps) if len(temps) > 1 else None,
        "humidity_trend": _trend(humidities),
        "pressure_trend": _trend(pressures),
        "wind_shift": _wind_shift(wind_dirs),
        "max_wind_speed_mph": max(wind_speeds) if wind_speeds else None,
        "source_urls": [url],
    }

def _market_day_utc_window(city_config: dict[str, Any]) -> tuple[str, str]:
    market_date = city_config.get("market_date")
    tz_name = city_config.get("timezone", "UTC")
    if not market_date:
        start = datetime.now(timezone.utc) - timedelta(hours=18)
        end = datetime.now(timezone.utc)
        return _iso_z(start), _iso_z(end)

    local_tz = ZoneInfo(tz_name)
    local_start = datetime.fromisoformat(market_date).replace(tzinfo=local_tz)
    local_end = local_start + timedelta(days=1) - timedelta(seconds=1)
    return (
        _iso_z(local_start.astimezone(timezone.utc)),
        _iso_z(local_end.astimezone(timezone.utc)),
    )


def fetch_forecast_weather_gov_xml(city_config: dict[str, Any]) -> dict[str, Any]:
    params = {
        "lat": city_config["latitude"],
        "lon": city_config["longitude"],
        "unit": "0",
        "lg": "english",
    }
    query = urllib.parse.urlencode(
        {
            **params,
            "FcstType": "digitalDWML",
        }
    )
    url = f"https://forecast.weather.gov/MapClick.php?{query}"
    xml_text = _get_text(url)
    parsed = parse_digital_dwml_forecast(xml_text, city_config.get("market_date"))
    parsed["forecast_source_url"] = url
    parsed["forecast_graph_url"] = (
        "https://forecast.weather.gov/MapClick.php?"
        + urllib.parse.urlencode({**params, "FcstType": "graphical"})
    )
    parsed["source_urls"] = [url]
    return parsed


def parse_digital_dwml_forecast(xml_text: str, target_date: str | None) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    generated_at = _first_text(root, ".//creation-date")
    layouts = _time_layouts(root)
    hourly_pairs = _dated_value_pairs(root, "temperature", "hourly", layouts, target_date)
    hourly_temps = [value for _, value in hourly_pairs]
    humidities = _dated_values(root, "humidity", "relative", layouts, target_date)
    clouds = _dated_values(root, "cloud-amount", "total", layouts, target_date)
    wind_speeds = _dated_values(root, "wind-speed", "sustained", layouts, target_date)
    wind_dirs = _dated_values(root, "direction", "wind", layouts, target_date)

    if not hourly_temps:
        hourly_pairs = _dated_value_pairs(root, "temperature", "maximum", layouts, target_date)
        hourly_temps = [value for _, value in hourly_pairs]
    high_pair = max(hourly_pairs, key=lambda item: item[1]) if hourly_pairs else None

    return {
        "forecast_high_f": max(hourly_temps) if hourly_temps else None,
        "forecast_high_time": high_pair[0] if high_pair else None,
        "forecast_hourly_temps_f": hourly_temps[:24],
        "forecast_humidity_values": humidities[:24],
        "forecast_cloud_values": clouds[:24],
        "forecast_wind_speeds_mph": wind_speeds[:24],
        "forecast_wind_directions_deg": wind_dirs[:24],
        "cloud_cover_change": _change(clouds[:12]),
        "forecast_source_status": "same_day_hourly_forecast" if hourly_temps else "forecast_unavailable",
        "forecast_generated_at": generated_at,
    }


def fetch_open_meteo(city_config: dict[str, Any]) -> dict[str, Any]:
    forecast_days = _forecast_days_needed(city_config)
    params = {
        "latitude": city_config["latitude"],
        "longitude": city_config["longitude"],
        "hourly": ",".join(
            [
                "temperature_2m",
                "cloud_cover",
                "relative_humidity_2m",
                "pressure_msl",
                "wind_speed_10m",
                "wind_direction_10m",
            ]
        ),
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": city_config.get("timezone", "auto"),
        "forecast_days": forecast_days,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    data = _get_json(url)
    hourly = data.get("hourly", {})
    target_date = city_config.get("market_date")
    hourly_times = hourly.get("time", [])
    temps = _target_dated_numbers(hourly_times, hourly.get("temperature_2m", []), target_date)
    clouds = _target_dated_numbers(hourly_times, hourly.get("cloud_cover", []), target_date)
    open_high = max(temps) if temps else None
    return {
        "open_meteo_high_f": open_high,
        "open_meteo_cloud_change": _change(clouds[:12]),
        "source_urls": [url],
    }


def _empty_weather(city_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "city": city_config["city"],
        "station_id": city_config["station_id"],
        "station_name": city_config["station_name"],
        "threshold_f": city_config["threshold_f"],
        "market_date": city_config.get("market_date"),
        "contract_side": city_config.get("contract_side", "below"),
        "coastal_risk": city_config.get("coastal_risk", False),
        "current_temp_f": None,
        "raw_high_so_far_f": None,
        "high_so_far_f": None,
        "latest_observation_time": None,
        "market_local_time": None,
        "active_heating_window": True,
        "forecast_high_f": None,
        "cli_high_f": None,
        "cli_report_date": None,
        "cli_report_issued": None,
        "cli_source_url": city_config.get("official_source_url"),
        "official_climate_product": city_config.get("official_climate_product"),
        "official_location": city_config.get("official_location"),
        "settlement_source_status": "cli_not_checked",
        "analysis_source_status": None,
        "forecast_source_status": None,
        "open_meteo_high_f": None,
        "forecast_graph_url": None,
        "humidity_trend": "unknown",
        "pressure_trend": "unknown",
        "wind_shift": False,
        "cloud_cover_change": None,
        "station_temp_stdev_f": None,
        "model_disagreement_f": None,
        "source_urls": [],
        "warnings": [],
    }


def _fill_derived_weather(
    weather: dict[str, Any],
    city_config: dict[str, Any],
    now: datetime | None = None,
) -> None:
    cli_high = weather.get("cli_high_f")
    target_date = city_config.get("market_date")
    cli_report_date = weather.get("cli_report_date")
    market_day_state = weather.get("market_day_state") or _market_day_state(city_config, now)
    weather["market_day_state"] = market_day_state
    market_is_future = market_day_state == "future"
    observed_candidates = [
        value
        for value in [weather.get("current_temp_f"), weather.get("high_so_far_f")]
        if value is not None and not market_is_future
    ]
    observed_high = max(observed_candidates) if observed_candidates else None
    if cli_high is not None and target_date and cli_report_date and cli_report_date != target_date:
        weather["settlement_source_status"] = "cli_wrong_date"
        weather["warnings"].append(
            f"NWS CLI settlement report date {cli_report_date} does not match Kalshi market date {target_date}; using same-day station observations when available."
        )
    elif cli_high is not None and target_date and not cli_report_date:
        weather["settlement_source_status"] = "cli_unverified_date"
        weather["warnings"].append(
            "NWS CLI report date could not be parsed; treating CLI high as unverified for this market date."
        )
    elif cli_high is not None and observed_high is not None and observed_high > cli_high + 1:
        weather["settlement_source_status"] = "cli_inconsistent"
        weather["warnings"].append(
            f"NWS CLI high {cli_high:.1f}F is below observed high/current {observed_high:.1f}F; treating CLI as preliminary or stale."
        )
    elif cli_high is not None and _market_day_still_open(city_config, now):
        weather["settlement_source_status"] = "cli_preliminary"
        weather["warnings"].append(
            "NWS CLI report matches the market date but the local weather day is still open; treating CLI high as preliminary."
        )
    elif cli_high is not None:
        weather["high_so_far_f"] = weather["cli_high_f"]
        weather["forecast_high_f"] = weather["cli_high_f"]
        weather["settlement_source_status"] = "cli_available"
    if weather.get("high_so_far_f") is None and not market_is_future:
        weather["high_so_far_f"] = weather.get("current_temp_f")
    if weather.get("latest_observation_time") is None:
        weather["latest_observation_time"] = weather.get("observation_time")
    if weather.get("forecast_high_f") is None:
        weather["forecast_high_f"] = weather.get("open_meteo_high_f")
    if weather.get("settlement_source_status") in {None, "cli_not_checked"}:
        weather["settlement_source_status"] = "cli_unavailable"
    if market_is_future:
        weather["analysis_source_status"] = "future_hourly_forecast"
        if weather.get("forecast_high_f") is not None:
            weather["forecast_source_status"] = "future_hourly_forecast"
    elif weather.get("high_so_far_f") is not None or weather.get("current_temp_f") is not None:
        weather["analysis_source_status"] = "same_day_station_observations"
    elif weather.get("settlement_source_status") in {
        "cli_wrong_date",
        "cli_inconsistent",
        "cli_preliminary",
        "cli_unavailable",
        "cli_unverified_date",
    }:
        if weather.get("forecast_source_status") == "same_day_hourly_forecast":
            weather["analysis_source_status"] = "same_day_hourly_forecast"
    if weather.get("analysis_source_status") is None:
        weather["analysis_source_status"] = weather.get("settlement_source_status")
    if weather.get("model_disagreement_f") is None:
        a = weather.get("forecast_high_f")
        b = weather.get("open_meteo_high_f")
        weather["model_disagreement_f"] = abs(a - b) if a is not None and b is not None else None
    if weather.get("cloud_cover_change") is None:
        weather["cloud_cover_change"] = weather.get("open_meteo_cloud_change")
    _fill_heating_window(weather, city_config, now)
    weather["notes"] = city_config.get("notes", "")

def _market_day_still_open(city_config: dict[str, Any], now: datetime | None) -> bool:
    target_date = city_config.get("market_date")
    if not target_date:
        return False
    try:
        market_day = datetime.fromisoformat(target_date).date()
    except ValueError:
        return True
    tz = ZoneInfo(city_config.get("timezone", "UTC"))
    local_now = (now or datetime.now(timezone.utc)).astimezone(tz)
    return local_now.date() <= market_day and local_now.hour < 21

def _market_day_state(city_config: dict[str, Any], now: datetime | None = None) -> str:
    target_date = city_config.get("market_date")
    if not target_date:
        return "unknown"
    try:
        market_day = datetime.fromisoformat(target_date).date()
    except ValueError:
        return "unknown"
    tz = ZoneInfo(city_config.get("timezone", "UTC"))
    local_now = (now or datetime.now(timezone.utc)).astimezone(tz).date()
    if market_day > local_now:
        return "future"
    if market_day < local_now:
        return "past"
    return "today"

def _forecast_days_needed(city_config: dict[str, Any]) -> int:
    target_date = city_config.get("market_date")
    if not target_date:
        return 1
    try:
        target = datetime.fromisoformat(target_date).date()
    except ValueError:
        return 1
    tz = ZoneInfo(city_config.get("timezone", "UTC"))
    today = datetime.now(timezone.utc).astimezone(tz).date()
    return max(1, min(7, (target - today).days + 1))

def _fill_heating_window(
    weather: dict[str, Any],
    city_config: dict[str, Any],
    now: datetime | None,
) -> None:
    tz = ZoneInfo(city_config.get("timezone", "UTC"))
    local_now = (now or datetime.now(timezone.utc)).astimezone(tz)
    weather["market_local_time"] = local_now.isoformat(timespec="seconds")

    if weather.get("settlement_source_status") == "cli_available" and weather.get("cli_high_f") is not None:
        weather["active_heating_window"] = False
        return

    market_date = city_config.get("market_date")
    active = True
    if market_date:
        try:
            market_day = datetime.fromisoformat(market_date).date()
            if market_day > local_now.date():
                weather["active_heating_window"] = True
                return
            active = local_now.date() <= market_day and local_now.hour < 21
        except ValueError:
            active = True

    latest_text = weather.get("latest_observation_time")
    latest_time = _parse_time(latest_text) if latest_text else None
    if latest_time is None:
        active = True
        weather["warnings"].append(
            "Latest station observation timestamp is unavailable; keeping heating-window risk active."
        )
    else:
        age_minutes = (local_now.astimezone(timezone.utc) - latest_time.astimezone(timezone.utc)).total_seconds() / 60
        if age_minutes > 90:
            active = True
            weather["warnings"].append(
                f"Latest station observation is stale ({age_minutes:.0f} minutes old); keeping heating-window risk active."
            )

    weather["active_heating_window"] = active


def _get_json(url: str) -> dict[str, Any]:
    return json.loads(_get_text(url))


def _get_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")

def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _epoch_to_iso(value: Any) -> str | None:
    try:
        if value is None:
            return None
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError):
        return None


def _latest_time_text(values: list[str]) -> str | None:
    parsed = [(_parse_time(value), value) for value in values]
    parsed = [(time, value) for time, value in parsed if time is not None]
    if not parsed:
        return None
    return max(parsed, key=lambda item: item[0])[1]


def _recent_temp_points(points: list[tuple[str, float]]) -> list[dict[str, float | str]]:
    parsed = [(_parse_time(timestamp), timestamp, temp) for timestamp, temp in points]
    parsed = [(time, timestamp, temp) for time, timestamp, temp in parsed if time is not None]
    if not parsed:
        return []
    parsed.sort(key=lambda item: item[0])
    latest = parsed[-1][0]
    cutoff = latest - timedelta(minutes=70)
    recent = [(timestamp, temp) for time, timestamp, temp in parsed if time >= cutoff]
    return [{"time": timestamp, "temp_f": round(temp, 1)} for timestamp, temp in recent[-12:]]


def _heating_rate_f_per_hour(points: list[dict[str, float | str]]) -> float | None:
    if len(points) < 2:
        return None
    first = points[0]
    last = points[-1]
    first_time = _parse_time(str(first.get("time")))
    last_time = _parse_time(str(last.get("time")))
    if first_time is None or last_time is None:
        return None
    hours = (last_time - first_time).total_seconds() / 3600
    if hours <= 0:
        return None
    first_temp = _to_float(first.get("temp_f"))
    last_temp = _to_float(last.get("temp_f"))
    if first_temp is None or last_temp is None:
        return None
    return round((last_temp - first_temp) / hours, 1)


def _value(props: dict[str, Any], key: str) -> float | None:
    raw = props.get(key)
    if isinstance(raw, dict):
        raw = raw.get("value")
    return _to_float(raw)


def _to_float(value: Any) -> float | None:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_numbers(values: list[Any]) -> list[float]:
    return [number for number in (_to_float(value) for value in values) if number is not None]

def _target_dated_numbers(times: list[str], values: list[Any], target_date: str | None) -> list[float]:
    if not target_date or not times:
        return _clean_numbers(values)
    return [
        number
        for time_text, number in zip(times, (_to_float(value) for value in values))
        if number is not None and str(time_text).startswith(target_date)
    ]


def _float_values(nodes: list[ET.Element]) -> list[float]:
    return [number for number in (_to_float(node.text) for node in nodes) if number is not None]

def _first_text(root: ET.Element, path: str) -> str | None:
    node = root.find(path)
    if node is None or not node.text:
        return None
    return node.text.strip()


def _time_layouts(root: ET.Element) -> dict[str, list[str]]:
    layouts: dict[str, list[str]] = {}
    for layout in root.findall(".//time-layout"):
        key_node = layout.find("layout-key")
        if key_node is None or not key_node.text:
            continue
        layouts[key_node.text] = [
            node.text or ""
            for node in layout.findall("start-valid-time")
        ]
    return layouts


def _dated_values(
    root: ET.Element,
    tag: str,
    value_type: str,
    layouts: dict[str, list[str]],
    target_date: str | None,
) -> list[float]:
    for node in root.findall(f".//{tag}"):
        if node.attrib.get("type") != value_type:
            continue
        layout_key = node.attrib.get("time-layout")
        times = layouts.get(layout_key or "", [])
        values = _float_values(node.findall("value"))
        if not target_date or not times:
            return values
        return [
            value
            for time_text, value in zip(times, values)
            if time_text.startswith(target_date)
        ]
    return []

def _dated_value_pairs(
    root: ET.Element,
    tag: str,
    value_type: str,
    layouts: dict[str, list[str]],
    target_date: str | None,
) -> list[tuple[str, float]]:
    for node in root.findall(f".//{tag}"):
        if node.attrib.get("type") != value_type:
            continue
        layout_key = node.attrib.get("time-layout")
        times = layouts.get(layout_key or "", [])
        values = _float_values(node.findall("value"))
        pairs = [
            (time_text, value)
            for time_text, value in zip(times, values)
            if not target_date or time_text.startswith(target_date)
        ]
        if pairs:
            return pairs
        if not target_date and values:
            return [(str(index), value) for index, value in enumerate(values)]
    return []


def _c_to_f(value: float | None) -> float | None:
    return None if value is None else round(value * 9 / 5 + 32, 1)

def _round_official_temp(value: float | None) -> float | None:
    if value is None:
        return None
    return float(math.floor(value + 0.5))


def _ms_to_mph(value: float | None) -> float | None:
    return None if value is None else round(value * 2.23694, 1)


def _trend(values: list[float]) -> str:
    if len(values) < 4:
        return "unknown"
    recent = statistics.mean(values[:3])
    older = statistics.mean(values[-3:])
    if recent > older * 1.01:
        return "rising"
    if recent < older * 0.99:
        return "falling"
    return "steady"


def _change(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return round(values[-1] - values[0], 1)


def _wind_shift(values: list[float]) -> bool:
    if len(values) < 4:
        return False
    diff = abs(values[0] - values[-1])
    return min(diff, 360 - diff) > 45


def _cli_date(match: re.Match[str]) -> str | None:
    months = {
        "JANUARY": 1,
        "FEBRUARY": 2,
        "MARCH": 3,
        "APRIL": 4,
        "MAY": 5,
        "JUNE": 6,
        "JULY": 7,
        "AUGUST": 8,
        "SEPTEMBER": 9,
        "OCTOBER": 10,
        "NOVEMBER": 11,
        "DECEMBER": 12,
    }
    month = months.get(match.group(1).upper())
    if month is None:
        return None
    return f"{int(match.group(3)):04d}-{month:02d}-{int(match.group(2)):02d}"
