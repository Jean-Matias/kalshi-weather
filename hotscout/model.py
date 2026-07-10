"""hotscout probability model.

bucket_probabilities() is the single function used by both the backtest
engine and the live dashboard to turn a fitted residual distribution into
per-bucket settlement probabilities. See hotscout/schema.py for the frozen
contracts this module implements.
"""

from hotscout.fees import kalshi_fee_cents

_INF = float("inf")


def _bucket_interval(bucket):
    """Return the (lo, hi) real-valued interval a bucket covers, expanding
    each inclusive integer-F bound by 0.5 to account for CLI rounding, and
    open-ended bounds to +/-inf."""
    low_f = bucket.get("low_f")
    high_f = bucket.get("high_f")
    lo = -_INF if low_f is None else low_f - 0.5
    hi = _INF if high_f is None else high_f + 0.5
    return lo, hi


def _overlap(sample, lo, hi):
    """Fraction (0..1) of the sample's [-0.5, +0.5) rounding window that
    falls inside [lo, hi)."""
    window_lo = sample - 0.5
    window_hi = sample + 0.5
    overlap = min(window_hi, hi) - max(window_lo, lo)
    if overlap < 0:
        return 0.0
    if overlap > 1:
        return 1.0
    return overlap


def bucket_probabilities(
    residual_dist,
    forecast_high_f,
    buckets,
    high_so_far_f=None,
    hours_to_peak=None,
):
    """Compute settlement probability per bucket.

    residual_dist: ResidualDist ({"residuals_f", "n", "blend_weight"}).
    forecast_high_f: point forecast for the day's high (deg F).
    buckets: list[Bucket].
    high_so_far_f: observed max temp so far today, if known.
    hours_to_peak: hours remaining until the climatological peak, if known.

    Returns list[{"ticker", "prob"}] with probs summing to 1.0.
    """
    residuals = residual_dist.get("residuals_f") or [0.0]
    samples = [forecast_high_f + r for r in residuals]

    if high_so_far_f is not None:
        samples = [max(s, high_so_far_f) for s in samples]

    weighted = [(s, 1.0) for s in samples]

    if (
        high_so_far_f is not None
        and hours_to_peak is not None
        and hours_to_peak <= 0
    ):
        blend_weight = residual_dist.get("blend_weight", 1.0)
        n = len(samples)
        weighted = [(s, blend_weight) for s in samples]
        weighted.append((high_so_far_f, (1.0 - blend_weight) * n))

    totals = []
    for bucket in buckets:
        lo, hi = _bucket_interval(bucket)
        mass = sum(weight * _overlap(sample, lo, hi) for sample, weight in weighted)
        totals.append(mass)

    total = sum(totals)
    if total <= 0:
        n = len(buckets)
        return [{"ticker": b["ticker"], "prob": 1.0 / n} for b in buckets]

    return [
        {"ticker": b["ticker"], "prob": mass / total}
        for b, mass in zip(buckets, totals)
    ]


def edge_after_fees(model_prob, yes_ask_c):
    """Edge of buying YES at yes_ask_c (integer cents) after fees, per the
    frozen decision rule: edge_yes = model_prob - (yes_ask_c + fee)/100."""
    fee = kalshi_fee_cents(yes_ask_c, 1)
    return model_prob - (yes_ask_c + fee) / 100.0
