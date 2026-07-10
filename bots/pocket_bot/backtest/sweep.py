"""Parameter sweep over the cached real-pair data from run.py, to see whether
any RSI period/threshold combo (or a simple trend filter) clears the 92%-payout
breakeven win rate (52.08%) by a statistically meaningful margin — not just
nominally. Uses the already-cached, already-deduped closes; no new network
calls.

Usage:
    python bots/pocket_bot/backtest/sweep.py
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
BREAKEVEN = 1 / (1 + PAYOUT)  # 0.5208... — win rate needed to break even


def standard_error(win_rate: float, n: int) -> float:
    if n == 0:
        return float("inf")
    return sqrt(win_rate * (1 - win_rate) / n)


def sma(values: list[float], window: int) -> list[float | None]:
    """Simple moving average, None where there isn't enough history yet."""
    out: list[float | None] = []
    total = 0.0
    for i, v in enumerate(values):
        total += v
        if i >= window:
            total -= values[i - window]
        out.append(total / window if i >= window - 1 else None)
    return out


def simulate_with_trend_filter(
    pair: str,
    closes: list[float],
    *,
    period: int,
    overbought: float,
    oversold: float,
    payout: float,
    trend_window: int,
    stake: float = 1.0,
) -> dict:
    """Like simulate(), but only takes a signal when it agrees with a longer
    SMA's direction: "call" only if price is above the SMA (uptrend), "put"
    only if below (downtrend) — the methodological fix for raw RSI being too
    noisy alone."""
    from pocket_bot.signals import rsi, signal

    trend = sma(closes, trend_window)
    signals_fired = 0
    wins = 0
    pnl = 0.0
    for i in range(period + 1, len(closes) - 1):
        if trend[i] is None:
            continue
        window = closes[: i + 1][-(period + 1):]
        rsi_value = rsi(window, period)
        direction = signal(rsi_value, overbought, oversold)
        if direction is None:
            continue
        cur_close = closes[i]
        if direction == "call" and not (cur_close > trend[i]):
            continue
        if direction == "put" and not (cur_close < trend[i]):
            continue
        signals_fired += 1
        next_close = closes[i + 1]
        won = (next_close > cur_close) if direction == "call" else (next_close < cur_close)
        if won:
            wins += 1
            pnl += stake * payout
        else:
            pnl -= stake
    win_rate = wins / signals_fired if signals_fired else 0.0
    return {"pair": pair, "signals": signals_fired, "wins": wins, "win_rate": win_rate, "pnl": pnl}


def main() -> None:
    print(f"Breakeven win rate at {PAYOUT:.0%} payout: {BREAKEVEN:.4f} ({BREAKEVEN * 100:.2f}%)\n")

    print("=== Raw RSI parameter sweep (best combo per pair by P&L) ===")
    print(f"{'pair':10} {'period':>6} {'ob/os':>9} {'signals':>8} {'win_rate':>9} {'edge(pp)':>9} {'se(pp)':>7} {'pnl':>9}")
    for pair in PAIRS:
        closes = data.fetch_closes(pair)
        best = None
        for period in PERIODS:
            for ob, os in THRESHOLDS:
                result = simulate(pair, closes, period=period, overbought=ob, oversold=os, payout=PAYOUT)
                if result["signals"] < 30:  # too few to mean anything
                    continue
                if best is None or result["pnl"] > best["pnl"]:
                    best = {**result, "period": period, "ob": ob, "os": os}
        if best is None:
            print(f"{pair:10}  no combo produced >=30 signals")
            continue
        se = standard_error(best["win_rate"], best["signals"])
        edge_pp = (best["win_rate"] - BREAKEVEN) * 100
        thresholds_label = f"{best['ob']:.0f}/{best['os']:.0f}"
        print(
            f"{pair:10} {best['period']:>6} {thresholds_label:>9} "
            f"{best['signals']:>8} {best['win_rate'] * 100:>8.1f}% {edge_pp:>+8.2f} "
            f"{se * 100:>6.2f} {best['pnl']:>+9.2f}"
        )

    print("\n=== With a 50-period trend filter (RSI signal must agree with SMA direction) ===")
    print(f"{'pair':10} {'period':>6} {'ob/os':>9} {'signals':>8} {'win_rate':>9} {'edge(pp)':>9} {'se(pp)':>7} {'pnl':>9}")
    for pair in PAIRS:
        closes = data.fetch_closes(pair)
        best = None
        for period in PERIODS:
            for ob, os in THRESHOLDS:
                result = simulate_with_trend_filter(
                    pair, closes, period=period, overbought=ob, oversold=os, payout=PAYOUT, trend_window=50,
                )
                if result["signals"] < 30:
                    continue
                if best is None or result["pnl"] > best["pnl"]:
                    best = {**result, "period": period, "ob": ob, "os": os}
        if best is None:
            print(f"{pair:10}  no combo produced >=30 signals")
            continue
        se = standard_error(best["win_rate"], best["signals"])
        edge_pp = (best["win_rate"] - BREAKEVEN) * 100
        thresholds_label = f"{best['ob']:.0f}/{best['os']:.0f}"
        print(
            f"{pair:10} {best['period']:>6} {thresholds_label:>9} "
            f"{best['signals']:>8} {best['win_rate'] * 100:>8.1f}% {edge_pp:>+8.2f} "
            f"{se * 100:>6.2f} {best['pnl']:>+9.2f}"
        )


if __name__ == "__main__":
    main()
