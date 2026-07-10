"""Fetch & accumulate real historical 1-minute forex closes via yfinance
(free, no API key).

Yahoo Finance only retains ~7 days of 1-minute intraday history per request.
To build a longer sample than that single window, `update_history()` merges
each fetch into a persistent, growing history file (deduped by timestamp)
instead of overwriting it — call it periodically (e.g. once a day) and the
usable history keeps extending. This is a separate dependency from the live
bot (bots/pocket_bot itself has no yfinance dependency) — see
backtest/requirements.txt.
"""
from __future__ import annotations

import json
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "cache"
_YF_SUFFIX = "=X"


def _history_path(pair: str) -> Path:
    return CACHE_DIR / f"{pair.upper()}_history.json"


def _dedupe_consecutive(closes: list[float]) -> list[float]:
    """Consecutive duplicate closes are stale/dead ticks (e.g. weekend market
    closure), not real price action — they contain zero information for a
    momentum signal and degenerate the RSI math (avg_loss=0 pins RSI at 100,
    firing spurious signals). Collapse runs of identical closes to one."""
    if not closes:
        return []
    out = closes[:1]
    for c in closes[1:]:
        if c != out[-1]:
            out.append(c)
    return out


def merge_history(existing: dict[int, float], fetched: dict[int, float]) -> tuple[dict[int, float], int]:
    """Merge `fetched` bars into `existing` (keyed by unix timestamp).

    Returns (merged, new_bar_count). Pure function, no I/O — kept separate
    from update_history() so the merge logic is testable without a network
    call or yfinance installed.
    """
    new_count = sum(1 for t in fetched if t not in existing)
    merged = dict(existing)
    merged.update(fetched)
    return merged, new_count


def _merge_and_save(pair: str, fetched: dict[int, float]) -> int:
    history_file = _history_path(pair)
    existing: dict[int, float] = {}
    if history_file.exists():
        existing = {int(t): c for t, c in json.loads(history_file.read_text())}

    merged, new_count = merge_history(existing, fetched)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    history_file.write_text(json.dumps(sorted(merged.items())))
    return new_count


def update_history(pair: str) -> int:
    """Fetch the latest 7-day window from yfinance and merge it into the
    persistent history file for `pair`. Returns the number of new bars
    added (0 if nothing new — e.g. market's been closed since last update)."""
    import yfinance as yf  # imported lazily: only needed when actually fetching

    ticker = f"{pair.upper()}{_YF_SUFFIX}"
    df = yf.download(ticker, period="7d", interval="1m", progress=False)
    if df.empty:
        raise RuntimeError(f"yfinance returned no data for {ticker}")

    close_col = df["Close"]
    if hasattr(close_col, "columns"):  # MultiIndex columns (newer yfinance)
        close_col = close_col.iloc[:, 0]
    close_col = close_col.dropna()
    fetched = {int(ts.timestamp()): float(c) for ts, c in close_col.items()}

    return _merge_and_save(pair, fetched)


def update_history_dukascopy(pair: str, *, days_back: int = 90, threads: int = 4) -> int:
    """Fetch TRUE 1-minute candles from Dukascopy's free historical feed (no
    API key, no signup) covering the last `days_back` days, and merge them
    into the same persistent history file used by update_history().

    Dukascopy's CDN (Cloudflare) blocks the `duka` library's default
    requests because it sends no browser User-Agent — every request comes
    back 503. Patching a normal User-Agent onto requests.get for the
    duration of this call fixes it; see the manual curl reproduction this
    was diagnosed with.

    ponytail: `duka` fails an ENTIRE day if even one of its 24 hourly
    requests raises after retries (Cloudflare drops a request here and there
    under load), with no partial-day fallback — costly since each day is 24
    requests. Patching duka.core.fetch.get to swallow a persistent per-hour
    failure into an empty buffer (== "no ticks that hour", already a normal
    case the decompressor handles for closed-market hours) means one bad
    request costs an hour of data, not a whole day.
    """
    import csv
    import tempfile
    from datetime import date, datetime as dt, timedelta
    from io import BytesIO

    import requests
    import duka.core.fetch as fetch_module
    from duka.app.app import app as duka_app
    from duka.core.utils import TimeFrame

    original_fetch_get = fetch_module.get

    async def _resilient_get(url):
        try:
            return await original_fetch_get(url)
        except Exception:
            return BytesIO().getbuffer()

    fetch_module.get = _resilient_get

    browser_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    original_get = requests.get

    def _get_with_browser_ua(url, **kwargs):
        headers = kwargs.pop("headers", None) or {}
        headers.setdefault("User-Agent", browser_ua)
        return original_get(url, headers=headers, **kwargs)

    requests.get = _get_with_browser_ua
    try:
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=days_back)
        with tempfile.TemporaryDirectory() as folder:
            duka_app([pair.upper()], start, end, threads, TimeFrame.M1, folder, True)
            fetched: dict[int, float] = {}
            for csv_path in Path(folder).glob("*.csv"):
                with open(csv_path, newline="") as f:
                    for row in csv.DictReader(f):
                        ts = dt.strptime(row["time"], "%Y-%m-%d %H:%M:%S").timestamp()
                        fetched[int(ts)] = float(row["close"])
    finally:
        requests.get = original_get
        fetch_module.get = original_fetch_get

    return _merge_and_save(pair, fetched)


def fetch_closes(pair: str, *, force: bool = False) -> list[float]:
    """Return the full accumulated chronological list of real 1-minute
    closes for `pair` (e.g. 'EURUSD'), with consecutive stale-tick duplicates
    collapsed. Fetches (and merges into history) if no history exists yet,
    or if force=True.
    """
    history_file = _history_path(pair)
    if force or not history_file.exists():
        update_history(pair)

    raw = json.loads(history_file.read_text())
    closes = [c for _, c in raw]
    return _dedupe_consecutive(closes)
