from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def init_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS weather_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            city TEXT NOT NULL,
            station_id TEXT,
            payload_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS market_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            city TEXT NOT NULL,
            url TEXT,
            payload_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scored_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            city TEXT NOT NULL,
            final_label TEXT NOT NULL,
            estimated_edge_score INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        );
        """
    )
    return conn


def save_snapshot(
    conn: sqlite3.Connection,
    run_id: str,
    weather: dict[str, Any],
    market: dict[str, Any],
    scored: dict[str, Any],
) -> None:
    captured_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO weather_snapshots
        (run_id, captured_at, city, station_id, payload_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            run_id,
            captured_at,
            weather.get("city"),
            weather.get("station_id"),
            json.dumps(weather, sort_keys=True, default=str),
        ),
    )
    conn.execute(
        """
        INSERT INTO market_snapshots
        (run_id, captured_at, city, url, payload_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            run_id,
            captured_at,
            market.get("city"),
            market.get("url"),
            json.dumps(market, sort_keys=True, default=str),
        ),
    )
    conn.execute(
        """
        INSERT INTO scored_signals
        (run_id, captured_at, city, final_label, estimated_edge_score, payload_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            captured_at,
            scored.get("city"),
            scored.get("final_label"),
            scored.get("estimated_edge_score", 0),
            json.dumps(scored, sort_keys=True, default=str),
        ),
    )
    conn.commit()
