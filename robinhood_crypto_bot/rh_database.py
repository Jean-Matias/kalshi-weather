import sqlite3
from datetime import datetime
from pathlib import Path
from decimal import Decimal
from typing import Any, Dict, List, Optional
import contextlib

def init_db(db_path: Path | str) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    bid REAL,
                    ask REAL,
                    mark REAL,
                    spread REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_quotes_timestamp ON quotes(timestamp DESC)")

def insert_quote(
    db_path: Path | str,
    timestamp: datetime,
    symbol: str,
    bid: Optional[Decimal],
    ask: Optional[Decimal],
    mark: Optional[Decimal],
    spread: Optional[Decimal]
) -> None:
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("""
                INSERT INTO quotes (timestamp, symbol, bid, ask, mark, spread)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                timestamp.isoformat(),
                symbol,
                float(bid) if bid is not None else None,
                float(ask) if ask is not None else None,
                float(mark) if mark is not None else None,
                float(spread) if spread is not None else None
            ))

def get_recent_quotes(db_path: Path | str, limit: int = 10) -> List[Dict[str, Any]]:
    db_path = Path(db_path)
    if not db_path.exists():
        return []
        
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT timestamp, symbol, bid, ask, mark, spread
            FROM quotes
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        results = []
        for row in cursor:
            results.append({
                "timestamp": row["timestamp"],
                "symbol": row["symbol"],
                "bid": row["bid"],
                "ask": row["ask"],
                "mark": row["mark"],
                "spread": row["spread"]
            })
        return results
