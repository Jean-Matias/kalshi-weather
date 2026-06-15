# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Las Vegas low_weather_prediction@h6

- Event days: 60
- Trades: 22
- Skips: 38
- Win rate: 13.6%
- Average win: +157.00c
- Average loss: -76.79c
- EV/trade: -44.91c
- Total simulated P&L: -988c ($-9.88)
- Worst drawdown: -988c ($-9.88)

### Stability

- Older half: n=11, win_rate=18.2%, EV/trade=-39.45c, total=-434c
- Newer half: n=11, win_rate=9.1%, EV/trade=-50.36c, total=-554c

### City Breakdown

- Las Vegas: n=22, win_rate=13.6%, EV/trade=-44.91c, total=-988c

### Skip reasons

- weather bucket price outside entry band: 38
