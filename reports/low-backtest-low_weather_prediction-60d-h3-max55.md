# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Las Vegas low_weather_prediction@h3

- Event days: 60
- Trades: 27
- Skips: 33
- Win rate: 11.1%
- Average win: +153.00c
- Average loss: -78.00c
- EV/trade: -52.33c
- Total simulated P&L: -1413c ($-14.13)
- Worst drawdown: -1413c ($-14.13)

### Stability

- Older half: n=13, win_rate=15.4%, EV/trade=-50.85c, total=-661c
- Newer half: n=14, win_rate=7.1%, EV/trade=-53.71c, total=-752c

### City Breakdown

- Las Vegas: n=27, win_rate=11.1%, EV/trade=-52.33c, total=-1413c

### Skip reasons

- weather bucket price outside entry band: 33
