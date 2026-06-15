# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Las Vegas low_market_confirmed@h6

- Event days: 30
- Trades: 6
- Skips: 24
- Win rate: 83.3%
- Average win: +101.60c
- Average loss: -133.00c
- EV/trade: +62.50c
- Total simulated P&L: +375c ($+3.75)
- Worst drawdown: -133c ($-1.33)

### Stability

- Older half: n=3, win_rate=66.7%, EV/trade=+6.00c, total=+18c
- Newer half: n=3, win_rate=100.0%, EV/trade=+119.00c, total=+357c

### City Breakdown

- Las Vegas: n=6, win_rate=83.3%, EV/trade=+62.50c, total=+375c

### Skip reasons

- weather target disagrees with market favorite: 23
- favorite price outside entry band: 1
