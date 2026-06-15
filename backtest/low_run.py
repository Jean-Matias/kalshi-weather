from __future__ import annotations

import argparse
from pathlib import Path

from backtest import low_data, low_strategies, low_weather
from backtest.low_engine import run_low_backtest
from backtest.low_report import render_low_backtest_report
from backtest.market_specs import low_market_spec


DEFAULT_REPORT_PATH = Path("reports") / "low-backtest.md"


def _parse_params(pairs: list[str]) -> dict:
    params = {}
    for pair in pairs:
        key, _, raw = pair.partition("=")
        if not key or not _:
            raise SystemExit(f"Invalid --param '{pair}'. Use key=value.")
        try:
            value: object = int(raw)
        except ValueError:
            try:
                value = float(raw)
            except ValueError:
                value = raw
        params[key] = value
    return params


def _build_strategy(name: str, params: dict):
    if name not in low_strategies.REGISTRY:
        raise SystemExit(f"Unknown strategy '{name}'. Options: {', '.join(sorted(low_strategies.REGISTRY))}")
    return low_strategies.REGISTRY[name](**params)


def run_city(
    city: str,
    *,
    days: int,
    target_events: int,
    strategy_name: str,
    params: dict,
    decision_hour: int,
    contracts: int,
    update_cache: bool,
) -> tuple[str, object]:
    spec = low_market_spec(city)
    did_update_market_cache = False
    if update_cache or not _cache_exists(city):
        low_data.ensure_cached(city, target_events=max(target_events, days))
        did_update_market_cache = True
    dataset = low_data.load_dataset(city, days=days)
    if dataset and (update_cache or did_update_market_cache or not _weather_cache_exists(spec, dataset)):
        low_weather.ensure_cached(spec, [entry["event"] for entry in dataset], sleep_seconds=0.1)
    strategy = _build_strategy(strategy_name, params)
    result = run_low_backtest(
        dataset,
        strategy,
        weather_loader=lambda event: low_weather.load_history_for_event(spec, event),
        contracts=contracts,
        label=f"{city} {strategy_name}@h{decision_hour}",
        decision_hour=decision_hour,
    )
    return city, result


def _cache_exists(city: str) -> bool:
    spec = low_market_spec(city)
    return (low_data.CACHE_ROOT / spec.series_ticker / "events.json").exists()


def _weather_cache_exists(spec, dataset) -> bool:
    if not dataset:
        return False
    sample = dataset[-1]["event"]
    needed = low_weather.event_dates([sample], lookback_days=1)
    return all((low_weather.CACHE_ROOT / spec.station_id / f"{date_str}.json").exists() for date_str in needed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run low-temperature Kalshi historical backtests.")
    parser.add_argument("--city", action="append", default=None, help="city to run; repeat for multiple cities")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--target-events", type=int, default=None)
    parser.add_argument("--strategy", default="low_persistence")
    parser.add_argument("--param", action="append", default=[], help="strategy parameter as key=value")
    parser.add_argument("--decision-hour", type=int, default=6)
    parser.add_argument("--contracts", type=int, default=3)
    parser.add_argument("--update-cache", action="store_true")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()

    params = _parse_params(args.param)
    cities = args.city or ["Las Vegas"]
    target_events = args.target_events if args.target_events is not None else args.days
    results = []
    for city in cities:
        _, result = run_city(
            city,
            days=args.days,
            target_events=target_events,
            strategy_name=args.strategy,
            params=params,
            decision_hour=args.decision_hour,
            contracts=args.contracts,
            update_cache=args.update_cache,
        )
        results.append(result)
        print(result.report.line())
        print(f"  skips={len(result.skipped)} worst_drawdown={result.worst_drawdown_cents:+d}c")

    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_low_backtest_report(results))
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
