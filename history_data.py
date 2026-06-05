from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from config import DATABASE_PATH


def load_historical_payload(
    city: str,
    *,
    days: int = 3,
    db_path: Path = DATABASE_PATH,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(db_path)
        close_conn = True
    conn.row_factory = sqlite3.Row
    try:
        market_rows = _rows(conn, "market_snapshots", city)
        weather_rows = _rows(conn, "weather_snapshots", city)
        weather_by_time = {row["captured_at"]: _payload(row) for row in weather_rows}
        market_dates = _latest_market_dates(market_rows, weather_by_time, days)
        return {
            "city": city,
            "days": [
                _day_payload(date, [row for row in market_rows if _market_date(row, weather_by_time) == date], weather_by_time)
                for date in market_dates
            ],
        }
    finally:
        if close_conn:
            conn.close()


def _rows(conn: sqlite3.Connection, table: str, city: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            f"""
            select captured_at, payload_json
            from {table}
            where city = ?
            order by captured_at asc
            """,
            (city,),
        )
    )


def _latest_market_dates(
    rows: list[sqlite3.Row],
    weather_by_time: dict[str, dict[str, Any]],
    days: int,
) -> list[str]:
    dates: list[str] = []
    for row in reversed(rows):
        date = _market_date(row, weather_by_time)
        if date and date not in dates:
            dates.append(date)
        if len(dates) >= days:
            break
    return dates


def _day_payload(
    market_date: str,
    market_rows: list[sqlite3.Row],
    weather_by_time: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    series = []
    bucket_labels: list[str] = []
    for row in market_rows:
        market = _payload(row)
        contracts = market.get("contracts") or []
        favorite = _favorite_contract(contracts)
        for contract in contracts:
            label = str(contract.get("label") or "")
            if label and label not in bucket_labels:
                bucket_labels.append(label)
        weather = weather_by_time.get(row["captured_at"], {})
        actual = _first_number(
            weather.get("raw_high_so_far_f"),
            weather.get("current_temp_f"),
            weather.get("high_so_far_f"),
        )
        series.append(
            {
                "captured_at": row["captured_at"],
                "time_label": _time_label(row["captured_at"]),
                "favorite_bucket": favorite.get("label") if favorite else None,
                "favorite_price": _to_float(favorite.get("yes_price")) if favorite else None,
                "kalshi_forecast_f": _contract_midpoint(favorite) if favorite else None,
                "actual_temp_f": actual,
                "forecast_temp_f": _to_float(weather.get("forecast_high_f")),
                "bucket_prices": {
                    str(contract.get("label")): _to_float(contract.get("yes_price"))
                    for contract in contracts
                    if contract.get("label") and _to_float(contract.get("yes_price")) is not None
                },
            }
        )
    return {
        "market_date": market_date,
        "point_count": len(series),
        "bucket_labels": bucket_labels,
        "series": series,
    }


def _payload(row: sqlite3.Row) -> dict[str, Any]:
    try:
        return json.loads(row["payload_json"])
    except (json.JSONDecodeError, TypeError):
        return {}


def _market_date(row: sqlite3.Row, weather_by_time: dict[str, dict[str, Any]] | None = None) -> str | None:
    payload = _payload(row)
    if payload.get("market_date"):
        return str(payload["market_date"])
    if weather_by_time:
        weather = weather_by_time.get(row["captured_at"], {})
        if weather.get("market_date"):
            return str(weather["market_date"])
    title = str(payload.get("market_title") or "")
    return None


def _favorite_contract(contracts: list[dict[str, Any]]) -> dict[str, Any] | None:
    priced = [contract for contract in contracts if _to_float(contract.get("yes_price")) is not None]
    return max(priced, key=lambda contract: _to_float(contract.get("yes_price")) or 0) if priced else None


def _contract_midpoint(contract: dict[str, Any] | None) -> float | None:
    if not contract:
        return None
    low = _to_float(contract.get("low_f"))
    high = _to_float(contract.get("high_f"))
    if low is not None and high is not None:
        return round((low + high) / 2, 1)
    if high is not None:
        return high
    if low is not None:
        return low
    return None


def _time_label(value: str) -> str:
    return value.replace("T", " ")[:16]


def _first_number(*values: Any) -> float | None:
    for value in values:
        number = _to_float(value)
        if number is not None:
            return number
    return None


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
