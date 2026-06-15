# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Las Vegas low_weather_prediction@h9

- Event days: 60
- Trades: 30
- Skips: 30
- Win rate: 36.7%
- Average win: +111.09c
- Average loss: -89.11c
- EV/trade: -15.70c
- Total simulated P&L: -471c ($-4.71)
- Worst drawdown: -877c ($-8.77)

### Stability

- Older half: n=15, win_rate=46.7%, EV/trade=-4.00c, total=-60c
- Newer half: n=15, win_rate=26.7%, EV/trade=-27.40c, total=-411c

### City Breakdown

- Las Vegas: n=30, win_rate=36.7%, EV/trade=-15.70c, total=-471c

### Skip reasons

- weather bucket price outside entry band: 30
