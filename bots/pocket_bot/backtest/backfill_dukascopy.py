"""One-off (long-running) backfill: pull a full year of TRUE 1-minute
Dukascopy history for each real pair into the persistent cache used by
run.py/sweep.py/oos.py. Each day is 24 requests, so this can take hours —
run it in the background.

Usage:
    python bots/pocket_bot/backtest/backfill_dukascopy.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pocket_bot.backtest import data  # noqa: E402

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
DAYS_BACK = 365


def main() -> None:
    for pair in PAIRS:
        start = time.time()
        added = data.update_history_dukascopy(pair, days_back=DAYS_BACK, threads=4)
        total = len(data.fetch_closes(pair))
        elapsed = time.time() - start
        print(f"{pair}: +{added} new bars, {total} total (deduped), took {elapsed / 60:.1f} min")


if __name__ == "__main__":
    main()
