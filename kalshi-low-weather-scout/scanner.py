from __future__ import annotations

import os
from datetime import datetime, timezone

from config import (
    CITY_CONFIGS,
    DATABASE_PATH,
    DATA_DIR,
    REPORT_PATH,
    REPORTS_DIR,
    SIGNALS_REPORT_PATH,
    TEMPERATURE_CONFIDENCE_REPORT_PATH,
    CITY_RELIABILITY_REPORT_PATH,
    DASHBOARD_REPORT_PATH,
)
from database import init_db, save_snapshot
from kalshi_api import (
    fetch_kalshi_api_observation,
    should_fetch_api_observation,
)
from kalshi_browser import fetch_kalshi_market
from report import (
    write_city_reliability_report,
    write_dashboard_report,
    write_report,
    write_signal_report,
    write_temperature_confidence_report,
)
from scoring import score_contract_signals, score_market
from weather_sources import fetch_weather


def _market_from_fastest_source(city_config: dict, weather: dict) -> dict:
    if not should_fetch_api_observation(weather):
        return fetch_kalshi_market(city_config)

    api_market = fetch_kalshi_api_observation(city_config)
    if api_market.get("market_data_source") == "kalshi_api":
        return api_market

    market = fetch_kalshi_market(city_config)
    market["api_observation_status"] = api_market.get("market_data_source")
    return market


def collect_city_set(
    city_configs: list[dict],
    conn,
    run_id: str,
    *,
    save_snapshots: bool,
    label: str,
) -> tuple[list[dict], list[dict]]:
    scored_rows = []
    all_signals = []

    print(f"Collecting {label} city set...")
    for city_config in city_configs:
        city = city_config["city"]
        print(f"Collecting {city}...")
        weather = fetch_weather(city_config)
        market = _market_from_fastest_source(city_config, weather)
        scored = score_market(city, weather, market)
        signals = score_contract_signals(city, weather, market)
        if save_snapshots:
            save_snapshot(conn, run_id, weather, market, scored)
        scored_rows.append(scored)
        all_signals.extend(signals)
        print(
            f"  {scored['final_label']}: edge {scored['estimated_edge_score']}/100, "
            f"weather confidence {scored['weather_confidence_score']}/100, "
            f"{len(signals)} side signals"
        )

    return scored_rows, all_signals


def _selected_city_configs(city_configs: list[dict]) -> list[dict]:
    selected = os.environ.get("KALSHI_CITIES")
    if not selected:
        return city_configs

    wanted = {_normalize_city_name(name) for name in selected.split(",") if name.strip()}
    if not wanted:
        return city_configs

    filtered = [
        config
        for config in city_configs
        if _normalize_city_name(config["city"]) in wanted
    ]
    found = {_normalize_city_name(config["city"]) for config in filtered}
    missing = sorted(wanted - found)
    if missing:
        print(f"Warning: KALSHI_CITIES did not match: {', '.join(missing)}")
    print(f"City filter active: {len(filtered)}/{len(city_configs)} cities")
    return filtered


def _default_city_configs(city_configs: list[dict]) -> list[dict]:
    if os.environ.get("KALSHI_CITIES"):
        return _selected_city_configs(city_configs)
    return city_configs


def _normalize_city_name(name: str) -> str:
    return name.strip().lower().replace(" ", "").replace("-", "")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    conn = init_db(DATABASE_PATH)

    market_dates = sorted({config.get("market_date", "unknown") for config in CITY_CONFIGS})
    print(f"Starting kalshi-low-weather-scout run {run_id}")
    print(f"Target Kalshi market date: {', '.join(market_dates)}")
    print("Set KALSHI_MARKET_DATE=YYYY-MM-DD when aiming at a specific low-temp market.")
    city_configs = _default_city_configs(CITY_CONFIGS)
    scored_rows, all_signals = collect_city_set(
        city_configs,
        conn,
        run_id,
        save_snapshots=True,
        label="target market date",
    )

    write_report(REPORT_PATH, scored_rows)
    write_signal_report(SIGNALS_REPORT_PATH, all_signals)
    write_temperature_confidence_report(TEMPERATURE_CONFIDENCE_REPORT_PATH, scored_rows)
    write_city_reliability_report(CITY_RELIABILITY_REPORT_PATH, scored_rows, all_signals)
    write_dashboard_report(DASHBOARD_REPORT_PATH, scored_rows, all_signals)
    conn.close()
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {SIGNALS_REPORT_PATH}")
    print(f"Wrote {TEMPERATURE_CONFIDENCE_REPORT_PATH}")
    print(f"Wrote {CITY_RELIABILITY_REPORT_PATH}")
    print(f"Wrote {DASHBOARD_REPORT_PATH}")
    print(f"Saved snapshots to {DATABASE_PATH}")


if __name__ == "__main__":
    main()
