"""Replay engine for KXHIGHTLV (multi-bucket daily-high-temperature) markets.

Each event-day has several mutually exclusive "bucket" markets (e.g. "96-97F",
"98-99F", "100F or above" ...). Exactly one settles "yes". A strategy looks at
the bucket prices at a chosen decision point and may buy YES on one bucket
(betting that's the day's actual high) or NO on one bucket (betting it's NOT),
or skip the day entirely.

A strategy is any callable with signature:

    strategy(event: dict, buckets: list[dict], hour_idx: int) -> dict | None

- `event`: {"event_ticker", "open_ts", "close_ts", "buckets": [...]}
- `buckets`: list of {"ticker", "label", "result", "prices": [...]}, where
  `prices[i]` is the yes_ask close price in cents for hour `i` (chronological,
  hour 0 = market open). Strategies must only look at `prices[0..hour_idx]`.
- `hour_idx`: index of the decision point (hours since open).

Return `None` to skip, or `{"side": "yes"|"no", "bucket": <ticker>,
"limit_price": <cents>}`.

P&L: win -> gross = (100 - limit_price) * contracts; loss -> gross =
-limit_price * contracts; net = gross - 1.5c/contract fee (mirrors the BTC
bot's fee-aware accounting in bot/backtest/engine.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

FEE_CENTS_PER_CONTRACT = 1.5

Strategy = Callable[[dict, list[dict], int], Optional[dict]]

FeeFn = Callable[[int, int], float]


def _flat_fee(_price_cents: int, contracts: int) -> float:
    """Default fee model: flat FEE_CENTS_PER_CONTRACT/contract (existing
    behavior — known to not match Kalshi's actual price-dependent fee
    schedule; kept as the default only so existing callers are unaffected).
    Reads the module-level constant at call time so monkeypatching it in
    tests still works."""
    return FEE_CENTS_PER_CONTRACT * contracts


@dataclass
class Trade:
    event_ticker: str
    open_ts: int
    bucket: str
    side: str
    limit_price: int
    won: bool
    net_cents: int


@dataclass
class Report:
    label: str
    trades: list[Trade] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        return 100 * sum(1 for t in self.trades if t.won) / len(self.trades)

    @property
    def total_net_cents(self) -> int:
        return sum(t.net_cents for t in self.trades)

    @property
    def ev_per_trade(self) -> float:
        if not self.trades:
            return 0.0
        return self.total_net_cents / len(self.trades)

    @property
    def avg_win(self) -> float:
        wins = [t.net_cents for t in self.trades if t.won]
        return sum(wins) / len(wins) if wins else 0.0

    @property
    def avg_loss(self) -> float:
        losses = [t.net_cents for t in self.trades if not t.won]
        return sum(losses) / len(losses) if losses else 0.0

    def line(self) -> str:
        if not self.trades:
            return f"{self.label}: no trades"
        return (
            f"{self.label}: n={self.n} win_rate={self.win_rate:.1f}% "
            f"avg_win={self.avg_win:+.2f}c avg_loss={self.avg_loss:+.2f}c "
            f"EV/trade={self.ev_per_trade:+.2f}c "
            f"total_net={self.total_net_cents:+d}c (${self.total_net_cents / 100:+.2f})"
        )


def _hourly_prices(candles: list[dict]) -> list[Optional[int]]:
    """Per-hour yes_ask close price in cents (None where missing), in
    chronological order (index 0 = first cached hour after market open)."""
    rows = sorted(candles, key=lambda c: c.get("end_period_ts") or 0)
    out = []
    for c in rows:
        ya = (c.get("yes_ask") or {}).get("close_dollars")
        out.append(round(float(ya) * 100) if ya is not None else None)
    return out


def _hourly_bids(candles: list[dict]) -> list[Optional[int]]:
    """Per-hour yes_bid close price in cents — what you'd actually receive
    selling YES back into the market before settlement (round-trip exits)."""
    rows = sorted(candles, key=lambda c: c.get("end_period_ts") or 0)
    out = []
    for c in rows:
        yb = (c.get("yes_bid") or {}).get("close_dollars")
        out.append(round(float(yb) * 100) if yb is not None else None)
    return out


def _build_buckets(event: dict, bucket_candles: dict[str, list[dict]]) -> list[dict]:
    buckets = []
    for b in event["buckets"]:
        candles = bucket_candles.get(b["ticker"])
        if not candles:
            continue
        buckets.append({
            "ticker": b["ticker"],
            "label": b["label"],
            "result": b["result"],
            "prices": _hourly_prices(candles),
            "bids": _hourly_bids(candles),
        })
    return buckets


def run(
    dataset: list[dict],
    strategy: Strategy,
    contracts: int = 3,
    label: str = "strategy",
    decision_hour: int = 24,
    fee_fn: Optional[FeeFn] = None,
) -> Report:
    """Replay `strategy` over `dataset` (from data.load_dataset()).

    `decision_hour`: hours after event open at which the strategy is asked to
    decide (clamped to the shortest bucket's available history per event).
    Markets/days are skipped when there's no usable price data at that hour
    or the strategy declines (`returns None`).

    `fee_fn(limit_price_cents, contracts) -> cents`: pluggable per-trade fee
    model. Defaults to the flat FEE_CENTS_PER_CONTRACT/contract behavior so
    existing callers are unaffected; pass a real fee schedule (e.g.
    hotscout.fees.kalshi_fee_cents) for callers that need it.
    """
    fee_fn = fee_fn or _flat_fee
    report = Report(label=label)
    for entry in dataset:
        event = entry["event"]
        buckets = _build_buckets(event, entry["bucket_candles"])
        if not buckets:
            continue
        max_idx = min(len(b["prices"]) for b in buckets) - 1
        if max_idx < 0:
            continue
        idx = min(decision_hour, max_idx)
        if any(b["prices"][idx] is None for b in buckets):
            continue

        decision = strategy(event, buckets, idx)
        if decision is None:
            continue

        side = decision["side"]
        bucket_ticker = decision["bucket"]
        limit_price = max(1, min(99, int(decision["limit_price"])))
        bucket = next((b for b in buckets if b["ticker"] == bucket_ticker), None)
        if bucket is None:
            continue
        bucket_is_yes = bucket["result"] == "yes"
        won = bucket_is_yes if side == "yes" else not bucket_is_yes
        if won:
            gross = (100 - limit_price) * contracts
        else:
            gross = -limit_price * contracts
        net = gross - int(fee_fn(limit_price, contracts))

        report.trades.append(Trade(
            event_ticker=event["event_ticker"],
            open_ts=event["open_ts"],
            bucket=bucket_ticker,
            side=side,
            limit_price=limit_price,
            won=won,
            net_cents=net,
        ))
    return report


FlipStrategy = Callable[[dict, list[dict], int], Optional[dict]]


def run_flip(
    dataset: list[dict],
    strategy: FlipStrategy,
    contracts: int = 3,
    label: str = "flip-strategy",
    earliest_hour: int = 1,
    latest_hour: int = 30,
    max_hold_hours: int = 12,
) -> Report:
    """Replay a "buy low, sell before settlement" round-trip strategy.

    Unlike `run()` (hold-to-resolution, single transaction fee), this models
    TWO transactions — entry (buy YES at the ask) and exit (sell YES at the
    bid, before the market closes) — so it charges fees on both legs and
    scores P&L from the realized price move, not the settlement outcome
    (unless no exit triggers, in which case it falls back to settlement).

    `strategy(event, buckets, hour_idx) -> dict | None` is asked at every hour
    from `earliest_hour` to `latest_hour`. It should look only at
    `prices[0..hour_idx]` / `bids[0..hour_idx]` and return `None` to keep
    waiting, or an entry decision:

        {"side": "yes", "bucket": <ticker>, "entry_price": <cents>,
         "take_profit": <cents>, "stop_loss": <cents>}

    `entry_price` is paid at `hour_idx` (yes_ask). From `hour_idx + 1` onward
    the engine watches that bucket's yes_bid each hour: the first hour where
    bid >= take_profit or bid <= stop_loss, it exits at that bid. If neither
    triggers within `max_hold_hours` hours (or before the data/market ends),
    it holds to settlement and scores a normal win/loss payout instead.

    Only "yes"-side round trips are modeled (selling NO back is structurally
    symmetric but Kalshi's NO book is thinner / less reliably quoted in our
    cached candles).
    """
    report = Report(label=label)
    for entry in dataset:
        event = entry["event"]
        buckets = _build_buckets(event, entry["bucket_candles"])
        if not buckets:
            continue
        max_idx = min(len(b["prices"]) for b in buckets) - 1
        if max_idx < 1:
            continue

        decision = None
        entry_idx = None
        for idx in range(earliest_hour, min(latest_hour, max_idx) + 1):
            if any(b["prices"][idx] is None for b in buckets):
                continue
            candidate = strategy(event, buckets, idx)
            if candidate is not None:
                decision = candidate
                entry_idx = idx
                break
        if decision is None:
            continue

        bucket_ticker = decision["bucket"]
        bucket = next((b for b in buckets if b["ticker"] == bucket_ticker), None)
        if bucket is None:
            continue
        entry_price = max(1, min(99, int(decision["entry_price"])))
        take_profit = int(decision["take_profit"])
        stop_loss = int(decision["stop_loss"])

        exit_price = None
        for h in range(entry_idx + 1, min(entry_idx + max_hold_hours, max_idx) + 1):
            bid = bucket["bids"][h]
            if bid is None:
                continue
            if bid >= take_profit or bid <= stop_loss:
                exit_price = bid
                break

        if exit_price is not None:
            gross = (exit_price - entry_price) * contracts
            net = gross - int(2 * FEE_CENTS_PER_CONTRACT * contracts)
            won = gross > 0
        else:
            bucket_is_yes = bucket["result"] == "yes"
            won = bucket_is_yes
            if won:
                gross = (100 - entry_price) * contracts
            else:
                gross = -entry_price * contracts
            net = gross - int(FEE_CENTS_PER_CONTRACT * contracts)

        report.trades.append(Trade(
            event_ticker=event["event_ticker"],
            open_ts=event["open_ts"],
            bucket=bucket_ticker,
            side="yes",
            limit_price=entry_price,
            won=won,
            net_cents=net,
        ))
    return report


def split_chronological(report: Report) -> tuple[Report, Report]:
    """Split a report's trades in half by open_ts — checks whether an edge is
    stable over time or just a lucky streak in one window."""
    trades_sorted = sorted(report.trades, key=lambda t: t.open_ts)
    mid = len(trades_sorted) // 2
    older = Report(label=f"{report.label} (older half)", trades=trades_sorted[:mid])
    newer = Report(label=f"{report.label} (newer half)", trades=trades_sorted[mid:])
    return older, newer
