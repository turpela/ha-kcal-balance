#!/usr/bin/env python3
"""
Kcal Balance add-on — v2.3.0

Architecture:
  - Flask web server (port 8080) served via HA ingress → dashboard in sidebar
  - Background polling thread → FatSecret every scan_interval seconds
  - SQLite /data/kcal.db → persistent history (food + burned per day)
  - HA sensor push → thin layer for automations/notifications

Modules:
  fatsecret.py  — FatSecret API client
  ha.py         — HA Supervisor API + sensor push
  store.py      — SQLite persistence
"""

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template_string, request

import fatsecret as fs
import ha
import store

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("kcal-balance")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OPTIONS_FILE   = "/data/options.json"
TIMEZONE       = ZoneInfo("Europe/Helsinki")
DEFAULT_GARMIN = {"U1": "sensor.garmin_connect_calories",
                  "U2": "sensor.garmin_connect_calories_2"}
DEFAULT_GDA    = 2000.0

# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def today_local():
    return datetime.now(TIMEZONE).date()

def week_monday(d):
    return d - timedelta(days=d.weekday())

def week_dates(d):
    """All dates from Monday of d's week through d (inclusive)."""
    monday = week_monday(d)
    return [monday + timedelta(days=i) for i in range(d.weekday() + 1)]

def month_start(d):
    return d.replace(day=1)

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config():
    with open(OPTIONS_FILE) as f:
        return json.load(f)

def _strip(v):
    return (v or "").strip()

def build_user_list(opts):
    def _user(label, suffix, prefix):
        return {
            "label":  label,
            "suffix": suffix,
            "creds": {
                "consumer_key":        _strip(opts.get(f"{prefix}consumer_key")),
                "consumer_secret":     _strip(opts.get(f"{prefix}consumer_secret")),
                "access_token":        _strip(opts.get(f"{prefix}access_token")),
                "access_token_secret": _strip(opts.get(f"{prefix}access_token_secret")),
            },
            "garmin_entity": _strip(opts.get(f"{prefix}garmin_entity"))
                             or DEFAULT_GARMIN[label],
        }

    users = [_user("U1", "u1", "u1_")]
    if _strip(opts.get("u2_consumer_key")):
        users.append(_user("U2", "u2", "u2_"))
        log.info("User 2 configured — polling both users")
    else:
        log.info("User 2 not configured — polling User 1 only")
    return users

# ---------------------------------------------------------------------------
# Shared state (updated by poller, read by API routes)
# ---------------------------------------------------------------------------
_state_lock = threading.Lock()
_state = {}
_users = []

# ---------------------------------------------------------------------------
# Background polling thread
# ---------------------------------------------------------------------------

def _poll_loop(users, supervisor_token, scan_interval):
    # Backfill missing week days from FatSecret on startup (no burned data available)
    today = today_local()
    for user in users:
        for d in week_dates(today):
            if not store.has_day(user["label"], d.isoformat()):
                log.info("[%s] Backfilling %s from FatSecret...", user["label"], d.isoformat())
                totals = fs.fetch_day(user["creds"], d)
                if totals:
                    store.upsert_day(user["label"], d.isoformat(), totals)
                time.sleep(0.3)

    log.info("Polling %d user(s) every %ds", len(users), scan_interval)

    while True:
        today     = today_local()
        today_str = today.isoformat()
        monday    = week_monday(today)
        mstart    = month_start(today)

        for user in users:
            label  = user["label"]
            suffix = user["suffix"]
            try:
                # FatSecret: consumed today
                totals = fs.fetch_day(user["creds"], today)
                if totals is None:
                    continue

                # Garmin: burned calories (read before storing so we persist it)
                burned = ha.ha_get(supervisor_token, user["garmin_entity"])

                # Persist food + burned for today
                store.upsert_day(label, today_str, totals, burned=burned)

                # GDA from settings (editable in dashboard Settings tab)
                gda     = float(store.get_setting(f"{suffix}_gda", DEFAULT_GDA))
                gda_pct = round(totals["calories"] / gda * 100, 1) if gda > 0 else None

                # Net energy: burned − consumed (positive = deficit)
                net = round(burned - totals["calories"], 1) if burned is not None else None

                # Weekly totals from DB (includes stored burned per day)
                week_rows     = store.get_range(label, monday.isoformat(), today_str)
                weekly_totals = store.aggregate(week_rows)
                days_tracked  = len(week_rows)
                days_elapsed  = len(week_dates(today))

                # Weekly net = sum of daily (burned − consumed) for days with Garmin data
                weekly_net = round(
                    sum((r["burned"] - r["calories"]) for r in week_rows if (r.get("burned") or 0) > 0),
                    1
                ) if any((r.get("burned") or 0) > 0 for r in week_rows) else None

                # Pro-rated weekly GDA
                weekly_gda     = round(gda * days_elapsed, 1) if gda > 0 else None
                weekly_gda_pct = round(weekly_totals["calories"] / weekly_gda * 100, 1) \
                                 if weekly_gda and weekly_gda > 0 else None

                # Monthly totals (for snapshot summary)
                month_rows     = store.get_range(label, mstart.isoformat(), today_str)
                monthly_totals = store.aggregate(month_rows)
                monthly_net    = round(
                    sum((r["burned"] - r["calories"]) for r in month_rows if (r.get("burned") or 0) > 0),
                    1
                ) if any((r.get("burned") or 0) > 0 for r in month_rows) else None
                monthly_days_tracked = len(month_rows)

                snapshot = {
                    "label":               label,
                    "today":               totals,
                    "burned":              burned,
                    "gda":                 gda,
                    "gda_pct":             gda_pct,
                    "net":                 net,
                    "weekly":              weekly_totals,
                    "weekly_net":          weekly_net,
                    "weekly_gda":          weekly_gda,
                    "weekly_gda_pct":      weekly_gda_pct,
                    "days_tracked":        days_tracked,
                    "days_elapsed":        days_elapsed,
                    "monthly":             monthly_totals,
                    "monthly_net":         monthly_net,
                    "monthly_days_tracked": monthly_days_tracked,
                    "last_updated":        datetime.now(TIMEZONE).isoformat(),
                }

                with _state_lock:
                    _state[label] = snapshot

                # Push HA sensors
                try:
                    ha.push_sensors(
                        supervisor_token, suffix, label,
                        totals, burned, net,
                        gda, gda_pct,
                        weekly_totals, weekly_gda, weekly_gda_pct, days_tracked,
                    )
                except Exception as exc:
                    log.warning("[%s] Sensor push error: %s", label, exc)

                log.info(
                    "[%s] Consumed %.0f kcal | GDA: %s%% | Net: %s | Burned: %s",
                    label,
                    totals["calories"],
                    f"{gda_pct:.1f}" if gda_pct is not None else "N/A",
                    f"{net:+.0f}"    if net     is not None else "N/A",
                    f"{burned:.0f}"  if burned  is not None else "N/A",
                )

            except Exception as exc:
                log.exception("[%s] Unexpected poll error: %s", label, exc)

        time.sleep(scan_interval)

# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------
app = Flask(__name__)

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kcal Balance</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root {
  --bg:     #111113;
  --card:   #1c1c1e;
  --card2:  #2c2c2e;
  --text:   #f5f5f7;
  --sub:    #98989f;
  --green:  #30d158;
  --yellow: #ffd60a;
  --red:    #ff453a;
  --blue:   #0a84ff;
  --border: rgba(255,255,255,0.08);
  --r:      12px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  padding: 16px;
  font-size: 15px;
}
/* ── Tabs ── */
.tabs { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
.tab {
  padding: 7px 18px; border-radius: 20px; border: none; cursor: pointer;
  font-size: 14px; font-weight: 500;
  background: var(--card2); color: var(--sub); transition: all .15s;
}
.tab.active { background: var(--blue); color: #fff; }
.panel { display: none; }
.panel.active { display: block; }
/* ── Section titles ── */
.section-title {
  font-size: 18px; font-weight: 700; margin-bottom: 12px;
  padding-bottom: 8px; border-bottom: 1px solid var(--border);
}
.user-block { margin-bottom: 28px; }
/* ── Card grid ── */
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
@media (max-width: 560px) { .grid { grid-template-columns: 1fr; } }
.card {
  background: var(--card); border-radius: var(--r); padding: 14px;
}
.card-title {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .6px; color: var(--sub); margin-bottom: 10px;
}
/* ── Big value ── */
.big { display: flex; align-items: baseline; gap: 5px; }
.big-num { font-size: 34px; font-weight: 700; line-height: 1; }
.big-unit { font-size: 15px; color: var(--sub); }
.big-sub { font-size: 12px; color: var(--sub); margin-top: 4px; }
/* ── Progress bar ── */
.bar-wrap {
  height: 5px; border-radius: 3px;
  background: rgba(255,255,255,0.08); margin: 10px 0 3px; overflow: hidden;
}
.bar-fill { height: 100%; border-radius: 3px; transition: width .4s; }
.bar-label { font-size: 11px; }
/* ── Metric rows ── */
.metric {
  display: flex; justify-content: space-between; align-items: center;
  padding: 7px 0; border-bottom: 1px solid var(--border);
}
.metric:last-child { border-bottom: none; }
.metric-label { font-size: 13px; color: var(--sub); }
.metric-value { font-size: 14px; font-weight: 600; }
/* ── Colours ── */
.green  { color: var(--green);  }
.yellow { color: var(--yellow); }
.red    { color: var(--red);    }
.blue   { color: var(--blue);   }
.muted  { color: var(--sub);    }
/* ── Footer ── */
.footer { text-align: center; font-size: 12px; color: var(--sub); margin-top: 16px; }
/* ── Empty state ── */
.empty { padding: 32px; text-align: center; color: var(--sub); }
/* ── Editable name ── */
.user-name {
  cursor: pointer; border-radius: 6px; padding: 2px 6px; margin: -2px -6px;
  transition: background .15s;
}
.user-name:hover { background: rgba(255,255,255,0.08); }
.user-name:focus {
  outline: none; background: rgba(255,255,255,0.12);
  box-shadow: 0 0 0 2px var(--blue);
}
/* ── Settings panel ── */
.settings-block { margin-bottom: 24px; }
.settings-block h3 {
  font-size: 16px; font-weight: 600; margin-bottom: 12px;
  padding-bottom: 8px; border-bottom: 1px solid var(--border);
}
.field { margin-bottom: 12px; }
.field label {
  display: block; font-size: 12px; color: var(--sub);
  text-transform: uppercase; letter-spacing: .5px; margin-bottom: 5px;
}
.field input {
  width: 100%; padding: 9px 12px; background: var(--card2);
  border: 1px solid var(--border); border-radius: 8px;
  color: var(--text); font-size: 15px;
}
.field input:focus { outline: none; border-color: var(--blue); }
.btn-save {
  padding: 9px 24px; background: var(--blue); color: #fff;
  border: none; border-radius: 10px; font-size: 14px; font-weight: 600;
  cursor: pointer; transition: opacity .15s;
}
.btn-save:hover { opacity: .85; }
.save-msg { font-size: 13px; color: var(--green); margin-left: 12px; display: none; }
</style>
</head>
<body>

<div class="tabs">
  <button class="tab active" onclick="showTab('today',this)">Today</button>
  <button class="tab"        onclick="showTab('week',this)">This Week</button>
  <button class="tab"        onclick="showTab('month',this)">This Month</button>
  <button class="tab"        onclick="showTab('settings',this)">Settings</button>
</div>

<div id="today"    class="panel active"><div id="today-content"><div class="empty">Loading…</div></div></div>
<div id="week"     class="panel"><div id="week-content"><div class="empty">Loading…</div></div></div>
<div id="month"    class="panel"><div id="month-content"><div class="empty">Loading…</div></div></div>
<div id="settings" class="panel"><div id="settings-content"><div class="empty">Loading…</div></div></div>

<div class="footer" id="footer"></div>

<script>
/* ── Utilities ── */
function gdaColor(pct) {
  if (pct == null) return 'var(--sub)';
  if (pct < 90)   return 'var(--green)';
  if (pct <= 100) return 'var(--yellow)';
  return 'var(--red)';
}
function netColor(v) {
  if (v == null) return 'var(--sub)';
  return v > 0 ? 'var(--green)' : v < 0 ? 'var(--red)' : 'var(--sub)';
}
function netBarColor(v) {
  if (!v) return 'rgba(152,152,159,.4)';
  return v > 0 ? 'rgba(48,209,88,.75)' : 'rgba(255,69,58,.75)';
}
function sign(v, dec=0) {
  if (v == null) return '—';
  return (v >= 0 ? '+' : '') + Number(v).toFixed(dec);
}
function fmt(v, dec=1) { return v != null ? Number(v).toFixed(dec) : '—'; }

function metric(label, valueHtml) {
  return `<div class="metric">
    <span class="metric-label">${label}</span>
    <span class="metric-value">${valueHtml}</span>
  </div>`;
}

/* ── Settings / user names ── */
let _settings = { u1_name: 'User 1', u2_name: 'User 2', u1_gda: 2000, u2_gda: 2000 };

async function loadSettings() {
  try {
    const r = await fetch('api/settings');
    const s = await r.json();
    _settings.u1_name = s.u1_name || 'User 1';
    _settings.u2_name = s.u2_name || 'User 2';
    _settings.u1_gda  = s.u1_gda  || 2000;
    _settings.u2_gda  = s.u2_gda  || 2000;
  } catch(e) { /* keep defaults */ }
}

function userName(lbl) { return lbl === 'U1' ? _settings.u1_name : _settings.u2_name; }

function editableName(lbl) {
  return `<span
    class="user-name"
    contenteditable="true"
    spellcheck="false"
    data-lbl="${lbl}"
    onkeydown="if(event.key==='Enter'){event.preventDefault();this.blur();}"
    onblur="saveName(this)"
  >${userName(lbl)}</span>`;
}

async function saveName(el) {
  const lbl  = el.dataset.lbl;
  const key  = lbl === 'U1' ? 'u1_name' : 'u2_name';
  const name = el.textContent.trim() || (lbl === 'U1' ? 'User 1' : 'User 2');
  el.textContent = name;
  _settings[key] = name;
  try {
    await fetch('api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [key]: name }),
    });
    document.querySelectorAll(`[data-lbl="${lbl}"].user-name`).forEach(e => {
      if (e !== el) e.textContent = name;
    });
  } catch(e) { console.error('Could not save name', e); }
}

/* ── Tabs ── */
let weekLoaded = false, monthLoaded = false;
function showTab(name, btn) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === name));
  if (name === 'week'     && !weekLoaded)  { loadWeek();  weekLoaded  = true; }
  if (name === 'month'    && !monthLoaded) { loadMonth(); monthLoaded = true; }
  if (name === 'settings') renderSettings();
}

/* ── Today ── */
function renderUserToday(d) {
  const t   = d.today || {};
  const pct = d.gda_pct ?? 0;
  const barW = Math.min(100, pct).toFixed(1);
  const barC = gdaColor(pct);

  return `
  <div class="grid">
    <!-- Net Cal — hero card -->
    <div class="card">
      <div class="card-title">Net Cal</div>
      ${d.net != null ? `
        <div class="big">
          <span class="big-num" style="color:${netColor(d.net)}">${sign(d.net)}</span>
          <span class="big-unit">kcal</span>
        </div>
        <div class="big-sub muted">${d.net > 0 ? 'deficit' : d.net < 0 ? 'surplus' : 'balanced'}</div>
        ${metric('Garmin burned', `<span class="blue">${fmt(d.burned, 0)} kcal</span>`)}
      ` : `
        <div class="big-num muted">—</div>
        <div class="big-sub muted" style="margin-top:6px">Garmin not connected</div>
      `}
    </div>

    <!-- Consumed + GDA% -->
    <div class="card">
      <div class="card-title">Consumed</div>
      <div class="big">
        <span class="big-num">${fmt(t.calories, 0)}</span>
        <span class="big-unit">kcal</span>
      </div>
      <div class="bar-wrap">
        <div class="bar-fill" style="width:${barW}%;background:${barC}"></div>
      </div>
      <div class="bar-label" style="color:${barC}">${pct.toFixed(1)}% of GDA (${fmt(d.gda, 0)} kcal)</div>
    </div>

    <!-- Macros -->
    <div class="card" style="grid-column:1/-1">
      <div class="card-title">Macros</div>
      ${metric('Protein', `${fmt(t.protein)} g`)}
      ${metric('Fat',     `${fmt(t.fat)} g`)}
      ${metric('Carbs',   `${fmt(t.carbs)} g`)}
    </div>
  </div>`;
}

async function loadToday() {
  try {
    const r = await fetch('api/today');
    const data = await r.json();

    if (!Object.keys(data).length) {
      document.getElementById('today-content').innerHTML =
        '<div class="empty">Add-on is starting — first poll in a moment…</div>';
      return;
    }

    let html = '';
    for (const lbl of ['U1','U2']) {
      if (!data[lbl]) continue;
      html += `<div class="user-block">
        <div class="section-title">👤 ${editableName(lbl)}</div>
        ${renderUserToday(data[lbl])}
      </div>`;
    }
    document.getElementById('today-content').innerHTML = html;

    const ts = data.U1?.last_updated || data.U2?.last_updated;
    if (ts) {
      document.getElementById('footer').textContent =
        `Updated ${new Date(ts).toLocaleTimeString()} · auto-refreshes every 60 s`;
    }
  } catch(e) {
    document.getElementById('today-content').innerHTML =
      '<div class="empty" style="color:var(--red)">Could not load data</div>';
  }
}

/* ── Shared chart builder ── */
const chartInstances = {};

function buildNetChart(canvasId, rows, chartKey) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  if (chartInstances[chartKey]) chartInstances[chartKey].destroy();

  const labels   = rows.map(r => {
    const d = new Date(r.date + 'T12:00:00');
    return d.toLocaleDateString(undefined, {weekday:'short', day:'numeric'});
  });
  const netVals  = rows.map(r => (r.burned > 0) ? +(r.burned - r.calories).toFixed(1) : 0);
  const colors   = netVals.map(v => netBarColor(v));

  chartInstances[chartKey] = new Chart(canvas, {
    data: {
      labels,
      datasets: [
        {
          type: 'bar', label: 'Net Cal', data: netVals,
          backgroundColor: colors, borderRadius: 5,
        },
        {
          type: 'line', label: 'Break-even',
          data: rows.map(() => 0),
          borderColor: 'rgba(152,152,159,.5)', borderDash: [4,4],
          pointRadius: 0, fill: false, borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color:'#98989f', font:{size:11} }, grid: { color:'rgba(255,255,255,.04)' } },
        y: {
          ticks: { color:'#98989f', font:{size:11},
            callback: v => (v >= 0 ? '+' : '') + v },
          grid: { color:'rgba(255,255,255,.04)' },
        },
      },
    },
  });
}

/* ── This Week ── */
async function loadWeek() {
  try {
    const [wr, tr] = await Promise.all([fetch('api/week'), fetch('api/today')]);
    const weekData  = await wr.json();
    const todayData = await tr.json();

    let html = '';
    for (const lbl of ['U1','U2']) {
      const rows = weekData[lbl];
      if (!rows || !rows.length) continue;
      const td  = todayData[lbl] || {};
      const gda = td.gda || 2000;

      html += `<div class="user-block">
        <div class="section-title">👤 ${editableName(lbl)} — This Week</div>
        <div class="card" style="margin-bottom:10px">
          <div class="card-title">Daily Net Cal (burned − consumed)</div>
          <canvas id="wchart-${lbl}" height="110"></canvas>
        </div>
        <div class="card">
          <div class="card-title">Weekly Summary</div>
          ${td.weekly_net != null ? metric('Net Cal',
              `<span style="color:${netColor(td.weekly_net)}">${sign(td.weekly_net)} kcal</span>`) : ''}
          ${metric('Consumed', `${fmt(td.weekly?.calories ?? 0, 0)} kcal`)}
          ${td.weekly_gda_pct != null ? metric(
              `GDA% (${td.days_elapsed ?? 1} day${(td.days_elapsed ?? 1) !== 1 ? 's' : ''})`,
              `<span style="color:${gdaColor(td.weekly_gda_pct)}">${fmt(td.weekly_gda_pct, 1)}%</span>`) : ''}
          ${metric('Days tracked', `${td.days_tracked ?? rows.length} / ${td.days_elapsed ?? 7}`)}
          ${metric('Protein', `${fmt(td.weekly?.protein ?? 0)} g`)}
          ${metric('Fat',     `${fmt(td.weekly?.fat ?? 0)} g`)}
          ${metric('Carbs',   `${fmt(td.weekly?.carbs ?? 0)} g`)}
        </div>
      </div>`;
    }

    document.getElementById('week-content').innerHTML = html || '<div class="empty">No weekly data yet</div>';

    for (const lbl of ['U1','U2']) {
      const rows = weekData[lbl];
      if (!rows || !rows.length) continue;
      buildNetChart(`wchart-${lbl}`, rows, `week-${lbl}`);
    }
  } catch(e) {
    document.getElementById('week-content').innerHTML =
      '<div class="empty" style="color:var(--red)">Could not load week data</div>';
    console.error(e);
  }
}

/* ── This Month ── */
async function loadMonth() {
  try {
    const [mr, tr] = await Promise.all([fetch('api/month'), fetch('api/today')]);
    const monthData = await mr.json();
    const todayData = await tr.json();

    let html = '';
    for (const lbl of ['U1','U2']) {
      const rows = monthData[lbl];
      if (!rows || !rows.length) continue;
      const td = todayData[lbl] || {};

      // Days in deficit/surplus for summary
      const netRows = rows.filter(r => (r.burned || 0) > 0);
      const deficitDays  = netRows.filter(r => r.burned - r.calories > 0).length;
      const surplusDays  = netRows.filter(r => r.burned - r.calories <= 0).length;

      // Month label from first row date
      const monthLabel = rows.length
        ? new Date(rows[0].date + 'T12:00:00').toLocaleDateString(undefined, {month:'long', year:'numeric'})
        : 'This Month';

      html += `<div class="user-block">
        <div class="section-title">👤 ${editableName(lbl)} — ${monthLabel}</div>
        <div class="card" style="margin-bottom:10px">
          <div class="card-title">Daily Net Cal (burned − consumed)</div>
          <canvas id="mchart-${lbl}" height="130"></canvas>
        </div>
        <div class="card">
          <div class="card-title">Monthly Summary</div>
          ${td.monthly_net != null ? metric('Net Cal (total)',
              `<span style="color:${netColor(td.monthly_net)}">${sign(td.monthly_net)} kcal</span>`) : ''}
          ${metric('Consumed', `${fmt(td.monthly?.calories ?? 0, 0)} kcal`)}
          ${netRows.length ? metric('Deficit days', `<span class="green">${deficitDays}</span> / ${netRows.length}`) : ''}
          ${netRows.length ? metric('Surplus days', `<span class="red">${surplusDays}</span> / ${netRows.length}`) : ''}
          ${metric('Days tracked', `${td.monthly_days_tracked ?? rows.length}`)}
          ${metric('Protein', `${fmt(td.monthly?.protein ?? 0)} g`)}
          ${metric('Fat',     `${fmt(td.monthly?.fat ?? 0)} g`)}
          ${metric('Carbs',   `${fmt(td.monthly?.carbs ?? 0)} g`)}
        </div>
      </div>`;
    }

    document.getElementById('month-content').innerHTML = html || '<div class="empty">No data for this month yet</div>';

    for (const lbl of ['U1','U2']) {
      const rows = monthData[lbl];
      if (!rows || !rows.length) continue;
      buildNetChart(`mchart-${lbl}`, rows, `month-${lbl}`);
    }
  } catch(e) {
    document.getElementById('month-content').innerHTML =
      '<div class="empty" style="color:var(--red)">Could not load month data</div>';
    console.error(e);
  }
}

/* ── Settings panel ── */
function renderSettings() {
  let html = '';
  for (const lbl of ['U1', 'U2']) {
    const sfx     = lbl.toLowerCase();
    const nameKey = `${sfx}_name`;
    const gdaKey  = `${sfx}_gda`;
    const nameVal = (_settings[nameKey] || '').replace(/"/g, '&quot;');
    const gdaVal  = _settings[gdaKey]  || 2000;
    html += `
    <div class="settings-block">
      <h3>${lbl === 'U1' ? 'User 1' : 'User 2'}</h3>
      <div class="field">
        <label>Name</label>
        <input type="text" id="set-${nameKey}" value="${nameVal}" maxlength="40" placeholder="${lbl === 'U1' ? 'User 1' : 'User 2'}">
      </div>
      <div class="field">
        <label>GDA — Guideline Daily Amount (kcal)</label>
        <input type="number" id="set-${gdaKey}" value="${gdaVal}" min="500" max="9999" step="50">
      </div>
    </div>`;
  }
  html += `
  <button class="btn-save" onclick="saveSettings()">Save</button>
  <span class="save-msg" id="save-msg">Saved!</span>`;
  document.getElementById('settings-content').innerHTML = html;
}

async function saveSettings() {
  const payload = {};
  for (const lbl of ['U1', 'U2']) {
    const sfx = lbl.toLowerCase();
    const nameEl = document.getElementById(`set-${sfx}_name`);
    const gdaEl  = document.getElementById(`set-${sfx}_gda`);
    if (nameEl) {
      const name = nameEl.value.trim();
      if (name) { payload[`${sfx}_name`] = name; _settings[`${sfx}_name`] = name; }
    }
    if (gdaEl) {
      const gda = parseFloat(gdaEl.value);
      if (gda > 0) { payload[`${sfx}_gda`] = gda; _settings[`${sfx}_gda`] = gda; }
    }
  }
  try {
    await fetch('api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const msg = document.getElementById('save-msg');
    msg.style.display = 'inline';
    setTimeout(() => { msg.style.display = 'none'; }, 2000);
  } catch(e) { console.error('Could not save settings', e); }
}

// Boot
loadSettings().then(() => {
  loadToday();
  setInterval(loadToday, 60_000);
});
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    return jsonify({
        "u1_name": store.get_setting("u1_name", "User 1"),
        "u2_name": store.get_setting("u2_name", "User 2"),
        "u1_gda":  float(store.get_setting("u1_gda", DEFAULT_GDA)),
        "u2_gda":  float(store.get_setting("u2_gda", DEFAULT_GDA)),
    })


@app.route("/api/settings", methods=["POST"])
def api_settings_post():
    data = request.get_json(silent=True) or {}
    for key in ("u1_name", "u2_name"):
        if key in data:
            name = str(data[key]).strip()[:40]
            if name:
                store.set_setting(key, name)
    for key in ("u1_gda", "u2_gda"):
        if key in data:
            try:
                gda = float(data[key])
                if 100 <= gda <= 99999:
                    store.set_setting(key, str(gda))
            except (ValueError, TypeError):
                pass
    return jsonify({"ok": True})


@app.route("/api/today")
def api_today():
    with _state_lock:
        return jsonify(dict(_state))


@app.route("/api/week")
def api_week():
    today  = today_local()
    monday = week_monday(today)
    result = {}
    for label in ["U1", "U2"]:
        rows = store.get_range(label, monday.isoformat(), today.isoformat())
        if rows:
            result[label] = rows
    return jsonify(result)


@app.route("/api/month")
def api_month():
    today = today_local()
    start = month_start(today)
    result = {}
    for label in ["U1", "U2"]:
        rows = store.get_range(label, start.isoformat(), today.isoformat())
        if rows:
            result[label] = rows
    return jsonify(result)


@app.route("/api/history")
def api_history():
    """Return n weeks of history. Query param: ?weeks=4"""
    weeks = min(int(request.args.get("weeks", 4)), 52)
    today = today_local()
    start = today - timedelta(weeks=weeks)
    result = {}
    for label in ["U1", "U2"]:
        rows = store.get_range(label, start.isoformat(), today.isoformat())
        if rows:
            result[label] = rows
    return jsonify(result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    log.info("Kcal Balance v2.3.0 starting...")

    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if not supervisor_token:
        log.error("SUPERVISOR_TOKEN not set — is homeassistant_api: true in config.yaml?")
        sys.exit(1)
    log.debug("SUPERVISOR_TOKEN present (%d chars)", len(supervisor_token))

    store.init_db()
    log.info("Database initialised at /data/kcal.db")

    opts          = load_config()
    users         = build_user_list(opts)
    scan_interval = int(opts.get("scan_interval", 300))

    global _users
    _users = users

    t = threading.Thread(
        target=_poll_loop,
        args=(users, supervisor_token, scan_interval),
        daemon=True,
    )
    t.start()

    log.info("Web UI on http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
