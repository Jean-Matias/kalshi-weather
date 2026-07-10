"""hotscout dashboard HTML: a single self-contained page (no external
assets) that fetches /api/board and /api/picks and auto-refreshes."""

from __future__ import annotations


def render_html() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hotscout Dashboard</title>
  <style>{_css()}</style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div>
        <p class="kicker">Hotscout</p>
        <h1>Kalshi High-Temperature Board</h1>
        <p>Las Vegas. Research only.</p>
      </div>
      <div class="statusDeck">
        <div class="status"><span>Generated</span><strong id="generatedAt">Loading</strong></div>
        <div class="status"><span>Refresh</span><strong id="refreshCountdown">--</strong></div>
      </div>
    </header>
    <section id="cards" class="cards"></section>
    <section class="picksPanel">
      <div class="picksHead">
        <strong>Picks Log</strong>
        <div id="record" class="record"></div>
      </div>
      <div class="tableWrap">
        <table id="picksTable">
          <thead>
            <tr>
              <th>City</th><th>Date</th><th>Hour</th><th>Ticker</th><th>Side</th>
              <th>Model %</th><th>Entry c</th><th>Edge</th><th>Outcome</th><th>PnL c</th>
            </tr>
          </thead>
          <tbody id="picksBody"></tbody>
        </table>
      </div>
    </section>
  </main>
  <script>{_javascript()}</script>
</body>
</html>"""


def _css() -> str:
    return """
:root {
  color-scheme: dark;
  --bg: #0a0f14;
  --panel: #111a22;
  --line: #24333f;
  --ink: #eef6f2;
  --muted: #8fa2ac;
  --good: #4fd28f;
  --good-bg: rgba(79, 210, 143, 0.15);
  --warn: #e8a53f;
  --warn-bg: rgba(232, 165, 63, 0.15);
  --bad: #ff6f61;
  --bad-bg: rgba(255, 111, 97, 0.15);
  --accent: #45c8d8;
}
* { box-sizing: border-box; }
body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, Arial, sans-serif; background: var(--bg); color: var(--ink); }
.shell { max-width: 1180px; margin: 0 auto; padding: 26px 22px 40px; }
.topbar { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 18px; }
.kicker { color: var(--accent); font-size: 12px; font-weight: 800; letter-spacing: 0.1em; margin: 0 0 6px; text-transform: uppercase; }
h1 { margin: 0; font-size: 28px; }
p { margin: 6px 0 0; color: var(--muted); }
.statusDeck { display: flex; gap: 10px; }
.status { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 10px 14px; min-width: 120px; }
.status span { display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; font-weight: 700; }
.status strong { display: block; font-size: 15px; margin-top: 3px; }
.cards { display: grid; gap: 16px; }
.card { background: var(--panel); border: 1px solid var(--line); border-top: 4px solid var(--warn); border-radius: 8px; padding: 16px; }
.card.validated { border-top-color: var(--good); }
.card.invalidated { border-top-color: var(--bad); }
.cardHead { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.cardHead h2 { margin: 0; font-size: 20px; }
.obsStrip { display: flex; gap: 10px; flex-wrap: wrap; margin: 10px 0; }
.obsItem { background: #0c141b; border: 1px solid var(--line); border-radius: 7px; padding: 8px 10px; min-width: 110px; }
.obsItem span { display: block; font-size: 10px; color: var(--muted); text-transform: uppercase; font-weight: 800; }
.obsItem strong { display: block; font-size: 16px; margin-top: 3px; }
.badge { border-radius: 999px; padding: 6px 10px; font-size: 12px; font-weight: 800; white-space: nowrap; }
.badge.good { background: var(--good-bg); color: var(--good); }
.badge.bad { background: var(--bad-bg); color: var(--bad); }
.tableWrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 7px 8px; text-align: left; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { color: var(--muted); font-size: 11px; text-transform: uppercase; font-weight: 800; }
.chip { border-radius: 999px; padding: 4px 9px; font-size: 11px; font-weight: 800; }
.chip.buy-yes { background: var(--good-bg); color: var(--good); }
.chip.buy-no { background: var(--warn-bg); color: var(--warn); }
.chip.pass { background: rgba(143, 162, 172, 0.15); color: var(--muted); }
.warnings { color: var(--warn); font-size: 12px; margin-top: 10px; }
.picksPanel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; margin-top: 18px; }
.picksHead { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px; }
.record { color: var(--muted); font-size: 13px; font-weight: 700; }
@media (max-width: 760px) {
  .topbar { flex-direction: column; }
}
"""


def _javascript() -> str:
    return """
const cardsEl = document.getElementById('cards');
const generatedAtEl = document.getElementById('generatedAt');
const refreshCountdownEl = document.getElementById('refreshCountdown');
const picksBodyEl = document.getElementById('picksBody');
const recordEl = document.getElementById('record');
let nextRefreshAt = null;

function esc(value) {
  return String(value === null || value === undefined ? '' : value).replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[ch]);
}

function pct(value) {
  return value === null || value === undefined ? 'n/a' : `${(Number(value) * 100).toFixed(1)}%`;
}

function fnum(value, digits = 1) {
  return value === null || value === undefined ? 'n/a' : Number(value).toFixed(digits);
}

function recChipClass(rec) {
  if (rec === 'BUY YES') return 'buy-yes';
  if (rec === 'BUY NO') return 'buy-no';
  return 'pass';
}

function renderCity(city) {
  const badge = city.backtest_badge || {};
  const cardTone = badge.validated ? 'validated' : 'invalidated';
  const badgeText = badge.validated
    ? `Validated: ${(Number(badge.win_rate || 0) * 100).toFixed(0)}% win, ${(Number(badge.roi || 0) * 100).toFixed(0)}% ROI, n=${badge.n_trades} (${esc(badge.window || '')})`
    : `NOT VALIDATED - recommendations disabled (n=${badge.n_trades || 0})`;
  const rows = (city.buckets || []).map(bucket => `
    <tr>
      <td>${esc(bucket.label)}</td>
      <td>${pct(bucket.model_prob)}</td>
      <td>${bucket.yes_bid_c ?? 'n/a'}c / ${bucket.yes_ask_c ?? 'n/a'}c</td>
      <td>${bucket.edge_after_fees === null || bucket.edge_after_fees === undefined ? 'n/a' : pct(bucket.edge_after_fees)}</td>
      <td><span class="chip ${recChipClass(bucket.recommendation)}">${esc(bucket.recommendation)}</span></td>
      <td>${esc(bucket.confidence)}</td>
    </tr>
  `).join('');
  return `
    <article class="card ${cardTone}">
      <div class="cardHead">
        <div>
          <h2>${esc(city.city)}</h2>
          <p>${esc(city.market_date)}</p>
        </div>
        <span class="badge ${badge.validated ? 'good' : 'bad'}">${badge.validated ? '✓' : '✗'} ${esc(badgeText)}</span>
      </div>
      <div class="obsStrip">
        <div class="obsItem"><span>Forecast High</span><strong>${fnum(city.forecast_high_f)}F</strong></div>
        <div class="obsItem"><span>High So Far</span><strong>${fnum(city.high_so_far_f)}F</strong></div>
        <div class="obsItem"><span>Heating Rate</span><strong>${fnum(city.heating_rate)}F/hr</strong></div>
      </div>
      <div class="tableWrap">
        <table>
          <thead><tr><th>Bucket</th><th>Model %</th><th>Bid/Ask</th><th>Edge</th><th>Rec</th><th>Confidence</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="6">No buckets available.</td></tr>'}</tbody>
        </table>
      </div>
      ${(city.warnings || []).length ? `<div class="warnings">${(city.warnings || []).map(esc).join(' | ')}</div>` : ''}
    </article>
  `;
}

function renderBoard(payload) {
  generatedAtEl.textContent = new Date(payload.generated_at).toLocaleTimeString();
  const ttl = Number(payload.cache_ttl_seconds || 60);
  nextRefreshAt = Date.now() + ttl * 1000;
  cardsEl.innerHTML = (payload.cities || []).map(renderCity).join('');
}

function renderPicks(payload) {
  const record = payload.record || {};
  recordEl.textContent = `Record: ${record.wins || 0}W - ${record.losses || 0}L, total PnL ${(record.total_pnl_c || 0) / 100}`;
  picksBodyEl.innerHTML = (payload.picks || []).map(pick => `
    <tr>
      <td>${esc(pick.city)}</td>
      <td>${esc(pick.market_date)}</td>
      <td>${esc(pick.decision_hour_local)}</td>
      <td>${esc(pick.market_ticker)}</td>
      <td>${esc(pick.side)}</td>
      <td>${pct(pick.model_prob)}</td>
      <td>${pick.market_price_c ?? 'n/a'}</td>
      <td>${pick.edge_after_fees === null || pick.edge_after_fees === undefined ? 'n/a' : pct(pick.edge_after_fees)}</td>
      <td>${esc(pick.outcome || 'open')}</td>
      <td>${pick.pnl_c ?? ''}</td>
    </tr>
  `).join('');
}

async function loadBoard() {
  try {
    const response = await fetch('/api/board', {cache: 'no-store'});
    renderBoard(await response.json());
  } catch (error) {
    generatedAtEl.textContent = 'error';
  }
}

async function loadPicks() {
  try {
    const response = await fetch('/api/picks', {cache: 'no-store'});
    renderPicks(await response.json());
  } catch (error) {
    recordEl.textContent = 'Picks unavailable';
  }
}

function updateCountdown() {
  if (!nextRefreshAt) { refreshCountdownEl.textContent = '--'; return; }
  const seconds = Math.max(0, Math.ceil((nextRefreshAt - Date.now()) / 1000));
  refreshCountdownEl.textContent = `${seconds}s`;
  if (seconds <= 0) {
    loadBoard();
    loadPicks();
  }
}

loadBoard();
loadPicks();
setInterval(updateCountdown, 1000);
setInterval(loadPicks, 60000);
"""
