# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Las Vegas low_weather_confirmed@h12

- Event days: 60
- Trades: 9
- Skips: 51
- Win rate: 66.7%
- Average win: +86.00c
- Average loss: -147.00c
- EV/trade: +8.33c
- Total simulated P&L: +75c ($+0.75)
- Worst drawdown: -352c ($-3.52)

### Stability

- Older half: n=4, win_rate=100.0%, EV/trade=+88.25c, total=+353c
- Newer half: n=5, win_rate=40.0%, EV/trade=-55.60c, total=-278c

### City Breakdown

- Las Vegas: n=9, win_rate=66.7%, EV/trade=+8.33c, total=+75c

### Skip reasons

- weather target disagrees with market favorite: 49
- favorite price outside entry band: 2
