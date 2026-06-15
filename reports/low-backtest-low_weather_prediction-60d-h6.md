# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Las Vegas low_weather_prediction@h6

- Event days: 60
- Trades: 32
- Skips: 28
- Win rate: 37.5%
- Average win: +103.00c
- Average loss: -82.30c
- EV/trade: -12.81c
- Total simulated P&L: -410c ($-4.10)
- Worst drawdown: -855c ($-8.55)

### Stability

- Older half: n=16, win_rate=50.0%, EV/trade=+4.06c, total=+65c
- Newer half: n=16, win_rate=25.0%, EV/trade=-29.69c, total=-475c

### City Breakdown

- Las Vegas: n=32, win_rate=37.5%, EV/trade=-12.81c, total=-410c

### Skip reasons

- weather bucket price outside entry band: 28
