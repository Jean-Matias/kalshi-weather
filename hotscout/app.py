"""hotscout FastAPI dashboard app.

Run with: uvicorn hotscout.app:app --port 8801
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from hotscout import db as hs_db
from hotscout import picks as hs_picks
from hotscout.live import build_board
from hotscout.ui import render_html


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


BOARD_CACHE_TTL_SECONDS = _env_int("HOTSCOUT_BOARD_CACHE_SECONDS", 60)

logger = logging.getLogger(__name__)


class BoardCache:
    """60-second TTL cache around build_board(), matching the pattern used by
    the root live_dashboard.LiveDashboardCache. On every cache refresh it also
    records new BUY picks and resolves any settled picks, guarded so a DB
    hiccup never breaks the board response."""

    def __init__(
        self,
        ttl_seconds: int = BOARD_CACHE_TTL_SECONDS,
        builder: Callable[[], dict[str, Any]] = build_board,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.builder = builder
        self.clock = clock
        self.value: dict[str, Any] | None = None
        self.fetched_at: datetime | None = None

    def get(self) -> dict[str, Any]:
        now = self.clock()
        if self.value is None or self.fetched_at is None or now - self.fetched_at >= timedelta(seconds=self.ttl_seconds):
            self.value = self.builder()
            self._record_and_resolve_picks()
            self.fetched_at = now
        payload = dict(self.value)
        payload["cache_ttl_seconds"] = self.ttl_seconds
        return payload

    def _record_and_resolve_picks(self) -> None:
        if self.value is None:
            return
        try:
            conn = hs_db.connect()
            try:
                hs_db.init(conn)
                hs_picks.record_from_board(conn, self.value)
                hs_picks.resolve_open(conn)
            finally:
                conn.close()
        except Exception as exc:
            # Board must still render, but a broken picks pipeline should be
            # visible in the server log, not swallowed.
            logger.warning("pick recording/resolution failed: %s", exc)


def create_app(board_builder: Callable[[], dict[str, Any]] = build_board) -> FastAPI:
    app = FastAPI(title="Hotscout Dashboard")
    board_cache = BoardCache(builder=board_builder)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse(render_html())

    @app.get("/api/board")
    def api_board() -> JSONResponse:
        return JSONResponse(board_cache.get())

    @app.get("/api/backtest")
    def api_backtest(city: str) -> JSONResponse:
        conn = hs_db.connect()
        try:
            hs_db.init(conn)
            rows = conn.execute(
                """
                SELECT city, strategy, decision_hour_local, edge_threshold, n_trades,
                       wins, roi, brier, window_start, window_end, created_at
                FROM backtest_results
                WHERE city = ?
                ORDER BY created_at DESC
                """,
                (city,),
            ).fetchall()
            return JSONResponse({"city": city, "results": [dict(row) for row in rows]})
        finally:
            conn.close()

    @app.get("/api/picks")
    def api_picks() -> JSONResponse:
        conn = hs_db.connect()
        try:
            hs_db.init(conn)
            rows = conn.execute(
                """
                SELECT id, city, market_date, decision_hour_local, market_ticker, side,
                       model_prob, market_price_c, edge_after_fees, recommended_at,
                       outcome, pnl_c
                FROM picks
                ORDER BY id DESC
                LIMIT 100
                """
            ).fetchall()
            picks_list = [dict(row) for row in rows]

            record_row = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) AS losses,
                    SUM(COALESCE(pnl_c, 0)) AS total_pnl_c
                FROM picks
                WHERE outcome IS NOT NULL
                """
            ).fetchone()
            record = {
                "wins": record_row["wins"] or 0,
                "losses": record_row["losses"] or 0,
                "total_pnl_c": record_row["total_pnl_c"] or 0,
            }
            return JSONResponse({"picks": picks_list, "record": record})
        finally:
            conn.close()

    return app


app = create_app()
