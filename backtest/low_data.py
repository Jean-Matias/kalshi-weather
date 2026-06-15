from __future__ import annotations

import base64
import json
import os
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backtest.market_specs import MarketSpec, low_market_spec


CACHE_ROOT = Path(__file__).parent / "cache"
API_BASE = "https://api.elections.kalshi.com/trade-api/v2"
TIMEOUT = 20
BTC_CREDENTIALS_ENV = Path(r"C:\Users\jeanm\OneDrive\Documents\btc betting\btc betting\credentials.env")

FetchJson = Callable[[str, str], dict[str, Any]]


def ensure_cached(
    city: str,
    target_events: int = 90,
    *,
    cache_root: Path = CACHE_ROOT,
    fetch_json: FetchJson | None = None,
    sleep_seconds: float = 0.6,
) -> dict[str, Any]:
    spec = low_market_spec(city)
    cache_dir, events_file, candles_dir = _paths(spec, cache_root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    candles_dir.mkdir(parents=True, exist_ok=True)
    fetch = fetch_json or _get_json

    events = _read_json_list(events_file)
    have = {event["event_ticker"] for event in events}
    if len(events) < target_events:
        fetched = _fetch_settled_events(spec, target_events, fetch)
        for event in fetched:
            if event["event_ticker"] not in have:
                events.append(event)
                have.add(event["event_ticker"])
        events.sort(key=lambda event: event["open_ts"])
        events_file.write_text(json.dumps(events, indent=2))

    fetched_count = 0
    for event in events:
        event_dir = candles_dir / event["event_ticker"]
        event_dir.mkdir(parents=True, exist_ok=True)
        for bucket in event["buckets"]:
            candle_file = event_dir / f"{bucket['ticker']}.json"
            if candle_file.exists():
                continue
            candles = _fetch_candles(spec, bucket["ticker"], event["open_ts"], event["close_ts"], fetch)
            candle_file.write_text(json.dumps(candles, indent=2))
            fetched_count += 1
            if sleep_seconds:
                time.sleep(sleep_seconds)

    return {
        "city": spec.city,
        "series_ticker": spec.series_ticker,
        "total_events": len(events),
        "newly_fetched_candle_sets": fetched_count,
    }


def load_dataset(city: str, *, cache_root: Path = CACHE_ROOT, days: int | None = None) -> list[dict[str, Any]]:
    spec = low_market_spec(city)
    _, events_file, candles_dir = _paths(spec, cache_root)
    if not events_file.exists():
        raise RuntimeError(f"No cache found for {city}. Run: python -m backtest.low_data --city \"{city}\"")

    events = json.loads(events_file.read_text())
    if days is not None:
        events = events[-days:]

    dataset = []
    for event in events:
        event_dir = candles_dir / event["event_ticker"]
        bucket_candles = {}
        ok = True
        for bucket in event["buckets"]:
            candle_file = event_dir / f"{bucket['ticker']}.json"
            if not candle_file.exists():
                ok = False
                break
            candles = json.loads(candle_file.read_text())
            if not candles:
                ok = False
                break
            bucket_candles[bucket["ticker"]] = candles
        if ok:
            dataset.append({"city": spec.city, "spec": spec, "event": event, "bucket_candles": bucket_candles})
    dataset.sort(key=lambda item: item["event"]["open_ts"])
    return dataset


def cache_span_days(city: str, *, cache_root: Path = CACHE_ROOT) -> float | None:
    spec = low_market_spec(city)
    _, events_file, _ = _paths(spec, cache_root)
    if not events_file.exists():
        return None
    events = json.loads(events_file.read_text())
    if not events:
        return None
    return (max(event["close_ts"] for event in events) - min(event["open_ts"] for event in events)) / 86400


def _paths(spec: MarketSpec, cache_root: Path) -> tuple[Path, Path, Path]:
    cache_dir = cache_root / spec.series_ticker
    return cache_dir, cache_dir / "events.json", cache_dir / "candles"


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _fetch_settled_events(spec: MarketSpec, max_events: int, fetch: FetchJson) -> list[dict[str, Any]]:
    markets = _fetch_markets("/markets", spec.series_ticker, max_events, fetch)
    if not markets:
        markets = _fetch_markets("/historical/markets", spec.series_ticker, max_events, fetch)
    events = _events_from_markets(markets)
    return events[-max_events:]


def _fetch_markets(path: str, series_ticker: str, max_events: int, fetch: FetchJson) -> list[dict[str, Any]]:
    raw: list[dict[str, Any]] = []
    cursor = ""
    for _ in range(40):
        query = f"series_ticker={series_ticker}&status=settled&limit=200"
        if cursor:
            query += f"&cursor={cursor}"
        try:
            payload = fetch(path, query)
        except Exception:
            return []
        batch = payload.get("markets") or []
        raw.extend(batch)
        cursor = payload.get("cursor") or ""
        if not cursor:
            break
        if len({market.get("event_ticker") for market in raw}) >= max_events:
            break
    return raw


def _events_from_markets(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for market in markets:
        if not market.get("event_ticker") or not market.get("open_time") or not market.get("close_time"):
            continue
        if not market.get("result"):
            continue
        by_event[market["event_ticker"]].append(market)

    events = []
    for event_ticker, event_markets in by_event.items():
        event_markets.sort(key=lambda market: (_range_from_market(market), market.get("ticker", "")))
        events.append(
            {
                "event_ticker": event_ticker,
                "open_time": event_markets[0]["open_time"],
                "close_time": event_markets[0]["close_time"],
                "open_ts": _to_ts(event_markets[0]["open_time"]),
                "close_ts": _to_ts(event_markets[0]["close_time"]),
                "buckets": [
                    {
                        "ticker": market["ticker"],
                        "label": _label_for_market(market),
                        "result": str(market["result"]).lower(),
                    }
                    for market in event_markets
                ],
            }
        )
    events.sort(key=lambda event: event["open_ts"])
    return events


def _fetch_candles(spec: MarketSpec, ticker: str, start_ts: int, end_ts: int, fetch: FetchJson) -> list[dict[str, Any]]:
    query = f"start_ts={start_ts}&end_ts={end_ts}&period_interval=60"
    live_path = f"/series/{spec.series_ticker}/markets/{ticker}/candlesticks"
    try:
        payload = fetch(live_path, query)
        candles = payload.get("candlesticks") or []
    except Exception:
        candles = []
    if candles:
        return candles
    historical_payload = fetch(f"/historical/markets/{ticker}/candlesticks", query)
    return historical_payload.get("candlesticks") or []


def _get_json(path: str, query: str = "") -> dict[str, Any]:
    url = f"{API_BASE}{path}" + (f"?{query}" if query else "")
    request = Request(url, headers={"User-Agent": "kalshi-low-weather-backtest-research"})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode())
    except HTTPError as exc:
        if exc.code not in {401, 403}:
            raise
        headers = _optional_auth_headers("GET", path)
        if not headers:
            raise
        request = Request(url, headers=headers)
        with urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode())
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GET {path} failed: {exc}") from exc


def _optional_auth_headers(method: str, path: str) -> dict[str, str] | None:
    creds = _load_btc_credentials()
    key_id = creds.get("KALSHI_API_KEY_ID")
    key_path = creds.get("KALSHI_PRIVATE_KEY_PATH")
    if not key_id or not key_path:
        return None
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError:
        return None

    private_key_path = Path(key_path)
    if not private_key_path.exists():
        return None
    private_key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
    timestamp = str(int(time.time() * 1000))
    signed_path = f"/trade-api/v2{path}"
    message = (timestamp + method.upper() + signed_path).encode()
    signature = private_key.sign(
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
        "User-Agent": "kalshi-low-weather-backtest-research",
    }


def _load_btc_credentials() -> dict[str, str]:
    creds = dict(os.environ)
    if not BTC_CREDENTIALS_ENV.exists():
        return creds
    for line in BTC_CREDENTIALS_ENV.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        creds.setdefault(key.strip(), value.strip().strip('"'))
    return creds


def _to_ts(iso_str: str) -> int:
    return int(datetime.fromisoformat(iso_str.replace("Z", "+00:00")).timestamp())


def _range_from_market(market: dict[str, Any]) -> tuple[float, float]:
    low, high = _low_high_from_market(market)
    sort_low = float("-inf") if low is None else low
    sort_high = float("inf") if high is None else high
    return sort_low, sort_high


def _low_high_from_market(market: dict[str, Any]) -> tuple[float | None, float | None]:
    strike_type = str(market.get("strike_type") or "").lower()
    floor = _numeric(market.get("floor_strike"))
    cap = _numeric(market.get("cap_strike"))
    if strike_type == "less" and cap is not None:
        return None, cap - 1
    if strike_type == "greater" and floor is not None:
        return floor + 1, None
    if strike_type == "between":
        return floor, cap
    return floor, cap


def _label_for_market(market: dict[str, Any]) -> str:
    existing = market.get("yes_sub_title") or market.get("subtitle")
    if existing:
        return str(existing).replace("\u00b0", "F")
    low, high = _low_high_from_market(market)
    if low is None and high is not None:
        return f"{high:.0f}F or below"
    if high is None and low is not None:
        return f"{low:.0f}F or above"
    if low is not None and high is not None:
        return f"{low:.0f}F to {high:.0f}F"
    return str(market.get("ticker", "unknown"))


def _numeric(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Cache settled low-temperature Kalshi event history.")
    parser.add_argument("--city", default="Las Vegas")
    parser.add_argument("--target-events", type=int, default=90)
    args = parser.parse_args()
    summary = ensure_cached(args.city, target_events=args.target_events)
    span = cache_span_days(args.city)
    print(summary)
    if span:
        print(f"[{args.city}] Cache spans ~{span:.1f} days")


if __name__ == "__main__":
    main()
