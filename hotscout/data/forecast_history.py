"""Open-Meteo historical forecast puller -- forecast_daily table.

Two endpoints, verified live:

1. historical-forecast-api.open-meteo.com/v1/forecast
   daily=temperature_2m_max -- "what the forecast said the high would be, as
   archived for that calendar day" -> stored as lead_days=0.
   models=best_match always has data back to ~2022. models=ncep_nbm_conus
   (NWS's National Blend of Models, closest analog to what Kalshi traders
   actually look at) only returns non-null values from ~2025 onward -- older
   requests come back with `null` highs, which we skip.

2. previous-runs-api.open-meteo.com/v1/forecast
   hourly=temperature_2m_previous_dayN (N=1,2,3) -- the forecast for a given
   hour as it stood N days before that hour occurred. We take the max across
   each local calendar date's hours as that date's lead=N forecast high.
   Confirmed working for models=ncep_nbm_conus.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

from hotscout.config import city_config
from hotscout.data.retry import retrying

HIST_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
PREV_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
USER_AGENT = "hotscout-data/0.1 (research-only weather data puller; contact: local-user)"
TIMEOUT = 30

MODELS_LEAD0 = ["ncep_nbm_conus", "best_match"]
PREVIOUS_RUN_LEAD_DAYS = [1, 2, 3]
PREVIOUS_RUN_MODEL = "ncep_nbm_conus"


@retrying
def _get(url: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def fetch_lead0(lat, lon, tz, start_date, end_date, model) -> dict:
    return _get(HIST_URL, {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_max",
        "temperature_unit": "fahrenheit",
        "timezone": tz,
        "models": model,
    })


def fetch_previous_run(lat, lon, tz, start_date, end_date, lead_days, model=PREVIOUS_RUN_MODEL) -> dict:
    return _get(PREV_URL, {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": f"temperature_2m_previous_day{lead_days}",
        "temperature_unit": "fahrenheit",
        "timezone": tz,
        "models": model,
    })


def parse_lead0_response(payload: dict) -> list[tuple[str, float]]:
    daily = payload.get("daily") or {}
    dates = daily.get("time") or []
    highs = daily.get("temperature_2m_max") or []
    out = []
    for record_date, high in zip(dates, highs):
        if high is None:
            continue
        out.append((record_date, float(high)))
    return out


def parse_previous_run_response(payload: dict, lead_days: int) -> list[tuple[str, float]]:
    """Reduce the hourly temperature_2m_previous_dayN series to one
    daily-max forecast high per local calendar date."""
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    key = f"temperature_2m_previous_day{lead_days}"
    values = hourly.get(key) or []
    by_date: dict[str, float] = {}
    for ts, val in zip(times, values):
        if val is None:
            continue
        record_date = ts.split("T")[0]
        by_date[record_date] = max(val, by_date.get(record_date, val))
    return sorted(by_date.items())


def upsert_forecast_daily(conn, city: str, rows: list[tuple[str, float]], lead_days: int, model: str, source: str) -> int:
    inserted = 0
    for record_date, high_f in rows:
        cur = conn.execute(
            "INSERT OR IGNORE INTO forecast_daily(city, date, lead_days, forecast_high_f, model, source) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (city, record_date, lead_days, high_f, model, source),
        )
        inserted += cur.rowcount
    return inserted


def backfill_city(conn, city: str, start_date: str, end_date: str, sleep_s: float = 0.5) -> dict:
    config = city_config(city)
    lat, lon, tz = config["latitude"], config["longitude"], config["timezone"]
    total_inserted = 0
    errors = []

    for model in MODELS_LEAD0:
        try:
            payload = fetch_lead0(lat, lon, tz, start_date, end_date, model)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            errors.append(f"lead0/{model}: {exc}")
            continue
        rows = parse_lead0_response(payload)
        total_inserted += upsert_forecast_daily(conn, city, rows, 0, model, "open_meteo_historical_forecast")
        conn.commit()
        time.sleep(sleep_s)

    for lead_days in PREVIOUS_RUN_LEAD_DAYS:
        try:
            payload = fetch_previous_run(lat, lon, tz, start_date, end_date, lead_days)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            errors.append(f"previous_run/lead{lead_days}: {exc}")
            continue
        rows = parse_previous_run_response(payload, lead_days)
        total_inserted += upsert_forecast_daily(
            conn, city, rows, lead_days, PREVIOUS_RUN_MODEL, "open_meteo_previous_runs"
        )
        conn.commit()
        time.sleep(sleep_s)

    return {"city": city, "rows_inserted": total_inserted, "errors": errors}


def probe(city: str) -> dict:
    """Hit each forecast endpoint once for one city over a short recent
    window, without bulk-downloading or writing to the database."""
    config = city_config(city)
    lat, lon, tz = config["latitude"], config["longitude"], config["timezone"]
    # A short, recent window so ncep_nbm_conus (2025+ coverage) has data.
    start_date, end_date = "2025-06-01", "2025-06-05"
    result = {"city": city, "lat": lat, "lon": lon, "tz": tz, "lead0": {}, "previous_runs": {}}

    for model in MODELS_LEAD0:
        try:
            payload = fetch_lead0(lat, lon, tz, start_date, end_date, model)
            rows = parse_lead0_response(payload)
            result["lead0"][model] = {"ok": True, "rows": len(rows), "sample": rows[:2]}
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            result["lead0"][model] = {"ok": False, "error": str(exc)}

    for lead_days in PREVIOUS_RUN_LEAD_DAYS:
        try:
            payload = fetch_previous_run(lat, lon, tz, start_date, end_date, lead_days)
            rows = parse_previous_run_response(payload, lead_days)
            result["previous_runs"][lead_days] = {"ok": True, "rows": len(rows), "sample": rows[:2]}
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            result["previous_runs"][lead_days] = {"ok": False, "error": str(exc)}

    return result
