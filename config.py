import os
import re
from copy import deepcopy
from datetime import timedelta
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_NAME = "kalshi-weather-scout"
DATA_DIR = Path("data")
REPORTS_DIR = Path("reports")
DATABASE_PATH = DATA_DIR / "snapshots.sqlite3"
REPORT_PATH = REPORTS_DIR / "today.md"
SIGNALS_REPORT_PATH = REPORTS_DIR / "signals.md"
TEMPERATURE_CONFIDENCE_REPORT_PATH = REPORTS_DIR / "temperature-confidence.md"
CITY_RELIABILITY_REPORT_PATH = REPORTS_DIR / "city-reliability.md"
DASHBOARD_REPORT_PATH = REPORTS_DIR / "dashboard.html"

USER_AGENT = (
    "kalshi-weather-scout/0.1 "
    "(research-only weather market scanner; contact: local-user)"
)

PLAYWRIGHT_TIMEOUT_MS = 15_000


def city(
    name,
    state,
    station_id,
    station_name,
    latitude,
    longitude,
    timezone,
    threshold_f,
    kalshi_url,
    event_ticker,
    cli_product,
    cli_site,
    cli_issuedby,
    official_location,
    coastal_risk=False,
):
    market_date = _market_date_for_timezone(timezone)
    kalshi_url = _with_market_date_suffix(kalshi_url, market_date, uppercase=False)
    event_ticker = _with_market_date_suffix(event_ticker, market_date, uppercase=True)
    return {
        "city": name,
        "state": state,
        "station_id": station_id,
        "station_name": station_name,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone,
        "threshold_f": threshold_f,
        "market_date": market_date,
        "contract_side": "range",
        "coastal_risk": coastal_risk,
        "kalshi_url": kalshi_url,
        "kalshi_event_ticker": event_ticker,
        "official_climate_product": cli_product,
        "cli_site": cli_site,
        "cli_issuedby": cli_issuedby,
        "official_source_url": (
            "https://forecast.weather.gov/product.php?"
            f"site={cli_site}&product=CLI&issuedby={cli_issuedby}&format=TXT"
        ),
        "official_location": official_location,
        "notes": (
            "Kalshi rules say the official outcome is the NWS Climatological "
            f"Report Daily for {official_location}."
        ),
    }

def _market_date_for_timezone(timezone: str) -> str:
    override = os.environ.get("KALSHI_MARKET_DATE")
    if override:
        return override
    return datetime.now(ZoneInfo(timezone)).date().isoformat()

def _with_market_date_suffix(value: str, market_date: str, uppercase: bool) -> str:
    suffix = _kalshi_date_suffix(market_date)
    if uppercase:
        suffix = suffix.upper()
    return re.sub(r"-\d{2}[A-Za-z]{3}\d{2}$", f"-{suffix}", value)

def _kalshi_date_suffix(market_date: str) -> str:
    date = datetime.fromisoformat(market_date)
    return date.strftime("%y%b%d").lower()

def city_configs_for_date(market_date: str):
    configs = deepcopy(CITY_CONFIGS)
    for config in configs:
        config["market_date"] = market_date
        config["kalshi_url"] = _with_market_date_suffix(config["kalshi_url"], market_date, uppercase=False)
        config["kalshi_event_ticker"] = _with_market_date_suffix(
            config["kalshi_event_ticker"],
            market_date,
            uppercase=True,
        )
    return configs

def next_market_date() -> str:
    base = datetime.fromisoformat(_market_date_for_timezone("America/New_York")).date()
    return (base + timedelta(days=1)).isoformat()


CITY_CONFIGS = [
    city(
        "Los Angeles",
        "CA",
        "KLAX",
        "Los Angeles International Airport",
        33.9425,
        -118.4081,
        "America/Los_Angeles",
        69.0,
        "https://kalshi.com/markets/kxhighlax/highest-temperature-in-los-angeles/kxhighlax-26may24",
        "KXHIGHLAX-26MAY24",
        "CLILAX",
        "LOX",
        "LAX",
        "Los Angeles Airport, CA",
        coastal_risk=True,
    ),
    city(
        "Chicago",
        "IL",
        "KMDW",
        "Chicago Midway International Airport",
        41.7868,
        -87.7522,
        "America/Chicago",
        77.0,
        "https://kalshi.com/markets/kxhighchi/highest-temperature-in-chicago/kxhighchi-26may24",
        "KXHIGHCHI-26MAY24",
        "CLIMDW",
        "LOT",
        "MDW",
        "Chicago Midway, IL",
    ),
    city(
        "NYC",
        "NY",
        "KNYC",
        "Central Park",
        40.7794,
        -73.9692,
        "America/New_York",
        59.0,
        "https://kalshi.com/markets/kxhighny/highest-temperature-in-nyc/kxhighny-26may24",
        "KXHIGHNY-26MAY24",
        "CLINYC",
        "OKX",
        "NYC",
        "Central Park, New York",
    ),
    city(
        "Miami",
        "FL",
        "KMIA",
        "Miami International Airport",
        25.7959,
        -80.2870,
        "America/New_York",
        90.0,
        "https://kalshi.com/markets/kxhighmia/highest-temperature-in-miami/kxhighmia-26may24",
        "KXHIGHMIA-26MAY24",
        "CLIMIA",
        "MFL",
        "MIA",
        "Miami International Airport",
        coastal_risk=True,
    ),
    city(
        "Atlanta",
        "GA",
        "KATL",
        "Atlanta Hartsfield-Jackson International Airport",
        33.6367,
        -84.4281,
        "America/New_York",
        81.0,
        "https://kalshi.com/markets/kxhightatl/atlanta-max-temperature/kxhightatl-26may24",
        "KXHIGHTATL-26MAY24",
        "CLIATL",
        "FFC",
        "ATL",
        "Atlanta, GA",
    ),
    city(
        "Phoenix",
        "AZ",
        "KPHX",
        "Phoenix Sky Harbor International Airport",
        33.4342,
        -112.0116,
        "America/Phoenix",
        100.0,
        "https://kalshi.com/markets/kxhightphx/phoenix-high-temperature-daily/kxhightphx-26may24",
        "KXHIGHTPHX-26MAY24",
        "CLIPHX",
        "PSR",
        "PHX",
        "Phoenix, AZ",
    ),
    city(
        "Boston",
        "MA",
        "KBOS",
        "Boston Logan International Airport",
        42.3656,
        -71.0096,
        "America/New_York",
        56.0,
        "https://kalshi.com/markets/kxhightbos/boston-maximum-daily-temperature/kxhightbos-26may24",
        "KXHIGHTBOS-26MAY24",
        "CLIBOS",
        "BOX",
        "BOS",
        "Boston (Logan Airport), MA",
        coastal_risk=True,
    ),
    city(
        "San Francisco",
        "CA",
        "KSFO",
        "San Francisco International Airport",
        37.6213,
        -122.3790,
        "America/Los_Angeles",
        67.0,
        "https://kalshi.com/markets/kxhightsfo/san-francisco-high-temperature-daily/kxhightsfo-26may24",
        "KXHIGHTSFO-26MAY24",
        "CLISFO",
        "MTR",
        "SFO",
        "San Francisco Airport",
        coastal_risk=True,
    ),
    city(
        "Austin",
        "TX",
        "KAUS",
        "Austin-Bergstrom International Airport",
        30.1945,
        -97.6699,
        "America/Chicago",
        88.0,
        "https://kalshi.com/markets/kxhighaus/highest-temperature-in-austin/kxhighaus-26may24",
        "KXHIGHAUS-26MAY24",
        "CLIAUS",
        "EWX",
        "AUS",
        "Austin Bergstrom",
    ),
    city(
        "Las Vegas",
        "NV",
        "KLAS",
        "Harry Reid International Airport",
        36.0719,
        -115.1634,
        "America/Los_Angeles",
        94.0,
        "https://kalshi.com/markets/kxhightlv/las-vegas-max-daily-temperature/kxhightlv-26may24",
        "KXHIGHTLV-26MAY24",
        "CLILAS",
        "VEF",
        "LAS",
        "Las Vegas, NV",
    ),
    city(
        "Minneapolis",
        "MN",
        "KMSP",
        "Minneapolis-St Paul International Airport",
        44.8848,
        -93.2223,
        "America/Chicago",
        83.0,
        "https://kalshi.com/markets/kxhightmin/minneapolis-daily-high-temperature/kxhightmin-26may24",
        "KXHIGHTMIN-26MAY24",
        "CLIMSP",
        "MPX",
        "MSP",
        "Minneapolis/St Paul, MN",
    ),
    city(
        "Denver",
        "CO",
        "KDEN",
        "Denver International Airport",
        39.8617,
        -104.6731,
        "America/Denver",
        82.0,
        "https://kalshi.com/markets/kxhighden/highest-temperature-in-denver/kxhighden-26may24",
        "KXHIGHDEN-26MAY24",
        "CLIDEN",
        "BOU",
        "DEN",
        "Denver, CO",
    ),
    city(
        "Philadelphia",
        "PA",
        "KPHL",
        "Philadelphia International Airport",
        39.8733,
        -75.2268,
        "America/New_York",
        64.0,
        "https://kalshi.com/markets/kxhighphil/highest-temperature-in-philadelphia/kxhighphil-26may24",
        "KXHIGHPHIL-26MAY24",
        "CLIPHL",
        "PHI",
        "PHL",
        "Philadelphia International Airport",
    ),
    city(
        "Seattle",
        "WA",
        "KSEA",
        "Seattle-Tacoma International Airport",
        47.4502,
        -122.3088,
        "America/Los_Angeles",
        71.0,
        "https://kalshi.com/markets/kxhightsea/seattle-maximum-temperature-daily/kxhightsea-26may24",
        "KXHIGHTSEA-26MAY24",
        "CLISEA",
        "SEW",
        "SEA",
        "Seattle-Tacoma, WA",
        coastal_risk=True,
    ),
    city(
        "Washington DC",
        "DC",
        "KDCA",
        "Washington National Airport",
        38.8521,
        -77.0377,
        "America/New_York",
        70.0,
        "https://kalshi.com/markets/kxhightdc/washington-dc-daily-max-temp/kxhightdc-26may24",
        "KXHIGHTDC-26MAY24",
        "CLIDCA",
        "LWX",
        "DCA",
        "Washington-National",
    ),
    city(
        "Dallas",
        "TX",
        "KDFW",
        "Dallas/Fort Worth International Airport",
        32.8975,
        -97.0404,
        "America/Chicago",
        87.0,
        "https://kalshi.com/markets/kxhightdal/dallas-maximum-temperature/kxhightdal-26may24",
        "KXHIGHTDAL-26MAY24",
        "CLIDFW",
        "FWD",
        "DFW",
        "Dallas/Fort Worth, TX",
    ),
    city(
        "Houston",
        "TX",
        "KHOU",
        "Houston Hobby Airport",
        29.6454,
        -95.2789,
        "America/Chicago",
        87.0,
        "https://kalshi.com/markets/kxhighthou/daily-high-temperature-houston/kxhighthou-26may24",
        "KXHIGHTHOU-26MAY24",
        "CLIHOU",
        "HGX",
        "HOU",
        "Houston-Hobby, TX",
        coastal_risk=True,
    ),
    city(
        "San Antonio",
        "TX",
        "KSAT",
        "San Antonio International Airport",
        29.5337,
        -98.4698,
        "America/Chicago",
        88.0,
        "https://kalshi.com/markets/kxhightsatx/san-antonio-daily-maximum-temperature/kxhightsatx-26may24",
        "KXHIGHTSATX-26MAY24",
        "CLISAT",
        "EWX",
        "SAT",
        "San Antonio",
    ),
    city(
        "Oklahoma City",
        "OK",
        "KOKC",
        "Will Rogers World Airport",
        35.3931,
        -97.6007,
        "America/Chicago",
        86.0,
        "https://kalshi.com/markets/kxhightokc/oklahoma-city-maximum-high-temperature/kxhightokc-26may24",
        "KXHIGHTOKC-26MAY24",
        "CLIOKC",
        "OUN",
        "OKC",
        "Oklahoma City Will Rogers Airport",
    ),
    city(
        "New Orleans",
        "LA",
        "KMSY",
        "Louis Armstrong New Orleans International Airport",
        29.9934,
        -90.2580,
        "America/Chicago",
        79.0,
        "https://kalshi.com/markets/kxhightnola/new-orleans-max-temp-daily/kxhightnola-26may24",
        "KXHIGHTNOLA-26MAY24",
        "CLIMSY",
        "LIX",
        "MSY",
        "New Orleans, LA",
        coastal_risk=True,
    ),
]
