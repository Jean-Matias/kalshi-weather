"""Backtest the pocket_bot RSI signal against REAL historical forex data.

Real OTC price history (the pair bots/pocket_bot actually trades) isn't
published anywhere, so this validates the same RSI(period)/overbought/oversold
rule against real, non-OTC FX pairs instead — a proxy check for whether the
signal has any edge at all before trusting it with real money on the OTC bot.
Reuses bots/pocket_bot/signals.py's rsi()/signal() verbatim; does not modify
or import anything that would affect the live bot.

Requires `yfinance` (pip install yfinance) under whichever Python interpreter
you run this with — a separate dependency from the live bot on purpose.

Usage:
    python bots/pocket_bot/backtest/run.py --pairs EURUSD,GBPUSD,USDJPY,AUDUSD --payout 0.92
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # puts bots/ on sys.path

from pocket_bot.backtest import data  # noqa: E402
from pocket_bot.signals import rsi, signal  # noqa: E402


def simulate(
    pair: str,
    closes: list[float],
    *,
    period: int,
    overbought: float,
    oversold: float,
    payout: float,
    stake: float = 1.0,
) -> dict:
    """Walk `closes` through the RSI signal, scoring each fired signal against
    the very next close (the "next candle" a 1-min-expiry binary option would
    settle against)."""
    signals_fired = 0
    wins = 0
    pnl = 0.0
    for i in range(period + 1, len(closes) - 1):
        window = closes[: i + 1][-(period + 1):]
        rsi_value = rsi(window, period)
        direction = signal(rsi_value, overbought, oversold)
        if direction is None:
            continue
        signals_fired += 1
        cur_close = closes[i]
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", default="EURUSD,GBPUSD,USDJPY,AUDUSD")
    parser.add_argument("--period", type=int, default=14)
    parser.add_argument("--overbought", type=float, default=70.0)
    parser.add_argument("--oversold", type=float, default=30.0)
    parser.add_argument("--payout", type=float, default=0.92)
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()

    print(f"{'pair':10} {'signals':>8} {'win_rate':>9} {'pnl@'+str(args.payout):>10}")
    for raw_pair in args.pairs.split(","):
        pair = raw_pair.strip().upper()
        closes = data.fetch_closes(pair, force=args.force_refresh)
        result = simulate(
            pair,
            closes,
            period=args.period,
            overbought=args.overbought,
            oversold=args.oversold,
            payout=args.payout,
        )
        print(
            f"{result['pair']:10} {result['signals']:>8} "
            f"{result['win_rate'] * 100:>8.1f}% {result['pnl']:>+9.2f}"
        )


if __name__ == "__main__":
    main()
