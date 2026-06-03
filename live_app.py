from __future__ import annotations

import hashlib
import hmac
import html
import os
from urllib.parse import parse_qs

from fastapi import Cookie, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from live_dashboard import LiveDashboardCache

COOKIE_NAME = "kalshi_live_session"

app = FastAPI(title="Kalshi Weather Live Dashboard")
live_cache = LiveDashboardCache()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def dashboard(kalshi_live_session: str | None = Cookie(default=None)) -> HTMLResponse:
    if not _authorized(kalshi_live_session):
        return HTMLResponse(_login_html(), status_code=401)
    return HTMLResponse(_dashboard_html())


@app.post("/login")
async def login(request: Request) -> RedirectResponse:
    body = (await request.body()).decode("utf-8", errors="replace")
    password = parse_qs(body).get("password", [""])[0]
    if not _password_configured() or not hmac.compare_digest(password, _password()):
        return RedirectResponse("/", status_code=303)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        _session_token(),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 18,
    )
    return response


@app.get("/api/live")
def api_live(kalshi_live_session: str | None = Cookie(default=None)) -> JSONResponse:
    if not _authorized(kalshi_live_session):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse(live_cache.get())


def _password_configured() -> bool:
    return bool(_password())


def _password() -> str:
    return os.environ.get("LIVE_DASHBOARD_PASSWORD", "")


def _authorized(cookie: str | None) -> bool:
    if not _password_configured():
        return True
    return bool(cookie) and hmac.compare_digest(cookie, _session_token())


def _session_token() -> str:
    return hashlib.sha256(("kalshi-live-dashboard:" + _password()).encode("utf-8")).hexdigest()


def _login_html() -> str:
    warning = "" if _password_configured() else "<p>Set LIVE_DASHBOARD_PASSWORD before exposing this dashboard.</p>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kalshi Weather Live Login</title>
  <style>{_css()}</style>
</head>
<body>
  <main class="login">
    <h1>Weather Live</h1>
    <p>Research only. No trading or order placement.</p>
    {warning}
    <form method="post" action="/login">
      <label>Password <input type="password" name="password" autofocus></label>
      <button type="submit">Open Dashboard</button>
    </form>
  </main>
</body>
</html>"""


def _dashboard_html() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kalshi Weather Live</title>
  <style>{_css()}</style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div>
        <h1>Weather Live</h1>
        <p>Las Vegas, Phoenix, San Antonio. Research only. No trading or order placement.</p>
      </div>
      <div class="status">
        <strong id="statusText">Loading...</strong>
        <span id="updatedText">Waiting for first pull</span>
      </div>
    </header>
    <section id="cards" class="cards"></section>
    <footer class="support">
      <a href="https://www.buymeacoffee.com/jeanmatias" target="_blank" rel="noopener noreferrer" aria-label="Buy Jean Matias a coffee">
        <img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=jeanmatias&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff" alt="Buy me a coffee">
      </a>
    </footer>
  </main>
  <script>{_javascript()}</script>
</body>
</html>"""


def _css() -> str:
    return """
:root {
  color-scheme: light;
  --bg: #f5f7fa;
  --panel: #fff;
  --line: #d7e0ea;
  --ink: #152235;
  --muted: #64748b;
  --good: #147a54;
  --good-bg: #e9f8f0;
  --warn: #9a6700;
  --warn-bg: #fff5d9;
  --bad: #b42318;
  --bad-bg: #ffe9e6;
}
* { box-sizing: border-box; }
body { margin: 0; font-family: Arial, Helvetica, sans-serif; background: var(--bg); color: var(--ink); }
.shell { max-width: 1180px; margin: 0 auto; padding: 24px; }
.topbar { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 18px; }
h1 { margin: 0; font-size: 32px; letter-spacing: 0; }
p { margin: 6px 0 0; color: var(--muted); }
.status, .login {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
}
.status strong, .status span { display: block; }
.cards { display: grid; gap: 14px; }
.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-left: 5px solid var(--warn);
  border-radius: 8px;
  padding: 16px;
}
.card.good { border-left-color: var(--good); }
.card.bad { border-left-color: var(--bad); }
.card h2 { margin: 0; font-size: 22px; }
.card-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.badge { border-radius: 999px; padding: 5px 9px; font-size: 12px; font-weight: 700; background: var(--warn-bg); color: var(--warn); }
.good .badge { background: var(--good-bg); color: var(--good); }
.bad .badge { background: var(--bad-bg); color: var(--bad); }
.metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 14px; }
.metric { background: #f8fafc; border: 1px solid var(--line); border-radius: 6px; padding: 10px; min-width: 0; }
.metric span { display: block; color: var(--muted); font-size: 11px; margin-bottom: 5px; }
.metric strong { display: block; font-size: 18px; overflow-wrap: anywhere; }
.note { margin-top: 12px; font-weight: 700; color: var(--ink); }
.warnings { margin-top: 10px; color: var(--bad); font-size: 13px; }
.login { max-width: 420px; margin: 12vh auto; }
label, input, button { display: block; width: 100%; }
input, button { margin-top: 8px; padding: 10px; border-radius: 6px; border: 1px solid var(--line); font: inherit; }
button { background: var(--ink); color: #fff; cursor: pointer; }
.support { display: flex; justify-content: center; margin-top: 22px; }
.support img { display: block; height: 42px; max-width: 220px; }
@media (max-width: 850px) {
  .topbar { display: block; }
  .status { margin-top: 12px; }
  .metrics { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 560px) {
  .shell { padding: 14px; }
  .metrics { grid-template-columns: 1fr; }
}
"""


def _javascript() -> str:
    return """
const cards = document.getElementById('cards');
const statusText = document.getElementById('statusText');
const updatedText = document.getElementById('updatedText');

function fmtTemp(value) {
  return value === null || value === undefined ? 'n/a' : `${Number(value).toFixed(1)}F`;
}

function fmtRate(value) {
  return value === null || value === undefined ? 'n/a' : `${Number(value).toFixed(1)}F/hr`;
}

function fmtPrice(bucket) {
  if (!bucket) return 'n/a';
  const price = bucket.yes_price === null || bucket.yes_price === undefined ? 'n/a' : `${Number(bucket.yes_price).toFixed(0)}c`;
  return `${bucket.label || 'unknown'} @ ${price}`;
}

function tone(city) {
  if (city.false_pump_warning || city.reachability_label === 'CROSSED_ABOVE') return 'bad';
  if (city.market_weather_alignment === 'ALIGNED' && ['REACHED', 'REACHABLE'].includes(city.reachability_label)) return 'good';
  return 'warn';
}

function render(payload) {
  const updated = payload.last_updated || payload.generated_at || 'unknown';
  statusText.textContent = `Updated ${new Date(updated).toLocaleTimeString()}`;
  updatedText.textContent = `Backend refresh: ${payload.refresh_seconds || 60}s`;
  cards.innerHTML = (payload.cities || []).map(city => `
    <article class="card ${tone(city)}">
      <div class="card-head">
        <div>
          <h2>${escapeHtml(city.city)}</h2>
          <p>${escapeHtml(city.station_id || '')} · ${escapeHtml(city.market_date || '')}</p>
        </div>
        <span class="badge">${escapeHtml(city.reachability_label || 'n/a')}</span>
      </div>
      <div class="metrics">
        <div class="metric"><span>Winning Bucket</span><strong>${escapeHtml(fmtPrice(city.winning_bucket))}</strong></div>
        <div class="metric"><span>Second Bucket</span><strong>${escapeHtml(fmtPrice(city.second_bucket))}</strong></div>
        <div class="metric"><span>Current Temp</span><strong>${fmtTemp(city.current_temp_f)}</strong></div>
        <div class="metric"><span>High So Far</span><strong>${fmtTemp(city.high_so_far_f)}</strong></div>
        <div class="metric"><span>Raw High</span><strong>${fmtTemp(city.raw_high_so_far_f)}</strong></div>
        <div class="metric"><span>Forecast High</span><strong>${fmtTemp(city.forecast_high_f)}</strong></div>
        <div class="metric"><span>Critical Hour</span><strong>${escapeHtml(city.critical_window_et || 'n/a')}</strong></div>
        <div class="metric"><span>Market vs Weather</span><strong>${escapeHtml(city.market_weather_alignment || 'n/a')}</strong></div>
        <div class="metric"><span>Heating Pace</span><strong>${fmtRate(city.heating_rate_f_per_hour)}</strong></div>
        <div class="metric"><span>Needed Rate</span><strong>${fmtRate(city.required_rate_f_per_hour)}</strong></div>
        <div class="metric"><span>Degrees Needed</span><strong>${fmtTemp(city.degrees_needed_to_reach_bucket)}</strong></div>
        <div class="metric"><span>False Pump</span><strong>${city.false_pump_warning ? 'YES' : 'no'}</strong></div>
      </div>
      <p class="note">${escapeHtml(city.decision_note || '')}</p>
      ${(city.warnings || []).length ? `<p class="warnings">${escapeHtml(city.warnings[0])}</p>` : ''}
    </article>
  `).join('');
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
}

async function load() {
  try {
    const response = await fetch('/api/live', {cache: 'no-store'});
    if (response.status === 401) {
      window.location.reload();
      return;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    statusText.textContent = 'Live update failed';
    updatedText.textContent = error.message;
  }
}

load();
setInterval(load, 15000);
"""
