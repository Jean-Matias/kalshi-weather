"""Kalshi trading fee calculation."""

import math


def kalshi_fee_cents(price_cents: int, contracts: int = 1) -> int:
    """Kalshi trading fee in integer cents.

    fee = ceil(0.07 * contracts * p * (1-p)) dollars, where p = price_cents/100,
    expressed in cents: ceil(7 * contracts * price_cents * (100 - price_cents) / 10000).
    """
    return math.ceil(7 * contracts * price_cents * (100 - price_cents) / 10000)
