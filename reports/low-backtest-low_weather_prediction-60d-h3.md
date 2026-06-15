# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Las Vegas low_weather_prediction@h3

- Event days: 60
- Trades: 35
- Skips: 25
- Win rate: 31.4%
- Average win: +105.91c
- Average loss: -78.00c
- EV/trade: -20.20c
- Total simulated P&L: -707c ($-7.07)
- Worst drawdown: -1155c ($-11.55)

### Stability

- Older half: n=17, win_rate=47.1%, EV/trade=+0.41c, total=+7c
- Newer half: n=18, win_rate=16.7%, EV/trade=-39.67c, total=-714c

### City Breakdown

- Las Vegas: n=35, win_rate=31.4%, EV/trade=-20.20c, total=-707c

### Skip reasons

- weather bucket price outside entry band: 25
