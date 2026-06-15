"""Compare official NWS settlement-aligned highs against Kalshi KXHIGHT*
settled buckets.

Two NWS-derived sources are used:

- NWS CLI archive (`forecast.weather.gov/product.php?...&version=N`): the
  exact climate product Kalshi cites for settlement. The product browser only
  retains roughly the last ~25 issuance days (2 versions/day), so this gives
  a short but authoritative recent window.
- Open-Meteo historical reanalysis archive, already cached by
  `backtest.weather_cache` for the full backtest window: a faithful "what the
  weather actually did" record, used to extend coverage back to ~2 months.

Usage:
    python -m backtest.high_actual_check --city "Las Vegas" --days 60
    python -m backtest.high_actual_check --city "Las Vegas" --update-cli-cache
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import config
from backtest import data as hi_data
from backtest.weather_strategies import bucket_range

CLI_CACHE_ROOT = Path(__file__).parent / "cache" / "nws_cli"
WEATHER_OBS_ROOT = Path(__file__).parent / "cache" / "weather_obs"

_DATE_RE = re.compile(r"CLIMATE SUMMARY FOR ([A-Z]+)\s+(\d{1,2})\s+(\d{4})", re.I)
_MAX_RE = re.compile(r"^\s*MAXIMUM\s+(-?\d{1,3})\b", re.I | re.M)


def _city_config(city: str) -> dict[str, Any]:
    for c in config.CITY_CONFIGS:
        if c["city"] == city:
            return c
    raise ValueError(f"Unknown city '{city}'. Available: {', '.join(c['city'] for c in config.CITY_CONFIGS)}")


def _get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def ensure_cli_cache(city: str, max_versions: int = 50) -> dict:
    """Top up the local NWS CLI archive cache for `city` by walking
    forecast.weather.gov's product version history. Stops at the first
    version that fails (the browser caps history around ~25 days back) or
    once a date we've already cached is seen again."""
    spec = _city_config(city)
    cache_dir = CLI_CACHE_ROOT / spec["station_id"]
    cache_dir.mkdir(parents=True, exist_ok=True)
    base = (
        "https://forecast.weather.gov/product.php?"
        f"site={spec['cli_site']}&product=CLI&issuedby={spec['cli_issuedby']}&format=TXT"
    )

    fetched = 0
    for version in range(1, max_versions + 1):
        url = base if version == 1 else f"{base}&version={version}"
        try:
            text = _get_text(url)
        except Exception as exc:
            print(f"  [{city}] stop at version={version}: {exc}")
            break

        date_match = _DATE_RE.search(text)
        if not date_match:
            continue
        month, day, year = date_match.groups()
        date = datetime.strptime(f"{month} {day} {year}", "%B %d %Y").date()
        out_file = cache_dir / f"{date.isoformat()}.json"
        if out_file.exists():
            time.sleep(0.2)
            continue

        max_match = _MAX_RE.search(text)
        max_f = float(max_match.group(1)) if max_match else None
        out_file.write_text(json.dumps({"date": date.isoformat(), "max_f": max_f, "source_url": url}))
        fetched += 1
        time.sleep(0.3)

    return {"city": city, "newly_fetched": fetched, "cache_dir": str(cache_dir)}


def load_cli_highs(city: str) -> dict[str, float]:
    spec = _city_config(city)
    cache_dir = CLI_CACHE_ROOT / spec["station_id"]
    out: dict[str, float] = {}
    if not cache_dir.exists():
        return out
    for f in cache_dir.glob("*.json"):
        d = json.loads(f.read_text())
        if d.get("max_f") is not None:
            out[d["date"]] = d["max_f"]
    return out


def load_open_meteo_highs(city: str) -> dict[str, float]:
    spec = _city_config(city)
    cache_dir = WEATHER_OBS_ROOT / spec["station_id"]
    out: dict[str, float] = {}
    if not cache_dir.exists():
        return out
    for f in cache_dir.glob("*.json"):
        d = json.loads(f.read_text())
        high = (d.get("summary") or {}).get("high_f")
        if high is not None:
            out[f.stem] = high
    return out


def load_settled_buckets(city: str) -> dict[str, tuple[float, float]]:
    spec = _city_config(city)
    series = hi_data.SERIES_BY_CITY[city]
    events_file = hi_data.CACHE_ROOT / series / "events.json"
    if not events_file.exists():
        raise RuntimeError(f"No cache found for {city} — run backtest.data.ensure_cached('{city}') first.")
    tz = ZoneInfo(spec["timezone"])
    events = json.loads(events_file.read_text())
    out: dict[str, tuple[float, float]] = {}
    for e in events:
        measure_date = (datetime.fromtimestamp(e["open_ts"], tz).date() + timedelta(days=1)).isoformat()
        yes_bucket = next((b for b in e["buckets"] if b["result"] == "yes"), None)
        if yes_bucket:
            out[measure_date] = bucket_range(yes_bucket["label"])
    return out


def _check(value: float, bucket: tuple[float, float]) -> tuple[bool, float]:
    lo, hi = bucket
    if lo <= value <= hi:
        return True, 0.0
    return False, min(abs(value - lo), abs(value - hi))


def analyze(city: str, days: int) -> None:
    settled = load_settled_buckets(city)
    cli_highs = load_cli_highs(city)
    om_highs = load_open_meteo_highs(city)

    dates = sorted(settled)[-days:]

    print(f"=== {city}: NWS-actual vs Kalshi settled bucket ({len(dates)} event-days) ===\n")
    print(f"{'date':12} {'settled_bucket':>16} {'NWS_CLI':>9} {'in_range':>9} {'OpenMeteo':>10} {'in_range':>9}")

    cli_results = []
    om_results = []
    for d in dates:
        bucket = settled[d]
        lo, hi = bucket
        bucket_str = f"{lo:.0f}-{hi:.0f}"

        cli_val = cli_highs.get(d)
        cli_str = f"{cli_val:.0f}" if cli_val is not None else "n/a"
        cli_in = ""
        if cli_val is not None:
            ok, diff = _check(cli_val, bucket)
            cli_results.append((ok, diff))
            cli_in = "yes" if ok else f"no(-{diff:.0f})"

        om_val = om_highs.get(d)
        om_str = f"{om_val:.1f}" if om_val is not None else "n/a"
        om_in = ""
        if om_val is not None:
            ok, diff = _check(om_val, bucket)
            om_results.append((ok, diff))
            om_in = "yes" if ok else f"no(-{diff:.1f})"

        print(f"{d:12} {bucket_str:>16} {cli_str:>9} {cli_in:>9} {om_str:>10} {om_in:>9}")

    print()
    if cli_results:
        n = len(cli_results)
        matches = sum(1 for ok, _ in cli_results if ok)
        avg_diff = sum(diff for _, diff in cli_results) / n
        print(f"NWS CLI archive:    {matches}/{n} ({100*matches/n:.0f}%) within settled bucket, avg miss-distance {avg_diff:.2f}F")
    else:
        print("NWS CLI archive:    no cached data (run with --update-cli-cache)")

    if om_results:
        n = len(om_results)
        matches = sum(1 for ok, _ in om_results if ok)
        avg_diff = sum(diff for _, diff in om_results) / n
        print(f"Open-Meteo archive: {matches}/{n} ({100*matches/n:.0f}%) within settled bucket, avg miss-distance {avg_diff:.2f}F")
    else:
        print("Open-Meteo archive: no cached data")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", default="Las Vegas")
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--update-cli-cache", action="store_true", help="fetch the NWS CLI product version archive (~25 days)")
    args = parser.parse_args()

    if args.update_cli_cache:
        summary = ensure_cli_cache(args.city)
        print(summary)
        print()

    analyze(args.city, args.days)


if __name__ == "__main__":
    main()
