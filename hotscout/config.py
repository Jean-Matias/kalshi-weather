"""hotscout configuration.

Reuses city metadata (station, lat/lon, timezone, CLI product/site, Kalshi
event ticker prefix) from the root ``config.py``'s ``CITY_CONFIGS`` — nothing
here duplicates those values.
"""

from pathlib import Path

import config as root_config

CITIES = ["Las Vegas"]

SERIES_BY_CITY = {
    "Las Vegas": "KXHIGHTLV",
}

DECISION_HOURS_LOCAL = (9, 11, 13)

EDGE_THRESHOLD_DEFAULT = 0.05

MIN_VALIDATION_TRADES = 30

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "hotscout.sqlite3"

_CITY_CONFIGS_BY_NAME = {c["city"]: c for c in root_config.CITY_CONFIGS}


def city_config(name):
    """Return the root config.py CITY_CONFIGS entry for a hotscout city."""
    return _CITY_CONFIGS_BY_NAME[name]
