"""hotscout database connection helpers."""

import sqlite3

from hotscout.config import DB_PATH
from hotscout.schema import DDL


def connect():
    """Open a sqlite3 connection to the hotscout database, creating the
    parent directory if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init(conn=None):
    """Create all hotscout tables if they don't already exist. Idempotent."""
    owns_conn = conn is None
    if owns_conn:
        conn = connect()
    try:
        for statement in DDL:
            conn.execute(statement)
        conn.commit()
    finally:
        if owns_conn:
            conn.close()
