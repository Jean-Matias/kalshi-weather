from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class PriceWindow:
    maxlen: int = 20
    prices: deque[float] = field(default_factory=deque)

    def add(self, price: float) -> None:
        if self.prices.maxlen != self.maxlen:
            self.prices = deque(self.prices, maxlen=self.maxlen)
        self.prices.append(price)

    def momentum_pct(self) -> float | None:
        if len(self.prices) < 2:
            return None
        first = self.prices[0]
        last = self.prices[-1]
        if first == 0:
            return None
        return ((last - first) / first) * 100


def dry_run_signal(momentum_pct: float | None) -> str:
    if momentum_pct is None:
        return "OBSERVE"
    if momentum_pct >= 0.35:
        return "MOMENTUM_UP"
    if momentum_pct <= -0.35:
        return "MOMENTUM_DOWN"
    return "FLAT"

