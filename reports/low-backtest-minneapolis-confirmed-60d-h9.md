# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Minneapolis low_weather_confirmed@h9

- Event days: 60
- Trades: 12
- Skips: 48
- Win rate: 50.0%
- Average win: +139.00c
- Average loss: -155.00c
- EV/trade: -8.00c
- Total simulated P&L: -96c ($-0.96)
- Worst drawdown: -645c ($-6.45)

### Stability

- Older half: n=6, win_rate=33.3%, EV/trade=-40.00c, total=-240c
- Newer half: n=6, win_rate=66.7%, EV/trade=+24.00c, total=+144c

### City Breakdown

- Minneapolis: n=12, win_rate=50.0%, EV/trade=-8.00c, total=-96c

### Skip reasons

- weather target disagrees with market favorite: 48
