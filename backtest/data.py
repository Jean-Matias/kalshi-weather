"""Fetch + locally cache real KXHIGHTLV (Las Vegas daily-high-temperature)
settlement history for backtesting.

Settled events never change, so everything here is cached to disk forever —
re-running `ensure_cached()` only fetches what's missing.

Cache layout (under backtest/cache/):
  events.json                    - list of settled event-days: ticker, open/
                                   close timestamps, list of bucket markets
                                   (ticker, label, result)
  candles/<event_ticker>/<market_ticker>.json
                                   - per-bucket hourly candlesticks
                                   (yes_ask/yes_bid/price)

No trading credentials required: Kalshi's market-data endpoints
(/markets, /candlesticks) are public and need no auth.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CACHE_ROOT = Path(__file__).parent / "cache"

API_BASE = "https://api.elections.kalshi.com/trade-api/v2"
TIMEOUT = 20

# The dashboard's three-city board.
SERIES_BY_CITY = {
    "Las Vegas": "KXHIGHTLV",
    "Phoenix": "KXHIGHTPHX",
    "San Antonio": "KXHIGHTSATX",
}


def _paths(series_ticker: str) -> tuple[Path, Path, Path]:
    cache_dir = CACHE_ROOT / series_ticker
    return cache_dir, cache_dir / "events.json", cache_dir / "candles"


def _get(path: str, query: str = "") -> dict:
    url = f"{API_BASE}{path}" + (f"?{query}" if query else "")
    req = Request(url, headers={"User-Agent": "kalshi-weather-backtest-research"})
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GET {path} failed: {exc}") from exc


def _to_ts(iso_str: str) -> int:
    return int(datetime.fromisoformat(iso_str.replace("Z", "+00:00")).timestamp())


def _label_for_market(m: dict) -> str:
    return m.get("yes_sub_title") or m.get("subtitle") or m.get("ticker", "")


def _fetch_settled_markets(series_ticker: str, max_events: int) -> list[dict]:
    """Fetch settled bucket markets for the series, grouped into event-days."""
    raw: list[dict] = []
    cursor = ""
    for _ in range(40):
        query = f"series_ticker={series_ticker}&status=settled&limit=200"
        if cursor:
            query += f"&cursor={cursor}"
        resp = _get("/markets", query=query)
        batch = resp.get("markets") or []
        if not batch:
            break
        raw.extend(batch)
        cursor = resp.get("cursor") or ""
        if not cursor:
            break

    by_event: dict[str, list[dict]] = defaultdict(list)
    for m in raw:
        if not m.get("open_time") or not m.get("close_time") or not m.get("result"):
            continue
        by_event[m["event_ticker"]].append(m)

    events = []
    for event_ticker, markets in by_event.items():
        markets.sort(key=lambda m: m["ticker"])
        events.append({
            "event_ticker": event_ticker,
            "open_time": markets[0]["open_time"],
            "close_time": markets[0]["close_time"],
            "open_ts": _to_ts(markets[0]["open_time"]),
            "close_ts": _to_ts(markets[0]["close_time"]),
            "buckets": [
                {
                    "ticker": m["ticker"],
                    "label": _label_for_market(m),
                    "result": m["result"],  # "yes" = this bucket is the actual settled high temp
                }
                for m in markets
            ],
        })
    events.sort(key=lambda e: e["open_ts"])
    return events[-max_events:]


def _fetch_candles(series_ticker: str, ticker: str, start_ts: int, end_ts: int) -> list[dict]:
    resp = _get(
        f"/series/{series_ticker}/markets/{ticker}/candlesticks",
        query=f"start_ts={start_ts}&end_ts={end_ts}&period_interval=60",
    )
    return resp.get("candlesticks") or []


def ensure_cached(city: str, target_events: int = 90, progress_every: int = 5) -> dict:
    """Top up the local cache for one city to at least `target_events` settled
    event-days with hourly candlestick data for every bucket. Safe to re-run."""
    series_ticker = SERIES_BY_CITY[city]
    cache_dir, events_file, candles_dir = _paths(series_ticker)
    cache_dir.mkdir(parents=True, exist_ok=True)
    candles_dir.mkdir(parents=True, exist_ok=True)

    events = json.loads(events_file.read_text()) if events_file.exists() else []
    have = {e["event_ticker"] for e in events}

    if len(events) < target_events:
        print(f"[{city}] Fetching settled event list (have {len(events)}, want {target_events})...")
        fetched = _fetch_settled_markets(series_ticker, target_events)
        for e in fetched:
            if e["event_ticker"] not in have:
                events.append(e)
                have.add(e["event_ticker"])
        events.sort(key=lambda e: e["open_ts"])
        events_file.write_text(json.dumps(events))
        print(f"[{city}] Event list now has {len(events)} settled event-days.")

    fetched_count = 0
    for e in events:
        event_dir = candles_dir / e["event_ticker"]
        event_dir.mkdir(parents=True, exist_ok=True)
        for bucket in e["buckets"]:
            candle_file = event_dir / f"{bucket['ticker']}.json"
            if candle_file.exists():
                continue
            try:
                candles = _fetch_candles(series_ticker, bucket["ticker"], e["open_ts"], e["close_ts"])
            except Exception as exc:
                print(f"  [{city}] skip {bucket['ticker']}: {exc}")
                continue
            candle_file.write_text(json.dumps(candles))
            fetched_count += 1
            if fetched_count % progress_every == 0:
                print(f"  [{city}] fetched {fetched_count} bucket candle sets...")
            time.sleep(0.6)

    return {
        "city": city,
        "total_events": len(events),
        "newly_fetched_candle_sets": fetched_count,
    }


def load_dataset(city: str) -> list[dict]:
    """Load everything from disk cache for one city: list of {event,
    bucket_candles} dicts sorted oldest-first. bucket_candles maps bucket
    ticker -> candle list. No network calls."""
    series_ticker = SERIES_BY_CITY[city]
    _, events_file, candles_dir = _paths(series_ticker)
    if not events_file.exists():
        raise RuntimeError(f"No cache found for {city} — run ensure_cached('{city}') first.")
    events = json.loads(events_file.read_text())
    dataset = []
    for e in events:
        event_dir = candles_dir / e["event_ticker"]
        bucket_candles = {}
        ok = True
        for bucket in e["buckets"]:
            candle_file = event_dir / f"{bucket['ticker']}.json"
            if not candle_file.exists():
                ok = False
                break
            candles = json.loads(candle_file.read_text())
            if not candles:
                ok = False
                break
            bucket_candles[bucket["ticker"]] = candles
        if not ok:
            continue
        dataset.append({"event": e, "bucket_candles": bucket_candles, "city": city})
    dataset.sort(key=lambda d: d["event"]["open_ts"])
    return dataset


def cache_span_days(city: str) -> float | None:
    series_ticker = SERIES_BY_CITY[city]
    _, events_file, _ = _paths(series_ticker)
    if not events_file.exists():
        return None
    events = json.loads(events_file.read_text())
    if not events:
        return None
    earliest = min(e["open_ts"] for e in events)
    latest = max(e["close_ts"] for e in events)
    return (latest - earliest) / 86400


if __name__ == "__main__":
    for city in SERIES_BY_CITY:
        summary = ensure_cached(city)
        print(summary)
        span = cache_span_days(city)
        print(f"[{city}] Cache spans ~{span:.1f} days" if span else f"[{city}] Cache empty")
