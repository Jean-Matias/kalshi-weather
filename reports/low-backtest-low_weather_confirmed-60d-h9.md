# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Las Vegas low_weather_confirmed@h9

- Event days: 60
- Trades: 11
- Skips: 49
- Win rate: 81.8%
- Average win: +101.00c
- Average loss: -178.00c
- EV/trade: +50.27c
- Total simulated P&L: +553c ($+5.53)
- Worst drawdown: -356c ($-3.56)

### Stability

- Older half: n=5, win_rate=100.0%, EV/trade=+87.80c, total=+439c
- Newer half: n=6, win_rate=66.7%, EV/trade=+19.00c, total=+114c

### City Breakdown

- Las Vegas: n=11, win_rate=81.8%, EV/trade=+50.27c, total=+553c

### Skip reasons

- weather target disagrees with market favorite: 48
- favorite price outside entry band: 1
