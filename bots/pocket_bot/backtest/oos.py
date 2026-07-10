"""Out-of-sample check for the parameter sweep in sweep.py: split each pair's
cached closes in half chronologically, pick the best (period, overbought,
oversold) combo on the FIRST half only, then measure that exact combo
(no further tuning) on the SECOND half it never saw. A real edge should
survive this; an overfit one usually won't.

Usage:
    python bots/pocket_bot/backtest/oos.py
"""
from __future__ import annotations

import sys
from math import sqrt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pocket_bot.backtest import data  # noqa: E402
from pocket_bot.backtest.run import simulate  # noqa: E402

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
PERIODS = [7, 14, 21]
THRESHOLDS = [(65.0, 35.0), (70.0, 30.0), (75.0, 25.0), (80.0, 20.0)]
PAYOUT = 0.92
BREAKEVEN = 1 / (1 + PAYOUT)


def standard_error(win_rate: float, n: int) -> float:
    if n == 0:
        return float("inf")
    return sqrt(win_rate * (1 - win_rate) / n)


def best_combo(pair: str, closes: list[float]) -> dict | None:
    best = None
    for period in PERIODS:
        for ob, os in THRESHOLDS:
            result = simulate(pair, closes, period=period, overbought=ob, oversold=os, payout=PAYOUT)
            if result["signals"] < 30:
                continue
            if best is None or result["pnl"] > best["pnl"]:
                best = {**result, "period": period, "ob": ob, "os": os}
    return best


def main() -> None:
    print(f"Breakeven win rate at {PAYOUT:.0%} payout: {BREAKEVEN * 100:.2f}%\n")
    header = f"{'pair':10} {'split':6} {'period':>6} {'ob/os':>9} {'signals':>8} {'win_rate':>9} {'edge(pp)':>9} {'se(pp)':>7} {'pnl':>9}"
    print(header)

    for pair in PAIRS:
        closes = data.fetch_closes(pair)
        midpoint = len(closes) // 2
        train, test = closes[:midpoint], closes[midpoint:]

        train_best = best_combo(pair, train)
        if train_best is None:
            print(f"{pair:10}  not enough train-half signals to pick a combo")
            continue

        thresholds_label = f"{train_best['ob']:.0f}/{train_best['os']:.0f}"
        train_se = standard_error(train_best["win_rate"], train_best["signals"])
        train_edge = (train_best["win_rate"] - BREAKEVEN) * 100
        print(
            f"{pair:10} {'train':6} {train_best['period']:>6} {thresholds_label:>9} "
            f"{train_best['signals']:>8} {train_best['win_rate'] * 100:>8.1f}% {train_edge:>+8.2f} "
            f"{train_se * 100:>6.2f} {train_best['pnl']:>+9.2f}"
        )

        test_result = simulate(
            pair, test, period=train_best["period"], overbought=train_best["ob"], oversold=train_best["os"], payout=PAYOUT,
        )
        test_se = standard_error(test_result["win_rate"], test_result["signals"]) if test_result["signals"] else float("inf")
        test_edge = (test_result["win_rate"] - BREAKEVEN) * 100
        print(
            f"{pair:10} {'TEST':6} {train_best['period']:>6} {thresholds_label:>9} "
            f"{test_result['signals']:>8} {test_result['win_rate'] * 100:>8.1f}% {test_edge:>+8.2f} "
            f"{test_se * 100:>6.2f} {test_result['pnl']:>+9.2f}"
        )
        print()


if __name__ == "__main__":
    main()
