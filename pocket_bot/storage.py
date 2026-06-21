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
