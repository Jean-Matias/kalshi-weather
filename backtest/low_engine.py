from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from backtest.engine import FEE_CENTS_PER_CONTRACT, Report, Trade, _build_buckets


WeatherLoader = Callable[[dict[str, Any]], dict[str, dict[str, Any]]]


@dataclass
class LowBacktestResult:
    label: str
    report: Report
    total_event_days: int
    skipped: list[dict[str, Any]] = field(default_factory=list)
    city_results: dict[str, Report] = field(default_factory=dict)

    @property
    def worst_drawdown_cents(self) -> int:
        running = 0
        peak = 0
        worst = 0
        for trade in sorted(self.report.trades, key=lambda item: item.open_ts):
            running += trade.net_cents
            peak = max(peak, running)
            worst = min(worst, running - peak)
        return worst


def run_low_backtest(
    dataset: list[dict[str, Any]],
    strategy,
    *,
    weather_loader: WeatherLoader,
    contracts: int = 3,
    label: str = "low-strategy",
    decision_hour: int = 6,
) -> LowBacktestResult:
    report = Report(label=label)
    skipped: list[dict[str, Any]] = []
    city_results: dict[str, Report] = {}
    for entry in dataset:
        city = entry.get("city", "unknown")
        city_report = city_results.setdefault(city, Report(label=city))
        event = _event_for_decision(entry, decision_hour)
        buckets = _build_buckets(event, entry["bucket_candles"])
        if not buckets:
            skipped.append(_skip(entry, "no bucket candles"))
            continue
        max_idx = min(len(bucket["prices"]) for bucket in buckets) - 1
        if max_idx < 0:
            skipped.append(_skip(entry, "no usable prices"))
            continue
        idx = min(decision_hour, max_idx)
        if any(bucket["prices"][idx] is None for bucket in buckets):
            skipped.append(_skip(entry, "missing decision-hour price"))
            continue

        visible_buckets = [_truncate_bucket(bucket, idx) for bucket in buckets]
        decision = strategy(event, visible_buckets, weather_loader(event))
        if decision is None:
            skipped.append(_skip(entry, "strategy skipped"))
            continue
        if decision.get("skip_reason"):
            skipped.append(_skip(entry, decision["skip_reason"], features=decision.get("features")))
            continue

        trade = _score_trade(event, buckets, decision, idx, contracts)
        if trade is None:
            skipped.append(_skip(entry, "invalid strategy decision", features=decision.get("features")))
            continue
        report.trades.append(trade)
        city_report.trades.append(trade)

    return LowBacktestResult(
        label=label,
        report=report,
        total_event_days=len(dataset),
        skipped=skipped,
        city_results=city_results,
    )


def _truncate_bucket(bucket: dict[str, Any], idx: int) -> dict[str, Any]:
    copy = dict(bucket)
    copy["prices"] = list(bucket.get("prices", []))[: idx + 1]
    copy["bids"] = list(bucket.get("bids", []))[: idx + 1]
    return copy


def _event_for_decision(entry: dict[str, Any], decision_hour: int) -> dict[str, Any]:
    event = dict(entry["event"])
    event["decision_hour"] = decision_hour
    event["decision_ts"] = int(event["open_ts"]) + decision_hour * 3600
    spec = entry.get("spec")
    timezone = getattr(spec, "timezone", None)
    if timezone:
        event["decision_local_iso"] = (
            datetime.fromtimestamp(event["decision_ts"], ZoneInfo(timezone))
            .replace(tzinfo=None)
            .isoformat(timespec="minutes")
        )
    return event


def _score_trade(
    event: dict[str, Any],
    buckets: list[dict[str, Any]],
    decision: dict[str, Any],
    idx: int,
    contracts: int,
) -> Trade | None:
    side = decision.get("side")
    bucket_ticker = decision.get("bucket")
    bucket = next((candidate for candidate in buckets if candidate["ticker"] == bucket_ticker), None)
    if side not in {"yes", "no"} or bucket is None:
        return None
    market_price = bucket["prices"][idx]
    if market_price is None:
        return None
    exec_price = decision.get("limit_price")
    if exec_price is None:
        exec_price = int(market_price) if side == "yes" else 100 - int(market_price)
    exec_price = max(1, min(99, int(exec_price)))

    bucket_is_yes = bucket["result"] == "yes"
    won = bucket_is_yes if side == "yes" else not bucket_is_yes
    gross = (100 - exec_price) * contracts if won else -exec_price * contracts
    net = gross - int(FEE_CENTS_PER_CONTRACT * contracts)
    return Trade(
        event_ticker=event["event_ticker"],
        open_ts=event["open_ts"],
        bucket=bucket_ticker,
        side=side,
        limit_price=exec_price,
        won=won,
        net_cents=net,
    )


def _skip(entry: dict[str, Any], reason: str, *, features: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "city": entry.get("city", "unknown"),
        "event_ticker": (entry.get("event") or {}).get("event_ticker"),
        "reason": reason,
        "features": features or {},
    }
