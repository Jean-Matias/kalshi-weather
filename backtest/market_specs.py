from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
LOW_CONFIG_PATH = REPO_ROOT / "kalshi-low-weather-scout" / "config.py"
_DATE_SUFFIX_RE = re.compile(r"-\d{2}[A-Z]{3}\d{2}$")


@dataclass(frozen=True)
class MarketSpec:
    market_type: str
    city: str
    state: str
    station_id: str
    station_name: str
    latitude: float
    longitude: float
    timezone: str
    series_ticker: str
    event_ticker_template: str
    cli_product: str
    cli_site: str
    cli_issuedby: str
    official_location: str


def load_low_market_specs(config_path: Path = LOW_CONFIG_PATH) -> list[MarketSpec]:
    module = _load_module(config_path)
    specs = [_spec_from_low_config(config) for config in module.CITY_CONFIGS]
    specs.sort(key=lambda spec: spec.city)
    return specs


def low_market_spec(city: str, config_path: Path = LOW_CONFIG_PATH) -> MarketSpec:
    normalized = city.casefold()
    for spec in load_low_market_specs(config_path):
        if spec.city.casefold() == normalized:
            return spec
    available = ", ".join(spec.city for spec in load_low_market_specs(config_path))
    raise ValueError(f"Unknown low-weather city '{city}'. Available: {available}")


def series_ticker_from_event(event_ticker: str) -> str:
    return _DATE_SUFFIX_RE.sub("", event_ticker)


def _load_module(config_path: Path):
    if not config_path.exists():
        raise FileNotFoundError(f"Low-weather config not found: {config_path}")
    spec = importlib.util.spec_from_file_location("kalshi_low_weather_config_for_backtest", config_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load low-weather config: {config_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _spec_from_low_config(config: dict[str, Any]) -> MarketSpec:
    event_ticker = str(config["kalshi_event_ticker"])
    return MarketSpec(
        market_type="low",
        city=str(config["city"]),
        state=str(config["state"]),
        station_id=str(config["station_id"]),
        station_name=str(config["station_name"]),
        latitude=float(config["latitude"]),
        longitude=float(config["longitude"]),
        timezone=str(config["timezone"]),
        series_ticker=series_ticker_from_event(event_ticker),
        event_ticker_template=event_ticker,
        cli_product=str(config["official_climate_product"]),
        cli_site=str(config["cli_site"]),
        cli_issuedby=str(config["cli_issuedby"]),
        official_location=str(config["official_location"]),
    )
