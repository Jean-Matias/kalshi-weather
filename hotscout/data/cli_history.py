"""IEM CLI (NWS Climatological Report Daily) puller -- cli_daily table.

This is settlement truth: Kalshi's daily-high-temperature markets resolve on
the NWS CLI report's "high" value for each city's official station.

Endpoint verified live: https://mesonet.agron.iastate.edu/json/cli.py
    ?station=<ICAO, e.g. KLAS>&year=<YYYY>
(NOT /api/1/nws/cli.json -- that path 404s despite appearing in some docs.)
Returns {"results": [{"station", "valid" (YYYY-MM-DD), "high", ...}, ...]}.
Missing/unavailable values come back as the string "M" rather than a number.
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import date
from urllib.error import HTTPError, URLError

from hotscout.config import city_config
from hotscout.data.retry import retrying

BASE_URL = "https://mesonet.agron.iastate.edu/json/cli.py"
USER_AGENT = "hotscout-data/0.1 (research-only weather data puller; contact: local-user)"
TIMEOUT = 20

# A year is treated as "fully backfilled" (safe to skip re-fetching) once it
# has at least this many rows and is not the current year.
_FULL_YEAR_ROW_THRESHOLD = 300


@retrying
def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def fetch_cli_year(station: str, year: int) -> list[dict]:
    """Fetch one year of CLI reports for a station. Returns the raw `results` list."""
    url = f"{BASE_URL}?station={station}&year={year}"
    data = _get(url)
    return data.get("results") or []


def parse_cli_record(record: dict) -> tuple[str, float] | None:
    """Extract (date, high_f) from one IEM CLI json record. Returns None if
    the date is missing or the high is missing/non-numeric (IEM uses "M")."""
    record_date = record.get("valid")
    high = record.get("high")
    if not record_date or not isinstance(high, (int, float)) or isinstance(high, bool):
        return None
    return record_date, float(high)


def upsert_cli_daily(conn, city: str, records: list[dict]) -> int:
    """INSERT OR IGNORE parsed CLI records into cli_daily. Returns rows inserted."""
    inserted = 0
    for record in records:
        parsed = parse_cli_record(record)
        if parsed is None:
            continue
        record_date, high_f = parsed
        cur = conn.execute(
            "INSERT OR IGNORE INTO cli_daily(city, date, cli_high_f, source, raw_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (city, record_date, high_f, "iem_cli", json.dumps(record)),
        )
        inserted += cur.rowcount
    return inserted


def _year_is_complete(conn, city: str, year: int) -> bool:
    if year >= date.today().year:
        return False
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM cli_daily WHERE city = ? AND date LIKE ?",
        (city, f"{year}-%"),
    ).fetchone()
    return row["n"] >= _FULL_YEAR_ROW_THRESHOLD


def backfill_city(conn, city: str, years: list[int], sleep_s: float = 0.5) -> dict:
    """Resumable: years already fully covered are skipped without an HTTP call."""
    config = city_config(city)
    station = config["station_id"]
    total_inserted = 0
    fetched_years = []
    skipped_years = []
    errors = []
    for year in years:
        if _year_is_complete(conn, city, year):
            skipped_years.append(year)
            continue
        try:
            records = fetch_cli_year(station, year)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            errors.append(f"{year}: {exc}")
            continue
        inserted = upsert_cli_daily(conn, city, records)
        conn.commit()
        total_inserted += inserted
        fetched_years.append(year)
        time.sleep(sleep_s)
    return {
        "city": city,
        "station": station,
        "rows_inserted": total_inserted,
        "fetched_years": fetched_years,
        "skipped_years": skipped_years,
        "errors": errors,
    }


def probe(city: str) -> dict:
    """Hit the endpoint once for one city and report what came back, without
    writing anything to the database."""
    config = city_config(city)
    station = config["station_id"]
    year = date.today().year
    try:
        records = fetch_cli_year(station, year)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "city": city, "station": station, "error": str(exc)}
    parsed = [parse_cli_record(r) for r in records]
    parsed = [p for p in parsed if p is not None]
    return {
        "ok": True,
        "city": city,
        "station": station,
        "url": f"{BASE_URL}?station={station}&year={year}",
        "raw_rows": len(records),
        "parsed_rows": len(parsed),
        "sample": parsed[:2],
    }
