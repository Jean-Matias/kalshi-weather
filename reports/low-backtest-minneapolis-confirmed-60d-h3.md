# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Minneapolis low_weather_confirmed@h3

- Event days: 60
- Trades: 14
- Skips: 46
- Win rate: 42.9%
- Average win: +130.50c
- Average loss: -167.12c
- EV/trade: -39.57c
- Total simulated P&L: -554c ($-5.54)
- Worst drawdown: -983c ($-9.83)

### Stability

- Older half: n=7, win_rate=28.6%, EV/trade=-65.71c, total=-460c
- Newer half: n=7, win_rate=57.1%, EV/trade=-13.43c, total=-94c

### City Breakdown

- Minneapolis: n=14, win_rate=42.9%, EV/trade=-39.57c, total=-554c

### Skip reasons

- weather target disagrees with market favorite: 46
