# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Las Vegas low_weather_prediction@h9

- Event days: 60
- Trades: 21
- Skips: 39
- Win rate: 14.3%
- Average win: +169.00c
- Average loss: -82.17c
- EV/trade: -46.29c
- Total simulated P&L: -972c ($-9.72)
- Worst drawdown: -972c ($-9.72)

### Stability

- Older half: n=10, win_rate=20.0%, EV/trade=-34.30c, total=-343c
- Newer half: n=11, win_rate=9.1%, EV/trade=-57.18c, total=-629c

### City Breakdown

- Las Vegas: n=21, win_rate=14.3%, EV/trade=-46.29c, total=-972c

### Skip reasons

- weather bucket price outside entry band: 39
