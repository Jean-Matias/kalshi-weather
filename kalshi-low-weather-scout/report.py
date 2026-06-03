from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any


def write_report(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_markdown_report(rows), encoding="utf-8")


def write_signal_report(path: Path, signals: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_signal_report(signals), encoding="utf-8")


def write_temperature_confidence_report(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_temperature_confidence_report(rows), encoding="utf-8")

def write_city_reliability_report(
    path: Path,
    rows: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_city_reliability_report(rows, signals), encoding="utf-8")

def write_dashboard_report(
    path: Path,
    rows: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_dashboard_report(rows, signals), encoding="utf-8")

def build_dashboard_report(
    rows: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> str:
    generated = datetime.now().isoformat(timespec="seconds")
    target_view = _dashboard_view(rows, signals)
    live_count = sum(1 for row in rows if row.get("source_safety_state") == "LIVE_OBS_PRELIMINARY")
    final_count = sum(1 for row in rows if row.get("source_safety_state") == "FINAL_CLI_AVAILABLE")
    forecast_count = sum(1 for row in rows if row.get("source_safety_state") in {"FUTURE_FORECAST", "FORECAST_ONLY"})
    target_dates = _target_date_text(rows)
    dashboard_markup = _dashboard_content(target_view)

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>Kalshi Low Weather Scout Dashboard</title>",
            "<style>",
            _dashboard_css(),
            "</style>",
            "</head>",
            "<body>",
            '<main class="shell">',
            '<section class="topbar">',
            "<div>",
            "<h1>Low Weather Scout</h1>",
            f"<p>Updated {html.escape(generated)}. Target Kalshi market date: {html.escape(target_dates)}. Research only; no trades are placed.</p>",
            "</div>",
            '<div class="status-strip">',
            _stat_card("Tracked Cities", str(len(rows)), "selected target date"),
            _stat_card("Final CLI", str(final_count), "settlement source posted"),
            _stat_card("Live Preliminary", str(live_count), "low can still change"),
            _stat_card("Forecast Only", str(forecast_count), "watchlist, not final"),
            "</div>",
            "</section>",
            dashboard_markup,
            "</main>",
            "</body>",
            "</html>",
        ]
    )

def _target_date_text(rows: list[dict[str, Any]]) -> str:
    dates = sorted({str(row.get("market_date")) for row in rows if row.get("market_date")})
    if not dates:
        return "unknown"
    if len(dates) == 1:
        return dates[0]
    return ", ".join(dates)

def _dashboard_view(rows: list[dict[str, Any]], signals: list[dict[str, Any]]) -> dict[str, Any]:
    city_rows = sorted(rows, key=lambda row: _city_reliability_score(row), reverse=True)
    visible_rows = [row for row in city_rows if not _hide_city_by_default(row)]
    hidden_rows = [row for row in city_rows if _hide_city_by_default(row)]
    return {
        "city_rows": city_rows,
        "visible_rows": visible_rows,
        "hidden_rows": hidden_rows,
        "signal_lookup": _city_signal_lookup(signals),
    }

def _dashboard_content(view: dict[str, Any]) -> str:
    note = (
        "Start here for the selected market date. During daytime low-temp research, set KALSHI_MARKET_DATE to the next morning's market; "
        "forecast-only rows are watchlist data until live observations or final NWS CLI are available."
    )
    hidden_note = "Hidden by default because the data is stale, incomplete, volatile, forecast-only, or the remaining low window is too jumpy."
    return (
        '<section class="panel">'
        '<div class="panel-head"><h2>Most Reliable Cities</h2><span>ranked by source quality and low-temperature stability</span></div>'
        f'<p class="note">{html.escape(note)}</p>'
        + _city_rank_cards(view["visible_rows"], view["signal_lookup"])
        + "</section>"
        + _hidden_city_section(view["hidden_rows"], view["signal_lookup"], hidden_note)
        + '<section class="panel compact-panel">'
        + '<div class="panel-head"><h2>All City Rank</h2><span>best to worst after hiding volatile cities above</span></div>'
        + _city_table(view["city_rows"])
        + "</section>"
    )

def _enrich_signal(signal: dict[str, Any]) -> dict[str, Any]:
    probability = int(signal.get("estimated_probability") or 0)
    price = float(signal.get("side_price") or 0)
    fail_risk = max(0, min(100, 100 - probability))
    value_gap = round(probability - price, 1)
    volatility = int(signal.get("volatility_risk_score") or 0)
    cooling = int(signal.get("cooling_risk_score") or 0)
    confidence = int(signal.get("weather_confidence_score") or 0)
    blocked = bool(signal.get("blocked_from_near_misses"))
    source_state = signal.get("source_safety_state")
    bucket = signal.get("bucket_state")
    clean_final = source_state == "FINAL_CLI_AVAILABLE" and bucket in {"FINAL_YES", "FINAL_NO"}
    positive_gap = value_gap >= 8 and probability >= 55
    weak_price = value_gap <= -15 or (probability <= 25 and price >= 40)
    if positive_gap and clean_final and not blocked and confidence >= 85 and volatility < 60 and cooling < 60:
        reliability = "RELIABLE"
        rank = 4
    elif positive_gap and not weak_price:
        reliability = "REVIEW"
        rank = 3
    else:
        reliability = "AVOID"
        rank = 1
    if blocked and reliability == "RELIABLE":
        reliability = "REVIEW"
        rank = 2
    enriched = dict(signal)
    enriched.update(
        {
            "side_probability": probability,
            "side_price": price,
            "fail_risk": fail_risk,
            "value_gap": value_gap,
            "reliability": reliability,
            "reliability_rank": rank,
            "confidence": confidence,
        }
    )

def _city_signal_lookup(signals: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    lookup: dict[str, list[dict[str, Any]]] = {}
    for signal in signals:
        city = signal.get("city")
        if city:
            lookup.setdefault(str(city), []).append(signal)
    return lookup

def _hide_city_by_default(row: dict[str, Any]) -> bool:
    if row.get("source_safety_state") == "FINAL_CLI_AVAILABLE":
        return False
    if row.get("source_safety_state") == "FUTURE_FORECAST":
        return True
    if _city_reliability_score(row) < 45:
        return True
    if float(row.get("volatility_risk_score") or 0) >= 70:
        return True
    if float(row.get("cooling_risk_score") or 0) >= 65:
        return True
    if float(row.get("weather_confidence_score") or 0) < 55:
        return True
    if row.get("forecast_low_f") is None:
        return True
    if row.get("latest_observation_time") is None:
        return True
    return False

def _city_rank_cards(rows: list[dict[str, Any]], signal_lookup: dict[str, list[dict[str, Any]]]) -> str:
    if not rows:
        return '<p class="empty">No cities cleared the reliability filter right now.</p>'
    cards = []
    for rank, row in enumerate(rows, start=1):
        cards.append(_city_rank_card(row, rank, signal_lookup.get(str(row.get("city")), [])))
    return '<div class="city-list">' + "".join(cards) + "</div>"

def _city_rank_card(row: dict[str, Any], rank: int, signals: list[dict[str, Any]]) -> str:
    side = _best_side_for_selected_bucket(row, signals)
    score = _city_reliability_score(row)
    hidden_reason = _hide_reason(row)
    tone = "stable" if score >= 60 else "caution"
    if _hide_city_by_default(row):
        tone = "hidden-risk"
    return (
        f'<article class="city-card {tone}">'
        '<div class="city-main">'
        f'<div class="rank">{rank}</div>'
        '<div class="city-copy">'
        f'<h3>{html.escape(str(row.get("city", "Unknown city")))}</h3>'
        f'<p>{html.escape(_reliability_lane(row))} &middot; {html.escape(str(row.get("source_safety_state") or "unknown"))}</p>'
        "</div>"
        f'<div class="score"><strong>{score}</strong><span>/100</span></div>'
        "</div>"
        '<div class="city-metrics">'
        f'<div><span>Bracket</span><strong>{html.escape(side["bracket"])}</strong></div>'
        f'<div><span>Best Side</span><strong>{html.escape(side["side"])} {side["probability"]}%</strong></div>'
        f'<div><span>Crowd Favorite</span><strong>{html.escape(_crowd_favorite_text(row))}</strong></div>'
        f'<div><span>Market Source</span><strong>{html.escape(_market_source_text(row))}</strong></div>'
        "</div>"
        '<div class="city-metrics">'
        f'<div><span>Current Low</span><strong>{_esc_temp(row.get("low_so_far_f"))}</strong></div>'
        f'<div><span>Forecast Low</span><strong>{_esc_temp(row.get("forecast_low_f"))}</strong></div>'
        f'<div><span>Low Time</span><strong>{html.escape(_event_time_text(row.get("forecast_low_time")))}</strong></div>'
        "</div>"
        f'<p class="risk-line">{html.escape(hidden_reason or _stability_note(row))}</p>'
        '<div class="fresh-row">'
        f'<span>Fresh: {html.escape(_freshness_text(row))}</span>'
        f"{_source_details(row)}"
        "</div>"
        "</article>"
    )

def _best_side_for_selected_bucket(row: dict[str, Any], signals: list[dict[str, Any]]) -> dict[str, Any]:
    bracket = _fmt_range(row)
    matching = [signal for signal in signals if (signal.get("contract_title") or _fmt_range(signal)) == row.get("contract_title")]
    if not matching:
        matching = [signal for signal in signals if _fmt_range(signal) == bracket]
    if matching:
        best = max(matching, key=lambda signal: float(signal.get("estimated_probability") or 0))
        return {
            "bracket": str(best.get("contract_title") or _fmt_range(best)),
            "side": str(best.get("side") or "YES"),
            "probability": int(best.get("estimated_probability") or 0),
        }
    yes_probability = int(row.get("estimated_probability") or 0)
    no_probability = max(0, min(100, 100 - yes_probability))
    if no_probability > yes_probability:
        return {"bracket": bracket, "side": "NO", "probability": no_probability}
    return {"bracket": bracket, "side": "YES", "probability": yes_probability}

def _hidden_city_section(
    rows: list[dict[str, Any]],
    signal_lookup: dict[str, list[dict[str, Any]]],
    note: str = "Hidden by default because the data is stale, incomplete, volatile, or the remaining low window is too jumpy.",
) -> str:
    return (
        '<details class="panel hidden-toggle">'
        f'<summary>Show Avoided / Volatile Cities ({len(rows)})</summary>'
        f'<p class="note">{html.escape(note)}</p>'
        + _city_rank_cards(rows, signal_lookup)
        + "</details>"
    )

def _stability_note(row: dict[str, Any]) -> str:
    return (
        f"Volatility {row.get('volatility_risk_score', 0)}/100 / "
        f"cooling risk {row.get('cooling_risk_score', 0)}/100 / "
        f"confidence {row.get('weather_confidence_score', 0)}/100"
    )

def _hide_reason(row: dict[str, Any]) -> str:
    reasons = []
    if _city_reliability_score(row) < 45:
        reasons.append("low reliability score")
    if float(row.get("volatility_risk_score") or 0) >= 70:
        reasons.append("volatile temperature path")
    if float(row.get("cooling_risk_score") or 0) >= 65:
        reasons.append("remaining low-window risk")
    if float(row.get("weather_confidence_score") or 0) < 55:
        reasons.append("weak source confidence")
    if row.get("forecast_low_f") is None:
        reasons.append("missing forecast low")
    if row.get("latest_observation_time") is None and row.get("source_safety_state") != "FUTURE_FORECAST":
        reasons.append("missing fresh observation")
    return "Hidden: " + ", ".join(reasons) if reasons else ""

def _freshness_text(row: dict[str, Any]) -> str:
    latest = row.get("latest_observation_time") or row.get("forecast_generated_at") or row.get("market_local_time")
    if not latest:
        return "n/a"
    return str(latest)

def _source_details(row: dict[str, Any]) -> str:
    sources = [
        ("Kalshi page", row.get("kalshi_url")),
        ("NWS CLI", row.get("cli_source_url")),
        ("NWS hourly forecast", row.get("forecast_source_url")),
        ("NWS forecast graph", row.get("forecast_graph_url")),
    ]
    station = row.get("official_location") or row.get("station_name") or "n/a"
    station_id = row.get("station_id") or "n/a"
    lines = [
        f"<li><strong>Official station:</strong> {html.escape(str(station))} ({html.escape(str(station_id))})</li>",
        f"<li><strong>Climate product:</strong> {html.escape(str(row.get('official_climate_product') or 'n/a'))}</li>",
        f"<li><strong>Market date:</strong> {html.escape(str(row.get('market_date') or 'n/a'))}</li>",
        f"<li><strong>Final CLI status:</strong> {html.escape(str(row.get('settlement_source_status') or 'unknown'))}</li>",
        f"<li><strong>Market observation:</strong> {html.escape(_market_source_text(row))} / {html.escape(_crowd_favorite_text(row))}</li>",
    ]
    for label, url in sources:
        if url:
            lines.append(f'<li><a href="{html.escape(str(url), quote=True)}">{html.escape(label)}</a></li>')
    return (
        '<details class="sources">'
        "<summary>Sources used</summary>"
        "<ul>"
        + "".join(lines)
        + "</ul>"
        "</details>"
    )
    return enriched

def _stat_card(label: str, value: str, note: str) -> str:
    return (
        '<div class="stat">'
        f"<strong>{html.escape(value)}</strong>"
        f"<span>{html.escape(label)}</span>"
        f"<small>{html.escape(note)}</small>"
        "</div>"
    )

def _call_section(title: str, calls: list[dict[str, Any]], subtitle: str, empty: str) -> str:
    body = "".join(_call_card(call) for call in calls) if calls else f'<p class="empty">{html.escape(empty)}</p>'
    return (
        '<section class="panel">'
        f'<div class="panel-head"><h2>{html.escape(title)}</h2><span>{html.escape(subtitle)}</span></div>'
        f'<div class="cards">{body}</div>'
        "</section>"
    )

def _call_card(call: dict[str, Any]) -> str:
    tone = "good" if call["reliability"] == "RELIABLE" else "warn" if call["reliability"] == "REVIEW" else "bad"
    warnings = call.get("warnings") or []
    warning = warnings[0] if warnings else _call_reason(call)
    return (
        f'<article class="call-card {tone}">'
        '<div class="call-title">'
        f'<span class="badge">{html.escape(call["reliability"])}</span>'
        f'<strong>{html.escape(str(call.get("city")))} {html.escape(str(call.get("side")))}</strong>'
        "</div>"
        f'<h3>{html.escape(str(call.get("contract_title") or "n/a"))}</h3>'
        '<div class="metric-row">'
        f'<div><b>{call["side_probability"]}%</b><span>model chance</span></div>'
        f'<div><b>{call["fail_risk"]}%</b><span>fail risk</span></div>'
        f'<div><b>{call["side_price"]:.0f}c</b><span>price</span></div>'
        f'<div><b>{call["value_gap"]:+.0f}</b><span>gap</span></div>'
        "</div>"
        '<dl class="facts">'
        f'<div><dt>Low</dt><dd>{_esc_temp(call.get("low_so_far_f"))}</dd></div>'
        f'<div><dt>Forecast</dt><dd>{_esc_temp(call.get("forecast_low_f"))}</dd></div>'
        f'<div><dt>Obs</dt><dd>{html.escape(_short_time(call.get("latest_observation_time")))}</dd></div>'
        f'<div><dt>Risk</dt><dd>vol {call.get("volatility_risk_score", 0)} / cool {call.get("cooling_risk_score", 0)}</dd></div>'
        f'<div><dt>Source</dt><dd>{html.escape(str(call.get("source_safety_state") or "unknown"))}</dd></div>'
        f'<div><dt>Bucket</dt><dd>{html.escape(str(call.get("bucket_state") or "unknown"))}</dd></div>'
        f'<div><dt>Confidence</dt><dd>{call.get("weather_confidence_score", 0)}/100</dd></div>'
        f'<div><dt>Blocked</dt><dd>{html.escape(_fmt_bool(call.get("blocked_from_near_misses")))}</dd></div>'
        "</dl>"
        f'<p class="reason">{html.escape(str(warning))}</p>'
        "</article>"
    )

def _call_reason(call: dict[str, Any]) -> str:
    if call.get("active_low_window"):
        return "Low-temperature window is active; treat this as live tracking until final CLI arrives."
    if call.get("source_safety_state") == "FINAL_CLI_AVAILABLE":
        return "Final CLI source is available; still research-only and not financial advice."
    return "Final source unavailable or market data should be verified before acting."

def _city_table(rows: list[dict[str, Any]]) -> str:
    headers = ["City", "Lane", "Label", "Bucket", "Crowd", "Price", "Prob", "Edge", "Low", "Forecast", "Low Time", "Obs"]
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td><strong>{html.escape(str(row.get('city', 'n/a')))}</strong></td>"
            f"<td>{html.escape(_reliability_lane(row))}</td>"
            f"<td>{html.escape(str(row.get('final_label', 'n/a')))}</td>"
            f"<td>{html.escape(_fmt_range(row))}</td>"
            f"<td>{html.escape(_crowd_favorite_text(row))}</td>"
            f"<td>{html.escape(_fmt_price(row.get('kalshi_price')))}</td>"
            f"<td>{html.escape(_fmt_percent(row.get('estimated_probability')))}</td>"
            f"<td>{html.escape(str(row.get('estimated_edge_score', 0)))}</td>"
            f"<td>{_esc_temp(row.get('low_so_far_f'))}</td>"
            f"<td>{_esc_temp(row.get('forecast_low_f'))}</td>"
            f"<td>{html.escape(_event_time_text(row.get('forecast_low_time')))}</td>"
            f"<td>{html.escape(_short_time(row.get('latest_observation_time')))}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        + "".join(f"<th>{html.escape(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )

def _short_time(value: Any) -> str:
    if not value:
        return "n/a"
    text = str(value)
    return text[11:16] + "Z" if "T" in text else text

def _event_time_text(value: Any) -> str:
    if not value:
        return "n/a"
    text = str(value)
    if "T" in text:
        return text[11:16]
    return text

def _esc_temp(value: Any) -> str:
    return html.escape(_fmt_temp(value))

def _crowd_favorite_text(row: dict[str, Any]) -> str:
    favorite = row.get("api_crowd_favorite")
    price = row.get("api_crowd_price")
    if not favorite:
        return "n/a"
    if price is None:
        return str(favorite)
    return f"{favorite} @ {float(price):.0f}c"

def _market_source_text(row: dict[str, Any]) -> str:
    source = row.get("market_data_source")
    if source == "kalshi_api":
        return "API Market Data"
    if source == "kalshi_api_unavailable":
        return "API unavailable"
    return "Visible Page"

def _dashboard_css() -> str:
    return """
:root {
  color-scheme: light;
  --bg: #f4f6f8;
  --panel: #ffffff;
  --text: #17202a;
  --muted: #627083;
  --line: #d9e0e7;
  --good: #13795b;
  --good-bg: #e7f6ef;
  --warn: #9a6700;
  --warn-bg: #fff4d6;
  --bad: #b42318;
  --bad-bg: #ffe9e6;
  --ink: #24364b;
  --soft: #f8fafc;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Arial, Helvetica, sans-serif;
  background: var(--bg);
  color: var(--text);
}
.shell { max-width: 1180px; margin: 0 auto; padding: 24px; }
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 18px;
}
h1 { margin: 0; font-size: 32px; letter-spacing: 0; }
h2 { margin: 0; font-size: 18px; }
h3 { margin: 12px 0; font-size: 18px; }
p { color: var(--muted); margin: 6px 0 0; }
.note { font-size: 14px; line-height: 1.45; margin-bottom: 14px; }
.status-strip { display: grid; grid-template-columns: repeat(4, minmax(118px, 1fr)); gap: 10px; }
.stat {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  min-width: 130px;
}
.stat strong { display: block; font-size: 24px; color: var(--ink); }
.stat span, .stat small { display: block; color: var(--muted); font-size: 12px; margin-top: 2px; }
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; margin-bottom: 12px; }
.panel-head span { color: var(--muted); font-size: 13px; }
.compact-panel { padding-bottom: 10px; }
.city-list { display: grid; gap: 12px; }
.city-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px 16px;
  background: #fff;
}
.city-card.stable { border-left: 5px solid var(--good); }
.city-card.caution { border-left: 5px solid var(--warn); }
.city-card.hidden-risk { border-left: 5px solid var(--bad); }
.city-main {
  display: grid;
  grid-template-columns: 42px minmax(160px, 1fr) auto;
  align-items: center;
  gap: 12px;
}
.rank {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--soft);
  border: 1px solid var(--line);
  color: var(--ink);
  font-weight: 700;
}
.city-copy h3 { margin: 0; font-size: 20px; }
.city-copy p { font-size: 13px; }
.score { text-align: right; color: var(--muted); }
.score strong { font-size: 28px; color: var(--ink); }
.city-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin: 14px 0 10px;
}
.city-metrics div {
  background: var(--soft);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 10px;
  min-width: 0;
}
.city-metrics span {
  display: block;
  color: var(--muted);
  font-size: 11px;
  margin-bottom: 4px;
}
.city-metrics strong { display: block; font-size: 17px; overflow-wrap: anywhere; }
.risk-line { font-size: 13px; line-height: 1.4; }
.fresh-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 13px;
}
.sources { min-width: 180px; }
.sources summary, .hidden-toggle summary {
  cursor: pointer;
  color: var(--ink);
  font-weight: 700;
}
.sources ul { margin: 8px 0 0; padding-left: 18px; color: var(--muted); }
.sources li { margin: 4px 0; }
a { color: #1b64a0; }
.hidden-toggle summary { font-size: 17px; }
.empty { padding: 18px; border: 1px dashed var(--line); border-radius: 8px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { color: var(--muted); font-weight: 700; background: #f7f9fb; }
@media (max-width: 980px) {
  .topbar { display: block; }
  .status-strip { grid-template-columns: repeat(2, 1fr); margin-top: 12px; }
  .city-metrics { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .shell { padding: 14px; }
  .status-strip, .city-metrics { grid-template-columns: 1fr; }
  .city-main { grid-template-columns: 36px 1fr; }
  .score { grid-column: 1 / -1; text-align: left; }
  .fresh-row { display: block; }
  .sources { margin-top: 10px; }
}
"""


def build_signal_report(signals: list[dict[str, Any]]) -> str:
    ranked = sorted(signals, key=lambda row: row.get("estimated_edge_score", 0), reverse=True)
    lines = [
        "# Kalshi Low Weather YES/NO Research Signals",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "> Research only. Not financial advice. This tool does not place trades.",
        "",
    ]
    useful = [row for row in ranked if row.get("signal_label") in {"WATCH", "LEAN"}]
    if not useful:
        lines.extend(["No WATCH or LEAN signals found.", ""])
        blocked = [row for row in ranked if row.get("blocked_from_near_misses")]
        useful = [row for row in ranked if not row.get("blocked_from_near_misses")][:10]
        if blocked:
            lines.extend([f"Blocked/danger signals hidden from near-misses: {len(blocked)}", ""])
        if useful:
            lines.extend(["Top near-misses:", ""])

    for index, row in enumerate(useful[:30], start=1):
        lines.extend(
            [
                f"## {index}. {row.get('city')} {row.get('side')} - {row.get('signal_label')}",
                "",
                f"- Contract: {row.get('contract_title') or 'n/a'}",
                f"- Bucket: {_fmt_range(row)}",
                f"- Side price: {_fmt_price(row.get('side_price'))}",
                f"- Estimated side probability: {_fmt_percent(row.get('estimated_probability'))}",
                f"- Edge score: {row.get('estimated_edge_score', 0)}/100",
                f"- Official station/location: {row.get('official_location') or 'n/a'}",
                f"- Source safety state: {row.get('source_safety_state') or 'unknown'}",
                f"- Bucket state: {row.get('bucket_state') or 'unknown'}",
                f"- NWS CLI low: {_fmt_temp(row.get('cli_low_f'))}",
                f"- Raw low so far: {_fmt_temp(row.get('raw_low_so_far_f'))}",
                f"- Rounded/market low so far: {_fmt_temp(row.get('low_so_far_f'))}",
                f"- Latest observation: {row.get('latest_observation_time') or 'n/a'}",
                f"- Market local time: {row.get('market_local_time') or 'n/a'}",
                f"- Active low-temperature window: {_fmt_bool(row.get('active_low_window'))}",
                f"- Settlement source status: {row.get('settlement_source_status') or 'unknown'}",
                f"- CLI source URL: {row.get('cli_source_url') or 'n/a'}",
                f"- Forecast source URL: {row.get('forecast_source_url') or 'n/a'}",
                f"- Hourly forecast graph URL: {row.get('forecast_graph_url') or 'n/a'}",
                f"- Weather confidence: {row.get('weather_confidence_score', 0)}/100",
                f"- Liquidity risk: {row.get('liquidity_risk_score', 0)}/100",
                "",
                "**Reasoning**",
                "",
            ]
        )
        for reason in row.get("reasoning", []):
            lines.append(f"- {reason}")
        if row.get("warnings"):
            lines.extend(["", "**Warnings**", ""])
            for warning in row["warnings"]:
                lines.append(f"- {warning}")
        lines.append("")
    return "\n".join(lines)


def build_temperature_confidence_report(rows: list[dict[str, Any]]) -> str:
    ranked = sorted(rows, key=lambda row: row.get("weather_confidence_score", 0), reverse=True)
    lines = [
        "# Low Temperature Confidence Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "> Settlement-source confidence only. Use this to decide whether the temperature read is trustworthy.",
        "",
    ]
    for row in ranked:
        lines.extend(
            [
                f"## {row.get('city')} - {row.get('weather_confidence_score', 0)}/100",
                "",
                f"- Official station/location: {row.get('official_location') or row.get('station_name') or 'n/a'}",
                f"- Official station id: {row.get('station_id') or 'n/a'}",
                f"- Market date: {row.get('market_date') or 'n/a'}",
                f"- Market local time: {row.get('market_local_time') or 'n/a'}",
                f"- NWS climate product: {row.get('official_climate_product') or 'n/a'}",
                f"- Settlement source status: {row.get('settlement_source_status') or 'unknown'}",
                f"- Source safety state: {row.get('source_safety_state') or 'unknown'}",
                f"- Bucket state: {row.get('bucket_state') or 'unknown'}",
                f"- Active low-temperature window: {_fmt_bool(row.get('active_low_window'))}",
                f"- Analysis source status: {row.get('analysis_source_status') or 'unknown'}",
                f"- Hourly forecast status: {row.get('forecast_source_status') or 'unknown'}",
                f"- Hourly forecast generated: {row.get('forecast_generated_at') or 'n/a'}",
                f"- NWS CLI low: {_fmt_temp(row.get('cli_low_f'))}",
                f"- Current temp: {_fmt_temp(row.get('current_temp_f'))}",
                f"- Raw low so far: {_fmt_temp(row.get('raw_low_so_far_f'))}",
                f"- Low so far: {_fmt_temp(row.get('low_so_far_f'))}",
                f"- Latest observation: {row.get('latest_observation_time') or 'n/a'}",
                f"- Forecast low: {_fmt_temp(row.get('forecast_low_f'))}",
                f"- Volatility risk: {row.get('volatility_risk_score', 0)}/100",
                f"- Cooling risk: {row.get('cooling_risk_score', 0)}/100",
                "",
            ]
        )
    return "\n".join(lines)

def build_city_reliability_report(rows: list[dict[str, Any]], signals: list[dict[str, Any]]) -> str:
    ranked = sorted(rows, key=_city_reliability_score, reverse=True)
    lines = [
        "# City Reliability Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "> Research only. This ranks source quality and weather stability before any YES/NO edge. It is not betting advice.",
        "",
    ]
    if not ranked:
        lines.extend(["No city reliability rows generated.", ""])
        return "\n".join(lines)

    for index, row in enumerate(ranked, start=1):
        best_signal = _best_reviewable_signal(row.get("city"), signals)
        lines.extend(
            [
                f"## {index}. {row.get('city', 'Unknown city')} - {_city_reliability_score(row)}/100",
                "",
                f"- Reliability lane: {_reliability_lane(row)}",
                f"- Best reviewable side signal: {_fmt_signal(best_signal)}",
                f"- Official station/location: {row.get('official_location') or row.get('station_name') or 'n/a'}",
                f"- Official station id: {row.get('station_id') or 'n/a'}",
                f"- Market date: {row.get('market_date') or 'n/a'}",
                f"- Source safety state: {row.get('source_safety_state') or 'unknown'}",
                f"- Settlement source status: {row.get('settlement_source_status') or 'unknown'}",
                f"- Analysis data status: {row.get('analysis_source_status') or 'unknown'}",
                f"- Hourly forecast status: {row.get('forecast_source_status') or 'unknown'}",
                f"- Hourly forecast generated: {row.get('forecast_generated_at') or 'n/a'}",
                f"- Hourly forecast graph URL: {row.get('forecast_graph_url') or 'n/a'}",
                f"- Active low-temperature window: {_fmt_bool(row.get('active_low_window'))}",
                f"- Weather confidence: {row.get('weather_confidence_score', 0)}/100",
                f"- Volatility risk: {row.get('volatility_risk_score', 0)}/100",
                f"- Cooling risk: {row.get('cooling_risk_score', 0)}/100",
                f"- Current temp: {_fmt_temp(row.get('current_temp_f'))}",
                f"- Rounded/market low so far: {_fmt_temp(row.get('low_so_far_f'))}",
                f"- Forecast low: {_fmt_temp(row.get('forecast_low_f'))}",
                f"- Latest observation: {row.get('latest_observation_time') or 'n/a'}",
                "",
            ]
        )
        warnings = row.get("warnings", [])
        if warnings:
            lines.extend(["**Reliability warnings**", ""])
            for warning in warnings[:5]:
                lines.append(f"- {warning}")
            lines.append("")
    return "\n".join(lines)

def _city_reliability_score(row: dict[str, Any]) -> int:
    score = float(row.get("weather_confidence_score") or 0)
    score -= float(row.get("volatility_risk_score") or 0) * 0.35
    score -= float(row.get("cooling_risk_score") or 0) * 0.25
    is_future = row.get("market_day_state") == "future" or row.get("source_safety_state") == "FUTURE_FORECAST"
    if row.get("active_low_window") and not is_future:
        score -= 12
    state = row.get("source_safety_state")
    if state == "FINAL_CLI_AVAILABLE":
        score += 12
    elif state == "LIVE_OBS_PRELIMINARY":
        score += 8
    elif state == "CLI_STALE":
        score -= 8
    elif state == "FUTURE_FORECAST":
        score -= 12
    elif state == "FORECAST_ONLY":
        score -= 20
    if row.get("latest_observation_time") is None and not is_future:
        score -= 10
    if row.get("forecast_source_status") in {"same_day_hourly_forecast", "future_hourly_forecast"}:
        score += 7
    return int(max(0, min(100, round(score))))

def _reliability_lane(row: dict[str, Any]) -> str:
    score = _city_reliability_score(row)
    if row.get("source_safety_state") == "FUTURE_FORECAST":
        return "TOMORROW_FORECAST"
    if score >= 80:
        return "HIGH_SOURCE_CONFIDENCE"
    if row.get("source_safety_state") == "LIVE_OBS_PRELIMINARY" and row.get("forecast_source_status") == "same_day_hourly_forecast":
        return "LIVE_NWS_TRACKING"
    if score >= 60:
        return "REVIEW_WITH_CAUTION"
    return "LOW_RELIABILITY"

def _best_reviewable_signal(city: str | None, signals: list[dict[str, Any]]) -> dict[str, Any] | None:
    city_signals = [
        signal
        for signal in signals
        if signal.get("city") == city and not signal.get("blocked_from_near_misses")
    ]
    if not city_signals:
        return None
    return max(city_signals, key=lambda signal: signal.get("estimated_edge_score", 0))

def _fmt_signal(signal: dict[str, Any] | None) -> str:
    if not signal:
        return "none"
    return (
        f"{signal.get('side')} {signal.get('contract_title') or 'n/a'} "
        f"({signal.get('signal_label')}, edge {signal.get('estimated_edge_score', 0)}/100)"
    )


def build_markdown_report(rows: list[dict[str, Any]]) -> str:
    ranked = sorted(rows, key=lambda row: row.get("estimated_edge_score", 0), reverse=True)
    lines = [
        "# Kalshi Low Weather Scout Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "> Research only. This tool does not place trades and does not use paid APIs.",
        "",
    ]
    if not ranked:
        lines.extend(["No signals generated.", ""])
        return "\n".join(lines)

    for index, row in enumerate(ranked, start=1):
        title = row.get("market_title") or row.get("contract_title") or "Market not found"
        lines.extend(
            [
                f"## {index}. {row.get('city', 'Unknown city')} - {row.get('final_label', 'WAIT')}",
                "",
                f"- Market/contract: {title}",
                f"- Official station/location: {row.get('official_location') or row.get('station_name') or 'n/a'}",
                f"- Official station id: {row.get('station_id') or 'n/a'}",
                f"- Market date: {row.get('market_date') or 'n/a'}",
                f"- Market local time: {row.get('market_local_time') or 'n/a'}",
                f"- NWS climate product: {row.get('official_climate_product') or 'n/a'}",
                f"- Settlement source status: {row.get('settlement_source_status') or 'unknown'}",
                f"- Source safety state: {row.get('source_safety_state') or 'unknown'}",
                f"- Bucket state: {row.get('bucket_state') or 'unknown'}",
                f"- Active low-temperature window: {_fmt_bool(row.get('active_low_window'))}",
                f"- Analysis source status: {row.get('analysis_source_status') or 'unknown'}",
                f"- Hourly forecast status: {row.get('forecast_source_status') or 'unknown'}",
                f"- NWS CLI low: {_fmt_temp(row.get('cli_low_f'))}",
                f"- Current temp: {_fmt_temp(row.get('current_temp_f'))}",
                f"- Raw low so far: {_fmt_temp(row.get('raw_low_so_far_f'))}",
                f"- Low so far: {_fmt_temp(row.get('low_so_far_f'))}",
                f"- Latest observation: {row.get('latest_observation_time') or 'n/a'}",
                f"- Forecast low: {_fmt_temp(row.get('forecast_low_f'))}",
                f"- Forecast low time: {_event_time_text(row.get('forecast_low_time'))}",
                f"- CLI source URL: {row.get('cli_source_url') or 'n/a'}",
                f"- Forecast source URL: {row.get('forecast_source_url') or 'n/a'}",
                f"- Hourly forecast graph URL: {row.get('forecast_graph_url') or 'n/a'}",
                f"- Kalshi bucket: {_fmt_range(row)}",
                f"- Kalshi price: {_fmt_price(row.get('kalshi_price'))}",
                f"- Market data source: {_market_source_text(row)}",
                f"- API crowd favorite: {_crowd_favorite_text(row)}",
                f"- Estimated probability: {_fmt_percent(row.get('estimated_probability'))}",
                f"- Visible implied probability: {_fmt_probability(row.get('implied_probability'))}",
                f"- Weather confidence: {row.get('weather_confidence_score', 0)}/100",
                f"- Volatility risk: {row.get('volatility_risk_score', 0)}/100",
                f"- Cooling risk: {row.get('cooling_risk_score', 0)}/100",
                f"- Liquidity risk: {row.get('liquidity_risk_score', 0)}/100",
                f"- Market crowding: {row.get('market_crowding_score', 0)}/100",
                f"- Estimated edge: {row.get('estimated_edge_score', 0)}/100",
                "",
                "**Reasoning**",
                "",
            ]
        )
        for reason in row.get("reasoning", []) or ["No reasoning available."]:
            lines.append(f"- {reason}")
        warnings = row.get("warnings", [])
        if warnings:
            lines.extend(["", "**Warnings**", ""])
            for warning in warnings:
                lines.append(f"- {warning}")
        lines.append("")
    return "\n".join(lines)


def _fmt_temp(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.1f}F"


def _fmt_price(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.0f} cents"


def _fmt_percent(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.0f}%"


def _fmt_probability(value: Any) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.0f}%"


def _fmt_bool(value: Any) -> str:
    if value is None:
        return "unknown"
    return "yes" if bool(value) else "no"


def _fmt_range(row: dict[str, Any]) -> str:
    low = row.get("range_low_f")
    high = row.get("range_high_f")
    if low is None and high is None:
        return _fmt_temp(row.get("threshold_f"))
    if low is None:
        return f"{float(high):.0f}F or below"
    if high is None:
        return f"{float(low):.0f}F or above"
    return f"{float(low):.0f}F to {float(high):.0f}F"
