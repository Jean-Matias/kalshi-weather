# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Las Vegas low_market_confirmed@h3

- Event days: 60
- Trades: 12
- Skips: 48
- Win rate: 83.3%
- Average win: +105.50c
- Average loss: -128.50c
- EV/trade: +66.50c
- Total simulated P&L: +798c ($+7.98)
- Worst drawdown: -154c ($-1.54)

### Stability

- Older half: n=6, win_rate=83.3%, EV/trade=+70.00c, total=+420c
- Newer half: n=6, win_rate=83.3%, EV/trade=+63.00c, total=+378c

### City Breakdown

- Las Vegas: n=12, win_rate=83.3%, EV/trade=+66.50c, total=+798c

### Skip reasons

- weather target disagrees with market favorite: 47
- favorite price outside entry band: 1
