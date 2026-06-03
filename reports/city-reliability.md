# City Reliability Report

Generated: 2026-06-03T09:38:55

> Research only. This ranks source quality and weather stability before any YES/NO edge. It is not betting advice.

## 1. San Antonio - 53/100

- Reliability lane: LIVE_NWS_TRACKING
- Weather-only rank: source confidence minus volatility, rebound, and live-heating risk
- Market note: 88F to 89F @ 45c (API Market Data)
- Official station/location: San Antonio
- Official station id: KSAT
- Market date: 2026-06-03
- Source safety state: LIVE_OBS_PRELIMINARY
- Settlement source status: cli_preliminary
- Analysis data status: same_day_station_observations
- Hourly forecast status: same_day_hourly_forecast
- Hourly forecast generated: 2026-06-03T06:46:18-05:00
- Hourly forecast graph URL: https://forecast.weather.gov/MapClick.php?lat=29.5337&lon=-98.4698&unit=0&lg=english&FcstType=graphical
- Active heating window: yes
- Weather confidence: 83/100
- Volatility risk: 29/100
- Rebound risk: 93/100
- Current temp: 73.4F
- Rounded/market high so far: 74.0F
- Forecast high: 88.0F
- Critical hour ET: 4:00-5:00 PM ET
- Heating pace: 2.4F/hr
- Needed rate: 1.9F/hr
- Reachability: REACHABLE
- Market vs weather: agrees
- Decision note: 88F to 89F is reachable if live heating stays near the current pace.
- Latest observation: 2026-06-03T13:20:00+00:00

**Reliability warnings**

- NWS CLI report matches the market date but the local weather day is still open; treating CLI high as preliminary.

## 2. Las Vegas - 49/100

- Reliability lane: LIVE_NWS_TRACKING
- Weather-only rank: source confidence minus volatility, rebound, and live-heating risk
- Market note: 102F to 103F @ 57c (API Market Data)
- Official station/location: Las Vegas, NV
- Official station id: KLAS
- Market date: 2026-06-03
- Source safety state: LIVE_OBS_PRELIMINARY
- Settlement source status: cli_wrong_date
- Analysis data status: same_day_station_observations
- Hourly forecast status: same_day_hourly_forecast
- Hourly forecast generated: 2026-06-03T00:21:03-07:00
- Hourly forecast graph URL: https://forecast.weather.gov/MapClick.php?lat=36.0719&lon=-115.1634&unit=0&lg=english&FcstType=graphical
- Active heating window: yes
- Weather confidence: 85/100
- Volatility risk: 54/100
- Rebound risk: 80/100
- Current temp: 78.8F
- Rounded/market high so far: 86.0F
- Forecast high: 103.0F
- Critical hour ET: 8:00-9:00 PM ET
- Heating pace: 0.0F/hr
- Needed rate: 1.4F/hr
- Reachability: REACHABLE
- Market vs weather: agrees
- Decision note: 102F to 103F is reachable because the NWS forecast supports that bucket.
- Latest observation: 2026-06-03T13:20:00+00:00

**Reliability warnings**

- NWS CLI settlement report date 2026-06-02 does not match Kalshi market date 2026-06-03; using same-day station observations when available.

## 3. Phoenix - 28/100

- Reliability lane: LIVE_NWS_TRACKING
- Weather-only rank: source confidence minus volatility, rebound, and live-heating risk
- Market note: 107F to 108F @ 68c (API Market Data)
- Official station/location: Phoenix, AZ
- Official station id: KPHX
- Market date: 2026-06-03
- Source safety state: LIVE_OBS_PRELIMINARY
- Settlement source status: cli_wrong_date
- Analysis data status: same_day_station_observations
- Hourly forecast status: same_day_hourly_forecast
- Hourly forecast generated: 2026-06-03T03:57:36-07:00
- Hourly forecast graph URL: https://forecast.weather.gov/MapClick.php?lat=33.4342&lon=-112.0116&unit=0&lg=english&FcstType=graphical
- Active heating window: yes
- Weather confidence: 71/100
- Volatility risk: 75/100
- Rebound risk: 80/100
- Current temp: 80.6F
- Rounded/market high so far: 91.0F
- Forecast high: 106.0F
- Critical hour ET: 7:00-8:00 PM ET
- Heating pace: 2.2F/hr
- Needed rate: 1.5F/hr
- Reachability: UNLIKELY
- Market vs weather: market hotter
- Decision note: Kalshi favors 107F to 108F, but weather pace does not confirm the hotter move yet.
- Latest observation: 2026-06-03T13:20:00+00:00

**Reliability warnings**

- NWS CLI settlement report date 2026-06-02 does not match Kalshi market date 2026-06-03; using same-day station observations when available.
