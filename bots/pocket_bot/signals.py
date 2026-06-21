from __future__ import annotations


def rsi(closes: list[float], period: int) -> float:
    if len(closes) < period + 1:
        raise ValueError(f"need at least {period + 1} closes, got {len(closes)}")
    diffs = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    window = diffs[-period:]
    gains = [d for d in window if d > 0]
    losses = [-d for d in window if d < 0]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def signal(rsi_value: float, overbought: float, oversold: float) -> str | None:
    if rsi_value >= overbought:
        return "put"
    if rsi_value <= oversold:
        return "call"
    return None
