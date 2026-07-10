"""CLI orchestrator for hotscout historical data pullers.

Usage:
    python -m hotscout.data.build --probe [--city "Las Vegas"]
    python -m hotscout.data.build --city "Las Vegas" --days 180
    python -m hotscout.data.build --all --days 180

After a bulk build, runs a cross-check: for each city, what fraction of days
have a cli_daily high that falls inside that day's settled Kalshi bucket.
Kalshi settles on the CLI high, so a low match rate signals a bug in bucket
parsing, date alignment, or station selection.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta

from hotscout import db
from hotscout.config import CITIES

from . import cli_history, forecast_history, kalshi_history, obs_history


def _date_range(days: int) -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=days)
    return start.isoformat(), end.isoformat()


def _years_spanned(start_date: str, end_date: str) -> list[int]:
    y1 = int(start_date[:4])
    y2 = int(end_date[:4])
    return list(range(y1, y2 + 1))


def build_city(city: str, days: int) -> dict:
    conn = db.connect()
    db.init(conn)
    try:
        start_date, end_date = _date_range(days)
        years = _years_spanned(start_date, end_date)

        print(f"[{city}] cli_daily backfill ({years})...")
        cli_summary = cli_history.backfill_city(conn, city, years)

        print(f"[{city}] forecast_daily backfill ({start_date} to {end_date})...")
        forecast_summary = forecast_history.backfill_city(conn, city, start_date, end_date)

        print(f"[{city}] obs_hourly backfill ({start_date} to {end_date})...")
        obs_summary = obs_history.backfill_city(conn, city, start_date, end_date)

        target_events = max(days // 2, 30)  # rough: ~1 event-day per 2 calendar days of history desired
        print(f"[{city}] kalshi history backfill (target {target_events} settled events)...")
        kalshi_summary = kalshi_history.backfill_city(conn, city, target_events)

        return {
            "city": city,
            "cli_daily": cli_summary,
            "forecast_daily": forecast_summary,
            "obs_hourly": obs_summary,
            "kalshi": kalshi_summary,
        }
    finally:
        conn.close()


def cross_check_city(conn, city: str) -> dict:
    """% of settled Kalshi event-days where cli_daily's high falls inside
    that day's settled bucket bounds."""
    import json

    rows = conn.execute(
        "SELECT market_date, settled_bucket_label, buckets_json FROM kalshi_events WHERE city = ?",
        (city,),
    ).fetchall()

    matched = 0
    checked = 0
    mismatches = []
    for row in rows:
        cli_row = conn.execute(
            "SELECT cli_high_f FROM cli_daily WHERE city = ? AND date = ?",
            (city, row["market_date"]),
        ).fetchone()
        if cli_row is None or cli_row["cli_high_f"] is None:
            continue
        buckets = json.loads(row["buckets_json"])
        settled = next((b for b in buckets if b.get("result") == "yes"), None)
        if settled is None:
            continue
        checked += 1
        cli_high = cli_row["cli_high_f"]
        low = settled.get("low_f")
        high = settled.get("high_f")
        in_bounds = (low is None or cli_high >= low) and (high is None or cli_high <= high)
        if in_bounds:
            matched += 1
        else:
            mismatches.append({
                "date": row["market_date"],
                "cli_high_f": cli_high,
                "settled_label": settled.get("label"),
                "settled_low_f": low,
                "settled_high_f": high,
            })

    pct = (matched / checked * 100) if checked else None
    return {"city": city, "checked": checked, "matched": matched, "pct": pct, "mismatches": mismatches}


def run_cross_check(cities: list[str]) -> None:
    conn = db.connect()
    try:
        print("\n=== Cross-check: cli_daily high vs settled Kalshi bucket ===")
        for city in cities:
            result = cross_check_city(conn, city)
            if result["checked"] == 0:
                print(f"[{city}] no overlapping rows to check")
                continue
            print(f"[{city}] {result['matched']}/{result['checked']} = {result['pct']:.1f}%")
            for mismatch in result["mismatches"]:
                print(f"    MISMATCH {mismatch}")
    finally:
        conn.close()


def run_probe(city: str) -> None:
    conn = db.connect()
    db.init(conn)
    try:
        print(f"=== Probing sources for {city} ===")

        print("\n-- cli_history --")
        print(cli_history.probe(city))

        print("\n-- forecast_history --")
        print(forecast_history.probe(city))

        print("\n-- obs_history --")
        print(obs_history.probe(city))

        print("\n-- kalshi_history --")
        print(kalshi_history.probe(conn, city))
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="hotscout historical data puller orchestrator")
    parser.add_argument("--city", choices=CITIES, help="Single city to build")
    parser.add_argument("--all", action="store_true", help="Build all configured cities")
    parser.add_argument("--days", type=int, default=180, help="Days of history to backfill (default 180)")
    parser.add_argument("--probe", action="store_true", help="Verify endpoints once per source, no bulk download")
    args = parser.parse_args()

    if args.probe:
        run_probe(args.city or CITIES[0])
        return

    if args.all:
        cities = CITIES
    elif args.city:
        cities = [args.city]
    else:
        parser.error("specify --city, --all, or --probe")
        return

    for city in cities:
        summary = build_city(city, args.days)
        print(summary)

    run_cross_check(cities)


if __name__ == "__main__":
    main()
