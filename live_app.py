from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from live_dashboard import LiveDashboardCache, LiveTempMeterCache

app = FastAPI(title="Kalshi Weather Live Dashboard")
live_cache = LiveDashboardCache()
temp_meter_cache = LiveTempMeterCache()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse(_dashboard_html())


@app.get("/api/live")
def api_live() -> JSONResponse:
    return JSONResponse(live_cache.get())


@app.get("/api/temp-meter")
def api_temp_meter(city: str) -> JSONResponse:
    return JSONResponse(temp_meter_cache.get(city))


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
        <p class="kicker">Live Weather Scout</p>
        <h1>Three-City Market Board</h1>
        <p>Las Vegas, Phoenix, San Antonio. Research only. No trading or order placement.</p>
      </div>
      <div class="statusDeck">
        <div class="status">
          <span>Last pull</span>
          <strong id="statusText">Loading</strong>
        </div>
        <div class="status">
          <span>Refresh</span>
          <strong id="updatedText">60s backend</strong>
        </div>
      </div>
    </header>
    <section class="supportTop">
      <span>Do you want to see more cities? A small support goes a long way</span>
      <a href="https://www.buymeacoffee.com/jeanmatias" target="_blank" rel="noopener noreferrer" aria-label="Buy Jean Matias a coffee">
        <img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=jeanmatias&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff" alt="Buy me a coffee">
      </a>
    </section>
    <section id="summary" class="summary"></section>
    <section id="cards" class="cards"></section>
  </main>
  <script>{_javascript()}</script>
</body>
</html>"""


def _css() -> str:
    return """
:root {
  color-scheme: dark;
  --bg: #080d12;
  --panel: #101820;
  --panel-soft: #0c141b;
  --line: #243340;
  --ink: #eef7f3;
  --muted: #91a3ad;
  --good: #56d494;
  --good-bg: rgba(86, 212, 148, 0.14);
  --warn: #f3b74b;
  --warn-bg: rgba(243, 183, 75, 0.15);
  --bad: #ff6b5e;
  --bad-bg: rgba(255, 107, 94, 0.14);
  --accent: #45c8d8;
  --gold: #d49b31;
  --shadow: 0 22px 60px rgba(0, 0, 0, 0.36);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  background:
    radial-gradient(circle at 12% -10%, rgba(69, 200, 216, 0.24), transparent 34%),
    radial-gradient(circle at 92% 0%, rgba(212, 155, 49, 0.14), transparent 32%),
    linear-gradient(180deg, #0d151d 0, #080d12 310px),
    var(--bg);
  color: var(--ink);
}
.shell { max-width: 1220px; margin: 0 auto; padding: 28px 24px 32px; }
.topbar { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; margin-bottom: 18px; }
.kicker {
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  margin: 0 0 7px;
  text-transform: uppercase;
}
h1 { margin: 0; font-size: 34px; line-height: 1.05; letter-spacing: 0; }
p { margin: 7px 0 0; color: var(--muted); line-height: 1.45; }
.statusDeck { display: grid; grid-template-columns: repeat(2, minmax(126px, 1fr)); gap: 10px; }
.status {
  background: rgba(16, 24, 32, 0.86);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.22);
  min-width: 132px;
  padding: 12px 14px;
}
.status span { color: var(--muted); display: block; font-size: 11px; font-weight: 700; text-transform: uppercase; }
.status strong { display: block; font-size: 17px; margin-top: 4px; }
.summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 14px; }
.summaryItem {
  background: rgba(16, 24, 32, 0.78);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 13px 14px;
}
.summaryItem span { color: var(--muted); display: block; font-size: 12px; font-weight: 700; text-transform: uppercase; }
.summaryItem strong { display: block; font-size: 24px; line-height: 1.1; margin-top: 3px; }
.cards { display: grid; gap: 16px; }
.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-top: 4px solid var(--warn);
  border-radius: 8px;
  box-shadow: var(--shadow);
  overflow: hidden;
}
.card.good { border-top-color: var(--good); }
.card.bad { border-top-color: var(--bad); }
.card-main { padding: 18px; }
.card h2 { margin: 0; font-size: 24px; line-height: 1.05; }
.card-head { display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; }
.cardActions { align-items: flex-end; display: flex; flex-direction: column; gap: 8px; }
.badge { border-radius: 999px; padding: 6px 10px; font-size: 12px; font-weight: 800; background: var(--warn-bg); color: var(--warn); white-space: nowrap; }
.good .badge { background: var(--good-bg); color: var(--good); }
.bad .badge { background: var(--bad-bg); color: var(--bad); }
.finalToggle {
  background: rgba(69, 200, 216, 0.10);
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--accent);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 800;
  padding: 7px 10px;
  white-space: nowrap;
}
.finalToggle:hover { border-color: var(--accent); }
.finalPanel {
  background: rgba(69, 200, 216, 0.07);
  border: 1px solid rgba(69, 200, 216, 0.30);
  border-radius: 8px;
  display: none;
  margin-top: 14px;
  padding: 12px;
}
.card.final-open .finalPanel { display: block; }
.liveMeter {
  background: linear-gradient(135deg, rgba(69, 200, 216, 0.16), rgba(86, 212, 148, 0.08));
  border: 1px solid rgba(69, 200, 216, 0.36);
  border-radius: 8px;
  margin-bottom: 10px;
  padding: 12px;
}
.liveMeterHead {
  align-items: flex-start;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.liveMeterTitle { color: var(--ink); font-size: 13px; font-weight: 900; text-transform: uppercase; }
.liveMeterSub { color: var(--muted); font-size: 12px; margin-top: 2px; }
.liveMeterPill {
  background: rgba(86, 212, 148, 0.14);
  border: 1px solid rgba(86, 212, 148, 0.35);
  border-radius: 999px;
  color: var(--good);
  font-size: 11px;
  font-weight: 900;
  padding: 5px 8px;
  white-space: nowrap;
}
.liveMeterGrid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.liveMeterItem { background: rgba(8, 13, 18, 0.62); border: 1px solid var(--line); border-radius: 6px; padding: 9px; }
.liveMeterItem span { color: var(--muted); display: block; font-size: 10px; font-weight: 800; margin-bottom: 5px; text-transform: uppercase; }
.liveMeterItem strong { display: block; font-size: 18px; overflow-wrap: anywhere; }
.liveMeterItem.primary strong { color: var(--good); font-size: 24px; line-height: 1; }
.finalGrid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.finalItem { background: #0c141b; border: 1px solid var(--line); border-radius: 6px; padding: 9px; }
.finalItem span { color: var(--muted); display: block; font-size: 10px; font-weight: 800; margin-bottom: 5px; text-transform: uppercase; }
.finalItem strong { display: block; font-size: 15px; overflow-wrap: anywhere; }
.feedWarning {
  background: var(--warn-bg);
  border: 1px solid rgba(243, 183, 75, 0.38);
  border-radius: 6px;
  color: var(--warn);
  font-size: 13px;
  font-weight: 800;
  margin-top: 10px;
  padding: 9px;
}
.recentFeed {
  border-top: 1px solid var(--line);
  margin-top: 10px;
  padding-top: 10px;
}
.recentFeedHeader {
  color: var(--muted);
  font-size: 10px;
  font-weight: 800;
  margin-bottom: 7px;
  text-transform: uppercase;
}
.recentFeedRows { display: flex; flex-wrap: wrap; gap: 7px; }
.recentPoint {
  background: #0c141b;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--ink);
  font-size: 12px;
  font-weight: 800;
  padding: 6px 8px;
}
.visualGrid { display: grid; grid-template-columns: minmax(260px, 0.85fr) 1.15fr; gap: 14px; margin-top: 16px; }
.marketPanel, .tempPanel {
  background: var(--panel-soft);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 13px;
}
.panelTitle { color: var(--muted); font-size: 12px; font-weight: 800; margin-bottom: 10px; text-transform: uppercase; }
.bucketRow { display: grid; gap: 6px; margin-bottom: 12px; }
.bucketTop { display: flex; justify-content: space-between; gap: 8px; font-size: 14px; font-weight: 800; }
.bucketTop span { color: var(--muted); font-weight: 700; }
.barTrack { background: #1d2a34; border-radius: 999px; height: 10px; overflow: hidden; }
.barFill { background: linear-gradient(90deg, #2ca8b8, var(--accent)); border-radius: inherit; height: 100%; width: 0; }
.bucketRow.second .barFill { background: linear-gradient(90deg, #9d7a27, var(--gold)); }
.tempRail { margin-top: 8px; }
.tempLabels { display: flex; justify-content: space-between; color: var(--muted); font-size: 12px; font-weight: 700; margin-bottom: 6px; }
.tempTrack { background: #1d2a34; border-radius: 999px; height: 14px; overflow: hidden; position: relative; }
.tempFill { background: linear-gradient(90deg, #45c8d8, #d49228); border-radius: inherit; height: 100%; width: 0; }
.tempMarker {
  background: #f4fbf7;
  border: 2px solid var(--panel);
  border-radius: 999px;
  height: 18px;
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 18px;
}
.metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 14px; }
.metric { background: #0c141b; border: 1px solid var(--line); border-radius: 6px; min-width: 0; padding: 10px; }
.metric span { display: block; color: var(--muted); font-size: 11px; font-weight: 750; margin-bottom: 5px; text-transform: uppercase; }
.metric strong { display: block; font-size: 17px; overflow-wrap: anywhere; }
.note {
  background: #0c141b;
  border-top: 1px solid var(--line);
  color: var(--ink);
  font-weight: 800;
  margin: 0;
  padding: 13px 18px;
}
.warnings { color: var(--bad); font-size: 13px; margin: 10px 18px 0; }
.sourceLinks {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.sourceLinks a {
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
  padding: 6px 9px;
  text-decoration: none;
}
.sourceLinks a:hover { border-color: var(--accent); }
.supportTop {
  align-items: center;
  background: rgba(16, 24, 32, 0.78);
  border: 1px solid var(--line);
  border-radius: 8px;
  display: flex;
  gap: 14px;
  justify-content: space-between;
  margin-bottom: 14px;
  padding: 11px 14px;
}
.supportTop span {
  color: var(--ink);
  font-size: 14px;
  font-weight: 800;
}
.supportTop img { display: block; height: 38px; max-width: 210px; }
@media (max-width: 850px) {
  .topbar { display: block; }
  .statusDeck { margin-top: 12px; }
  .summary { grid-template-columns: 1fr; }
  .visualGrid { grid-template-columns: 1fr; }
  .metrics { grid-template-columns: repeat(2, 1fr); }
  .liveMeterGrid { grid-template-columns: repeat(2, 1fr); }
  .finalGrid { grid-template-columns: repeat(2, 1fr); }
  .supportTop { align-items: flex-start; flex-direction: column; }
}
@media (max-width: 560px) {
  .shell { padding: 14px; }
  .metrics { grid-template-columns: 1fr; }
  .card-head { display: block; }
  .cardActions { align-items: flex-start; margin-top: 10px; }
  .liveMeterGrid { grid-template-columns: 1fr; }
  .finalGrid { grid-template-columns: 1fr; }
}
"""


def _javascript() -> str:
    return """
const cards = document.getElementById('cards');
const summary = document.getElementById('summary');
const statusText = document.getElementById('statusText');
const updatedText = document.getElementById('updatedText');
let nextRefreshAt = null;
let refreshInFlight = false;
const openFinalCities = new Set();
const tempMeterInFlight = new Set();
const tempMeterNextPullAt = new Map();

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

function fmtEtTime(value) {
  if (!value) return 'n/a';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'n/a';
  return date.toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'America/New_York',
    timeZoneName: 'short'
  });
}

function fmtDuration(ms) {
  if (!Number.isFinite(ms)) return 'n/a';
  const absMs = Math.abs(ms);
  const totalMinutes = Math.round(absMs / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  const text = hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
  return ms >= 0 ? `in ${text}` : `${text} ago`;
}

function peakCountdown(city) {
  return peakCountdownFromIso(city.forecast_high_time);
}

function peakCountdownFromIso(isoValue) {
  if (!isoValue) return 'n/a';
  const peak = new Date(isoValue);
  if (Number.isNaN(peak.getTime())) return 'n/a';
  return fmtDuration(peak.getTime() - Date.now());
}

function lastObsAge(city) {
  if (!city.latest_observation_time) return 'n/a';
  const observed = new Date(city.latest_observation_time);
  if (Number.isNaN(observed.getTime())) return 'n/a';
  return fmtDuration(observed.getTime() - Date.now());
}

function recentFeedMax(city) {
  if (city.recent_observation_max_f !== null && city.recent_observation_max_f !== undefined) {
    return fmtTemp(city.recent_observation_max_f);
  }
  return fmtTemp(city.raw_high_so_far_f);
}

function tempMeterCountdown(cityName) {
  const nextPull = tempMeterNextPullAt.get(cityName);
  if (!nextPull) return 'starts when opened';
  const seconds = Math.max(0, Math.ceil((nextPull - Date.now()) / 1000));
  return seconds > 0 ? `${seconds}s` : 'due now';
}

function roundedOutcome(city) {
  return city.high_so_far_f === null || city.high_so_far_f === undefined ? 'n/a' : `${Number(city.high_so_far_f).toFixed(0)}F`;
}

function nextRoundDistance(city) {
  const rawHigh = Number(city.raw_high_so_far_f);
  if (!Number.isFinite(rawHigh)) return 'n/a';
  const currentRounded = Math.round(rawHigh);
  const nextThreshold = currentRounded + 0.5;
  const needed = Math.max(0, nextThreshold - rawHigh);
  return `+${needed.toFixed(1)}F to ${currentRounded + 1}F`;
}

function peakStatus(city) {
  if (!city.forecast_high_time) return 'n/a';
  const peak = new Date(city.forecast_high_time);
  if (Number.isNaN(peak.getTime())) return 'n/a';
  const deltaMinutes = (peak.getTime() - Date.now()) / 60000;
  if (deltaMinutes > 60) return 'Before peak';
  if (deltaMinutes >= -60) return 'Peak watch';
  return 'Past peak';
}

function cents(bucket) {
  if (!bucket || bucket.yes_price === null || bucket.yes_price === undefined) return 0;
  return Math.max(0, Math.min(100, Number(bucket.yes_price)));
}

function tempPercent(city, value) {
  const current = Number(city.current_temp_f);
  const forecast = Number(city.forecast_high_f);
  const rawHigh = Number(city.raw_high_so_far_f);
  const max = Math.max(current || 0, forecast || 0, rawHigh || 0);
  const min = Math.max(0, max - 28);
  const number = Number(value);
  if (!Number.isFinite(number) || max <= min) return 0;
  return Math.max(0, Math.min(100, ((number - min) / (max - min)) * 100));
}

function renderSummary(payload) {
  const cities = payload.cities || [];
  const aligned = cities.filter(city => city.market_weather_alignment === 'ALIGNED').length;
  const reachable = cities.filter(city => ['REACHED', 'REACHABLE'].includes(city.reachability_label)).length;
  const warnings = cities.filter(city => city.false_pump_warning || city.reachability_label === 'CROSSED_ABOVE').length;
  summary.innerHTML = `
    <div class="summaryItem"><span>Aligned</span><strong>${aligned}/${cities.length}</strong></div>
    <div class="summaryItem"><span>Reachable</span><strong>${reachable}/${cities.length}</strong></div>
    <div class="summaryItem"><span>Warnings</span><strong>${warnings}</strong></div>
  `;
}

function tone(city) {
  if (city.false_pump_warning || city.reachability_label === 'CROSSED_ABOVE') return 'bad';
  if (city.market_weather_alignment === 'ALIGNED' && ['REACHED', 'REACHABLE'].includes(city.reachability_label)) return 'good';
  return 'warn';
}

function render(payload) {
  const updated = payload.last_updated || payload.generated_at || 'unknown';
  nextRefreshAt = payload.next_refresh_eta ? new Date(payload.next_refresh_eta) : null;
  statusText.textContent = new Date(updated).toLocaleTimeString();
  updateCountdown();
  renderSummary(payload);
  cards.innerHTML = (payload.cities || []).map(city => `
    <article class="card ${tone(city)} ${openFinalCities.has(city.city) ? 'final-open' : ''}">
      <div class="card-main">
        <div class="card-head">
          <div>
            <h2>${escapeHtml(city.city)}</h2>
            <p>${escapeHtml(city.station_id || '')} | ${escapeHtml(city.market_date || '')}</p>
          </div>
          <div class="cardActions">
            <span class="badge">${escapeHtml(city.reachability_label || 'n/a')}</span>
            <button class="finalToggle" type="button" data-final-city="${escapeAttribute(city.city)}">${openFinalCities.has(city.city) ? 'Hide Final Read' : 'Final Minutes Mode'}</button>
          </div>
        </div>
        ${finalMinutesPanel(city)}
        <div class="visualGrid">
          <div class="marketPanel">
            <div class="panelTitle">Kalshi board</div>
            ${bucketVisual('Winning', city.winning_bucket, '')}
            ${bucketVisual('Second', city.second_bucket, 'second')}
          </div>
          <div class="tempPanel">
            <div class="panelTitle">Official station temperature</div>
            <div class="tempLabels">
              <span>Current ${fmtTemp(city.current_temp_f)}</span>
              <span>Forecast ${fmtTemp(city.forecast_high_f)}</span>
            </div>
            <div class="tempTrack">
              <div class="tempFill" style="width:${tempPercent(city, city.current_temp_f).toFixed(1)}%"></div>
              <div class="tempMarker" title="Raw high so far" style="left:${tempPercent(city, city.raw_high_so_far_f).toFixed(1)}%"></div>
            </div>
          </div>
        </div>
        <div class="metrics">
          <div class="metric"><span>High So Far</span><strong>${fmtTemp(city.high_so_far_f)}</strong></div>
          <div class="metric"><span>Raw High</span><strong>${fmtTemp(city.raw_high_so_far_f)}</strong></div>
          <div class="metric"><span>Critical Hour</span><strong>${escapeHtml(city.critical_window_et || 'n/a')}</strong></div>
          <div class="metric"><span>Peak Countdown</span><strong class="peakCountdown" data-peak-time="${escapeAttribute(city.forecast_high_time || '')}">${escapeHtml(peakCountdown(city))}</strong></div>
          <div class="metric"><span>Market vs Weather</span><strong>${escapeHtml(city.market_weather_alignment || 'n/a')}</strong></div>
          <div class="metric"><span>Heating Pace</span><strong>${fmtRate(city.heating_rate_f_per_hour)}</strong></div>
          <div class="metric"><span>Needed Rate</span><strong>${fmtRate(city.required_rate_f_per_hour)}</strong></div>
          <div class="metric"><span>Degrees Needed</span><strong>${fmtTemp(city.degrees_needed_to_reach_bucket)}</strong></div>
        </div>
        ${sourceLinks(city)}
        ${(city.warnings || []).length ? `<p class="warnings">${escapeHtml(city.warnings[0])}</p>` : ''}
      </div>
      <p class="note">${escapeHtml(city.decision_note || '')}</p>
    </article>
  `).join('');
}

function finalMinutesPanel(city) {
  return `
    <div class="finalPanel" data-final-panel="${escapeAttribute(city.city)}">
      ${liveTempMeter(city)}
      <div class="finalGrid">
        <div class="finalItem"><span>Latest Endpoint</span><strong>${fmtTemp(city.latest_endpoint_temp_f ?? city.current_temp_f)}</strong></div>
        <div class="finalItem"><span>Recent Max</span><strong>${recentFeedMax(city)}</strong></div>
        <div class="finalItem"><span>If Final Now</span><strong>${escapeHtml(roundedOutcome(city))}</strong></div>
        <div class="finalItem"><span>Next Round Risk</span><strong>${escapeHtml(nextRoundDistance(city))}</strong></div>
        <div class="finalItem"><span>Latest Endpoint Time</span><strong>${escapeHtml(fmtEtTime(city.latest_endpoint_time))}</strong></div>
        <div class="finalItem"><span>Recent Feed Time</span><strong>${escapeHtml(fmtEtTime(city.latest_history_time || city.latest_observation_time))}</strong></div>
        <div class="finalItem"><span>Last Obs Age</span><strong class="obsAge" data-obs-time="${escapeAttribute(city.latest_history_time || city.latest_observation_time || '')}">${escapeHtml(lastObsAge({latest_observation_time: city.latest_history_time || city.latest_observation_time}))}</strong></div>
        <div class="finalItem"><span>Peak Status</span><strong class="peakStatus" data-peak-time="${escapeAttribute(city.forecast_high_time || '')}">${escapeHtml(peakStatus(city))}</strong></div>
        <div class="finalItem"><span>Data Refresh</span><strong class="finalRefreshCountdown">${escapeHtml(refreshCountdownText())}</strong></div>
      </div>
      ${city.latest_feed_lag_warning ? `<div class="feedWarning">${escapeHtml(city.latest_feed_lag_note || 'Latest endpoint may be behind the recent observation list.')}</div>` : ''}
      ${recentObservationRows(city)}
    </div>
  `;
}

function liveTempMeter(city) {
  return `
    <div class="liveMeter" data-meter-city="${escapeAttribute(city.city)}">
      <div class="liveMeterHead">
        <div>
          <div class="liveMeterTitle">Live Temp Meter</div>
          <div class="liveMeterSub">Temp-only official NWS station check every 3 seconds while this panel is open.</div>
        </div>
        <div class="liveMeterPill">3s temp pull</div>
      </div>
      <div class="liveMeterGrid">
        <div class="liveMeterItem primary"><span>Latest Temp</span><strong data-meter-field="current">${fmtTemp(city.latest_endpoint_temp_f ?? city.current_temp_f)}</strong></div>
        <div class="liveMeterItem"><span>Recent Max</span><strong data-meter-field="recentMax">${recentFeedMax(city)}</strong></div>
        <div class="liveMeterItem"><span>Rounded Now</span><strong data-meter-field="rounded">${escapeHtml(roundedOutcome(city))}</strong></div>
        <div class="liveMeterItem"><span>Meter Refresh</span><strong data-meter-field="countdown">${escapeHtml(tempMeterCountdown(city.city))}</strong></div>
        <div class="liveMeterItem"><span>Latest Time ET</span><strong data-meter-field="endpointTime">${escapeHtml(fmtEtTime(city.latest_endpoint_time))}</strong></div>
        <div class="liveMeterItem"><span>Feed Time ET</span><strong data-meter-field="feedTime">${escapeHtml(fmtEtTime(city.latest_history_time || city.latest_observation_time))}</strong></div>
        <div class="liveMeterItem"><span>Last Obs Age</span><strong data-meter-field="age" data-meter-obs-time="${escapeAttribute(city.latest_history_time || city.latest_observation_time || '')}">${escapeHtml(lastObsAge({latest_observation_time: city.latest_history_time || city.latest_observation_time}))}</strong></div>
        <div class="liveMeterItem"><span>Status</span><strong data-meter-field="status">ready</strong></div>
      </div>
      <div data-meter-field="warning">${city.latest_feed_lag_warning ? `<div class="feedWarning">${escapeHtml(city.latest_feed_lag_note || '')}</div>` : ''}</div>
      <div data-meter-field="feedRows">${recentObservationRows(city)}</div>
    </div>
  `;
}

function recentObservationRows(city) {
  const points = (city.recent_observation_points || []).slice(-6);
  if (!points.length) return '';
  return `
    <div class="recentFeed">
      <div class="recentFeedHeader">Recent NWS station feed</div>
      <div class="recentFeedRows">
        ${points.map(point => `
          <span class="recentPoint">${escapeHtml(fmtEtTime(point.time))} ${fmtTemp(point.temp_f)}</span>
        `).join('')}
      </div>
    </div>
  `;
}

function refreshCountdownText() {
  if (!nextRefreshAt || Number.isNaN(nextRefreshAt.getTime())) return 'waiting';
  const seconds = Math.max(0, Math.ceil((nextRefreshAt.getTime() - Date.now()) / 1000));
  return seconds > 0 ? `${seconds}s` : 'due now';
}

function updateCountdown() {
  if (!nextRefreshAt || Number.isNaN(nextRefreshAt.getTime())) {
    updatedText.textContent = 'waiting';
    return;
  }
  const seconds = Math.max(0, Math.ceil((nextRefreshAt.getTime() - Date.now()) / 1000));
  updatedText.textContent = refreshCountdownText();
  document.querySelectorAll('.finalRefreshCountdown').forEach(element => {
    element.textContent = refreshCountdownText();
  });
  document.querySelectorAll('[data-meter-field="countdown"]').forEach(element => {
    const meter = element.closest('.liveMeter');
    element.textContent = meter ? tempMeterCountdown(meter.dataset.meterCity) : 'n/a';
  });
  if (seconds <= 0 && !refreshInFlight) {
    load();
  }
}

function updatePeakCountdowns() {
  document.querySelectorAll('.peakCountdown').forEach(element => {
    element.textContent = peakCountdownFromIso(element.dataset.peakTime);
  });
  document.querySelectorAll('.obsAge').forEach(element => {
    element.textContent = lastObsAge({latest_observation_time: element.dataset.obsTime});
  });
  document.querySelectorAll('.peakStatus').forEach(element => {
    element.textContent = peakStatus({forecast_high_time: element.dataset.peakTime});
  });
  document.querySelectorAll('[data-meter-field="age"]').forEach(element => {
    element.textContent = lastObsAge({latest_observation_time: element.dataset.meterObsTime});
  });
}

cards.addEventListener('click', event => {
  const button = event.target.closest('.finalToggle');
  if (!button) return;
  const card = button.closest('.card');
  const open = !card.classList.contains('final-open');
  if (open) {
    openFinalCities.add(button.dataset.finalCity);
  } else {
    openFinalCities.delete(button.dataset.finalCity);
  }
  card.classList.toggle('final-open', open);
  button.textContent = open ? 'Hide Final Read' : 'Final Minutes Mode';
  if (open) refreshTempMeter(button.dataset.finalCity);
});

async function refreshTempMeter(cityName) {
  if (!cityName || !openFinalCities.has(cityName) || tempMeterInFlight.has(cityName)) return;
  tempMeterInFlight.add(cityName);
  updateTempMeterStatus(cityName, 'pulling');
  try {
    const response = await fetch(`/api/temp-meter?city=${encodeURIComponent(cityName)}`, {cache: 'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    updateTempMeter(payload);
    const refreshSeconds = Number(payload.cache_ttl_seconds || payload.refresh_seconds || 3);
    tempMeterNextPullAt.set(cityName, Date.now() + refreshSeconds * 1000);
  } catch (error) {
    updateTempMeterStatus(cityName, error.message || 'failed');
    tempMeterNextPullAt.set(cityName, Date.now() + 3000);
  } finally {
    tempMeterInFlight.delete(cityName);
  }
}

function refreshOpenTempMeters() {
  openFinalCities.forEach(cityName => refreshTempMeter(cityName));
}

function updateTempMeter(payload) {
  const cityName = payload.city;
  const meter = document.querySelector(`.liveMeter[data-meter-city="${cssEscape(cityName)}"]`);
  if (!meter) return;
  setMeterText(meter, 'current', fmtTemp(payload.current_temp_f));
  setMeterText(meter, 'recentMax', fmtTemp(payload.recent_observation_max_f ?? payload.raw_high_so_far_f));
  setMeterText(meter, 'rounded', payload.rounded_if_final_now_f === null || payload.rounded_if_final_now_f === undefined ? 'n/a' : `${Number(payload.rounded_if_final_now_f).toFixed(0)}F`);
  setMeterText(meter, 'endpointTime', fmtEtTime(payload.latest_endpoint_time));
  setMeterText(meter, 'feedTime', fmtEtTime(payload.latest_history_time));
  const age = meter.querySelector('[data-meter-field="age"]');
  if (age) {
    age.dataset.meterObsTime = payload.latest_history_time || payload.latest_endpoint_time || '';
    age.textContent = lastObsAge({latest_observation_time: age.dataset.meterObsTime});
  }
  setMeterText(meter, 'status', payload.ok ? 'live' : (payload.error || 'unavailable'));
  const warning = meter.querySelector('[data-meter-field="warning"]');
  if (warning) {
    warning.innerHTML = payload.latest_feed_lag_warning ? `<div class="feedWarning">${escapeHtml(payload.latest_feed_lag_note || '')}</div>` : '';
  }
  const feedRows = meter.querySelector('[data-meter-field="feedRows"]');
  if (feedRows) {
    feedRows.innerHTML = recentObservationRows(payload);
  }
}

function updateTempMeterStatus(cityName, status) {
  const meter = document.querySelector(`.liveMeter[data-meter-city="${cssEscape(cityName)}"]`);
  if (!meter) return;
  setMeterText(meter, 'status', status);
}

function setMeterText(meter, field, text) {
  const element = meter.querySelector(`[data-meter-field="${field}"]`);
  if (element) element.textContent = text;
}

function cssEscape(value) {
  if (window.CSS && CSS.escape) return CSS.escape(value);
  return String(value).replace(/["\\\\]/g, '\\\\$&');
}

function bucketVisual(title, bucket, className) {
  const price = cents(bucket);
  return `
    <div class="bucketRow ${className}">
      <div class="bucketTop">
        <strong>${escapeHtml(title)}: ${escapeHtml(bucket?.label || 'n/a')}</strong>
        <span>${price.toFixed(0)}c</span>
      </div>
      <div class="barTrack"><div class="barFill" style="width:${price}%"></div></div>
    </div>
  `;
}

function sourceLinks(city) {
  const links = [
    city.kalshi_url ? ['Kalshi', city.kalshi_url] : null,
    city.station_id ? ['NWS Obs', `https://api.weather.gov/stations/${encodeURIComponent(city.station_id)}/observations/latest`] : null,
    city.forecast_graph_url ? ['NWS Forecast', city.forecast_graph_url] : null
  ].filter(Boolean);
  if (!links.length) return '';
  return `<div class="sourceLinks">${links.map(([label, url]) => `
    <a href="${escapeAttribute(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>
  `).join('')}</div>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
}

function escapeAttribute(value) {
  return escapeHtml(value).replace(/`/g, '&#96;');
}

async function load() {
  if (refreshInFlight) return;
  refreshInFlight = true;
  try {
    const response = await fetch('/api/live', {cache: 'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    statusText.textContent = 'Live update failed';
    updatedText.textContent = error.message;
  } finally {
    refreshInFlight = false;
  }
}

load();
setInterval(load, 15000);
setInterval(refreshOpenTempMeters, 3000);
setInterval(() => {
  updateCountdown();
  updatePeakCountdowns();
}, 1000);
"""
