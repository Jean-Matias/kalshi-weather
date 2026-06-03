# Low Temperature Report Format

Use this format whenever the user asks for a low-temperature Kalshi report.

## Target Date Rule

Always confirm the target Kalshi market date first.

For LOW-temperature markets, if the user asks during the day, the actionable
market is usually the next morning's low. Example: if the user asks on June 2
for low-temp betting signals, target June 3 unless the user says otherwise.

Run the scanner with the explicit target date:

```powershell
$env:KALSHI_MARKET_DATE="YYYY-MM-DD"; rtk python scanner.py
```

## Required Report Shape

The report should include the top 4 reliable cities only, unless the user asks
for more.

For each city, include:

1. City and official Kalshi/NWS station
2. The low temperature the data points to
3. Confidence score for that temperature read
4. The expected low-temperature time in Eastern Time
5. The local expected low-temperature time
6. Current Kalshi market state
7. Whether the signal is reliable, watchlist, or avoid

## Report Template

```markdown
# June X Low Temp Report

Target market date: YYYY-MM-DD
Generated: HH:MM ET

Bottom line:
- [Plain-English summary of whether there are reliable bets, watchlist-only
  cities, or no action yet.]

## Top 4 Reliable Cities

### 1. City

- Official station: STATION / NWS CLI product
- Expected low: XX°F
- Temp confidence: XX/100
- Lowest temp time: HH:MM ET
- Local time: HH:MM local
- Source state: FINAL_CLI_AVAILABLE / LIVE_OBS_PRELIMINARY /
  FUTURE_FORECAST / FORECAST_ONLY / CLI_STALE
- Kalshi market: visible bucket, visible price, and crowd favorite if available
- Read: RELIABLE / WATCHLIST / AVOID
- Why: one or two direct reasons

### 2. City

[same fields]

### 3. City

[same fields]

### 4. City

[same fields]

## Best Market Signals

- Signal 1: city, YES/NO, bucket, price, confidence, and why it matters.
- Signal 2: city, YES/NO, bucket, price, confidence, and why it matters.

If there are no clean signals, say: `No clean bet signal yet`.

## Timing Notes

- Earliest expected low in ET:
- Latest expected low in ET:
- Best time to refresh:

## Cautions

- Say clearly when rows are forecast-only.
- Say clearly when CLI is unavailable or stale.
- Do not call a forecast-only row a reliable bet.
- Do not mix today's already-passed low with tomorrow morning's target market.
```

## Ranking Rules

Rank the top 4 by weather reliability first, not price:

1. Strongest source state first:
   - `FINAL_CLI_AVAILABLE`
   - `LIVE_OBS_PRELIMINARY`
   - `CLI_STALE`
   - `FORECAST_ONLY`
   - `FUTURE_FORECAST`
2. Higher weather confidence score.
3. Lower volatility risk.
4. Lower cooling risk.
5. Clearer forecast low time.
6. Only then mention Kalshi pricing and bucket fit.

## Kalshi Market Section Rules

For "How is the Kalshi market doing?", include:

- Market title/date from the visible Kalshi page.
- Visible bucket being evaluated.
- Visible YES/NO price when available.
- Crowd favorite when available.
- Whether market pricing agrees with the weather read.
- Any mismatch between Kalshi's station/rules and the scanner station.

Never place trades or give financial advice. Phrase recommendations as research
signals: `reliable weather read`, `watchlist`, `avoid`, or `no clean signal`.
