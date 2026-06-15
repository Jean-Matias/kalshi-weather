# Low Weather Backtest

Research-only historical simulation. This report does not place trades or mutate any Kalshi account.

## Las Vegas low_market_confirmed@h12

- Event days: 60
- Trades: 10
- Skips: 50
- Win rate: 60.0%
- Average win: +86.00c
- Average loss: -139.00c
- EV/trade: -4.00c
- Total simulated P&L: -40c ($-0.40)
- Worst drawdown: -393c ($-3.93)

### Stability

- Older half: n=5, win_rate=80.0%, EV/trade=+47.60c, total=+238c
- Newer half: n=5, win_rate=40.0%, EV/trade=-55.60c, total=-278c

### City Breakdown

- Las Vegas: n=10, win_rate=60.0%, EV/trade=-4.00c, total=-40c

### Skip reasons

- weather target disagrees with market favorite: 48
- favorite price outside entry band: 2
