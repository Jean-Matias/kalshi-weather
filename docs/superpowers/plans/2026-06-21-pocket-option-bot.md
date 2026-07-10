# Pocket Option RSI Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone RSI-signal trading bot for a single Pocket Option OTC pair, demo account only, with a daily loss kill switch.

**Architecture:** New `pocket_bot/` package, independent of the existing Kalshi weather code. A pure RSI/signal module feeds a `Runner` that decides whether to trade and logs every trade to SQLite; a thin `client.py` wraps the third-party `BinaryOptionsToolsV2` library for the actual WebSocket connection to Pocket Option. `Runner` takes the client as a constructor argument (duck-typed), so its decision logic is fully testable with a fake client — no live account needed for tests.

**Tech Stack:** Python 3, stdlib `sqlite3`, `unittest` (matches repo convention), third-party `BinaryOptionsToolsV2` (pip) for the Pocket Option WebSocket connection.

## Global Constraints

- Demo account only — no real-money trading in this iteration (from spec: "Demo account only for this iteration — no real-money trading until the user explicitly asks for it").
- One OTC pair, one indicator (RSI), one expiry (1 min), fixed stake size — no multi-asset, no martingale/stake scaling.
- No backtesting — OTC price history isn't published anywhere; this can only be forward-tested live.
- Daily loss kill switch: once cumulative daily P&L drops below `-DAILY_MAX_LOSS`, no new trades are placed until the next calendar day.
- All tunables (pair, stake, RSI period/thresholds, expiry, daily loss cap) live in one config module — no magic numbers in logic.
- New code goes in `pocket_bot/`; tests go in `tests/` at the repo root, following the existing convention (`tests/test_*.py`, run via `python -m unittest discover tests`).

---

### Task 1: Scaffolding and config

**Files:**
- Create: `pocket_bot/__init__.py`
- Create: `pocket_bot/config.py`
- Test: `tests/test_pocket_config.py`

**Interfaces:**
- Produces: `config.PAIR: str`, `config.STAKE_AMOUNT: float`, `config.EXPIRY_SECONDS: int`, `config.RSI_PERIOD: int`, `config.RSI_OVERBOUGHT: float`, `config.RSI_OVERSOLD: float`, `config.DAILY_MAX_LOSS: float`, `config.CANDLE_WINDOW: int`, `config.DEMO: bool`, `config.SSID_ENV_VAR: str`, `config.get_ssid() -> str` (raises `RuntimeError` if env var unset).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pocket_config.py
import os
import unittest

from pocket_bot import config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.pop(config.SSID_ENV_VAR, None)

    def tearDown(self):
        if self._old is not None:
            os.environ[config.SSID_ENV_VAR] = self._old

    def test_get_ssid_raises_without_env_var(self):
        with self.assertRaises(RuntimeError):
            config.get_ssid()

    def test_get_ssid_returns_env_value(self):
        os.environ[config.SSID_ENV_VAR] = "abc123"
        self.assertEqual(config.get_ssid(), "abc123")

    def test_candle_window_covers_rsi_period(self):
        self.assertGreater(config.CANDLE_WINDOW, config.RSI_PERIOD)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_pocket_config -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pocket_bot'`

- [ ] **Step 3: Write minimal implementation**

```python
# pocket_bot/__init__.py
```

```python
# pocket_bot/config.py
import os

PAIR = "EURUSD_otc"
STAKE_AMOUNT = 1.0
EXPIRY_SECONDS = 60
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0
DAILY_MAX_LOSS = 20.0
CANDLE_WINDOW = RSI_PERIOD + 5
DEMO = True
SSID_ENV_VAR = "POCKET_OPTION_SSID"


def get_ssid() -> str:
    ssid = os.environ.get(SSID_ENV_VAR)
    if not ssid:
        raise RuntimeError(f"Set {SSID_ENV_VAR} env var with your Pocket Option session ID")
    return ssid
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_pocket_config -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add pocket_bot/__init__.py pocket_bot/config.py tests/test_pocket_config.py
git commit -m "Add pocket_bot config scaffolding"
```

---

### Task 2: RSI signal engine

**Files:**
- Create: `pocket_bot/signals.py`
- Test: `tests/test_pocket_signals.py`

**Interfaces:**
- Consumes: nothing (pure module, no dependency on Task 1).
- Produces: `signals.rsi(closes: list[float], period: int) -> float` (raises `ValueError` if `len(closes) < period + 1`), `signals.signal(rsi_value: float, overbought: float, oversold: float) -> "call" | "put" | None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pocket_signals.py
import unittest

from pocket_bot import signals


class RsiTests(unittest.TestCase):
    def test_rsi_known_value(self):
        # closes -> diffs [2, -1, 2, 1, -2]; period=3 uses last 3 diffs [2, 1, -2]
        # avg_gain = (2+1)/3 = 1.0, avg_loss = 2/3 = 0.6667, rs = 1.5
        # rsi = 100 - 100/(1+1.5) = 60.0
        closes = [10.0, 12.0, 11.0, 13.0, 14.0, 12.0]
        self.assertAlmostEqual(signals.rsi(closes, period=3), 60.0, places=6)

    def test_rsi_all_gains_is_100(self):
        closes = [10.0, 11.0, 12.0, 13.0]
        self.assertEqual(signals.rsi(closes, period=3), 100.0)

    def test_rsi_raises_with_too_few_closes(self):
        with self.assertRaises(ValueError):
            signals.rsi([10.0, 11.0], period=3)


class SignalTests(unittest.TestCase):
    def test_overbought_returns_put(self):
        self.assertEqual(signals.signal(75.0, overbought=70.0, oversold=30.0), "put")

    def test_oversold_returns_call(self):
        self.assertEqual(signals.signal(25.0, overbought=70.0, oversold=30.0), "call")

    def test_boundary_overbought_is_inclusive(self):
        self.assertEqual(signals.signal(70.0, overbought=70.0, oversold=30.0), "put")

    def test_boundary_oversold_is_inclusive(self):
        self.assertEqual(signals.signal(30.0, overbought=70.0, oversold=30.0), "call")

    def test_neutral_returns_none(self):
        self.assertIsNone(signals.signal(50.0, overbought=70.0, oversold=30.0))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_pocket_signals -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pocket_bot.signals'`

- [ ] **Step 3: Write minimal implementation**

```python
# pocket_bot/signals.py
from __future__ import annotations


def rsi(closes: list[float], period: int) -> float:
    if len(closes) < period + 1:
        raise ValueError(f"need at least {period + 1} closes, got {len(closes)}")
    diffs = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    window = diffs[-period:]
    gains = [d for d in window if d > 0]
    losses = [-d for d in window if d < 0]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def signal(rsi_value: float, overbought: float, oversold: float) -> str | None:
    if rsi_value >= overbought:
        return "put"
    if rsi_value <= oversold:
        return "call"
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_pocket_signals -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add pocket_bot/signals.py tests/test_pocket_signals.py
git commit -m "Add RSI signal engine for pocket_bot"
```

---

### Task 3: SQLite trade log and daily P&L

**Files:**
- Create: `pocket_bot/storage.py`
- Test: `tests/test_pocket_storage.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `storage.DB_PATH: Path`, `storage.init_db(path) -> sqlite3.Connection` (accepts a filesystem path string/Path or the literal string `":memory:"`), `storage.log_trade(conn, ts: str, pair: str, direction: str, stake: float, rsi_value: float, result: str | None = None, pnl: float | None = None) -> None`, `storage.daily_pnl(conn, date_str: str) -> float` (sums `pnl` for trades whose `ts` starts with `date_str`, treating no matching rows as `0.0`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pocket_storage.py
import unittest

from pocket_bot import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.conn = storage.init_db(":memory:")

    def test_daily_pnl_with_no_trades_is_zero(self):
        self.assertEqual(storage.daily_pnl(self.conn, "2026-06-21"), 0.0)

    def test_daily_pnl_sums_same_day_only(self):
        storage.log_trade(
            self.conn, "2026-06-21T10:00:00", "EURUSD_otc", "call", 1.0, 25.0,
            result="win", pnl=0.85,
        )
        storage.log_trade(
            self.conn, "2026-06-21T10:05:00", "EURUSD_otc", "put", 1.0, 75.0,
            result="loss", pnl=-1.0,
        )
        storage.log_trade(
            self.conn, "2026-06-20T10:00:00", "EURUSD_otc", "call", 1.0, 20.0,
            result="win", pnl=0.85,
        )
        self.assertAlmostEqual(storage.daily_pnl(self.conn, "2026-06-21"), -0.15, places=6)

    def test_log_trade_without_result_is_excluded_from_pnl(self):
        storage.log_trade(
            self.conn, "2026-06-21T10:00:00", "EURUSD_otc", "call", 1.0, 25.0,
        )
        self.assertEqual(storage.daily_pnl(self.conn, "2026-06-21"), 0.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_pocket_storage -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pocket_bot.storage'`

- [ ] **Step 3: Write minimal implementation**

```python
# pocket_bot/storage.py
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "pocket_bot.db"


def init_db(path) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            pair TEXT NOT NULL,
            direction TEXT NOT NULL,
            stake REAL NOT NULL,
            rsi_value REAL NOT NULL,
            result TEXT,
            pnl REAL
        )
        """
    )
    conn.commit()
    return conn


def log_trade(
    conn: sqlite3.Connection,
    ts: str,
    pair: str,
    direction: str,
    stake: float,
    rsi_value: float,
    result: str | None = None,
    pnl: float | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO trades (ts, pair, direction, stake, rsi_value, result, pnl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (ts, pair, direction, stake, rsi_value, result, pnl),
    )
    conn.commit()


def daily_pnl(conn: sqlite3.Connection, date_str: str) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE ts LIKE ? AND pnl IS NOT NULL",
        (f"{date_str}%",),
    ).fetchone()
    return row[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_pocket_storage -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add pocket_bot/storage.py tests/test_pocket_storage.py
git commit -m "Add SQLite trade log and daily P&L for pocket_bot"
```

---

### Task 4: Runner decision loop

**Files:**
- Create: `pocket_bot/runner.py`
- Test: `tests/test_pocket_runner.py`

**Interfaces:**
- Consumes: `signals.rsi`, `signals.signal` (Task 2); `storage.init_db`, `storage.log_trade`, `storage.daily_pnl` (Task 3); a `client` object that the test substitutes with a fake exposing `buy(pair: str, amount: float, expiry_seconds: int) -> str` and `sell(pair: str, amount: float, expiry_seconds: int) -> str`; a `cfg` object exposing the same attributes as `pocket_bot.config` (`PAIR`, `STAKE_AMOUNT`, `EXPIRY_SECONDS`, `RSI_PERIOD`, `RSI_OVERBOUGHT`, `RSI_OVERSOLD`, `DAILY_MAX_LOSS`, `CANDLE_WINDOW`).
- Produces: `runner.Runner(client, cfg, conn)` with method `.on_candle(close: float) -> "call" | "put" | None` (returns the direction traded, or `None` if no trade was placed this candle).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pocket_runner.py
import datetime as dt
import unittest

from pocket_bot import config, runner, storage


class FakeClient:
    def __init__(self):
        self.calls = []

    def buy(self, pair, amount, expiry):
        self.calls.append(("buy", pair, amount, expiry))
        return "trade-1"

    def sell(self, pair, amount, expiry):
        self.calls.append(("sell", pair, amount, expiry))
        return "trade-1"


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.conn = storage.init_db(":memory:")
        self.client = FakeClient()
        self.runner = runner.Runner(self.client, config, self.conn)

    def test_no_trade_until_window_full(self):
        for close in [10.0, 10.1, 10.2]:
            result = self.runner.on_candle(close)
            self.assertIsNone(result)
        self.assertEqual(self.client.calls, [])

    def test_oversold_streak_triggers_call(self):
        closes = [20.0 - i for i in range(config.RSI_PERIOD + 2)]
        last_result = None
        for close in closes:
            last_result = self.runner.on_candle(close)
        self.assertEqual(last_result, "call")
        self.assertEqual(self.client.calls[-1][0], "buy")

    def test_daily_loss_cap_stops_new_trades(self):
        today_ts = dt.datetime.combine(dt.date.today(), dt.time()).isoformat()
        storage.log_trade(
            self.conn, today_ts, config.PAIR, "call",
            config.STAKE_AMOUNT, 25.0, result="loss", pnl=-config.DAILY_MAX_LOSS,
        )
        closes = [20.0 - i for i in range(config.RSI_PERIOD + 2)]
        for close in closes:
            self.runner.on_candle(close)
        self.assertEqual(self.client.calls, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_pocket_runner -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pocket_bot.runner'`

- [ ] **Step 3: Write minimal implementation**

```python
# pocket_bot/runner.py
from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Optional

from pocket_bot import signals, storage


class Runner:
    def __init__(self, client, cfg, conn: sqlite3.Connection):
        self.client = client
        self.cfg = cfg
        self.conn = conn
        self.closes: list[float] = []

    def on_candle(self, close: float) -> Optional[str]:
        self.closes.append(close)
        if len(self.closes) > self.cfg.CANDLE_WINDOW:
            self.closes = self.closes[-self.cfg.CANDLE_WINDOW:]
        if len(self.closes) < self.cfg.RSI_PERIOD + 1:
            return None

        today = dt.date.today().isoformat()
        if storage.daily_pnl(self.conn, today) <= -self.cfg.DAILY_MAX_LOSS:
            return None

        rsi_value = signals.rsi(self.closes, self.cfg.RSI_PERIOD)
        direction = signals.signal(rsi_value, self.cfg.RSI_OVERBOUGHT, self.cfg.RSI_OVERSOLD)
        if direction is None:
            return None

        if direction == "call":
            self.client.buy(self.cfg.PAIR, self.cfg.STAKE_AMOUNT, self.cfg.EXPIRY_SECONDS)
        else:
            self.client.sell(self.cfg.PAIR, self.cfg.STAKE_AMOUNT, self.cfg.EXPIRY_SECONDS)

        storage.log_trade(
            self.conn,
            dt.datetime.now().isoformat(),
            self.cfg.PAIR,
            direction,
            self.cfg.STAKE_AMOUNT,
            rsi_value,
        )
        return direction
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_pocket_runner -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add pocket_bot/runner.py tests/test_pocket_runner.py
git commit -m "Add pocket_bot runner decision loop with daily loss kill switch"
```

---

### Task 5: Pocket Option client wrapper

**Files:**
- Create: `pocket_bot/client.py`
- Modify: `requirements.txt` (append `BinaryOptionsToolsV2`)

**Interfaces:**
- Consumes: third-party `BinaryOptionsToolsV2.PocketOption` class.
- Produces: `client.PocketOptionClient(ssid: str, demo: bool = True)` with methods `.get_recent_candles(pair: str, period: int, count: int) -> list[tuple[int, float]]` (list of `(candle_time, close)`, oldest first), `.buy(pair: str, amount: float, expiry_seconds: int) -> str` (trade id), `.sell(pair: str, amount: float, expiry_seconds: int) -> str` (trade id), `.check_result(trade_id: str) -> dict`.

This task has no automated test — it requires a live Pocket Option session ID, which isn't available in CI. Instead it has a manual verification step. This matches the spec's stated exception ("No automated test for `client.py` ... verify it manually against the demo account on first run").

- [ ] **Step 1: Add the dependency**

```bash
pip install BinaryOptionsToolsV2
```

Then append to `requirements.txt`:

```
BinaryOptionsToolsV2
```

- [ ] **Step 2: Manually verify the installed library's API**

The exact method names/signatures on `BinaryOptionsToolsV2.PocketOption` have drifted across published versions before. Before writing the wrapper, confirm them against what's actually installed:

```bash
python -c "from BinaryOptionsToolsV2 import PocketOption; print([m for m in dir(PocketOption) if not m.startswith('_')])"
```

Expected: a list including `get_candles`, `buy`, `sell`, `check_win` (or close variants). If any of these names differ in your installed version, use the actual names in Step 3 instead — the wrapper class below is the integration point that absorbs that drift, so the rest of `pocket_bot` never has to care.

- [ ] **Step 3: Write the wrapper**

```python
# pocket_bot/client.py
"""Thin wrapper around the BinaryOptionsToolsV2 PocketOption client.

ponytail: this is the one file that absorbs drift in the underlying
library's method names/signatures (confirmed in Task 5 Step 2) — if a
future version renames buy/sell/get_candles, fix it here only.
"""
from __future__ import annotations

from BinaryOptionsToolsV2 import PocketOption


class PocketOptionClient:
    def __init__(self, ssid: str, demo: bool = True):
        self._client = PocketOption(ssid, demo=demo)

    def get_recent_candles(self, pair: str, period: int, count: int) -> list[tuple[int, float]]:
        candles = self._client.get_candles(pair, period, count * period)
        return [(c["time"], c["close"]) for c in candles[-count:]]

    def buy(self, pair: str, amount: float, expiry_seconds: int) -> str:
        trade_id, _deal = self._client.buy(pair, amount, expiry_seconds)
        return trade_id

    def sell(self, pair: str, amount: float, expiry_seconds: int) -> str:
        trade_id, _deal = self._client.sell(pair, amount, expiry_seconds)
        return trade_id

    def check_result(self, trade_id: str) -> dict:
        return self._client.check_win(trade_id)
```

- [ ] **Step 4: Manual smoke test against the demo account**

```bash
POCKET_OPTION_SSID="<paste your session id>" python -c "
from pocket_bot.client import PocketOptionClient
c = PocketOptionClient('<paste your session id>', demo=True)
print(c.get_recent_candles('EURUSD_otc', period=60, count=5))
"
```

Expected: a list of 5 `(time, close)` tuples with increasing `time` values and plausible EUR/USD-range close prices (roughly 0.9-1.2). If this raises an exception, fix the method names in `client.py` to match Step 2's findings before moving on.

- [ ] **Step 5: Commit**

```bash
git add pocket_bot/client.py requirements.txt
git commit -m "Add Pocket Option client wrapper"
```

---

### Task 6: Entrypoint

**Files:**
- Create: `pocket_bot/main.py`

**Interfaces:**
- Consumes: `config` (Task 1), `storage.init_db`, `storage.DB_PATH` (Task 3), `runner.Runner` (Task 4), `client.PocketOptionClient` (Task 5).
- Produces: a runnable script, `python -m pocket_bot.main`. No new interface for other tasks to consume — this is the leaf of the dependency graph.

No automated test: this is an infinite polling loop against a live account, which is what Task 5's manual smoke test and this task's manual run step already cover end to end.

- [ ] **Step 1: Write the entrypoint**

```python
# pocket_bot/main.py
"""Entrypoint: python -m pocket_bot.main

Polls Pocket Option for new closed candles on the configured pair and feeds
each one to Runner. Ctrl+C to stop.
"""
from __future__ import annotations

import time

from pocket_bot import config, storage
from pocket_bot.client import PocketOptionClient
from pocket_bot.runner import Runner


def main() -> None:
    client = PocketOptionClient(config.get_ssid(), demo=config.DEMO)
    conn = storage.init_db(str(storage.DB_PATH))
    runner = Runner(client, config, conn)

    last_time: int | None = None
    print(f"Starting pocket_bot on {config.PAIR}, demo={config.DEMO}")
    while True:
        candles = client.get_recent_candles(config.PAIR, period=60, count=config.CANDLE_WINDOW)
        for candle_time, close in candles:
            if last_time is not None and candle_time <= last_time:
                continue
            last_time = candle_time
            direction = runner.on_candle(close)
            if direction:
                print(f"{direction.upper()} signal placed on {config.PAIR}")
        time.sleep(5)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Manual run against the demo account**

```bash
POCKET_OPTION_SSID="<paste your session id>" python -m pocket_bot.main
```

Expected: prints `Starting pocket_bot on EURUSD_otc, demo=True`, then runs indefinitely, printing a `CALL`/`PUT` line whenever RSI crosses a threshold. Confirm in the Pocket Option demo account UI that trades actually appear when a signal line prints. Stop with Ctrl+C.

- [ ] **Step 3: Commit**

```bash
git add pocket_bot/main.py
git commit -m "Add pocket_bot entrypoint"
```

---

## Plan Self-Review

**Spec coverage:**
- Single OTC pair, RSI, 1-min expiry, fixed stake → `config.py` (Task 1), enforced via `Runner` (Task 4). ✓
- Demo-only → `config.DEMO = True`, used in `main.py` and `client.py` (Tasks 5-6). ✓
- No backtesting → not built; plan only covers live forward-testing. ✓
- Daily loss kill switch → `Runner.on_candle` checks `storage.daily_pnl` against `cfg.DAILY_MAX_LOSS` before trading (Task 4), tested in `test_daily_loss_cap_stops_new_trades`. ✓
- SQLite trade log → `storage.py` (Task 3). ✓
- No multi-asset/martingale/dashboard → none built. ✓
- `test_signals.py`-equivalent (the only required automated test per spec) → Task 2, plus Tasks 3-4 also got tests since their logic is pure/injectable and cheap to test; Task 5-6 manual-only as the spec anticipated. ✓

**Placeholder scan:** none found — every step has runnable code or an exact command.

**Type consistency:** `Runner(client, cfg, conn)` constructor and `.on_candle(close: float)` signature match between Task 4's definition and Tasks 5-6's usage in `main.py`. `PocketOptionClient` methods (`buy`, `sell`, `get_recent_candles`, `check_result`) match between Task 5's definition and Task 6's usage. `cfg` attribute names match between `config.py` (Task 1) and `Runner` (Task 4).
