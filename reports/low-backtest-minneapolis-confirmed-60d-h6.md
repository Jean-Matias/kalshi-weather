# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Minneapolis low_weather_confirmed@h6

- Event days: 60
- Trades: 12
- Skips: 48
- Win rate: 58.3%
- Average win: +144.29c
- Average loss: -157.60c
- EV/trade: +18.50c
- Total simulated P&L: +222c ($+2.22)
- Worst drawdown: -411c ($-4.11)

### Stability

- Older half: n=6, win_rate=66.7%, EV/trade=+48.00c, total=+288c
- Newer half: n=6, win_rate=50.0%, EV/trade=-11.00c, total=-66c

### City Breakdown

- Minneapolis: n=12, win_rate=58.3%, EV/trade=+18.50c, total=+222c

### Skip reasons

- weather target disagrees with market favorite: 47
- favorite price outside entry band: 1
