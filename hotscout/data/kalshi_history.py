"""Kalshi settlement history ingestor -- kalshi_events / kalshi_candles tables.

Reuses backtest/data.py's disk cache (events.json + per-bucket candlestick
files, see that module's docstring) as the fetch/cache layer. This module
does NOT re-fetch from Kalshi directly -- it calls `backtest.data.ensure_cached`
to top up the disk cache, then ingests the cached JSON into sqlite.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime

from backtest import data as backtest_data

logger = logging.getLogger(__name__)

_RANGE_RE = re.compile(r"(\d+)\D+to\D+(\d+)")
_BELOW_RE = re.compile(r"(\d+)\D+or below")
_ABOVE_RE = re.compile(r"(\d+)\D+or above")


def parse_bucket_label(label: str) -> tuple[float | None, float | None]:
    """Parse a Kalshi bucket label like "76 to 77" (degree signs stripped by
    caller or present, either way), "75 or below", or "84 or above" into
    inclusive (low_f, high_f) bounds. None = open-ended. Returns (None, None)
    if the label doesn't match a known shape."""
    m = _RANGE_RE.search(label)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = _BELOW_RE.search(label)
    if m:
        return None, float(m.group(1))
    m = _ABOVE_RE.search(label)
    if m:
        return float(m.group(1)), None
    return None, None


def bucket_to_frozen(bucket: dict) -> dict:
    """Convert a backtest-cache bucket dict {ticker,label,result} into the
    frozen Bucket shape {ticker,label,low_f,high_f,result}."""
    low_f, high_f = parse_bucket_label(bucket.get("label", ""))
    return {
        "ticker": bucket["ticker"],
        "label": bucket["label"],
        "low_f": low_f,
        "high_f": high_f,
        "result": bucket.get("result"),
    }


def settled_bucket(buckets: list[dict]) -> dict | None:
    """Given a list of frozen Bucket dicts, return the one that settled yes."""
    for b in buckets:
        if b.get("result") == "yes":
            return b
    return None


def market_date_from_ticker(event_ticker: str) -> str:
    """"KXHIGHTLV-26APR02" -> "2026-04-02". Kalshi's event ticker date suffix
    is YYMMMDD."""
    suffix = event_ticker.split("-")[-1]
    return datetime.strptime(suffix, "%y%b%d").date().isoformat()


def ensure_cache_fresh(city: str, target_events: int) -> dict:
    """Delegates entirely to backtest.data.ensure_cached -- does not
    reimplement Kalshi fetching."""
    return backtest_data.ensure_cached(city, target_events=target_events)


def _dollars_to_cents(node: dict | None) -> int | None:
    if not node:
        return None
    val = node.get("close_dollars")
    if val is None:
        return None
    try:
        return round(float(val) * 100)
    except (TypeError, ValueError):
        return None


def _volume(candle: dict) -> int | None:
    val = candle.get("volume_fp")
    if val is None:
        return None
    try:
        return int(round(float(val)))
    except (TypeError, ValueError):
        return None


def upsert_event(conn, city: str, event: dict) -> int:
    buckets = [bucket_to_frozen(b) for b in event["buckets"]]
    # An unparseable label yields (None, None) bounds, which would silently
    # poison bucket probabilities (an "anything goes" bucket). Skip the whole
    # event loudly instead.
    bad = [b["label"] for b in buckets if b["low_f"] is None and b["high_f"] is None]
    if bad:
        logger.error(
            "skipping event %s: unparseable bucket label(s) %s",
            event.get("event_ticker"), bad,
        )
        return 0
    settled = settled_bucket(buckets)
    market_date = market_date_from_ticker(event["event_ticker"])
    cur = conn.execute(
        "INSERT OR IGNORE INTO kalshi_events"
        "(city, market_date, event_ticker, close_ts, settled_bucket_ticker, settled_bucket_label, buckets_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            city,
            market_date,
            event["event_ticker"],
            event["close_ts"],
            settled["ticker"] if settled else None,
            settled["label"] if settled else None,
            json.dumps(buckets),
        ),
    )
    return cur.rowcount


def upsert_candles(conn, event_ticker: str, market_ticker: str, candles: list[dict]) -> int:
    inserted = 0
    for c in candles:
        ts = c.get("end_period_ts")
        cur = conn.execute(
            "INSERT OR IGNORE INTO kalshi_candles"
            "(event_ticker, market_ticker, ts, yes_bid_c, yes_ask_c, price_c, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event_ticker,
                market_ticker,
                ts,
                _dollars_to_cents(c.get("yes_bid")),
                _dollars_to_cents(c.get("yes_ask")),
                _dollars_to_cents(c.get("price")),
                _volume(c),
            ),
        )
        inserted += cur.rowcount
    return inserted


def ingest_city(conn, city: str) -> dict:
    """Load the full backtest disk cache for a city (network-free -- assumes
    ensure_cache_fresh already ran) and upsert everything into sqlite."""
    dataset = backtest_data.load_dataset(city)
    events_inserted = 0
    candles_inserted = 0
    for entry in dataset:
        event = entry["event"]
        events_inserted += upsert_event(conn, city, event)
        for bucket in event["buckets"]:
            candles = entry["bucket_candles"].get(bucket["ticker"], [])
            candles_inserted += upsert_candles(conn, event["event_ticker"], bucket["ticker"], candles)
    conn.commit()
    return {
        "city": city,
        "event_days": len(dataset),
        "events_inserted": events_inserted,
        "candles_inserted": candles_inserted,
    }


def backfill_city(conn, city: str, target_events: int) -> dict:
    cache_summary = ensure_cache_fresh(city, target_events)
    ingest_summary = ingest_city(conn, city)
    return {**cache_summary, **ingest_summary}


def probe(conn, city: str) -> dict:
    """Top up the cache for a small number of events, then ingest and report
    without a bulk backfill."""
    cache_summary = ensure_cache_fresh(city, target_events=5)
    ingest_summary = ingest_city(conn, city)
    return {"cache": cache_summary, "ingest": ingest_summary}
