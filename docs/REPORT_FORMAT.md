# Weather Report Format

Use this format whenever the user asks for a weather market report.

The report is research-only. Do not present it as betting advice. Keep weather
reliability separate from the Kalshi market read.

## Required Report Sections

### Top 4 Reliable Cities

List the four cities that are most reliable by weather data, not by market
price.

For each city include:

- City name
- Weather reliability score
- Official station id
- Source state, such as `FINAL_CLI_AVAILABLE`, `LIVE_OBS_PRELIMINARY`, or
  `FUTURE_FORECAST`
- Any serious source warning, especially wrong-date CLI, stale CLI, missing
  observations, or forecast-only data

### Expected Temperature

For each city, give the temperature outcome the data points to.

For high-temperature markets:

- Expected daily high
- Current rounded high so far
- Forecast high
- Confidence score for the expected final high bucket

For low-temperature markets:

- Expected daily low
- Current rounded low so far
- Forecast low
- Confidence score for the expected final low bucket

If the exact Kalshi bucket differs from the forecast by rounding, explain the
rounding risk clearly.

### Time The Temperature Should Hit

For each city, include:

- Local time window
- Eastern Time window
- Whether the key window has passed, is active, or is still ahead

Use the scanner's `forecast_high_time` or `forecast_low_time` when available.
If only a broad window is supported, give a window instead of a fake exact time.

### Kalshi Market Read

For each city, summarize the market separately from the weather call:

- Current Kalshi leading bucket or visible/crowd favorite
- Price or implied probability
- Whether the market agrees with the weather data, is hotter/colder than the
  weather data, or is unstable
- Liquidity or page-data warning if available

Do not let the market price decide whether a city is weather-reliable.

## Recommended Extra Fields

Include these when available because they reduce follow-up questions:

- Latest observation timestamp
- Current temperature
- Raw high or low so far before rounding
- Main risk reason, such as clouds, wind, late rebound, overnight cooling,
  stale observations, coastal/marine influence, or CLI not final
- Action timing note: "too early", "watch now", "decision window", or
  "mostly settled"

## Short Summary Format

End with a short plain-English summary:

- Best weather-data city
- City with biggest weather-vs-market disagreement
- City to avoid because the data is too unstable
- Next best time to refresh

## Example Skeleton

```text
Top 4 weather-reliable cities:

1. City - reliability score
   Expected temp: 00F, confidence 00/100
   Hit time: 0-0 PM local / 0-0 PM ET
   Kalshi: bucket @ price, market agrees/disagrees
   Risk: short reason

Bottom line:
Best weather read is City. Biggest market disagreement is City. Refresh again
around TIME ET.
```
