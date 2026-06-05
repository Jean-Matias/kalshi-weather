from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from history_data import load_historical_payload
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
def api_live(day: str = "today") -> JSONResponse:
    return JSONResponse(live_cache.get(day))


@app.get("/api/temp-meter")
def api_temp_meter(city: str) -> JSONResponse:
    return JSONResponse(temp_meter_cache.get(city))


@app.get("/api/history")
def api_history(city: str = "Las Vegas") -> JSONResponse:
    return JSONResponse(load_historical_payload(city, days=3))


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
    <section id="dateBanner" class="dateBanner">
      <div>
        <span>Analyzing</span>
        <strong id="bannerDate">Loading market date</strong>
      </div>
      <p id="bannerNote">Today uses live NWS station observations, recent high-so-far, forecast, and Kalshi market board.</p>
    </section>
    <section id="summary" class="summary"></section>
    <section id="cards" class="cards"></section>
    <section class="historyPanel">
      <div class="historyHead">
        <div>
          <span>Historic Data</span>
          <strong>3-day market history</strong>
          <p>Saved snapshots only. This section is meant for pattern-reading, not live refresh.</p>
        </div>
        <label>
          City
          <select id="historyCity">
            <option>Las Vegas</option>
            <option>Phoenix</option>
            <option>San Antonio</option>
          </select>
        </label>
      </div>
      <div id="historyCharts" class="historyCharts"></div>
    </section>
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
.forecastOnly {
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 900;
  padding: 8px 10px;
  white-space: nowrap;
}
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
.heatingSignal {
  background: rgba(8, 13, 18, 0.62);
  border: 1px solid var(--line);
  border-radius: 8px;
  margin-top: 12px;
  padding: 12px;
}
.heatingSignalTop { align-items: center; display: flex; justify-content: space-between; gap: 10px; }
.heatingSignalTop span { color: var(--muted); display: block; font-size: 11px; font-weight: 850; text-transform: uppercase; }
.heatingSignalTop strong { display: block; font-size: 20px; margin-top: 2px; }
.heatingScore { color: var(--good); font-size: 24px; font-weight: 950; white-space: nowrap; }
.heatingSignal.slow .heatingScore { color: var(--bad); }
.heatingSignal.mixed .heatingScore { color: var(--warn); }
.heatingScoreTrack { background: #1d2a34; border-radius: 999px; height: 8px; margin-top: 10px; overflow: hidden; }
.heatingScoreFill { background: linear-gradient(90deg, var(--bad), var(--warn), var(--good)); border-radius: inherit; height: 100%; }
.heatingReasons { color: var(--muted); font-size: 12px; font-weight: 760; line-height: 1.45; margin-top: 9px; }
.marketChecklist {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(2, 1fr);
  margin-top: 10px;
}
.checkItem {
  background: rgba(8, 13, 18, 0.62);
  border: 1px solid var(--line);
  border-radius: 7px;
  min-width: 0;
  padding: 9px;
}
.checkItem.warn { border-color: rgba(243, 183, 75, 0.45); }
.checkItem.bad { border-color: rgba(255, 107, 94, 0.42); }
.checkItem span { color: var(--muted); display: block; font-size: 10px; font-weight: 850; margin-bottom: 4px; text-transform: uppercase; }
.checkItem strong { display: block; font-size: 13px; overflow-wrap: anywhere; }
.checkItem small { color: var(--muted); display: block; font-size: 11px; font-weight: 720; line-height: 1.35; margin-top: 4px; }
.tempGraphHead { display: flex; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.tempGraphHead strong { display: block; font-size: 26px; line-height: 1; }
.tempGraphHead span { color: var(--muted); display: block; font-size: 11px; font-weight: 800; margin-top: 4px; text-transform: uppercase; }
.tempGraphMeta { color: var(--muted); font-size: 12px; font-weight: 800; text-align: right; }
.tempGraph {
  background:
    linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px),
    #081017;
  background-size: 100% 32px, 56px 100%;
  border: 1px solid var(--line);
  border-radius: 8px;
  height: 174px;
  overflow: hidden;
  position: relative;
}
.tempGraph svg { display: block; height: 100%; width: 100%; }
.tempGraphPath { fill: none; stroke: var(--accent); stroke-linecap: round; stroke-linejoin: round; stroke-width: 3; }
.tempGraphHighPath { fill: none; stroke: var(--gold); stroke-linecap: round; stroke-linejoin: round; stroke-width: 3; }
.tempGraphArea { fill: rgba(69, 200, 216, 0.12); }
.tempGraphPoint { fill: var(--good); stroke: #081017; stroke-width: 2; }
.tempGraphHighPoint { fill: var(--gold); stroke: #081017; stroke-width: 2; }
.tempGraphEmpty { align-items: center; color: var(--muted); display: flex; font-size: 13px; font-weight: 800; inset: 0; justify-content: center; position: absolute; }
.tempLegend { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.legendItem { align-items: center; color: var(--muted); display: inline-flex; font-size: 12px; font-weight: 850; gap: 6px; }
.legendSwatch { border-radius: 999px; display: inline-block; height: 3px; width: 22px; }
.legendSwatch.current { background: var(--accent); }
.legendSwatch.high { background: var(--gold); }
.tempGraphFooter { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 9px; }
.tempChip {
  background: #0c141b;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--ink);
  font-size: 12px;
  font-weight: 850;
  padding: 6px 8px;
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
.dateBanner {
  align-items: center;
  background: linear-gradient(135deg, rgba(69, 200, 216, 0.16), rgba(212, 155, 49, 0.10));
  border: 1px solid rgba(69, 200, 216, 0.30);
  border-radius: 8px;
  display: flex;
  gap: 14px;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 13px 14px;
}
.dateBanner span { color: var(--muted); display: block; font-size: 11px; font-weight: 800; text-transform: uppercase; }
.dateBanner strong { color: var(--ink); display: block; font-size: 20px; margin-top: 2px; }
.dateBanner p { color: var(--muted); font-size: 13px; margin: 0; max-width: 560px; text-align: right; }
.historyPanel {
  background: rgba(16, 24, 32, 0.78);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 18px 42px rgba(0, 0, 0, 0.22);
  margin-top: 18px;
  padding: 15px;
}
.historyHead {
  align-items: flex-start;
  display: flex;
  gap: 14px;
  justify-content: space-between;
}
.historyHead span {
  color: var(--accent);
  display: block;
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
}
.historyHead strong { display: block; font-size: 21px; margin-top: 3px; }
.historyHead p { font-size: 13px; margin-top: 4px; }
.historyHead label {
  color: var(--muted);
  display: grid;
  font-size: 11px;
  font-weight: 900;
  gap: 6px;
  min-width: 180px;
  text-transform: uppercase;
}
.historyHead select {
  appearance: none;
  background: #0c141b;
  border: 1px solid var(--line);
  border-radius: 7px;
  color: var(--ink);
  font: inherit;
  font-size: 14px;
  font-weight: 850;
  padding: 10px 11px;
}
.historyCharts { display: grid; gap: 12px; margin-top: 13px; }
.historyCard {
  background: var(--panel-soft);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
}
.historyCardHead {
  align-items: flex-start;
  display: flex;
  gap: 10px;
  justify-content: space-between;
  margin-bottom: 10px;
}
.historyCardHead strong { display: block; font-size: 18px; }
.historyCardHead span { color: var(--muted); display: block; font-size: 12px; font-weight: 800; margin-top: 3px; }
.historyLegend { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.historyLegend .legendItem { font-size: 11px; }
.legendSwatch.kalshi { background: var(--gold); }
.legendSwatch.actual { background: var(--good); }
.legendSwatch.forecast { background: #dbe8ef; }
.legendSwatch.bucket { background: var(--accent); opacity: 0.7; }
.historyChart {
  background:
    linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px),
    #081017;
  background-size: 100% 36px, 64px 100%;
  border: 1px solid var(--line);
  border-radius: 8px;
  height: 258px;
  overflow: hidden;
}
.historyChart svg { display: block; height: 100%; width: 100%; }
.histAxis { stroke: rgba(238, 247, 243, 0.18); stroke-width: 1; }
.histLabel { fill: var(--muted); font-size: 10px; font-weight: 800; }
.histLine { fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-width: 2.8; }
.histKalshi { stroke: var(--gold); }
.histActual { stroke: var(--good); }
.histForecast { stroke: #dbe8ef; stroke-dasharray: 6 5; }
.histBucket { fill: none; stroke-width: 1.5; opacity: 0.62; }
.histPoint { stroke: #081017; stroke-width: 2; }
.histPoint.kalshi { fill: var(--gold); }
.histPoint.actual { fill: var(--good); }
.histPoint.forecast { fill: #dbe8ef; }
.histPoint.bucket { stroke-width: 1; opacity: 0.88; }
.historyEmpty {
  align-items: center;
  border: 1px dashed var(--line);
  border-radius: 8px;
  color: var(--muted);
  display: flex;
  font-size: 13px;
  font-weight: 850;
  justify-content: center;
  min-height: 118px;
  padding: 18px;
  text-align: center;
}
@media (max-width: 850px) {
  .topbar { display: block; }
  .statusDeck { margin-top: 12px; }
  .summary { grid-template-columns: 1fr; }
  .visualGrid { grid-template-columns: 1fr; }
  .metrics { grid-template-columns: repeat(2, 1fr); }
  .marketChecklist { grid-template-columns: 1fr; }
  .dateBanner { align-items: flex-start; flex-direction: column; }
  .dateBanner p { text-align: left; }
  .supportTop { align-items: flex-start; flex-direction: column; }
  .historyHead { flex-direction: column; }
  .historyHead label { width: 100%; }
  .historyLegend { justify-content: flex-start; }
}
@media (max-width: 560px) {
  .shell { padding: 14px; }
  .metrics { grid-template-columns: 1fr; }
  .card-head { display: block; }
  .cardActions { align-items: flex-start; margin-top: 10px; }
}
"""


def _javascript() -> str:
    return """
const cards = document.getElementById('cards');
const summary = document.getElementById('summary');
const statusText = document.getElementById('statusText');
const updatedText = document.getElementById('updatedText');
const bannerDate = document.getElementById('bannerDate');
const bannerNote = document.getElementById('bannerNote');
const historyCity = document.getElementById('historyCity');
const historyCharts = document.getElementById('historyCharts');
let nextRefreshAt = null;
let refreshInFlight = false;
let historyInFlight = false;
let mainPollSeconds = 15;
let tempMeterPollSeconds = 3;
let mainPollTimer = null;
let tempMeterPollTimer = null;
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
  if (!nextPull) return 'waiting';
  const seconds = Math.max(0, Math.ceil((nextPull - Date.now()) / 1000));
  return seconds > 0 ? `${seconds}s` : 'due now';
}

function tempMeterPullText() {
  return `${tempMeterPollSeconds}s temp pull`;
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
  mainPollSeconds = Number(payload.browser_poll_seconds || mainPollSeconds || 15);
  tempMeterPollSeconds = Number(payload.temp_meter_browser_poll_seconds || tempMeterPollSeconds || 3);
  syncPollTimers();
  statusText.textContent = new Date(updated).toLocaleTimeString();
  renderBanner(payload);
  updateCountdown();
  renderSummary(payload);
  cards.innerHTML = (payload.cities || []).map(city => `
    <article class="card ${tone(city)}" data-live-card="${escapeAttribute(city.city)}">
      <div class="card-main">
        <div class="card-head">
          <div>
            <h2>${escapeHtml(city.city)}</h2>
            <p>${escapeHtml(city.station_id || '')} | ${escapeHtml(city.market_date || '')}</p>
          </div>
          <div class="cardActions">
            <span class="badge">${escapeHtml(city.reachability_label || 'n/a')}</span>
            <span class="forecastOnly">${tempMeterPollSeconds}s live NWS graph</span>
          </div>
        </div>
        <div class="visualGrid">
          <div class="marketPanel">
            <div class="panelTitle">Kalshi board</div>
            ${bucketVisual('Winning', city.winning_bucket, '')}
            ${bucketVisual('Second', city.second_bucket, 'second')}
          </div>
          <div class="tempPanel">
            ${liveTempGraph(city)}
            ${heatingSignal(city)}
            ${marketChecklist(city)}
          </div>
        </div>
        <div class="metrics">
          <div class="metric"><span>Critical Hour</span><strong>${escapeHtml(city.critical_window_et || 'n/a')}</strong></div>
          <div class="metric"><span>High So Far Raw</span><strong data-live-field="rawHigh" data-live-city="${escapeAttribute(city.city)}">${fmtTemp(city.raw_high_so_far_f)}</strong></div>
          <div class="metric"><span>High Time ET</span><strong data-live-field="rawHighTime" data-live-city="${escapeAttribute(city.city)}">${escapeHtml(fmtEtTime(city.raw_high_so_far_time))}</strong></div>
          <div class="metric"><span>Rounded If Final</span><strong data-live-field="rounded" data-live-city="${escapeAttribute(city.city)}">${escapeHtml(roundedOutcome(city))}</strong></div>
          <div class="metric"><span>Peak Countdown</span><strong class="peakCountdown" data-peak-time="${escapeAttribute(city.forecast_high_time || '')}">${escapeHtml(peakCountdown(city))}</strong></div>
          <div class="metric"><span>Heating Pace</span><strong>${fmtRate(city.heating_rate_f_per_hour)}</strong></div>
        </div>
        ${sourceLinks(city)}
        ${(city.warnings || []).length ? `<p class="warnings">${escapeHtml(city.warnings[0])}</p>` : ''}
      </div>
      <p class="note">${escapeHtml(city.decision_note || '')}</p>
    </article>
  `).join('');
  refreshVisibleTempMeters();
}

function renderBanner(payload) {
  bannerDate.textContent = `Today market: ${payload.market_date_label || 'unknown'}`;
  bannerNote.textContent = 'Today uses live NWS station observations, recent high-so-far, forecast, and Kalshi market board.';
}

function liveTempGraph(city) {
  const points = normalizedTempPoints(city);
  const current = city.latest_endpoint_temp_f ?? city.current_temp_f;
  const recentMax = city.recent_observation_max_f ?? city.raw_high_so_far_f;
  return `
    <div class="panelTitle">NWS live temperature graph</div>
    <div class="tempGraphHead">
      <div>
        <strong data-live-field="current" data-live-city="${escapeAttribute(city.city)}">${fmtTemp(current)}</strong>
        <span>Latest NWS temp</span>
      </div>
      <div class="tempGraphMeta">
        <div data-live-field="refresh" data-live-city="${escapeAttribute(city.city)}">${escapeHtml(tempMeterCountdown(city.city))}</div>
        <div data-live-field="time" data-live-city="${escapeAttribute(city.city)}">${escapeHtml(fmtEtTime(city.latest_history_time || city.latest_endpoint_time || city.latest_observation_time))}</div>
      </div>
    </div>
    <div class="tempLegend">
      <span class="legendItem"><span class="legendSwatch current"></span>Latest temp</span>
      <span class="legendItem"><span class="legendSwatch high"></span>High so far</span>
    </div>
    <div class="tempGraph" data-live-field="graph" data-live-city="${escapeAttribute(city.city)}">${tempGraphSvg(points, city.raw_high_so_far_f)}</div>
    <div class="tempGraphFooter" data-live-field="chips" data-live-city="${escapeAttribute(city.city)}">
      <span class="tempChip">Day high: ${fmtTemp(city.raw_high_so_far_f)}${city.raw_high_so_far_time ? ` at ${escapeHtml(fmtEtTime(city.raw_high_so_far_time))}` : ''}</span>
      <span class="tempChip">Recent high: ${fmtTemp(recentMax)}</span>
      <span class="tempChip">Fast METAR: ${fmtTemp(city.fast_metar_temp_f)}</span>
      <span class="tempChip">Forecast: ${fmtTemp(city.forecast_high_f)}</span>
      <span class="tempChip">Checks every ${tempMeterPollSeconds}s; NWS points often post around 5 min</span>
    </div>
    ${city.latest_feed_lag_warning ? `<div class="feedWarning" data-live-field="warning" data-live-city="${escapeAttribute(city.city)}">${escapeHtml(city.latest_feed_lag_note || '')}</div>` : `<div data-live-field="warning" data-live-city="${escapeAttribute(city.city)}"></div>`}
    ${recentObservationRows(city)}
  `;
}

function heatingSignal(city) {
  const score = Number(city.heating_status_score);
  const safeScore = Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 0;
  const label = city.heating_status_label || 'n/a';
  const toneClass = safeScore >= 60 ? 'hot' : safeScore >= 40 ? 'mixed' : 'slow';
  const reasons = (city.heating_status_reasons || []).slice(0, 3);
  return `
    <div class="heatingSignal ${toneClass}">
      <div class="heatingSignalTop">
        <div>
          <span>Still heating?</span>
          <strong>${escapeHtml(label)}</strong>
        </div>
        <div class="heatingScore">${Number.isFinite(score) ? `${safeScore}/100` : 'n/a'}</div>
      </div>
      <div class="heatingScoreTrack"><div class="heatingScoreFill" style="width:${safeScore}%"></div></div>
      ${reasons.length ? `<div class="heatingReasons">${reasons.map(escapeHtml).join(' ')}</div>` : ''}
    </div>
  `;
}

function marketChecklist(city) {
  return `
    <div class="marketChecklist">
      ${checkItem('Station', city.station_truth_label || 'Official station', 'NWS source used for settlement-style tracking.', '')}
      ${checkItem('Rounding', city.rounding_risk_label || 'Rounding watch', city.rounding_risk_note || '', city.rounding_risk_label === 'Next bucket danger' ? 'warn' : '')}
      ${checkItem('6h clue', city.six_hour_lock_label || 'No 6h max yet', city.six_hour_lock_note || '', city.six_hour_lock_temp_f ? 'warn' : '')}
      ${checkItem('Market check', city.market_confirmation_label || 'Weather-confirmed board', city.false_pump_warning ? 'Kalshi is hotter than the weather signal.' : 'No hotter-market warning right now.', city.market_confirmation_warning ? 'bad' : '')}
    </div>
  `;
}

function checkItem(title, label, note, className) {
  return `
    <div class="checkItem ${className || ''}">
      <span>${escapeHtml(title)}</span>
      <strong>${escapeHtml(label)}</strong>
      ${note ? `<small>${escapeHtml(note)}</small>` : ''}
    </div>
  `;
}

function normalizedTempPoints(city) {
  const byTime = new Map();
  (city.recent_observation_points || []).forEach(point => {
    if (point.time && point.temp_f !== null && point.temp_f !== undefined) {
      byTime.set(point.time, {time: point.time, temp_f: Number(point.temp_f)});
    }
  });
  const endpointTime = city.latest_endpoint_time || city.observation_time;
  const endpointTemp = city.latest_endpoint_temp_f ?? city.current_temp_f;
  if (endpointTime && endpointTemp !== null && endpointTemp !== undefined) {
    byTime.set(endpointTime, {time: endpointTime, temp_f: Number(endpointTemp)});
  }
  return Array.from(byTime.values())
    .filter(point => Number.isFinite(point.temp_f))
    .sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime())
    .slice(-24);
}

function tempGraphSvg(points, dayHighValue = null) {
  if (!points.length) {
    return '<div class="tempGraphEmpty">Waiting for NWS live feed</div>';
  }
  const width = 420;
  const height = 174;
  const pad = 16;
  const temps = points.map(point => Number(point.temp_f)).filter(Number.isFinite);
  const dayHigh = Number(dayHighValue);
  let runningHigh = Number.isFinite(dayHigh) ? dayHigh : -Infinity;
  const highPoints = points.map(point => {
    runningHigh = Math.max(runningHigh, Number(point.temp_f));
    return {...point, temp_f: runningHigh};
  });
  const allTemps = temps.concat(highPoints.map(point => point.temp_f));
  const min = Math.floor(Math.min(...allTemps) - 1);
  const max = Math.ceil(Math.max(...allTemps) + 1);
  const span = Math.max(1, max - min);
  const x = index => points.length === 1 ? width - pad : pad + (index / (points.length - 1)) * (width - pad * 2);
  const y = temp => height - pad - ((temp - min) / span) * (height - pad * 2);
  const line = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${x(index).toFixed(1)} ${y(point.temp_f).toFixed(1)}`).join(' ');
  const highLine = highPoints.map((point, index) => {
    if (index === 0) return `M ${x(index).toFixed(1)} ${y(point.temp_f).toFixed(1)}`;
    const prev = highPoints[index - 1];
    return `L ${x(index).toFixed(1)} ${y(prev.temp_f).toFixed(1)} L ${x(index).toFixed(1)} ${y(point.temp_f).toFixed(1)}`;
  }).join(' ');
  const area = `${line} L ${x(points.length - 1).toFixed(1)} ${height - pad} L ${x(0).toFixed(1)} ${height - pad} Z`;
  const last = points[points.length - 1];
  const lastHigh = highPoints[highPoints.length - 1];
  return `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Recent NWS temperature graph">
      <path class="tempGraphArea" d="${area}"></path>
      <path class="tempGraphPath" d="${line}"></path>
      <path class="tempGraphHighPath" d="${highLine}"></path>
      <circle class="tempGraphPoint" cx="${x(points.length - 1).toFixed(1)}" cy="${y(last.temp_f).toFixed(1)}" r="5"></circle>
      <circle class="tempGraphHighPoint" cx="${x(highPoints.length - 1).toFixed(1)}" cy="${y(lastHigh.temp_f).toFixed(1)}" r="5"></circle>
    </svg>
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
  document.querySelectorAll('[data-live-field="refresh"]').forEach(element => {
    element.textContent = tempMeterCountdown(element.dataset.liveCity);
  });
  if (seconds <= 0 && !refreshInFlight) {
    load();
  }
}

function updatePeakCountdowns() {
  document.querySelectorAll('.peakCountdown').forEach(element => {
    element.textContent = peakCountdownFromIso(element.dataset.peakTime);
  });
}

async function refreshTempMeter(cityName) {
  if (!cityName || tempMeterInFlight.has(cityName)) return;
  tempMeterInFlight.add(cityName);
  try {
    const response = await fetch(`/api/temp-meter?city=${encodeURIComponent(cityName)}`, {cache: 'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    if (payload.browser_poll_seconds) {
      tempMeterPollSeconds = Number(payload.browser_poll_seconds);
      syncPollTimers();
    }
    updateLiveTempGraph(payload);
    const refreshSeconds = Number(payload.cache_ttl_seconds || payload.refresh_seconds || 3);
    tempMeterNextPullAt.set(cityName, Date.now() + refreshSeconds * 1000);
  } catch (error) {
    tempMeterNextPullAt.set(cityName, Date.now() + 3000);
  } finally {
    tempMeterInFlight.delete(cityName);
  }
}

function refreshVisibleTempMeters() {
  document.querySelectorAll('[data-live-card]').forEach(card => refreshTempMeter(card.dataset.liveCard));
}

function updateLiveTempGraph(payload) {
  const cityName = payload.city;
  setLiveField(cityName, 'current', fmtTemp(payload.current_temp_f));
  setLiveField(cityName, 'time', fmtEtTime(payload.latest_history_time || payload.latest_endpoint_time));
  setLiveField(cityName, 'rawHigh', fmtTemp(payload.raw_high_so_far_f));
  setLiveField(cityName, 'rawHighTime', fmtEtTime(payload.raw_high_so_far_time));
  setLiveField(cityName, 'rounded', payload.rounded_if_final_now_f === null || payload.rounded_if_final_now_f === undefined ? 'n/a' : `${Number(payload.rounded_if_final_now_f).toFixed(0)}F`);
  setLiveHtml(cityName, 'graph', tempGraphSvg(normalizedTempPoints(payload), payload.raw_high_so_far_f));
  setLiveHtml(cityName, 'chips', `
    <span class="tempChip">Day high: ${fmtTemp(payload.raw_high_so_far_f)}${payload.raw_high_so_far_time ? ` at ${escapeHtml(fmtEtTime(payload.raw_high_so_far_time))}` : ''}</span>
    <span class="tempChip">Recent high: ${fmtTemp(payload.recent_observation_max_f)}</span>
    <span class="tempChip">Fast METAR: ${fmtTemp(payload.fast_metar_temp_f)}</span>
    <span class="tempChip">Latest: ${fmtTemp(payload.current_temp_f)}</span>
    <span class="tempChip">Checks every ${tempMeterPollSeconds}s; NWS points often post around 5 min</span>
  `);
  setLiveHtml(cityName, 'warning', payload.latest_feed_lag_warning ? `<div class="feedWarning">${escapeHtml(payload.latest_feed_lag_note || '')}</div>` : '');
}

function setLiveField(cityName, field, text) {
  document.querySelectorAll(`[data-live-field="${field}"][data-live-city="${cssEscape(cityName)}"]`).forEach(element => {
    element.textContent = text;
  });
}

function setLiveHtml(cityName, field, html) {
  document.querySelectorAll(`[data-live-field="${field}"][data-live-city="${cssEscape(cityName)}"]`).forEach(element => {
    element.innerHTML = html;
  });
}

function cssEscape(value) {
  if (window.CSS && CSS.escape) return CSS.escape(value);
  return String(value).replace(/["\\\\]/g, '\\\\$&');
}

function syncPollTimers() {
  if (mainPollTimer) clearInterval(mainPollTimer);
  if (tempMeterPollTimer) clearInterval(tempMeterPollTimer);
  mainPollTimer = setInterval(load, Math.max(1, mainPollSeconds) * 1000);
  tempMeterPollTimer = setInterval(refreshVisibleTempMeters, Math.max(1, tempMeterPollSeconds) * 1000);
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
    city.fast_feed_url ? ['Fast METAR', city.fast_feed_url] : null,
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

async function loadHistory() {
  if (!historyCity || !historyCharts || historyInFlight) return;
  historyInFlight = true;
  historyCharts.innerHTML = '<div class="historyEmpty">Loading saved market history...</div>';
  try {
    const response = await fetch(`/api/history?city=${encodeURIComponent(historyCity.value)}`, {cache: 'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderHistory(await response.json());
  } catch (error) {
    historyCharts.innerHTML = `<div class="historyEmpty">Historic data failed to load: ${escapeHtml(error.message)}</div>`;
  } finally {
    historyInFlight = false;
  }
}

function renderHistory(payload) {
  const days = payload.days || [];
  if (!days.length) {
    historyCharts.innerHTML = `<div class="historyEmpty">No saved 3-day history yet for ${escapeHtml(payload.city || historyCity.value)}. Run the scanner through the day to build this view.</div>`;
    return;
  }
  historyCharts.innerHTML = days.map(day => historyDayCard(day)).join('');
}

function historyDayCard(day) {
  const points = day.series || [];
  const bucketCount = (day.bucket_labels || []).length;
  return `
    <article class="historyCard">
      <div class="historyCardHead">
        <div>
          <strong>${escapeHtml(day.market_date || 'Unknown date')}</strong>
          <span>${points.length} saved pulls | ${bucketCount} buckets tracked</span>
        </div>
        <div class="historyLegend">
          <span class="legendItem"><span class="legendSwatch kalshi"></span>Kalshi forecast</span>
          <span class="legendItem"><span class="legendSwatch actual"></span>Actual temp</span>
          <span class="legendItem"><span class="legendSwatch forecast"></span>NWS forecast</span>
          <span class="legendItem"><span class="legendSwatch bucket"></span>Bucket prices</span>
        </div>
      </div>
      <div class="historyChart">${historyChartSvg(day)}</div>
    </article>
  `;
}

function historyChartSvg(day) {
  const points = (day.series || []).filter(point => point && point.captured_at);
  if (!points.length) {
    return '<div class="historyEmpty">No saved points for this day yet.</div>';
  }
  const width = 760;
  const height = 258;
  const left = 42;
  const right = 18;
  const top = 18;
  const tempBottom = 153;
  const priceTop = 181;
  const priceBottom = 236;
  const x = index => points.length === 1 ? left : left + (index / (points.length - 1)) * (width - left - right);

  const tempKeys = ['kalshi_forecast_f', 'actual_temp_f', 'forecast_temp_f'];
  const tempValues = points.flatMap(point => tempKeys.map(key => Number(point[key]))).filter(Number.isFinite);
  const tempMin = tempValues.length ? Math.floor(Math.min(...tempValues) - 1) : 0;
  const tempMax = tempValues.length ? Math.ceil(Math.max(...tempValues) + 1) : 1;
  const tempSpan = Math.max(1, tempMax - tempMin);
  const yTemp = value => tempBottom - ((Number(value) - tempMin) / tempSpan) * (tempBottom - top);
  const yPrice = value => priceBottom - (Math.max(0, Math.min(100, Number(value))) / 100) * (priceBottom - priceTop);

  const bucketLabels = topHistoryBucketLabels(day, points).slice(0, 4);
  const bucketLines = bucketLabels.map((label, index) => {
    const path = historyLinePath(points, point => point.bucket_prices ? point.bucket_prices[label] : null, yPrice, x);
    if (!path) return '';
    const color = historyBucketColor(index);
    const circles = historyCircles(points, point => point.bucket_prices ? point.bucket_prices[label] : null, yPrice, x, color, 'bucket', point => `${historyPointTime(point)}\\n${label}: ${Number(point.bucket_prices[label]).toFixed(0)}c`);
    return `<path class="histBucket" d="${path}" stroke="${color}"></path>${circles}`;
  }).join('');

  const kalshiPath = historyLinePath(points, point => point.kalshi_forecast_f, yTemp, x);
  const actualPath = historyLinePath(points, point => point.actual_temp_f, yTemp, x);
  const forecastPath = historyLinePath(points, point => point.forecast_temp_f, yTemp, x);

  return `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Historic Kalshi and weather chart for ${escapeAttribute(day.market_date || '')}">
      <line class="histAxis" x1="${left}" x2="${width - right}" y1="${tempBottom}" y2="${tempBottom}"></line>
      <line class="histAxis" x1="${left}" x2="${width - right}" y1="${priceTop}" y2="${priceTop}"></line>
      <line class="histAxis" x1="${left}" x2="${width - right}" y1="${priceBottom}" y2="${priceBottom}"></line>
      <text class="histLabel" x="8" y="${top + 7}">Temp F</text>
      <text class="histLabel" x="8" y="${priceTop + 8}">Yes c</text>
      <text class="histLabel" x="${left}" y="${height - 8}">${escapeHtml(historyShortTime(points[0].captured_at))}</text>
      <text class="histLabel" x="${width - 84}" y="${height - 8}">${escapeHtml(historyShortTime(points[points.length - 1].captured_at))}</text>
      <text class="histLabel" x="${width - 54}" y="${top + 8}">${tempMax}F</text>
      <text class="histLabel" x="${width - 54}" y="${tempBottom - 4}">${tempMin}F</text>
      ${kalshiPath ? `<path class="histLine histKalshi" d="${kalshiPath}"></path>` : ''}
      ${actualPath ? `<path class="histLine histActual" d="${actualPath}"></path>` : ''}
      ${forecastPath ? `<path class="histLine histForecast" d="${forecastPath}"></path>` : ''}
      ${bucketLines}
      ${historyCircles(points, point => point.kalshi_forecast_f, yTemp, x, '', 'kalshi', point => `${historyPointTime(point)}\\nKalshi forecast: ${Number(point.kalshi_forecast_f).toFixed(1)}F\\nFavorite: ${point.favorite_bucket || 'n/a'} @ ${Number(point.favorite_price || 0).toFixed(0)}c`)}
      ${historyCircles(points, point => point.actual_temp_f, yTemp, x, '', 'actual', point => `${historyPointTime(point)}\\nActual/high-so-far: ${Number(point.actual_temp_f).toFixed(1)}F`)}
      ${historyCircles(points, point => point.forecast_temp_f, yTemp, x, '', 'forecast', point => `${historyPointTime(point)}\\nNWS forecast: ${Number(point.forecast_temp_f).toFixed(1)}F`)}
    </svg>
  `;
}

function historyLinePath(points, valueFn, yFn, xFn) {
  let path = '';
  let hasStarted = false;
  points.forEach((point, index) => {
    const value = Number(valueFn(point));
    if (!Number.isFinite(value)) {
      hasStarted = false;
      return;
    }
    path += `${hasStarted ? ' L' : ' M'} ${xFn(index).toFixed(1)} ${yFn(value).toFixed(1)}`;
    hasStarted = true;
  });
  return path.trim();
}

function historyCircles(points, valueFn, yFn, xFn, color, className, titleFn) {
  return points.map((point, index) => {
    const value = Number(valueFn(point));
    if (!Number.isFinite(value)) return '';
    const fill = color ? ` fill="${color}"` : '';
    return `<circle class="histPoint ${className}" cx="${xFn(index).toFixed(1)}" cy="${yFn(value).toFixed(1)}" r="4"${fill}><title>${escapeHtml(titleFn(point))}</title></circle>`;
  }).join('');
}

function topHistoryBucketLabels(day, points) {
  const labels = new Set(day.bucket_labels || []);
  points.forEach(point => Object.keys(point.bucket_prices || {}).forEach(label => labels.add(label)));
  return Array.from(labels).sort((a, b) => historyBucketMax(points, b) - historyBucketMax(points, a));
}

function historyBucketMax(points, label) {
  return Math.max(0, ...points.map(point => Number(point.bucket_prices ? point.bucket_prices[label] : null)).filter(Number.isFinite));
}

function historyBucketColor(index) {
  return ['#45c8d8', '#d49b31', '#a178ff', '#ff7e67'][index % 4];
}

function historyPointTime(point) {
  return historyShortTime(point.captured_at);
}

function historyShortTime(value) {
  if (!value) return 'n/a';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'n/a';
  return date.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York'});
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
loadHistory();
if (historyCity) historyCity.addEventListener('change', loadHistory);
syncPollTimers();
setInterval(() => {
  updateCountdown();
  updatePeakCountdowns();
}, 1000);
"""
