import os
import re
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_NAME = "kalshi-low-weather-scout"
DATA_DIR = Path("data")
REPORTS_DIR = Path("reports")
DATABASE_PATH = DATA_DIR / "snapshots.sqlite3"
REPORT_PATH = REPORTS_DIR / "today.md"
SIGNALS_REPORT_PATH = REPORTS_DIR / "signals.md"
TEMPERATURE_CONFIDENCE_REPORT_PATH = REPORTS_DIR / "temperature-confidence.md"
CITY_RELIABILITY_REPORT_PATH = REPORTS_DIR / "city-reliability.md"
DASHBOARD_REPORT_PATH = REPORTS_DIR / "dashboard.html"

USER_AGENT = (
    "kalshi-low-weather-scout/0.1 "
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
            "Kalshi rules say the official low-temperature outcome is the NWS Climatological "
            f"Report Daily for {official_location}."
        ),
    }

def _market_date_for_timezone(timezone: str, now: datetime | None = None) -> str:
    override = os.environ.get("KALSHI_MARKET_DATE")
    if override:
        return override
    kalshi_timezone = os.environ.get("KALSHI_MARKET_TIMEZONE", "America/New_York")
    base_time = now or datetime.now(datetime_timezone.utc)
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=datetime_timezone.utc)
    return base_time.astimezone(ZoneInfo(kalshi_timezone)).date().isoformat()

def _with_market_date_suffix(value: str, market_date: str, uppercase: bool) -> str:
    suffix = _kalshi_date_suffix(market_date)
    if uppercase:
        suffix = suffix.upper()
    return re.sub(r"-\d{2}[A-Za-z]{3}\d{2}$", f"-{suffix}", value)

def _kalshi_date_suffix(market_date: str) -> str:
    date = datetime.fromisoformat(market_date)
    return date.strftime("%y%b%d").lower()


CITY_CONFIGS = [
    city(
        "Chicago",
        "IL",
        "KMDW",
        "Chicago Midway International Airport",
        41.7868,
        -87.7522,
        "America/Chicago",
        52.0,
        "https://kalshi.com/markets/kxlowtchi/lowest-temperature-chicago/kxlowtchi-26may24",
        "KXLOWTCHI-26MAY24",
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
        55.0,
        "https://kalshi.com/markets/kxlowtnyc/lowest-temperature-nyc/kxlowtnyc-26may24",
        "KXLOWTNYC-26MAY24",
        "CLINYC",
        "OKX",
        "NYC",
        "Central Park, New York",
    ),
    city(
        "Atlanta",
        "GA",
        "KATL",
        "Atlanta Hartsfield-Jackson International Airport",
        33.6367,
        -84.4281,
        "America/New_York",
        64.0,
        "https://kalshi.com/markets/kxlowtatl/lowest-temperature-atlanta/kxlowtatl-26may24",
        "KXLOWTATL-26MAY24",
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
        73.0,
        "https://kalshi.com/markets/kxlowtphx/lowest-temperature-phoenix/kxlowtphx-26may24",
        "KXLOWTPHX-26MAY24",
        "CLIPHX",
        "PSR",
        "PHX",
        "Phoenix, AZ",
    ),
    city(
        "Austin",
        "TX",
        "KAUS",
        "Austin-Bergstrom International Airport",
        30.1945,
        -97.6699,
        "America/Chicago",
        64.0,
        "https://kalshi.com/markets/kxlowtaus/lowest-temperature-austin/kxlowtaus-26may24",
        "KXLOWTAUS-26MAY24",
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
        70.0,
        "https://kalshi.com/markets/kxlowtlv/lowest-temperature-las-vegas/kxlowtlv-26may24",
        "KXLOWTLV-26MAY24",
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
        50.0,
        "https://kalshi.com/markets/kxlowtmin/lowest-temperature-minneapolis/kxlowtmin-26may24",
        "KXLOWTMIN-26MAY24",
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
        39.0,
        "https://kalshi.com/markets/kxlowtden/lowest-temperature-denver/kxlowtden-26may24",
        "KXLOWTDEN-26MAY24",
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
        54.0,
        "https://kalshi.com/markets/kxlowtphil/lowest-temperature-philadelphia/kxlowtphil-26may24",
        "KXLOWTPHIL-26MAY24",
        "CLIPHL",
        "PHI",
        "PHL",
        "Philadelphia International Airport",
    ),
    city(
        "Washington DC",
        "DC",
        "KDCA",
        "Washington National Airport",
        38.8521,
        -77.0377,
        "America/New_York",
        56.0,
        "https://kalshi.com/markets/kxlowtdc/lowest-temperature-washington-dc/kxlowtdc-26may24",
        "KXLOWTDC-26MAY24",
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
        65.0,
        "https://kalshi.com/markets/kxlowtdal/lowest-temperature-dallas/kxlowtdal-26may24",
        "KXLOWTDAL-26MAY24",
        "CLIDFW",
        "FWD",
        "DFW",
        "Dallas/Fort Worth, TX",
    ),
    city(
        "San Antonio",
        "TX",
        "KSAT",
        "San Antonio International Airport",
        29.5337,
        -98.4698,
        "America/Chicago",
        65.0,
        "https://kalshi.com/markets/kxlowtsatx/lowest-temperature-san-antonio/kxlowtsatx-26may24",
        "KXLOWTSATX-26MAY24",
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
        59.0,
        "https://kalshi.com/markets/kxlowtokc/lowest-temperature-oklahoma-city/kxlowtokc-26may24",
        "KXLOWTOKC-26MAY24",
        "CLIOKC",
        "OUN",
        "OKC",
        "Oklahoma City Will Rogers Airport",
    ),
]
