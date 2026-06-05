from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from config import CITY_CONFIGS, DATABASE_PATH, USER_AGENT, city_configs_for_date


KALSHI_CANDLE_TIMEOUT_SECONDS = 20
KALSHI_API_BASE_URL = "https://external-api.kalshi.com/trade-api/v2"


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
        try:
            market_rows = _rows(conn, "market_snapshots", city)
            weather_rows = _rows(conn, "weather_snapshots", city)
        except sqlite3.OperationalError:
            return {"city": city, "days": []}
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


def load_kalshi_candle_history(
    city: str,
    *,
    days: int = 3,
    now: datetime | None = None,
    fetch_json: Any | None = None,
    db_path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    base_config = _city_config(city)
    if not base_config:
        return {"city": city, "days": [], "source": "kalshi_event_candlesticks", "warnings": ["Unknown city."]}
    tz = ZoneInfo(base_config["timezone"])
    local_now = (now or datetime.now(tz)).astimezone(tz)
    fetch = fetch_json or _fetch_json
    day_payloads = []
    for offset in range(days):
        market_day = local_now.date() - timedelta(days=offset)
        market_date = market_day.isoformat()
        config = _city_config_for_market_date(city, market_date)
        if not config:
            continue
        start_local = datetime.combine(market_day, datetime.min.time(), tzinfo=tz)
        if offset == 0:
            end_local = local_now
        else:
            end_local = start_local + timedelta(days=1)
        actual = _actual_outcome_from_snapshots(city, market_date, db_path)
        day_payloads.append(_kalshi_candle_day(config, start_local, end_local, fetch, actual))
    return {"city": city, "days": day_payloads, "source": "kalshi_event_candlesticks"}


def _kalshi_candle_day(
    config: dict[str, Any],
    start_local: datetime,
    end_local: datetime,
    fetch_json: Any,
    actual: dict[str, Any],
) -> dict[str, Any]:
    event_ticker = config["kalshi_event_ticker"]
    series_ticker = _series_ticker(event_ticker)
    market_date = start_local.date().isoformat()
    try:
        event_payload = fetch_json(f"{KALSHI_API_BASE_URL}/events/{event_ticker}")
        markets = event_payload.get("markets") or []
        contracts = [_contract_from_market(market) for market in markets]
        contracts = [contract for contract in contracts if contract]
        candles_url = _candles_url(series_ticker, event_ticker, start_local, end_local)
        candles_payload = fetch_json(candles_url)
        day = _day_from_kalshi_candles(
            market_date=market_date,
            event_ticker=event_ticker,
            series_ticker=series_ticker,
            contracts=contracts,
            candles_payload=candles_payload,
            actual=actual,
        )
        day["api_url"] = candles_url
        return day
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
        return {
            "market_date": market_date,
            "event_ticker": event_ticker,
            "series_ticker": series_ticker,
            "point_count": 0,
            "bucket_labels": [],
            "latest_buckets": [],
            "series": [],
            "actual_outcome_f": actual.get("actual_outcome_f"),
            "actual_raw_f": actual.get("actual_raw_f"),
            "actual_source": actual.get("actual_source"),
            "market_story": _market_story([], actual),
            "warnings": [f"Kalshi candle history unavailable: {exc}"],
        }


def _day_from_kalshi_candles(
    *,
    market_date: str,
    event_ticker: str,
    series_ticker: str,
    contracts: list[dict[str, Any]],
    candles_payload: dict[str, Any],
    actual: dict[str, Any],
) -> dict[str, Any]:
    contract_by_ticker = {contract["ticker"]: contract for contract in contracts if contract.get("ticker")}
    bucket_labels = [contract["label"] for contract in contracts if contract.get("label")]
    points_by_ts: dict[int, dict[str, Any]] = {}
    tickers = candles_payload.get("market_tickers") or []
    candle_arrays = candles_payload.get("market_candlesticks") or []
    for ticker, candle_list in zip(tickers, candle_arrays):
        contract = contract_by_ticker.get(ticker)
        if not contract:
            continue
        label = contract["label"]
        for candle in candle_list or []:
            timestamp = _to_int(candle.get("end_period_ts"))
            price = _candle_price_cents(candle)
            if timestamp is None or price is None:
                continue
            point = points_by_ts.setdefault(timestamp, {"bucket_prices": {}})
            point["bucket_prices"][label] = price
    series = []
    for timestamp in sorted(points_by_ts):
        bucket_prices = points_by_ts[timestamp]["bucket_prices"]
        enriched_buckets = [
            {
                "label": label,
                "price": price,
                "midpoint_f": _contract_midpoint(contract_by_label(contracts, label)),
            }
            for label, price in bucket_prices.items()
        ]
        weighted_forecast = _weighted_forecast(enriched_buckets)
        favorite = max(enriched_buckets, key=lambda bucket: bucket["price"]) if enriched_buckets else None
        series.append(
            {
                "captured_at": datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
                "end_period_ts": timestamp,
                "kalshi_forecast_f": weighted_forecast,
                "favorite_bucket": favorite["label"] if favorite else None,
                "favorite_price": favorite["price"] if favorite else None,
                "bucket_prices": bucket_prices,
            }
        )
    latest_prices = series[-1]["bucket_prices"] if series else {}
    latest_buckets = sorted(
        [{"label": label, "price": price} for label, price in latest_prices.items()],
        key=lambda bucket: bucket["price"],
        reverse=True,
    )
    return {
        "market_date": market_date,
        "event_ticker": event_ticker,
        "series_ticker": series_ticker,
        "point_count": len(series),
        "bucket_labels": bucket_labels,
        "latest_buckets": latest_buckets,
        "actual_outcome_f": actual.get("actual_outcome_f"),
        "actual_raw_f": actual.get("actual_raw_f"),
        "actual_source": actual.get("actual_source"),
        "market_story": _market_story(series, actual),
        "series": series,
        "warnings": [],
    }


def _actual_outcome_from_snapshots(city: str, market_date: str, db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {"actual_outcome_f": None, "actual_raw_f": None, "actual_source": "not_available"}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = list(
                conn.execute(
                    """
                    select captured_at, payload_json
                    from weather_snapshots
                    where city = ?
                    order by captured_at desc
                    """,
                    (city,),
                )
            )
        except sqlite3.OperationalError:
            return {"actual_outcome_f": None, "actual_raw_f": None, "actual_source": "not_available"}
        candidates = []
        for row in rows:
            weather = _payload(row)
            row_date = weather.get("market_date") or weather.get("cli_report_date")
            if row_date == market_date:
                candidates.append(weather)
        if not candidates:
            return {"actual_outcome_f": None, "actual_raw_f": None, "actual_source": "not_available"}
        weather = candidates[0]
        raw = _first_number(weather.get("raw_high_so_far_f"), weather.get("current_temp_f"))
        cli = _to_float(weather.get("cli_high_f")) if weather.get("cli_report_date") == market_date else None
        rounded = _first_number(weather.get("high_so_far_f"), cli)
        if raw is not None:
            return {
                "actual_outcome_f": round(raw),
                "actual_raw_f": raw,
                "actual_source": "station_high_so_far",
            }
        if cli is not None:
            return {
                "actual_outcome_f": cli,
                "actual_raw_f": cli,
                "actual_source": "nws_cli",
            }
        return {
            "actual_outcome_f": rounded,
            "actual_raw_f": rounded,
            "actual_source": "weather_snapshot",
        }
    finally:
        conn.close()


def _market_story(series: list[dict[str, Any]], actual: dict[str, Any]) -> dict[str, Any]:
    forecasts = [
        (index, _to_float(point.get("kalshi_forecast_f")))
        for index, point in enumerate(series)
        if _to_float(point.get("kalshi_forecast_f")) is not None
    ]
    if not forecasts:
        return {
            "open_forecast_f": None,
            "peak_forecast_f": None,
            "close_forecast_f": None,
            "pump_f": None,
            "dump_f": None,
            "close_vs_actual_f": None,
            "peak_vs_actual_f": None,
            "label": "No market history",
            "note": "No Kalshi candle movement was available for this day.",
        }
    open_index, open_forecast = forecasts[0]
    peak_index, peak_forecast = max(forecasts, key=lambda item: item[1])
    close_index, close_forecast = forecasts[-1]
    actual_f = _to_float(actual.get("actual_outcome_f"))
    pump = round(peak_forecast - open_forecast, 1)
    dump = round(peak_forecast - close_forecast, 1)
    close_vs_actual = round(close_forecast - actual_f, 1) if actual_f is not None else None
    peak_vs_actual = round(peak_forecast - actual_f, 1) if actual_f is not None else None
    label = "Actual pending"
    if actual_f is not None:
        if close_vs_actual >= 1:
            label = "Closed hotter than actual"
        elif close_vs_actual <= -1:
            label = "Closed colder than actual"
        else:
            label = "Closed near actual"
        if peak_vs_actual is not None and peak_vs_actual >= 2 and dump >= 1.5:
            label = "Hot pump then dump"
    elif pump >= 2 and dump >= 1.5:
        label = "Pump then dump"
    elif pump >= 2:
        label = "Market heated up"
    note = _market_story_note(label, open_forecast, peak_forecast, close_forecast, actual_f, pump, dump)
    return {
        "open_forecast_f": round(open_forecast, 1),
        "open_time": series[open_index].get("captured_at"),
        "peak_forecast_f": round(peak_forecast, 1),
        "peak_time": series[peak_index].get("captured_at"),
        "close_forecast_f": round(close_forecast, 1),
        "close_time": series[close_index].get("captured_at"),
        "pump_f": pump,
        "dump_f": dump,
        "close_vs_actual_f": close_vs_actual,
        "peak_vs_actual_f": peak_vs_actual,
        "label": label,
        "note": note,
    }


def _market_story_note(
    label: str,
    open_forecast: float,
    peak_forecast: float,
    close_forecast: float,
    actual_f: float | None,
    pump: float,
    dump: float,
) -> str:
    actual_text = f"; actual was {actual_f:.0f}F" if actual_f is not None else "; actual not available yet"
    return (
        f"{label}: Kalshi opened near {open_forecast:.1f}F, "
        f"pumped to {peak_forecast:.1f}F (+{pump:.1f}F), "
        f"then finished near {close_forecast:.1f}F (-{dump:.1f}F from peak){actual_text}."
    )


def _candles_url(series_ticker: str, event_ticker: str, start_local: datetime, end_local: datetime) -> str:
    params = urlencode(
        {
            "start_ts": int(start_local.astimezone(timezone.utc).timestamp()),
            "end_ts": int(end_local.astimezone(timezone.utc).timestamp()),
            "period_interval": 1,
        }
    )
    return f"{KALSHI_API_BASE_URL}/series/{series_ticker}/events/{event_ticker}/candlesticks?{params}"


def _fetch_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=KALSHI_CANDLE_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _city_config(city: str) -> dict[str, Any] | None:
    return next((config for config in CITY_CONFIGS if config["city"] == city), None)


def _city_config_for_market_date(city: str, market_date: str) -> dict[str, Any] | None:
    return next((config for config in city_configs_for_date(market_date) if config["city"] == city), None)


def _series_ticker(event_ticker: str) -> str:
    return event_ticker.rsplit("-", 1)[0]


def _contract_from_market(market: dict[str, Any]) -> dict[str, Any] | None:
    low, high = _range_from_api_market(market)
    if low is None and high is None:
        return None
    return {
        "ticker": market.get("ticker"),
        "label": _format_range(low, high),
        "low_f": low,
        "high_f": high,
    }


def _range_from_api_market(market: dict[str, Any]) -> tuple[float | None, float | None]:
    strike_type = str(market.get("strike_type") or "").lower()
    floor = _to_float(market.get("floor_strike"))
    cap = _to_float(market.get("cap_strike"))
    if strike_type == "less" and cap is not None:
        return None, cap - 1
    if strike_type == "greater" and floor is not None:
        return floor + 1, None
    if strike_type == "between":
        return floor, cap
    return floor, cap


def _format_range(low: float | None, high: float | None) -> str:
    if low is None and high is not None:
        return f"{high:.0f}F or below"
    if high is None and low is not None:
        return f"{low:.0f}F or above"
    if low is not None and high is not None:
        return f"{low:.0f}F to {high:.0f}F"
    return "unknown"


def contract_by_label(contracts: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
    return next((contract for contract in contracts if contract.get("label") == label), None)


def _candle_price_cents(candle: dict[str, Any]) -> float | None:
    for path in (
        ("price", "close_dollars"),
        ("price", "previous_dollars"),
        ("yes_ask", "close_dollars"),
        ("yes_bid", "close_dollars"),
    ):
        value = candle.get(path[0], {}).get(path[1])
        number = _to_float(value)
        if number is not None:
            return round(number * 100, 1)
    return None


def _weighted_forecast(buckets: list[dict[str, Any]]) -> float | None:
    usable = [
        bucket
        for bucket in buckets
        if _to_float(bucket.get("price")) is not None and _to_float(bucket.get("midpoint_f")) is not None
    ]
    total = sum(float(bucket["price"]) for bucket in usable)
    if total <= 0:
        return None
    value = sum(float(bucket["midpoint_f"]) * float(bucket["price"]) for bucket in usable) / total
    return round(value, 1)


def _to_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


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
