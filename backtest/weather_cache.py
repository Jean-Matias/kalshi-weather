"""Fetch + locally cache real hourly weather observations for Las Vegas
(Harry Reid Intl / KLAS, lat 36.08 lon -115.15) covering each historical
KXHIGHTLV event-day plus the prior 3 days — enough history for
persistence/trend weather-driven strategies.

IMPORTANT data-source note: NWS's `api.weather.gov/stations/.../observations`
endpoint (used live by weather_sources.fetch_nws_observation_history) only
retains a short rolling window (~1 week) of raw METAR observations for KLAS —
verified empirically: querying for Jan-May 2026 returns zero features, only
~June 1 2026 onward has data. That makes it useless for backtesting 67 days
of KXHIGHTLV history. Instead this module uses Open-Meteo's free historical
*archive* (reanalysis) API — `archive-api.open-meteo.com/v1/archive` — which
has full hourly temperature/pressure history for any past date, no auth, and
is what `weather_sources.fetch_open_meteo` already uses as a live fallback.
It blends station observations with ERA5 reanalysis, so it's a faithful
"what the weather actually did" record (not a forecast).

Cache layout (under backtest/cache/):
  weather_obs/KLAS/<YYYY-MM-DD>.json   - hourly temperature + pressure for
                                          that local calendar date
                                          (America/Los_Angeles) plus a
                                          derived summary (high/low/etc).

Idempotent/resumable like backtest.data.ensure_cached(): re-running only
fetches dates not already on disk.
"""
from __future__ import annotations

import json
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from config import USER_AGENT

CACHE_DIR = Path(__file__).parent / "cache" / "weather_obs" / "KLAS"
STATION_ID = "KLAS"
TZ = ZoneInfo("America/Los_Angeles")
TIMEOUT = 20
SLEEP_SECONDS = 0.4


def _get_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"})
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GET {url} failed: {exc}") from exc


def _c_to_f(celsius):
    if celsius is None:
        return None
    return celsius * 9.0 / 5.0 + 32.0


def _value(props: dict, key: str):
    entry = props.get(key)
    if not isinstance(entry, dict):
        return None
    return entry.get("value")


def measurement_date(event: dict):
    """The local calendar date (America/Los_Angeles) whose daily high the
    event settles on. Markets open at 7am local on day D-1 and close at 1am
    local on day D+1, settling the high temperature observed on day D — i.e.
    the day AFTER the local date of `open_ts` (confirmed by cross-checking
    cached observation highs against `events.json` settlement results)."""
    return datetime.fromtimestamp(event["open_ts"], TZ).date() + timedelta(days=1)


def event_dates(events: list[dict]) -> list[str]:
    """Local calendar dates (YYYY-MM-DD, America/Los_Angeles) to cache: each
    event's measurement day plus the prior 3 days."""
    dates: set[str] = set()
    for e in events:
        base = measurement_date(e)
        for delta in range(0, 4):  # 0 = measurement day, 1..3 = prior days
            dates.add((base - timedelta(days=delta)).isoformat())
    return sorted(dates)


LAT, LON = 36.08, -115.15

def _fetch_day(date_str: str) -> dict:
    """Fetch hourly historical weather for the full local calendar day
    `date_str` from Open-Meteo's archive (reanalysis) API, and derive an
    hourly trajectory + summary stats. (See module docstring for why this
    source is used instead of NWS's short-retention observations endpoint.)"""
    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={LAT}&longitude={LON}&start_date={date_str}&end_date={date_str}"
        "&hourly=temperature_2m,surface_pressure"
        "&timezone=America%2FLos_Angeles&temperature_unit=fahrenheit"
    )
    data = _get_json(url)
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps_raw = hourly.get("temperature_2m", [])
    pressures_raw = hourly.get("surface_pressure", [])

    points = []
    for i, ts in enumerate(times):
        temp_f = temps_raw[i] if i < len(temps_raw) else None
        pressure_hpa = pressures_raw[i] if i < len(pressures_raw) else None
        if temp_f is None:
            continue
        points.append({
            "timestamp": ts,  # local ISO "YYYY-MM-DDTHH:MM" (America/Los_Angeles)
            "temp_f": round(float(temp_f), 1),
            "pressure_hpa": pressure_hpa,
        })

    points.sort(key=lambda p: p["timestamp"])
    temps = [p["temp_f"] for p in points]
    pressures = [p["pressure_hpa"] for p in points if p["pressure_hpa"] is not None]

    summary = {
        "date": date_str,
        "station_id": STATION_ID,
        "source": "open-meteo-archive",
        "n_observations": len(points),
        "high_f": max(temps) if temps else None,
        "low_f": min(temps) if temps else None,
        "avg_pressure_hpa": (sum(pressures) / len(pressures)) if pressures else None,
        "first_observation": points[0]["timestamp"] if points else None,
        "last_observation": points[-1]["timestamp"] if points else None,
    }
    return {"summary": summary, "observations": points, "source_url": url}


def ensure_cached(events: list[dict] | None = None, progress_every: int = 5) -> dict:
    """Top up the local KLAS observation cache for every date needed by
    `events` (defaults to loading backtest/cache/KXHIGHTLV/events.json)."""
    if events is None:
        events_file = Path(__file__).parent / "cache" / "KXHIGHTLV" / "events.json"
        events = json.loads(events_file.read_text())

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dates = event_dates(events)
    fetched = 0
    skipped = 0
    failed = []
    for date_str in dates:
        out_file = CACHE_DIR / f"{date_str}.json"
        if out_file.exists():
            skipped += 1
            continue
        try:
            day = _fetch_day(date_str)
        except Exception as exc:
            print(f"  [weather_cache] skip {date_str}: {exc}")
            failed.append(date_str)
            continue
        out_file.write_text(json.dumps(day))
        fetched += 1
        if fetched % progress_every == 0:
            print(f"  [weather_cache] fetched {fetched} day(s) so far...")
        time.sleep(SLEEP_SECONDS)

    return {
        "total_dates_needed": len(dates),
        "already_cached": skipped,
        "newly_fetched": fetched,
        "failed": failed,
    }


def load_day(date_str: str) -> dict | None:
    """Load a cached day's observations + summary, or None if not cached."""
    f = CACHE_DIR / f"{date_str}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text())


def load_history_for_event(event: dict, lookback_days: int = 3) -> dict[str, dict]:
    """Return {date_str: day_dict} for the event's measurement day and the
    `lookback_days` days before it (only including days that are cached)."""
    base = measurement_date(event)
    out = {}
    for delta in range(0, lookback_days + 1):
        date_str = (base - timedelta(days=delta)).isoformat()
        day = load_day(date_str)
        if day is not None:
            out[date_str] = day
    return out


if __name__ == "__main__":
    summary = ensure_cached()
    print(summary)
