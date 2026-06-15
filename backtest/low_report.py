from __future__ import annotations

from collections import Counter

from backtest.engine import Report, split_chronological
from backtest.low_engine import LowBacktestResult


def render_low_backtest_report(results: list[LowBacktestResult]) -> str:
    lines = [
        "# Low Weather Backtest",
        "",
        "Research-only historical simulation. This report does not place trades or mutate any Kalshi account.",
        "",
    ]
    for result in results:
        lines.extend(_result_lines(result))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _result_lines(result: LowBacktestResult) -> list[str]:
    report = result.report
    older, newer = split_chronological(report)
    skip_counts = Counter(skip["reason"] for skip in result.skipped)
    lines = [
        f"## {result.label}",
        "",
        f"- Event days: {result.total_event_days}",
        f"- Trades: {report.n}",
        f"- Skips: {len(result.skipped)}",
        f"- Win rate: {report.win_rate:.1f}%",
        f"- Average win: {report.avg_win:+.2f}c",
        f"- Average loss: {report.avg_loss:+.2f}c",
        f"- EV/trade: {report.ev_per_trade:+.2f}c",
        f"- Total simulated P&L: {report.total_net_cents:+d}c (${report.total_net_cents / 100:+.2f})",
        f"- Worst drawdown: {result.worst_drawdown_cents:+d}c (${result.worst_drawdown_cents / 100:+.2f})",
        "",
        "### Stability",
        "",
        f"- Older half: {_short_line(older)}",
        f"- Newer half: {_short_line(newer)}",
        "",
        "### City Breakdown",
        "",
    ]
    for city, city_report in sorted(result.city_results.items()):
        lines.append(f"- {city}: {_short_line(city_report)}")
    if not result.city_results:
        lines.append("- No city trades.")
    lines.extend(["", "### Skip reasons", ""])
    if skip_counts:
        for reason, count in skip_counts.most_common():
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- None")
    return lines


def _short_line(report: Report) -> str:
    if not report.trades:
        return "no trades"
    return (
        f"n={report.n}, win_rate={report.win_rate:.1f}%, "
        f"EV/trade={report.ev_per_trade:+.2f}c, total={report.total_net_cents:+d}c"
    )
