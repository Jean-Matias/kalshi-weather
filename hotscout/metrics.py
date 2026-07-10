"""Backtest performance metrics for hotscout.

All functions are pure and take plain trade dicts / (prob, outcome) pairs so
they're trivial to unit test without a database.
"""

from __future__ import annotations


def win_rate(trades: list[dict]) -> float:
    """Fraction of trades where `won` is truthy. 0.0 if there are no trades."""
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.get("won"))
    return wins / len(trades)


def roi(trades: list[dict]) -> float:
    """Net pnl (cents) / total capital at risk (cents, i.e. sum of entry
    prices — the max a single 1-contract trade can lose). 0.0 if there are
    no trades or nothing was risked."""
    if not trades:
        return 0.0
    total_risk = sum(t["entry_price_c"] for t in trades)
    if total_risk <= 0:
        return 0.0
    net = sum(t["pnl_c"] for t in trades)
    return net / total_risk


def brier(pairs: list[tuple[float, float]]) -> float:
    """Mean squared error between predicted probability and realized
    0/1 outcome. 0.0 if `pairs` is empty."""
    if not pairs:
        return 0.0
    return sum((p - o) ** 2 for p, o in pairs) / len(pairs)


def calibration_bins(pairs: list[tuple[float, float]], n_bins: int = 10) -> list[dict]:
    """Bucket (predicted_prob, outcome01) pairs into `n_bins` equal-width
    probability bins in [0, 1]. Returns all `n_bins` bins (even empty ones)
    as {"bin_lo", "bin_hi", "count", "avg_predicted", "realized_freq"},
    with avg_predicted/realized_freq set to None for empty bins."""
    width = 1.0 / n_bins
    buckets: list[list[tuple[float, float]]] = [[] for _ in range(n_bins)]
    for p, o in pairs:
        idx = int(p / width)
        if idx < 0:
            idx = 0
        if idx >= n_bins:
            idx = n_bins - 1
        buckets[idx].append((p, o))

    bins = []
    for i in range(n_bins):
        items = buckets[i]
        if items:
            avg_predicted = sum(p for p, _ in items) / len(items)
            realized_freq = sum(o for _, o in items) / len(items)
        else:
            avg_predicted = None
            realized_freq = None
        bins.append({
            "bin_lo": i * width,
            "bin_hi": (i + 1) * width,
            "count": len(items),
            "avg_predicted": avg_predicted,
            "realized_freq": realized_freq,
        })
    return bins
