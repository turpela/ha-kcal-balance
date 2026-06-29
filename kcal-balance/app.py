#!/usr/bin/env python3
"""
Kcal Balance add-on — v2.0.0

Architecture:
  - Flask web server (port 8080) served via HA ingress → dashboard in sidebar
  - Background polling thread → FatSecret every scan_interval seconds
  - SQLite /data/kcal.db → persistent history (replaces weekly_state.json)
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
DEFAULT_OFFSETS = {"weight_loss": -500, "maintenance": 0, "muscle_gain": 300}

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

# ---------------------------------------------------------------------------
# Goal computation
# ---------------------------------------------------------------------------

def compute_goal(user, burned):
    """Return (goal_kcal: float|None, source: str)."""
    offset = user["goal_offset"] or DEFAULT_OFFSETS.get(user["goal_mode"], 0)
    if burned is not None:
        return round(burned + offset, 1), "garmin"
    if user["goal_kcal"]:
        return float(user["goal_kcal"]), "fixed"
    return None, "none"

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
            "label":        label,
            "suffix":       suffix,
            "creds": {
                "consumer_key":        _strip(opts.get(f"{prefix}consumer_key")),
                "consumer_secret":     _strip(opts.get(f"{prefix}consumer_secret")),
                "access_token":        _strip(opts.get(f"{prefix}access_token")),
                "access_token_secret": _strip(opts.get(f"{prefix}access_token_secret")),
            },
            "goal_mode":    opts.get(f"{prefix}goal_mode", "maintenance"),
            "goal_kcal":    opts.get(f"{prefix}goal_kcal") or 0,
            "goal_offset":  opts.get(f"{prefix}goal_offset") or 0,
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
_state = {}      # label → dict with today's snapshot
_users = []      # list of user dicts (set in main before thread starts)

# ---------------------------------------------------------------------------
# Background polling thread
# ---------------------------------------------------------------------------

def _poll_loop(users, supervisor_token, scan_interval):
    # Backfill any missing week days from FatSecret history on startup
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

        for user in users:
            label  = user["label"]
            suffix = user["suffix"]
            try:
                # FatSecret: consumed today
                totals = fs.fetch_day(user["creds"], today)
                if totals is None:
                    continue
                store.upsert_day(label, today_str, totals)

                # Garmin: burned calories
                burned = ha.ha_get(supervisor_token, user["garmin_entity"])

                # Goal
                goal, goal_source = compute_goal(user, burned)

                # Weekly totals from DB
                week_rows     = store.get_range(label, monday.isoformat(), today_str)
                weekly_totals = store.aggregate(week_rows)
                days_tracked  = len(week_rows)
                weekly_goal   = round(goal * 7, 1) if goal is not None else None

                # Balance / net
                balance         = round(goal - totals["calories"], 1) if goal is not None else None
                net             = round(burned - totals["calories"], 1) if burned is not None else None
                weekly_balance  = round(weekly_goal - weekly_totals["calories"], 1) \
                                  if weekly_goal is not None else None

                snapshot = {
                    "label":          label,
                    "today":          totals,
                    "burned":         burned,
                    "goal":           goal,
                    "goal_mode":      user["goal_mode"],
                    "goal_source":    goal_source,
                    "balance":        balance,
                    "net":            net,
                    "weekly":         weekly_totals,
                    "weekly_goal":    weekly_goal,
                    "weekly_balance": weekly_balance,
                    "days_tracked":   days_tracked,
                    "last_updated":   datetime.now(TIMEZONE).isoformat(),
                }

                with _state_lock:
                    _state[label] = snapshot

                # Push HA sensors
                try:
                    ha.push_sensors(
                        supervisor_token, suffix, label,
                        totals, burned, goal, user["goal_mode"], goal_source,
                        weekly_totals, weekly_goal, days_tracked,
                    )
                except Exception as exc:
                    log.warning("[%s] Sensor push error: %s", label, exc)

                log.info(
                    "[%s] Consumed %.0f kcal | Goal: %s | Balance: %s | Burned: %s",
                    label,
                    totals["calories"],
                    f"{goal:.0f}"    if goal    is not None else "N/A",
                    f"{balance:+.0f}" if balance is not None else "N/A",
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
.tabs { display: flex; gap: 8px; margin-bottom: 20px; }
.tab {
  padding: 7px 20px; border-radius: 20px; border: none; cursor: pointer;
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
.big-sub { font-size: 12px; color: var(--sub); margin-top: 3px; }
/* ── Progress bar ── */
.bar-wrap {
  height: 5px; border-radius: 3px;
  background: rgba(255,255,255,0.08); margin: 10px 0 3px; overflow: hidden;
}
.bar-fill { height: 100%; border-radius: 3px; transition: width .4s; }
.bar-pct { font-size: 11px; color: var(--sub); }
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
</style>
</head>
<body>

<div class="tabs">
  <button class="tab active" onclick="showTab('today',this)">Today</button>
  <button class="tab"        onclick="showTab('week',this)">This Week</button>
</div>

<div id="today" class="panel active">
  <div id="today-content"><div class="empty">Loading…</div></div>
</div>
<div id="week" class="panel">
  <div id="week-content"><div class="empty">Loading…</div></div>
</div>

<div class="footer" id="footer"></div>

<script>
/* ── Utilities ── */
function clr(v) {
  if (v == null) return 'var(--sub)';
  return v >= 100 ? 'var(--green)' : v >= 0 ? 'var(--yellow)' : 'var(--red)';
}
function sign(v) { return v != null ? (v >= 0 ? '+' : '') + v.toFixed(0) : '—'; }
function fmt(v, dec=1) { return v != null ? v.toFixed(dec) : '—'; }

function metric(label, valueHtml) {
  return `<div class="metric">
    <span class="metric-label">${label}</span>
    <span class="metric-value">${valueHtml}</span>
  </div>`;
}

/* ── Settings / user names ── */
let _names = { U1: 'User 1', U2: 'User 2' };

async function loadSettings() {
  try {
    const r = await fetch('api/settings');
    const s = await r.json();
    _names.U1 = s.u1_name || 'User 1';
    _names.U2 = s.u2_name || 'User 2';
  } catch(e) { /* keep defaults */ }
}

function nameKey(lbl) { return lbl === 'U1' ? 'u1_name' : 'u2_name'; }

function editableName(lbl) {
  return `<span
    class="user-name"
    contenteditable="true"
    spellcheck="false"
    data-lbl="${lbl}"
    onkeydown="if(event.key==='Enter'){event.preventDefault();this.blur();}"
    onblur="saveName(this)"
  >${_names[lbl]}</span>`;
}

async function saveName(el) {
  const lbl  = el.dataset.lbl;
  const name = el.textContent.trim() || (lbl === 'U1' ? 'User 1' : 'User 2');
  el.textContent = name;          // normalise whitespace
  _names[lbl] = name;
  try {
    await fetch('api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [nameKey(lbl)]: name }),
    });
    // sync the other tab's heading if visible
    document.querySelectorAll(`[data-lbl="${lbl}"].user-name`).forEach(e => {
      if (e !== el) e.textContent = name;
    });
  } catch(e) { console.error('Could not save name', e); }
}

/* ── Tabs ── */
let weekLoaded = false;
function showTab(name, btn) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === name));
  if (name === 'week' && !weekLoaded) { loadWeek(); weekLoaded = true; }
}

/* ── Today ── */
function renderUserToday(d) {
  const t = d.today || {};
  const pct = d.goal ? Math.min(100, (t.calories / d.goal) * 100) : 0;
  const barC = d.balance == null ? 'var(--sub)' : d.balance >= 0 ? 'var(--green)' : 'var(--red)';

  return `
  <div class="grid">
    <div class="card">
      <div class="card-title">Consumed</div>
      <div class="big">
        <span class="big-num">${fmt(t.calories, 0)}</span>
        <span class="big-unit">kcal</span>
      </div>
      ${d.goal ? `
        <div class="bar-wrap"><div class="bar-fill" style="width:${pct.toFixed(0)}%;background:${barC}"></div></div>
        <div class="bar-pct">${pct.toFixed(0)}% of ${fmt(d.goal,0)} kcal goal</div>
      ` : '<div class="big-sub muted">No goal configured</div>'}
    </div>

    <div class="card">
      <div class="card-title">Balance</div>
      ${d.balance != null ? `
        <div class="big">
          <span class="big-num" style="color:${clr(d.balance)}">${sign(d.balance)}</span>
          <span class="big-unit">kcal</span>
        </div>
        <div class="big-sub muted">${d.balance >= 0 ? 'remaining' : 'over goal'}</div>
      ` : '<div class="big-num muted">—</div><div class="big-sub muted">set a goal to see balance</div>'}

      ${d.burned != null ? `
        ${metric('Garmin burned', `<span class="blue">${fmt(d.burned,0)} kcal</span>`)}
        ${metric('Net energy', `<span style="color:${clr(d.net)}">${sign(d.net)} kcal</span>`)}
      ` : ''}
    </div>

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
    const labels = Object.keys(data);

    if (!labels.length) {
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
      const d = new Date(ts);
      document.getElementById('footer').textContent =
        `Updated ${d.toLocaleTimeString()} · auto-refreshes every 60 s`;
    }
  } catch(e) {
    document.getElementById('today-content').innerHTML =
      '<div class="empty" style="color:var(--red)">Could not load data</div>';
  }
}

/* ── Week ── */
const chartInstances = {};

async function loadWeek() {
  try {
    const [wr, tr] = await Promise.all([fetch('api/week'), fetch('api/today')]);
    const weekData  = await wr.json();
    const todayData = await tr.json();

    let html = '';
    for (const lbl of ['U1','U2']) {
      const rows = weekData[lbl];
      if (!rows || !rows.length) continue;
      const td = todayData[lbl] || {};
      const userNum = lbl === 'U1' ? '1' : '2';

      html += `<div class="user-block">
        <div class="section-title">👤 ${editableName(lbl)} — This Week</div>
        <div class="card" style="margin-bottom:10px">
          <div class="card-title">Daily Calories</div>
          <canvas id="chart-${lbl}" height="110"></canvas>
        </div>
        <div class="card">
          <div class="card-title">Weekly Summary</div>
          ${metric('Consumed', `${fmt(td.weekly?.calories ?? 0, 0)} kcal`)}
          ${td.weekly_goal != null ? metric('Goal', `${fmt(td.weekly_goal,0)} kcal`) : ''}
          ${td.weekly_balance != null ? metric('Balance',
              `<span style="color:${clr(td.weekly_balance)}">${sign(td.weekly_balance)} kcal</span>`) : ''}
          ${metric('Days tracked', `${td.days_tracked ?? rows.length} / 7`)}
          ${metric('Protein', `${fmt(td.weekly?.protein ?? 0)} g`)}
          ${metric('Fat',     `${fmt(td.weekly?.fat ?? 0)} g`)}
          ${metric('Carbs',   `${fmt(td.weekly?.carbs ?? 0)} g`)}
        </div>
      </div>`;
    }

    document.getElementById('week-content').innerHTML = html || '<div class="empty">No weekly data yet</div>';

    // Draw charts
    for (const lbl of ['U1','U2']) {
      const rows = weekData[lbl];
      if (!rows || !rows.length) continue;
      const td        = todayData[lbl] || {};
      const dailyGoal = td.goal;
      const canvas    = document.getElementById(`chart-${lbl}`);
      if (!canvas) continue;

      if (chartInstances[lbl]) { chartInstances[lbl].destroy(); }

      const labels = rows.map(r => {
        const d = new Date(r.date + 'T12:00:00');
        return d.toLocaleDateString(undefined, {weekday:'short', day:'numeric'});
      });
      const calories = rows.map(r => r.calories);
      const colors   = calories.map(c =>
        !dailyGoal ? 'rgba(10,132,255,.75)'
        : c <= dailyGoal ? 'rgba(48,209,88,.75)' : 'rgba(255,69,58,.75)'
      );

      chartInstances[lbl] = new Chart(canvas, {
        data: {
          labels,
          datasets: [
            {
              type: 'bar', label: 'Calories', data: calories,
              backgroundColor: colors, borderRadius: 5,
            },
            ...(dailyGoal ? [{
              type: 'line', label: 'Daily Goal',
              data: rows.map(() => dailyGoal),
              borderColor: 'rgba(255,214,10,.9)', borderDash: [5,4],
              pointRadius: 0, fill: false, borderWidth: 1.5,
            }] : []),
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color:'#98989f', font:{size:11} }, grid: { color:'rgba(255,255,255,.04)' } },
            y: { ticks: { color:'#98989f', font:{size:11} }, grid: { color:'rgba(255,255,255,.04)' }, beginAtZero: true },
          },
        },
      });
    }
  } catch(e) {
    document.getElementById('week-content').innerHTML =
      '<div class="empty" style="color:var(--red)">Could not load week data</div>';
    console.error(e);
  }
}

// Boot: load settings first, then render
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
    })


@app.route("/api/settings", methods=["POST"])
def api_settings_post():
    data = request.get_json(silent=True) or {}
    for key in ("u1_name", "u2_name"):
        if key in data:
            name = str(data[key]).strip()[:40]  # cap at 40 chars
            if name:
                store.set_setting(key, name)
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
    log.info("Kcal Balance v2.0.0 starting...")

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

    # Expose users to API routes (for future use)
    global _users
    _users = users

    # Start background poller thread (daemon so Flask shutdown kills it)
    t = threading.Thread(
        target=_poll_loop,
        args=(users, supervisor_token, scan_interval),
        daemon=True,
    )
    t.start()

    # Start Flask (use_reloader=False — we manage our own background thread)
    log.info("Web UI on http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
