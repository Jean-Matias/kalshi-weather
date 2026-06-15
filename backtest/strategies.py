"""Pluggable entry strategies for the KXHIGHTLV multi-bucket backtest engine.

Each strategy is a factory returning:
    (event, buckets, hour_idx) -> {"side", "bucket", "limit_price"} | None

`buckets` = [{"ticker", "label", "result", "prices": [...]}, ...] sorted by
the order Kalshi returns them (roughly low-to-high temperature range).
`prices[hour_idx]` = yes_ask close price in cents at the decision point.
"""
from __future__ import annotations


def _favorite(buckets, idx):
    scored = [(b, b["prices"][idx]) for b in buckets if b["prices"][idx] is not None]
    if not scored:
        return None
    return max(scored, key=lambda bp: bp[1])


def buy_favorite(min_price: int = 50, max_price: int = 90):
    """Buy YES on whichever bucket the market currently favors most, as long
    as its price sits in [min_price, max_price] — skip if the favorite is too
    uncertain (cheap, < min_price) or already priced as a near-lock (> max_price,
    thin payout margin)."""
    def strategy(event, buckets, idx):
        fav = _favorite(buckets, idx)
        if fav is None:
            return None
        bucket, price = fav
        if min_price <= price <= max_price:
            return {"side": "yes", "bucket": bucket["ticker"], "limit_price": price}
        return None
    return strategy


def fade_tails(max_no_price: int = 12):
    """Buy NO on the two extreme "tail" buckets (lowest temperature range and
    highest), betting the actual high won't land in the rare extremes —
    cheap longshot tails are often roughly fairly priced or slightly
    over-priced relative to true frequency. Only take the NO bet when it's
    cheap (the YES side is already a longshot, e.g. <= max_no_price cents,
    so the NO costs >= 100 - max_no_price, i.e. NO is the favorite already —
    we just want to make sure we're not overpaying for a "sure thing")."""
    def strategy(event, buckets, idx):
        if len(buckets) < 2:
            return None
        # tails = first and last bucket as Kalshi orders them (low/high range ends)
        for tail in (buckets[0], buckets[-1]):
            price = tail["prices"][idx]
            if price is None:
                continue
            if price <= max_no_price:
                no_price = 100 - price
                return {"side": "no", "bucket": tail["ticker"], "limit_price": no_price}
        return None
    return strategy


def favorite_with_margin(max_entry_price: int = 80, min_price: int = 45):
    """Like buy_favorite, but only take entries that leave at least
    `100 - max_entry_price` cents of payout margin — skips the thin 85-99c
    "sure thing" entries where a rare miss wipes out many wins' worth of edge."""
    def strategy(event, buckets, idx):
        fav = _favorite(buckets, idx)
        if fav is None:
            return None
        bucket, price = fav
        if min_price <= price <= max_entry_price:
            return {"side": "yes", "bucket": bucket["ticker"], "limit_price": price}
        return None
    return strategy


def top2_cheaper(min_price: int = 35, max_price: int = 70):
    """Instead of always backing the single favorite (which the market prices
    richly), back whichever of the top-2 most-favored buckets is *cheaper* —
    a bet that the market's top-2 split is roughly right but slightly
    mispriced toward the favorite, so the second-favorite offers better
    risk/reward for similar true odds."""
    def strategy(event, buckets, idx):
        scored = [(b, b["prices"][idx]) for b in buckets if b["prices"][idx] is not None]
        if len(scored) < 2:
            return None
        scored.sort(key=lambda bp: bp[1], reverse=True)
        _, second_price = scored[1]
        bucket, price = scored[1]
        if min_price <= price <= max_price:
            return {"side": "yes", "bucket": bucket["ticker"], "limit_price": price}
        return None
    return strategy


def momentum_favorite(lookback_hours: int = 6, min_move_cents: float = 5.0, min_price: int = 45, max_price: int = 88):
    """Track whichever bucket is currently favored, but only back it if its
    price has been *climbing* over the last `lookback_hours` (the market is
    converging toward it, not just momentarily ahead) — analogous to
    trend_following in the BTC backtest."""
    def strategy(event, buckets, idx):
        fav = _favorite(buckets, idx)
        if fav is None:
            return None
        bucket, price = fav
        if not (min_price <= price <= max_price):
            return None
        start = max(0, idx - lookback_hours)
        window = [p for p in bucket["prices"][start:idx + 1] if p is not None]
        if len(window) < 2:
            return None
        if window[-1] - window[0] < min_move_cents:
            return None
        return {"side": "yes", "bucket": bucket["ticker"], "limit_price": price}
    return strategy


def momentum_flip(
    lookback_hours: int = 4,
    min_move_cents: float = 6.0,
    min_entry: int = 30,
    max_entry: int = 75,
    profit_target_cents: int = 8,
    stop_loss_cents: int = 10,
):
    """Round-trip ("buy low, cash out before settlement") candidate: enter
    YES on whichever bucket is climbing fastest (price has risen at least
    `min_move_cents` over the last `lookback_hours`), as long as it's still
    mid-priced (not already a near-lock or a longshot). Plan to exit early —
    take profit once the bid has risen `profit_target_cents` above entry, or
    cut losses if it falls `stop_loss_cents` below entry — rather than
    holding to settlement."""
    def strategy(event, buckets, idx):
        if idx < lookback_hours:
            return None
        best = None
        for b in buckets:
            price = b["prices"][idx]
            if price is None or not (min_entry <= price <= max_entry):
                continue
            start = idx - lookback_hours
            window = [p for p in b["prices"][start:idx + 1] if p is not None]
            if len(window) < 2:
                continue
            move = window[-1] - window[0]
            if move < min_move_cents:
                continue
            if best is None or move > best[1]:
                best = (b, move, price)
        if best is None:
            return None
        bucket, _move, price = best
        return {
            "side": "yes",
            "bucket": bucket["ticker"],
            "entry_price": price,
            "take_profit": price + profit_target_cents,
            "stop_loss": price - stop_loss_cents,
        }
    return strategy


def quick_scalp(
    min_entry: int = 40,
    max_entry: int = 65,
    profit_target_cents: int = 5,
    stop_loss_cents: int = 6,
):
    """Simplest possible flip candidate: as soon as the current favorite's
    price first lands in a mid-range band [min_entry, max_entry], buy it and
    plan a small, fast scalp — exit on a `profit_target_cents` gain or a
    `stop_loss_cents` loss, whichever the bid hits first. No momentum filter;
    tests whether *any* round-trip edge exists from simply buying mid-priced
    favorites early and not holding to resolution."""
    def strategy(event, buckets, idx):
        scored = [(b, b["prices"][idx]) for b in buckets if b["prices"][idx] is not None]
        if not scored:
            return None
        bucket, price = max(scored, key=lambda bp: bp[1])
        if not (min_entry <= price <= max_entry):
            return None
        return {
            "side": "yes",
            "bucket": bucket["ticker"],
            "entry_price": price,
            "take_profit": price + profit_target_cents,
            "stop_loss": price - stop_loss_cents,
        }
    return strategy


REGISTRY = {
    "buy_favorite": buy_favorite,
    "fade_tails": fade_tails,
    "favorite_with_margin": favorite_with_margin,
    "top2_cheaper": top2_cheaper,
    "momentum_favorite": momentum_favorite,
}

FLIP_REGISTRY = {
    "momentum_flip": momentum_flip,
    "quick_scalp": quick_scalp,
}
