# Kalshi Weather Scout Report

Generated: 2026-06-03T09:38:55

> Research only. This tool does not place trades and does not use paid APIs.

## 1. Phoenix - AVOID

- Market/contract: Highest temperature in Phoenix on Jun 3, 2026?
- Official station/location: Phoenix, AZ
- Official station id: KPHX
- Market date: 2026-06-03
- Market local time: 2026-06-03T06:38:38-07:00
- NWS climate product: CLIPHX
- Settlement source status: cli_wrong_date
- Source safety state: LIVE_OBS_PRELIMINARY
- Bucket state: UNRESOLVED_BUCKET
- Active heating window: yes
- Analysis source status: same_day_station_observations
- Hourly forecast status: same_day_hourly_forecast
- NWS CLI high: 104.0F
- Current temp: 80.6F
- Raw high so far: 91.4F
- High so far: 91.0F
- Latest observation: 2026-06-03T13:20:00+00:00
- Forecast high: 106.0F
- Forecast high time: 17:00
- Critical hour ET: 7:00-8:00 PM ET
- Heating pace: 2.2F/hr
- Needed rate: 1.5F/hr
- Degrees needed to reach bucket: 15.1F
- Reachability: UNLIKELY
- Market vs weather: market hotter
- False hotter pump warning: yes
- Decision note: Kalshi favors 107F to 108F, but weather pace does not confirm the hotter move yet.
- CLI source URL: https://forecast.weather.gov/product.php?site=PSR&product=CLI&issuedby=PHX&format=TXT
- Forecast source URL: https://forecast.weather.gov/MapClick.php?lat=33.4342&lon=-112.0116&unit=0&lg=english&FcstType=digitalDWML
- Hourly forecast graph URL: https://forecast.weather.gov/MapClick.php?lat=33.4342&lon=-112.0116&unit=0&lg=english&FcstType=graphical
- Kalshi bucket: 107F to 108F
- Kalshi price: 68 cents
- Market data source: API Market Data
- API crowd favorite: 107F to 108F @ 68c
- Estimated probability: 0%
- Visible implied probability: 68%
- Weather confidence: 71/100
- Volatility risk: 75/100
- Rebound risk: 80/100
- Liquidity risk: 53/100
- Market crowding: 20/100
- Estimated edge: 0/100

**Reasoning**

- Estimated weather probability is 0% with edge score 0.
- NWS CLI report high is not available yet; using observation/forecast fallback.
- Scored visible Kalshi bucket: 107F to 108F.
- High so far is 91.0F vs threshold 100.0F.
- Forecast high is 106.0F vs threshold 100.0F.
- Visible Kalshi implied probability is 68%.

**Warnings**

- NWS CLI settlement report date 2026-06-02 does not match Kalshi market date 2026-06-03; using same-day station observations when available.

## 2. Las Vegas - AVOID

- Market/contract: Highest temperature in Las Vegas on Jun 3, 2026?
- Official station/location: Las Vegas, NV
- Official station id: KLAS
- Market date: 2026-06-03
- Market local time: 2026-06-03T06:38:47-07:00
- NWS climate product: CLILAS
- Settlement source status: cli_wrong_date
- Source safety state: LIVE_OBS_PRELIMINARY
- Bucket state: UNRESOLVED_BUCKET
- Active heating window: yes
- Analysis source status: same_day_station_observations
- Hourly forecast status: same_day_hourly_forecast
- NWS CLI high: 101.0F
- Current temp: 78.8F
- Raw high so far: 86.0F
- High so far: 86.0F
- Latest observation: 2026-06-03T13:20:00+00:00
- Forecast high: 103.0F
- Forecast high time: 18:00
- Critical hour ET: 8:00-9:00 PM ET
- Heating pace: 0.0F/hr
- Needed rate: 1.4F/hr
- Degrees needed to reach bucket: 15.5F
- Reachability: REACHABLE
- Market vs weather: agrees
- False hotter pump warning: no
- Decision note: 102F to 103F is reachable because the NWS forecast supports that bucket.
- CLI source URL: https://forecast.weather.gov/product.php?site=VEF&product=CLI&issuedby=LAS&format=TXT
- Forecast source URL: https://forecast.weather.gov/MapClick.php?lat=36.0719&lon=-115.1634&unit=0&lg=english&FcstType=digitalDWML
- Hourly forecast graph URL: https://forecast.weather.gov/MapClick.php?lat=36.0719&lon=-115.1634&unit=0&lg=english&FcstType=graphical
- Kalshi bucket: 102F to 103F
- Kalshi price: 57 cents
- Market data source: API Market Data
- API crowd favorite: 102F to 103F @ 57c
- Estimated probability: 15%
- Visible implied probability: 57%
- Weather confidence: 85/100
- Volatility risk: 54/100
- Rebound risk: 80/100
- Liquidity risk: 53/100
- Market crowding: 20/100
- Estimated edge: 0/100

**Reasoning**

- Estimated weather probability is 15% with edge score 0.
- NWS CLI report high is not available yet; using observation/forecast fallback.
- Scored visible Kalshi bucket: 102F to 103F.
- High so far is 86.0F vs threshold 94.0F.
- Forecast high is 103.0F vs threshold 94.0F.
- Visible Kalshi implied probability is 57%.

**Warnings**

- NWS CLI settlement report date 2026-06-02 does not match Kalshi market date 2026-06-03; using same-day station observations when available.

## 3. San Antonio - AVOID

- Market/contract: Highest temperature in San Antonio on Jun 3, 2026?
- Official station/location: San Antonio
- Official station id: KSAT
- Market date: 2026-06-03
- Market local time: 2026-06-03T08:38:55-05:00
- NWS climate product: CLISAT
- Settlement source status: cli_preliminary
- Source safety state: LIVE_OBS_PRELIMINARY
- Bucket state: UNRESOLVED_BUCKET
- Active heating window: yes
- Analysis source status: same_day_station_observations
- Hourly forecast status: same_day_hourly_forecast
- NWS CLI high: 74.0F
- Current temp: 73.4F
- Raw high so far: 73.9F
- High so far: 74.0F
- Latest observation: 2026-06-03T13:20:00+00:00
- Forecast high: 88.0F
- Forecast high time: 16:00
- Critical hour ET: 4:00-5:00 PM ET
- Heating pace: 2.4F/hr
- Needed rate: 1.9F/hr
- Degrees needed to reach bucket: 13.6F
- Reachability: REACHABLE
- Market vs weather: agrees
- False hotter pump warning: no
- Decision note: 88F to 89F is reachable if live heating stays near the current pace.
- CLI source URL: https://forecast.weather.gov/product.php?site=EWX&product=CLI&issuedby=SAT&format=TXT
- Forecast source URL: https://forecast.weather.gov/MapClick.php?lat=29.5337&lon=-98.4698&unit=0&lg=english&FcstType=digitalDWML
- Hourly forecast graph URL: https://forecast.weather.gov/MapClick.php?lat=29.5337&lon=-98.4698&unit=0&lg=english&FcstType=graphical
- Kalshi bucket: 88F to 89F
- Kalshi price: 45 cents
- Market data source: API Market Data
- API crowd favorite: 88F to 89F @ 45c
- Estimated probability: 42%
- Visible implied probability: 45%
- Weather confidence: 83/100
- Volatility risk: 29/100
- Rebound risk: 93/100
- Liquidity risk: 51/100
- Market crowding: 20/100
- Estimated edge: 0/100

**Reasoning**

- Estimated weather probability is 42% with edge score 0.
- NWS CLI report high is not available yet; using observation/forecast fallback.
- Scored visible Kalshi bucket: 88F to 89F.
- High so far is 74.0F vs threshold 88.0F.
- Forecast high is 88.0F vs threshold 88.0F.
- Visible Kalshi implied probability is 45%.

**Warnings**

- NWS CLI report matches the market date but the local weather day is still open; treating CLI high as preliminary.
