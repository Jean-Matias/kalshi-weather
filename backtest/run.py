"""CLI: run KXHIGHTLV (Las Vegas daily-high-temp) backtest strategies against
cached real settlement history.

Usage (from the kalshi-weather-scout project root):

    python -m backtest.data                      # build/top-up the cache
    python -m backtest.run --compare buy_favorite fade_tails favorite_with_margin top2_cheaper momentum_favorite
    python -m backtest.run --strategy buy_favorite --param min_price=55 --param max_price=85 --decision-hour 30
    python -m backtest.run --sweep-hours --strategy buy_favorite

Each run prints n / win_rate / EV per trade / total net, plus a chronological
older-half vs newer-half stability split — an edge that only shows up in one
half is very likely noise, not a real structural edge (see BTC bot's
bot/BACKTEST_GUIDE.md for the same principle).
"""
from __future__ import annotations

import argparse
import sys

from backtest import data, engine, strategies

DEFAULT_HOUR = 24  # ~mid-afternoon of the measurement day for a market that opens ~7am local


def _parse_params(pairs: list[str]) -> dict:
    params = {}
    for pair in pairs:
        key, _, raw = pair.partition("=")
        try:
            value: object = int(raw)
        except ValueError:
            try:
                value = float(raw)
            except ValueError:
                value = raw
        params[key] = value
    return params


def _build_strategy(name: str, params: dict):
    if name not in strategies.REGISTRY:
        sys.exit(f"Unknown strategy '{name}'. Options: {', '.join(strategies.REGISTRY)}")
    return strategies.REGISTRY[name](**params)


def _run_one(dataset, name, params, contracts, decision_hour, quiet=False):
    strategy = _build_strategy(name, params)
    label = f"{name}@h{decision_hour}" if not params else f"{name}@h{decision_hour} ({params})"
    report = engine.run(dataset, strategy, contracts=contracts, label=label, decision_hour=decision_hour)
    if not quiet:
        print(report.line())
        older, newer = engine.split_chronological(report)
        print(f"  stability: {older.line()}")
        print(f"  stability: {newer.line()}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Backtest daily-high-temp entry strategies against cached settlement history.")
    parser.add_argument("--city", default="Las Vegas", choices=sorted(data.SERIES_BY_CITY), help="city/series to backtest (default Las Vegas)")
    parser.add_argument("--update-cache", action="store_true", help="fetch/top up cached settlement history before running")
    parser.add_argument("--target-events", type=int, default=90, help="how many settled event-days to cache (default 90)")
    parser.add_argument("--strategy", help="single strategy to run")
    parser.add_argument("--param", action="append", default=[], help="key=value strategy parameter (repeatable)")
    parser.add_argument("--compare", nargs="+", help="run several strategies (default params) side by side")
    parser.add_argument("--contracts", type=int, default=3, help="contracts per trade (default 3)")
    parser.add_argument("--decision-hour", type=int, default=DEFAULT_HOUR, help="hours after event open to make the decision (default 24)")
    parser.add_argument("--sweep-hours", action="store_true", help="sweep decision_hour from 6 to 40 (step 6) for the chosen --strategy")
    args = parser.parse_args()

    if args.update_cache:
        summary = data.ensure_cached(args.city, target_events=args.target_events)
        print(summary)

    span = data.cache_span_days(args.city)
    if span:
        print(f"[{args.city}] Cache spans ~{span:.1f} days.\n")

    dataset = data.load_dataset(args.city)
    print(f"[{args.city}] Loaded {len(dataset)} settled event-days.\n")
    if not dataset:
        return

    params = _parse_params(args.param)

    if args.sweep_hours:
        if not args.strategy:
            sys.exit("--sweep-hours requires --strategy")
        print(f"=== Sweeping decision_hour for '{args.strategy}' ({params}) ===")
        results = []
        for hour in range(6, 41, 6):
            report = _run_one(dataset, args.strategy, params, args.contracts, hour, quiet=True)
            results.append((report.ev_per_trade, hour, report))
            print(f"  hour={hour:>3}  n={report.n:>3}  win%={report.win_rate:5.1f}%  EV/trade={report.ev_per_trade:+6.2f}c  total=${report.total_net_cents/100:+.2f}")
        results.sort(reverse=True)
        print("\nBest hours by EV/trade:")
        for ev, hour, report in results[:5]:
            print(f"  hour={hour}: EV/trade={ev:+.2f}c  n={report.n}  win%={report.win_rate:.1f}%")
        return

    if args.compare:
        for name in args.compare:
            _run_one(dataset, name, {}, args.contracts, args.decision_hour)
            print()
        return

    if args.strategy:
        _run_one(dataset, args.strategy, params, args.contracts, args.decision_hour)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
