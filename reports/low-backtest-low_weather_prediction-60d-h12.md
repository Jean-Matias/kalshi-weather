# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Las Vegas low_weather_prediction@h12

- Event days: 60
- Trades: 28
- Skips: 32
- Win rate: 35.7%
- Average win: +123.50c
- Average loss: -83.17c
- EV/trade: -9.36c
- Total simulated P&L: -262c ($-2.62)
- Worst drawdown: -727c ($-7.27)

### Stability

- Older half: n=14, win_rate=50.0%, EV/trade=+15.71c, total=+220c
- Newer half: n=14, win_rate=21.4%, EV/trade=-34.43c, total=-482c

### City Breakdown

- Las Vegas: n=28, win_rate=35.7%, EV/trade=-9.36c, total=-262c

### Skip reasons

- weather bucket price outside entry band: 32
