from __future__ import annotations

import json
import re
import time
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backtest.market_specs import MarketSpec


CACHE_ROOT = Path(__file__).parent / "cache" / "low_weather"
TIMEOUT = 20
SLEEP_SECONDS = 0.4
_EVENT_DATE_RE = re.compile(r"-(\d{2})([A-Z]{3})(\d{2})$")
_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def measurement_date(event: dict[str, Any]) -> date:
    match = _EVENT_DATE_RE.search(str(event["event_ticker"]))
    if match:
        year = 2000 + int(match.group(1))
        month = _MONTHS[match.group(2)]
        day = int(match.group(3))
        return date(year, month, day)
    return datetime.fromtimestamp(int(event["open_ts"])).date()


def select_low_settlement(
    cli_payload: dict[str, Any] | None,
    archive_day: dict[str, Any] | None,
    market_date: str,
) -> dict[str, Any]:
    warnings: list[str] = []
    cli_payload = cli_payload or {}
    cli_low = _to_float(cli_payload.get("cli_low_f"))
    cli_report_date = cli_payload.get("cli_report_date")
    if cli_low is not None and cli_report_date == market_date:
        return {
            "actual_low_f": cli_low,
            "actual_raw_f": cli_low,
            "actual_source": "nws_cli",
            "warnings": [],
        }
    if cli_low is not None and cli_report_date != market_date:
        warnings.append(f"Stale CLI ignored: report date {cli_report_date} does not match {market_date}.")

    archive_low = None
    if archive_day:
        archive_low = _to_float((archive_day.get("summary") or {}).get("low_f"))
    if archive_low is not None:
        return {
            "actual_low_f": archive_low,
            "actual_raw_f": archive_low,
            "actual_source": "open-meteo-archive",
            "warnings": warnings + ["Open-Meteo archive fallback used for historical low."],
        }

    return {
        "actual_low_f": None,
        "actual_raw_f": None,
        "actual_source": "not_available",
        "warnings": warnings + ["No low-temperature settlement source available."],
    }


def ensure_cached(
    spec: MarketSpec,
    events: list[dict[str, Any]],
    *,
    cache_root: Path = CACHE_ROOT,
    lookback_days: int = 3,
    sleep_seconds: float = SLEEP_SECONDS,
    fetch_json=None,
) -> dict[str, Any]:
    station_dir = cache_root / spec.station_id
    station_dir.mkdir(parents=True, exist_ok=True)
    dates = event_dates(events, lookback_days=lookback_days)
    fetched = 0
    skipped = 0
    failed: list[str] = []
    fetch = fetch_json or _get_json
    for date_str in dates:
        out_file = station_dir / f"{date_str}.json"
        if out_file.exists():
            skipped += 1
            continue
        try:
            day = _fetch_archive_day(spec, date_str, fetch)
        except Exception:
            failed.append(date_str)
            continue
        out_file.write_text(json.dumps(day, indent=2))
        fetched += 1
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return {
        "station_id": spec.station_id,
        "total_dates_needed": len(dates),
        "already_cached": skipped,
        "newly_fetched": fetched,
        "failed": failed,
    }


def event_dates(events: list[dict[str, Any]], *, lookback_days: int = 3) -> list[str]:
    dates: set[str] = set()
    for event in events:
        base = measurement_date(event)
        for delta in range(lookback_days + 1):
            dates.add((base - timedelta(days=delta)).isoformat())
    return sorted(dates)


def load_history_for_event(
    spec: MarketSpec,
    event: dict[str, Any],
    *,
    cache_root: Path = CACHE_ROOT,
    lookback_days: int = 3,
) -> dict[str, dict[str, Any]]:
    base = measurement_date(event)
    out = {}
    for delta in range(lookback_days + 1):
        date_str = (base - timedelta(days=delta)).isoformat()
        path = cache_root / spec.station_id / f"{date_str}.json"
        if path.exists():
            out[date_str] = json.loads(path.read_text())
    return out


def _fetch_archive_day(spec: MarketSpec, date_str: str, fetch_json) -> dict[str, Any]:
    params = {
        "latitude": spec.latitude,
        "longitude": spec.longitude,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": "temperature_2m,surface_pressure",
        "timezone": spec.timezone,
        "temperature_unit": "fahrenheit",
    }
    url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(params)
    payload = fetch_json(url)
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    pressures = hourly.get("surface_pressure") or []
    observations = []
    for index, timestamp in enumerate(times):
        if index >= len(temps) or temps[index] is None:
            continue
        observations.append(
            {
                "timestamp": timestamp,
                "temp_f": round(float(temps[index]), 1),
                "pressure_hpa": pressures[index] if index < len(pressures) else None,
            }
        )
    values = [obs["temp_f"] for obs in observations]
    pressure_values = [obs["pressure_hpa"] for obs in observations if obs["pressure_hpa"] is not None]
    return {
        "summary": {
            "date": date_str,
            "station_id": spec.station_id,
            "source": "open-meteo-archive",
            "n_observations": len(observations),
            "low_f": min(values) if values else None,
            "high_f": max(values) if values else None,
            "avg_pressure_hpa": sum(pressure_values) / len(pressure_values) if pressure_values else None,
            "first_observation": observations[0]["timestamp"] if observations else None,
            "last_observation": observations[-1]["timestamp"] if observations else None,
        },
        "observations": observations,
        "source_url": url,
    }


def _get_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "kalshi-low-weather-backtest-research"})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GET {url} failed: {exc}") from exc


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None
