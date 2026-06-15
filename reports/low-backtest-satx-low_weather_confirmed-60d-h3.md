# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## San Antonio low_weather_confirmed@h3

- Event days: 60
- Trades: 10
- Skips: 50
- Win rate: 20.0%
- Average win: +194.00c
- Average loss: -115.38c
- EV/trade: -53.50c
- Total simulated P&L: -535c ($-5.35)
- Worst drawdown: -820c ($-8.20)

### Stability

- Older half: n=5, win_rate=20.0%, EV/trade=-41.20c, total=-206c
- Newer half: n=5, win_rate=20.0%, EV/trade=-65.80c, total=-329c

### City Breakdown

- San Antonio: n=10, win_rate=20.0%, EV/trade=-53.50c, total=-535c

### Skip reasons

- weather target disagrees with market favorite: 50
