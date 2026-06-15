# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Minneapolis low_weather_confirmed@h12

- Event days: 60
- Trades: 15
- Skips: 45
- Win rate: 46.7%
- Average win: +149.43c
- Average loss: -149.50c
- EV/trade: -10.00c
- Total simulated P&L: -150c ($-1.50)
- Worst drawdown: -721c ($-7.21)

### Stability

- Older half: n=7, win_rate=28.6%, EV/trade=-56.71c, total=-397c
- Newer half: n=8, win_rate=62.5%, EV/trade=+30.88c, total=+247c

### City Breakdown

- Minneapolis: n=15, win_rate=46.7%, EV/trade=-10.00c, total=-150c

### Skip reasons

- weather target disagrees with market favorite: 44
- favorite price outside entry band: 1
