"""Measure whether the Kalshi low-temperature market favorite skews hotter than settlement.

Research-only. For each cached event-day, at a given decision hour, compare the
market favorite bucket against the bucket that actually settled YES, then score
three naive exploits:

- yes_favorite: buy YES on the favorite at market price
- no_favorite: buy NO on the favorite at (100 - price)
- yes_cooler: buy YES on the bucket one step cooler than the favorite
- yes_hotter: buy YES on the bucket one step hotter than the favorite

Usage:
    python -m backtest.low_skew --city "San Antonio" --days 60
"""
from __future__ import annotations

import argparse
import statistics
from typing import Any

from backtest import low_data
from backtest.engine import FEE_CENTS_PER_CONTRACT, _build_buckets
from backtest.low_strategies import bucket_center


def analyze_city(city: str, *, days: int, decision_hour: int) -> dict[str, Any]:
    dataset = low_data.load_dataset(city, days=days)
    rows = []
    for entry in dataset:
        event = entry["event"]
        buckets = _build_buckets(event, entry["bucket_candles"])
        if not buckets:
            continue
        max_idx = min(len(b["prices"]) for b in buckets) - 1
        if max_idx < 0:
            continue
        idx = min(decision_hour, max_idx)
        if any(b["prices"][idx] is None for b in buckets):
            continue
        winner = next((b for b in buckets if b["result"] == "yes"), None)
        if winner is None:
            continue
        favorite = max(buckets, key=lambda b: b["prices"][idx])
        fav_idx = buckets.index(favorite)
        cooler = buckets[fav_idx - 1] if fav_idx > 0 else None
        hotter_bucket = buckets[fav_idx + 1] if fav_idx + 1 < len(buckets) else None
        rows.append(
            {
                "event_ticker": event["event_ticker"],
                "favorite": favorite,
                "winner": winner,
                "cooler": cooler,
                "hotter": hotter_bucket,
                "fav_price": int(favorite["prices"][idx]),
                "cooler_price": int(cooler["prices"][idx]) if cooler else None,
                "hotter_price": int(hotter_bucket["prices"][idx]) if hotter_bucket else None,
                "skew_f": bucket_center(favorite["label"]) - bucket_center(winner["label"]),
            }
        )
    return {"city": city, "decision_hour": decision_hour, "rows": rows}


def _trade_net(price: int, won: bool) -> float:
    price = max(1, min(99, price))
    gross = (100 - price) if won else -price
    return gross - FEE_CENTS_PER_CONTRACT


def summarize(analysis: dict[str, Any]) -> str:
    rows = analysis["rows"]
    if not rows:
        return f"[{analysis['city']} h{analysis['decision_hour']}] no usable event-days"

    hotter = sum(1 for r in rows if r["skew_f"] > 0)
    colder = sum(1 for r in rows if r["skew_f"] < 0)
    exact = sum(1 for r in rows if r["skew_f"] == 0)
    mean_skew = statistics.mean(r["skew_f"] for r in rows)
    fav_wins = sum(1 for r in rows if r["favorite"] is r["winner"])
    avg_fav_price = statistics.mean(r["fav_price"] for r in rows)

    yes_fav = [_trade_net(r["fav_price"], r["favorite"] is r["winner"]) for r in rows]
    no_fav = [_trade_net(100 - r["fav_price"], r["favorite"] is not r["winner"]) for r in rows]
    cooler_rows = [r for r in rows if r["cooler"] is not None]
    yes_cooler = [_trade_net(r["cooler_price"], r["cooler"] is r["winner"]) for r in cooler_rows]
    hotter_rows = [r for r in rows if r["hotter"] is not None]
    yes_hotter = [_trade_net(r["hotter_price"], r["hotter"] is r["winner"]) for r in hotter_rows]

    lines = [
        f"[{analysis['city']} h{analysis['decision_hour']}] {len(rows)} event-days",
        f"  favorite vs settlement: hotter {hotter} ({100 * hotter / len(rows):.0f}%), "
        f"exact {exact} ({100 * exact / len(rows):.0f}%), colder {colder} ({100 * colder / len(rows):.0f}%), "
        f"mean skew {mean_skew:+.2f}F",
        f"  favorite calibration: priced {avg_fav_price:.0f}c, won {100 * fav_wins / len(rows):.0f}% "
        f"({fav_wins}/{len(rows)})",
        f"  EV/contract  yes_favorite: {statistics.mean(yes_fav):+.1f}c"
        f"  no_favorite: {statistics.mean(no_fav):+.1f}c"
        f"  yes_cooler: {statistics.mean(yes_cooler):+.1f}c (n={len(yes_cooler)})"
        f"  yes_hotter: {statistics.mean(yes_hotter):+.1f}c (n={len(yes_hotter)})",
    ]
    half = len(no_fav) // 2
    if half >= 5:
        lines.append(
            f"  no_favorite stability: older half {statistics.mean(no_fav[:half]):+.1f}c, "
            f"newer half {statistics.mean(no_fav[half:]):+.1f}c"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", action="append", default=None)
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--decision-hour", type=int, action="append", default=None)
    args = parser.parse_args()

    cities = args.city or ["San Antonio"]
    hours = args.decision_hour or [3, 6, 9, 12]
    for city in cities:
        for hour in hours:
            print(summarize(analyze_city(city, days=args.days, decision_hour=hour)))


if __name__ == "__main__":
    main()
