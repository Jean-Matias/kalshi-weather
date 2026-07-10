"""hotscout picks bookkeeping: recording BUY recommendations and resolving
their outcomes once a market date has settled."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hotscout.fees import kalshi_fee_cents
from hotscout.live import nearest_decision_hour
from hotscout import config as hs_config


def record_from_board(conn, board: dict[str, Any]) -> int:
    """Insert a picks row for every BUY recommendation on the board. Skips
    (dedups) a city/market_date/market_ticker/side combination that already
    has a row. Returns the number of rows inserted."""
    inserted = 0
    now = datetime.now(timezone.utc).isoformat()
    for city_payload in board.get("cities", []):
        city = city_payload["city"]
        market_date = city_payload["market_date"]
        try:
            decision_hour_local = nearest_decision_hour(hs_config.city_config(city)["timezone"])
        except Exception:
            decision_hour_local = None
        for bucket in city_payload.get("buckets", []):
            recommendation = bucket.get("recommendation")
            if recommendation not in ("BUY YES", "BUY NO"):
                continue
            side = "yes" if recommendation == "BUY YES" else "no"
            ticker = bucket["ticker"]

            exists = conn.execute(
                """
                SELECT 1 FROM picks
                WHERE city = ? AND market_date = ? AND market_ticker = ? AND side = ?
                LIMIT 1
                """,
                (city, market_date, ticker, side),
            ).fetchone()
            if exists:
                continue

            if side == "yes":
                market_price_c = bucket.get("yes_ask_c")
            else:
                yes_bid_c = bucket.get("yes_bid_c")
                market_price_c = None if yes_bid_c is None else 100 - yes_bid_c

            conn.execute(
                """
                INSERT INTO picks(
                    city, market_date, decision_hour_local, market_ticker, side,
                    model_prob, market_price_c, edge_after_fees, recommended_at,
                    outcome, pnl_c
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    city,
                    market_date,
                    bucket.get("decision_hour_local", decision_hour_local),
                    ticker,
                    side,
                    bucket.get("model_prob"),
                    market_price_c,
                    bucket.get("edge_after_fees"),
                    now,
                ),
            )
            inserted += 1
    conn.commit()
    return inserted


def resolve_open(conn, today: str | None = None) -> int:
    """Resolve any open (outcome IS NULL) picks whose market_date has passed,
    by looking up the settlement in kalshi_events. Picks for a market_date
    with no matching kalshi_events row (settlement not recorded yet) are left
    open. Returns the number of picks resolved."""
    today = today or datetime.now(timezone.utc).date().isoformat()
    open_picks = conn.execute(
        """
        SELECT id, city, market_date, market_ticker, side, market_price_c
        FROM picks
        WHERE outcome IS NULL AND market_date < ?
        """,
        (today,),
    ).fetchall()

    resolved = 0
    for pick in open_picks:
        event_row = conn.execute(
            """
            SELECT settled_bucket_ticker FROM kalshi_events
            WHERE city = ? AND market_date = ?
            LIMIT 1
            """,
            (pick["city"], pick["market_date"]),
        ).fetchone()
        if event_row is None or event_row["settled_bucket_ticker"] is None:
            continue

        settled_ticker = event_row["settled_bucket_ticker"]
        picked_ticker_won = pick["market_ticker"] == settled_ticker
        won = picked_ticker_won if pick["side"] == "yes" else not picked_ticker_won

        entry_price_c = pick["market_price_c"] or 0
        fee = kalshi_fee_cents(entry_price_c)
        pnl_c = (100 - entry_price_c - fee) if won else -(entry_price_c + fee)

        conn.execute(
            "UPDATE picks SET outcome = ?, pnl_c = ? WHERE id = ?",
            ("win" if won else "loss", pnl_c, pick["id"]),
        )
        resolved += 1

    if resolved:
        conn.commit()
    return resolved
