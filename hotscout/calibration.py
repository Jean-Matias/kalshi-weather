"""hotscout residual-distribution calibration.

Fits, per (city, decision_hour_local, month_center), the empirical
distribution of forecast error (residual = cli_high_f - forecast_high_f)
pooled over a +/-45 day window across years, plus an intraday blend_weight
that trades off the model distribution against the observed high-so-far.
Results are persisted to the residual_models table as JSON (ResidualDist,
frozen contract in hotscout/schema.py, with an extra "remaining_rise_f" key).
"""

import argparse
import datetime
import json

from hotscout import db
from hotscout.config import CITIES, DECISION_HOURS_LOCAL
from hotscout.model import bucket_probabilities

_BLEND_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
_WINDOW_DAYS = 45


def _day_of_year(date_str):
    _, m, d = (int(part) for part in date_str.split("-")[:3])
    # Project onto a fixed non-leap reference year so distances between
    # dates are comparable across years; clamp Feb 29 to Feb 28.
    if m == 2 and d == 29:
        d = 28
    return datetime.date(2001, m, d).timetuple().tm_yday


def _circular_day_distance(doy_a, doy_b, period=365):
    diff = abs(doy_a - doy_b)
    return min(diff, period - diff)


def _month_center_doy(month_center):
    return datetime.date(2001, month_center, 15).timetuple().tm_yday


def _in_month_window(date_str, month_center):
    doy = _day_of_year(date_str)
    return _circular_day_distance(doy, _month_center_doy(month_center)) <= _WINDOW_DAYS


def _select_forecast_by_date(conn, city, min_lead_days=0):
    """Map date -> forecast_high_f. Per date: smallest lead_days >=
    min_lead_days wins; within that lead, model='ncep_nbm_conus' is
    preferred over 'best_match'. The default (min_lead_days=0) reproduces
    the original lead-0 live behavior. A backtest that only allows itself
    forecasts issued before the decision hour passes min_lead_days=1 so the
    residuals are fit from the same forecast population it trades on."""
    rows = conn.execute(
        "SELECT date, model, lead_days, forecast_high_f FROM forecast_daily "
        "WHERE city=? AND lead_days>=? AND model IN ('ncep_nbm_conus', 'best_match')",
        (city, min_lead_days),
    ).fetchall()
    candidates = {}
    for row in rows:
        candidates.setdefault(row["date"], []).append(
            (row["lead_days"], row["model"] != "ncep_nbm_conus", row["forecast_high_f"])
        )
    return {date: min(rows_)[2] for date, rows_ in candidates.items()}


def _cli_by_date(conn, city):
    rows = conn.execute(
        "SELECT date, cli_high_f FROM cli_daily WHERE city=?", (city,)
    ).fetchall()
    return {row["date"]: row["cli_high_f"] for row in rows}


def _obs_by_date(conn, city):
    """Map date -> list of (local_hour, temp_f)."""
    rows = conn.execute(
        "SELECT date, ts_local, temp_f FROM obs_hourly WHERE city=?", (city,)
    ).fetchall()
    by_date = {}
    for row in rows:
        ts_local = row["ts_local"]
        try:
            hour = int(ts_local.split(" ")[1].split(":")[0])
        except (IndexError, ValueError):
            try:
                hour = int(ts_local.split("T")[1].split(":")[0])
            except (IndexError, ValueError):
                continue
        by_date.setdefault(row["date"], []).append((hour, row["temp_f"]))
    return by_date


def _brier_for_blend(blend_weight, residuals, train_records):
    total = 0.0
    for forecast_high_f, cli_high_f, obs_max in train_records:
        candidate_dist = {
            "residuals_f": residuals,
            "n": len(residuals),
            "blend_weight": blend_weight,
        }
        cli_int = round(cli_high_f)
        buckets = [
            {"ticker": "below", "label": "below", "low_f": None, "high_f": cli_int - 1},
            {"ticker": "exact", "label": "exact", "low_f": cli_int, "high_f": cli_int},
            {"ticker": "above", "label": "above", "low_f": cli_int + 1, "high_f": None},
        ]
        probs = bucket_probabilities(
            candidate_dist,
            forecast_high_f,
            buckets,
            high_so_far_f=obs_max,
            hours_to_peak=0,
        )
        prob_map = {p["ticker"]: p["prob"] for p in probs}
        total += (1.0 - prob_map["exact"]) ** 2
        total += prob_map["below"] ** 2
        total += prob_map["above"] ** 2
    return total / len(train_records)


def _choose_blend_weight(residuals, train_records):
    if not train_records:
        return 1.0
    split = int(len(train_records) * 0.7)
    if split < 1:
        split = len(train_records)
    train_split = train_records[:split]
    best_weight, best_brier = 1.0, None
    for weight in _BLEND_GRID:
        brier = _brier_for_blend(weight, residuals, train_split)
        if best_brier is None or brier < best_brier:
            best_brier = brier
            best_weight = weight
    return best_weight


def compute_residual_dist(forecast_by_date, cli_by_date, obs_by_date, decision_hour, month_center):
    """Fit a single ResidualDist (+ remaining_rise_f) for one (decision_hour,
    month_center) from date->value maps already restricted to whatever date
    range the caller wants pooled (e.g. all history for live use, or only
    train-window dates to avoid look-ahead in a backtest). Returns None if no
    dates fall in the +/-45 day window."""
    dates = sorted(
        d
        for d in forecast_by_date
        if d in cli_by_date and _in_month_window(d, month_center)
    )
    if not dates:
        return None

    residuals = [cli_by_date[d] - forecast_by_date[d] for d in dates]

    remaining_rise = []
    train_records = []
    for d in dates:
        obs_list = obs_by_date.get(d)
        if not obs_list:
            continue
        eligible = [temp for hour, temp in obs_list if hour <= decision_hour]
        if not eligible:
            continue
        obs_max = max(eligible)
        remaining_rise.append(cli_by_date[d] - obs_max)
        train_records.append((forecast_by_date[d], cli_by_date[d], obs_max))

    blend_weight = _choose_blend_weight(residuals, train_records)

    return {
        "residuals_f": residuals,
        "n": len(residuals),
        "blend_weight": blend_weight,
        "remaining_rise_f": remaining_rise,
    }


def load_date_maps(conn, city, min_lead_days=0):
    """Return (forecast_by_date, cli_by_date, obs_by_date) for `city`, the
    same per-date maps `fit()` pools from. Exposed so callers (e.g. the
    backtest) can restrict the date range themselves before fitting, to
    avoid pooling residuals from dates outside whatever window they intend
    to treat as "already known". min_lead_days=1 restricts forecasts to
    those issued at least a day ahead (see _select_forecast_by_date)."""
    return (
        _select_forecast_by_date(conn, city, min_lead_days=min_lead_days),
        _cli_by_date(conn, city),
        _obs_by_date(conn, city),
    )


def fit(conn, cities=None):
    """Fit residual distributions for every (city, decision_hour, month)
    and persist them to residual_models. Returns {city: n_residual_samples}."""
    cities = cities or CITIES
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sample_counts = {}

    for city in cities:
        forecast_by_date, cli_by_date, obs_by_date = load_date_maps(conn, city)
        city_total = 0

        for decision_hour in DECISION_HOURS_LOCAL:
            for month_center in range(1, 13):
                residual_dist = compute_residual_dist(
                    forecast_by_date, cli_by_date, obs_by_date, decision_hour, month_center
                )
                if residual_dist is None:
                    continue
                residuals = residual_dist["residuals_f"]

                conn.execute(
                    "INSERT INTO residual_models"
                    "(city, decision_hour_local, month_center, params_json, n_samples, fitted_at) "
                    "VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(city, decision_hour_local, month_center) DO UPDATE SET "
                    "params_json=excluded.params_json, n_samples=excluded.n_samples, "
                    "fitted_at=excluded.fitted_at",
                    (
                        city,
                        decision_hour,
                        month_center,
                        json.dumps(residual_dist),
                        len(residuals),
                        now,
                    ),
                )
                city_total += len(residuals)

        sample_counts[city] = city_total

    conn.commit()
    return sample_counts


def load_residual_dist(conn, city, decision_hour_local, month):
    """Load the fitted ResidualDist nearest to `month` for
    (city, decision_hour_local). Returns None if nothing is fitted."""
    rows = conn.execute(
        "SELECT month_center, params_json FROM residual_models "
        "WHERE city=? AND decision_hour_local=?",
        (city, decision_hour_local),
    ).fetchall()
    if not rows:
        return None

    target_doy = _month_center_doy(month)
    best_row = min(
        rows,
        key=lambda r: _circular_day_distance(_month_center_doy(r["month_center"]), target_doy),
    )
    return json.loads(best_row["params_json"])


def _main():
    parser = argparse.ArgumentParser(description="Fit hotscout residual distributions.")
    parser.add_argument("--all", action="store_true", help="Fit all configured cities.")
    parser.parse_args()

    conn = db.connect()
    try:
        db.init(conn)
        sample_counts = fit(conn)
        for city, n in sample_counts.items():
            print(f"{city}: {n} residual samples")
    finally:
        conn.close()


if __name__ == "__main__":
    _main()
