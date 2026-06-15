# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Las Vegas low_weather_prediction@h12

- Event days: 60
- Trades: 21
- Skips: 39
- Win rate: 19.0%
- Average win: +179.75c
- Average loss: -76.53c
- EV/trade: -27.71c
- Total simulated P&L: -582c ($-5.82)
- Worst drawdown: -645c ($-6.45)

### Stability

- Older half: n=10, win_rate=30.0%, EV/trade=-2.20c, total=-22c
- Newer half: n=11, win_rate=9.1%, EV/trade=-50.91c, total=-560c

### City Breakdown

- Las Vegas: n=21, win_rate=19.0%, EV/trade=-27.71c, total=-582c

### Skip reasons

- weather bucket price outside entry band: 39
