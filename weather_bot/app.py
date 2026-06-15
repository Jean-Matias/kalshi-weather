from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from weather_bot.core import bot_summaries, build_bot_snapshot, get_bot, update_bot_control


app = FastAPI(title="Weather Bot Command Center")


class BotControlUpdate(BaseModel):
    armed: bool | None = None
    contracts: int | None = None


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return DASHBOARD_HTML


@app.get("/api/bots")
def api_bots():
    return {"bots": bot_summaries()}


@app.get("/api/bots/{bot_id}/snapshot")
def api_bot_snapshot(bot_id: str, days: int = Query(default=60, ge=1, le=120)):
    try:
        bot = get_bot(bot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown bot") from exc
    return build_bot_snapshot(bot, days=days)


@app.post("/api/bots/{bot_id}/control")
def api_bot_control(bot_id: str, update: BotControlUpdate):
    try:
        control = update_bot_control(bot_id, armed=update.armed, contracts=update.contracts)
        bot = get_bot(bot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown bot") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "bot_id": bot.bot_id,
        "trading_enabled": bot.trading_enabled,
        "mode": bot.mode,
        "control": {"armed": control.armed, "contracts": control.contracts},
    }


DASHBOARD_HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Weather Bot Command Center</title>
  <style>
    :root {
      --bg: #f7f9f8;
      --surface: #ffffff;
      --surface-2: #f0f5f3;
      --text: #17211f;
      --muted: #697774;
      --border: #d9e2df;
      --teal: #0f766e;
      --teal-soft: #d9f1ed;
      --amber: #b7791f;
      --red: #b42318;
      --green: #0f7a4f;
      --shadow: 0 12px 28px rgba(15, 31, 27, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
      letter-spacing: 0;
    }
    .shell { display: grid; grid-template-columns: 258px 1fr; min-height: 100vh; }
    aside {
      border-right: 1px solid var(--border);
      background: #fbfcfb;
      padding: 22px 16px;
    }
    .brand { font-size: 15px; font-weight: 800; margin-bottom: 22px; }
    .botRow {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--surface);
      padding: 12px;
      text-align: left;
      font: inherit;
      color: var(--text);
      box-shadow: 0 1px 0 rgba(0,0,0,.03);
    }
    .botName { font-size: 14px; font-weight: 750; }
    .botMeta { margin-top: 6px; color: var(--muted); font-size: 12px; }
    main { padding: 22px; }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }
    h1 { margin: 0; font-size: 24px; line-height: 1.15; }
    .controls { display: flex; gap: 10px; align-items: center; }
    select, button {
      height: 36px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--surface);
      color: var(--text);
      font: 600 13px/1 Inter, ui-sans-serif, system-ui;
      padding: 0 11px;
    }
    button { background: var(--teal); color: white; border-color: var(--teal); }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) 360px;
      gap: 16px;
      align-items: start;
    }
    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      box-shadow: var(--shadow);
      padding: 16px;
      margin-bottom: 16px;
    }
    .panelTitle {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
      color: #31413d;
    }
    .status {
      border-radius: 999px;
      padding: 5px 9px;
      font-size: 12px;
      font-weight: 800;
      background: var(--teal-soft);
      color: var(--teal);
    }
    .stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
    .stat {
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--surface-2);
      padding: 12px;
      min-height: 76px;
    }
    .stat span { display: block; color: var(--muted); font-size: 12px; }
    .stat strong { display: block; margin-top: 8px; font-size: 22px; line-height: 1; }
    .signalBox {
      border-left: 4px solid var(--teal);
      background: #f6fbfa;
      padding: 14px;
      border-radius: 6px;
    }
    .signalBox h2 { margin: 0 0 8px; font-size: 18px; }
    .signalBox p { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.45; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--border); }
    th { color: var(--muted); font-size: 11px; text-transform: uppercase; }
    .moneyPos { color: var(--green); font-weight: 800; }
    .moneyNeg { color: var(--red); font-weight: 800; }
    .gate {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      padding: 10px 0;
      border-bottom: 1px solid var(--border);
    }
    .gate:last-child { border-bottom: 0; }
    .gateName { font-weight: 750; font-size: 13px; }
    .gateDetail { color: var(--muted); font-size: 12px; margin-top: 4px; }
    .gateStatus { font-size: 12px; font-weight: 800; color: var(--teal); }
    .gateStatus.fail { color: var(--red); }
    .gateStatus.watch { color: var(--amber); }
    .gateStatus.off { color: var(--muted); }
    .railText { color: var(--muted); font-size: 13px; line-height: 1.5; }
    .controlLine {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
      padding: 10px 0;
      border-bottom: 1px solid var(--border);
      font-size: 13px;
      font-weight: 750;
    }
    .controlLine:last-of-type { border-bottom: 0; }
    .controlLine span small {
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 500;
      line-height: 1.35;
    }
    input[type="checkbox"] {
      width: 42px;
      height: 24px;
      appearance: none;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: #dfe7e4;
      position: relative;
      cursor: pointer;
    }
    input[type="checkbox"]::after {
      content: "";
      position: absolute;
      width: 18px;
      height: 18px;
      top: 2px;
      left: 3px;
      border-radius: 999px;
      background: white;
      box-shadow: 0 1px 3px rgba(0,0,0,.18);
      transition: transform .16s ease;
    }
    input[type="checkbox"]:checked {
      background: var(--teal);
      border-color: var(--teal);
    }
    input[type="checkbox"]:checked::after { transform: translateX(17px); }
    input[type="number"] {
      width: 72px;
      height: 34px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0 8px;
      font: 700 13px/1 Inter, ui-sans-serif, system-ui;
      color: var(--text);
      background: var(--surface);
    }
    .controlActions {
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
      margin-top: 14px;
    }
    .controlNote {
      min-height: 18px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }
    @media (max-width: 980px) {
      .shell { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--border); }
      .grid { grid-template-columns: 1fr; }
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      header { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <div class="brand">Weather Bot Command Center</div>
      <button class="botRow" id="botButton" type="button">
        <div class="botName">Loading bot...</div>
        <div class="botMeta">Paper mode</div>
      </button>
    </aside>
    <main>
      <header>
        <h1>Weather Bot Command Center</h1>
        <div class="controls">
          <select id="days">
            <option value="30">30 days</option>
            <option value="60" selected>60 days</option>
          </select>
          <button id="refresh" type="button">Refresh</button>
        </div>
      </header>
      <div class="grid">
        <section>
          <div class="panel">
            <div class="panelTitle">Signal <span class="status" id="mode">Paper</span></div>
            <div class="signalBox">
              <h2 id="signalTitle">Loading signal...</h2>
              <p id="signalWhy"></p>
            </div>
          </div>
          <div class="panel">
            <div class="panelTitle">Backtest Summary</div>
            <div class="stats">
              <div class="stat"><span>Trades</span><strong id="trades">-</strong></div>
              <div class="stat"><span>Win Rate</span><strong id="winRate">-</strong></div>
              <div class="stat"><span>EV / Trade</span><strong id="ev">-</strong></div>
              <div class="stat"><span>Total P&L</span><strong id="pnl">-</strong></div>
            </div>
          </div>
          <div class="panel">
            <div class="panelTitle">Paper Trade Blotter</div>
            <table>
              <thead><tr><th>Event</th><th>Bucket</th><th>Side</th><th>Price</th><th>Net</th></tr></thead>
              <tbody id="tradesBody"></tbody>
            </table>
          </div>
        </section>
        <aside class="rightRail">
          <div class="panel">
            <div class="panelTitle">Paper Bot Controls <span class="status" id="armedPill">OFF</span></div>
            <label class="controlLine">
              <span>Paper armed<small>Turns paper signal tracking on or off. Real orders stay blocked.</small></span>
              <input id="botArmed" type="checkbox" />
            </label>
            <label class="controlLine">
              <span>Contracts<small>Simulation size for this Vegas bot.</small></span>
              <input id="contracts" type="number" min="1" max="10" step="1" value="3" />
            </label>
            <div class="controlActions">
              <button id="saveControls" type="button">Save Controls</button>
              <div class="controlNote" id="controlNote">Paper-only controls. Live trading is disabled.</div>
            </div>
          </div>
          <div class="panel">
            <div class="panelTitle">Risk Gates</div>
            <div id="gates"></div>
          </div>
          <div class="panel">
            <div class="panelTitle">Weather vs Kalshi</div>
            <p class="railText" id="weatherKalshi"></p>
          </div>
        </aside>
      </div>
    </main>
  </div>
  <script>
    const fmtMoney = cents => `${cents >= 0 ? '+' : '-'}$${Math.abs(cents / 100).toFixed(2)}`;
    const fmtCents = cents => `${cents >= 0 ? '+' : ''}${Number(cents).toFixed(2)}c`;
    const moneyClass = cents => Number(cents) >= 0 ? 'moneyPos' : 'moneyNeg';
    let currentBot = null;
    async function load() {
      const bots = await fetch('/api/bots').then(r => r.json());
      const bot = bots.bots[0];
      currentBot = bot;
      document.querySelector('.botName').textContent = bot.name;
      document.querySelector('.botMeta').textContent = `${bot.city} / ${bot.strategy_name} / h${bot.decision_hour} / ${bot.armed ? 'armed' : 'off'} / ${bot.contracts} contracts`;
      const days = document.getElementById('days').value;
      const snap = await fetch(`/api/bots/${bot.bot_id}/snapshot?days=${days}`).then(r => r.json());
      document.getElementById('mode').textContent = `${snap.mode.toUpperCase()} ${snap.armed ? 'ON' : 'OFF'}`;
      document.getElementById('armedPill').textContent = snap.armed ? 'ON' : 'OFF';
      document.getElementById('botArmed').checked = snap.armed;
      document.getElementById('contracts').value = snap.contracts;
      document.getElementById('contracts').max = snap.max_contracts;
      document.getElementById('signalTitle').textContent = snap.signal.label;
      document.getElementById('signalWhy').textContent = snap.signal.why;
      document.getElementById('trades').textContent = snap.backtest.trades;
      document.getElementById('winRate').textContent = `${snap.backtest.win_rate}%`;
      document.getElementById('ev').textContent = fmtCents(snap.backtest.ev_per_trade_cents);
      document.getElementById('ev').className = moneyClass(snap.backtest.ev_per_trade_cents);
      document.getElementById('pnl').textContent = fmtMoney(snap.backtest.total_net_cents);
      document.getElementById('pnl').className = moneyClass(snap.backtest.total_net_cents);
      document.getElementById('weatherKalshi').textContent =
        `This bot only paper-buys YES when the low-weather signal and Kalshi favorite agree. Real order placement is disabled. Current backtest uses ${snap.backtest.event_days} event-days, ${snap.contracts} contracts, and ${snap.backtest.skips} skipped days.`;
      document.getElementById('gates').innerHTML = snap.risk_gates.map(gate => `
        <div class="gate">
          <div><div class="gateName">${gate.name}</div><div class="gateDetail">${gate.detail}</div></div>
          <div class="gateStatus ${gate.status}">${gate.status.toUpperCase()}</div>
        </div>`).join('');
      document.getElementById('tradesBody').innerHTML = snap.paper_trades.map(trade => `
        <tr>
          <td>${trade.event_ticker}</td>
          <td>${trade.bucket}</td>
          <td>${trade.side}</td>
          <td>${trade.price_cents}c</td>
          <td class="${moneyClass(trade.net_cents)}">${fmtMoney(trade.net_cents)}</td>
        </tr>`).join('');
    }
    async function saveControls() {
      if (!currentBot) return;
      const contracts = Number(document.getElementById('contracts').value);
      const note = document.getElementById('controlNote');
      note.textContent = 'Saving paper controls...';
      const response = await fetch(`/api/bots/${currentBot.bot_id}/control`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          armed: document.getElementById('botArmed').checked,
          contracts
        })
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({detail: 'Could not save controls.'}));
        note.textContent = error.detail || 'Could not save controls.';
        return;
      }
      note.textContent = 'Saved. Paper bot controls updated.';
      await load();
    }
    document.getElementById('refresh').addEventListener('click', load);
    document.getElementById('days').addEventListener('change', load);
    document.getElementById('saveControls').addEventListener('click', saveControls);
    load();
  </script>
</body>
</html>
"""
