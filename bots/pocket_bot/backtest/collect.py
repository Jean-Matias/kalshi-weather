"""Daily forward data collection: merge today's new bars into the persistent
history cache for each real pair, growing the backtest sample beyond
yfinance's 7-day intraday retention limit over time.

Usage:
    python bots/pocket_bot/backtest/collect.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pocket_bot.backtest import data  # noqa: E402

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]


def main() -> None:
    for pair in PAIRS:
        added = data.update_history(pair)
        total = len(data.fetch_closes(pair))
        print(f"{pair}: +{added} new bars, {total} total (deduped)")


if __name__ == "__main__":
    main()
