"""IEM ASOS archive puller -- obs_hourly table.

Endpoint verified live:
    https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py
        ?station=<3-letter, K dropped, e.g. LAS>&data=tmpf
        &year1=&month1=&day1=&year2=&month2=&day2=
        &tz=<city IANA tz>&format=onlycomma&latlon=no
Returns "onlycomma" CSV: station,valid,tmpf -- 5-minute-resolution obs with
"M" for missing readings. We downsample to hourly (max temp per local hour).
"""
from __future__ import annotations

import csv
import io
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

from hotscout.config import city_config
from hotscout.data.retry import retrying

BASE_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
USER_AGENT = "hotscout-data/0.1 (research-only weather data puller; contact: local-user)"
TIMEOUT = 60


def iem_station(station_id: str) -> str:
    """IEM ASOS station ids drop the leading "K" (e.g. KLAS -> LAS)."""
    return station_id[1:] if station_id.startswith("K") else station_id


@retrying
def fetch_asos_csv(station: str, tz: str, start_date: str, end_date: str) -> str:
    y1, m1, d1 = start_date.split("-")
    y2, m2, d2 = end_date.split("-")
    params = {
        "station": station,
        "data": "tmpf",
        "year1": y1, "month1": m1, "day1": d1,
        "year2": y2, "month2": m2, "day2": d2,
        "tz": tz,
        "format": "onlycomma",
        "latlon": "no",
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode()


def parse_asos_csv(text: str) -> list[tuple[str, float]]:
    """Parse ASOS "onlycomma" CSV, downsample to hourly-max temp_f.
    Returns (ts_local "YYYY-MM-DDTHH:00", temp_f) sorted ascending."""
    reader = csv.DictReader(io.StringIO(text))
    hourly_max: dict[str, float] = {}
    for row in reader:
        raw_temp = (row.get("tmpf") or "").strip()
        if raw_temp in ("", "M"):
            continue
        try:
            temp_f = float(raw_temp)
        except ValueError:
            continue
        valid = (row.get("valid") or "").strip()
        if "T" in valid:
            date_part, time_part = valid.split("T", 1)
        elif " " in valid:
            date_part, time_part = valid.split(" ", 1)
        else:
            continue
        hour = time_part[:2]
        if not hour.isdigit():
            continue
        ts_local = f"{date_part}T{hour}:00"
        hourly_max[ts_local] = max(temp_f, hourly_max.get(ts_local, temp_f))
    return sorted(hourly_max.items())


def upsert_obs_hourly(conn, city: str, rows: list[tuple[str, float]], source: str) -> int:
    inserted = 0
    for ts_local, temp_f in rows:
        record_date = ts_local.split("T")[0]
        cur = conn.execute(
            "INSERT OR IGNORE INTO obs_hourly(city, date, ts_local, temp_f, source) "
            "VALUES (?, ?, ?, ?, ?)",
            (city, record_date, ts_local, temp_f, source),
        )
        inserted += cur.rowcount
    return inserted


def backfill_city(conn, city: str, start_date: str, end_date: str) -> dict:
    config = city_config(city)
    station = iem_station(config["station_id"])
    tz = config["timezone"]
    try:
        text = fetch_asos_csv(station, tz, start_date, end_date)
    except (HTTPError, URLError, TimeoutError) as exc:
        return {"city": city, "station": station, "rows_inserted": 0, "error": str(exc)}
    rows = parse_asos_csv(text)
    inserted = upsert_obs_hourly(conn, city, rows, "iem_asos")
    conn.commit()
    return {"city": city, "station": station, "rows_inserted": inserted, "hourly_points": len(rows)}


def probe(city: str) -> dict:
    """Hit the ASOS endpoint once for one city over a short recent window,
    without bulk-downloading or writing to the database."""
    config = city_config(city)
    station = iem_station(config["station_id"])
    tz = config["timezone"]
    start_date, end_date = "2025-06-01", "2025-06-02"
    try:
        text = fetch_asos_csv(station, tz, start_date, end_date)
    except (HTTPError, URLError, TimeoutError) as exc:
        return {"ok": False, "city": city, "station": station, "error": str(exc)}
    rows = parse_asos_csv(text)
    return {
        "ok": True,
        "city": city,
        "station": station,
        "raw_bytes": len(text),
        "hourly_points": len(rows),
        "sample": rows[:3],
    }
