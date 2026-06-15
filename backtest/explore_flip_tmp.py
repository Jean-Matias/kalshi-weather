"""Exploratory sweep for round-trip ('buy low, cash out before settlement')
flip strategies across cities. Throwaway script — _tmp.py convention."""
from __future__ import annotations

from backtest import data, engine, strategies

CITIES = ["Las Vegas", "Phoenix"]


def try_one(dataset, label, factory, **params):
    strat = factory(**params)
    report = engine.run_flip(dataset, strat, contracts=3, label=f"{label} {params}")
    if report.n < 8:
        return None
    older, newer = engine.split_chronological(report)
    return report, older, newer


def main():
    for city in CITIES:
        dataset = data.load_dataset(city)
        print(f"\n=== {city}: {len(dataset)} events ===")

        configs = []
        for min_move in (4, 6, 9):
            for pt in (5, 8, 12):
                for sl in (6, 10, 15):
                    configs.append(("momentum_flip", strategies.momentum_flip,
                                    dict(min_move_cents=min_move, profit_target_cents=pt, stop_loss_cents=sl)))
        for pt in (4, 6, 8):
            for sl in (5, 8, 12):
                configs.append(("quick_scalp", strategies.quick_scalp,
                                dict(profit_target_cents=pt, stop_loss_cents=sl)))

        results = []
        for label, factory, params in configs:
            out = try_one(dataset, label, factory, **params)
            if out is None:
                continue
            report, older, newer = out
            stable = (older.ev_per_trade > 0) == (newer.ev_per_trade > 0) and report.ev_per_trade > 0
            results.append((report.ev_per_trade, stable, label, params, report, older, newer))

        results.sort(reverse=True, key=lambda r: r[0])
        print(f"Top candidates by EV/trade ({len(results)} configs tested, n>=8):")
        for ev, stable, label, params, report, older, newer in results[:12]:
            flag = "STABLE" if stable else "  -   "
            print(f"  [{flag}] {label} {params}")
            print(f"           {report.line()}")
            print(f"           older: {older.line()}")
            print(f"           newer: {newer.line()}")


if __name__ == "__main__":
    main()
