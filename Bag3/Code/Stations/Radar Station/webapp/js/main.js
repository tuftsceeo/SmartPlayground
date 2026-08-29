/**
 * main.js -- Radar Station Viewer. Web Serial + 2D plan view of raw
 * targets, tracked objects, derived events. Records/replays JSONL.
 */

import { SerialAdapter } from "./device/serialAdapter.js";
import { RadarLink } from "./device/radarLink.js";
import { subscribe as subscribeLog, getEntries, clear as clearLog, logWarn } from "./device/serialLog.js";

const RANGE_MM = 6000; // LD2450 max range
const HALF_FOV_DEG = 60;
const PAD_PX = 24;

// Browser<->ESP32 USB-CDC link; port.open() requires a value, ignored
// in practice. Distinct from config.py's UART_BAUD (ESP32<->LD2450).
const USB_CDC_BAUD = 115200;

const HISTORY_MAX = 200; // ~20s at 10Hz

const state = {
  adapter: null,
  link: null,
  connected: false,   // firmware confirmed running (a hello arrived)
  deviceState: null,  // "running" | "repl" | "absent" | null (not connected)
  autoRecoverArmed: false,
  streaming: false,
  rawOn: false,
  lastTargets: [],
  lastTracks: [],
  lastEvents: null,
  history: [], // ring buffer of past 'events' messages, for the timeseries charts
  recording: false,
  recordBuf: [], // [{t_wall_ms, msg}]
  replaying: false,

  // -- timing diagnostics --
  clockOffsetMs: null, // running min of (performance.now() - device t), one-way latency floor
  lagMs: 0,            // current sample's excess over that floor -- rising = falling behind
  lagHistory: [],
  batchSizes: [],      // messages drained per single onData() call; >1 means backlog
  renderCount: 0,
  renderFps: 0,
};

// All render/DOM work is coalesced to at most once per animation frame,
// regardless of how many messages arrive in between -- a message-flood
// burst updates state (cheap) many times but paints (expensive) once.
// Data-push functions (pushHistory, updateClockSync, renderLogEntry) set
// these flags and call requestFrame(); they never render synchronously.
const dirty = { plan: false, events: false, history: false, timing: false };
let frameScheduled = false;

function requestFrame() {
  if (frameScheduled) return;
  frameScheduled = true;
  requestAnimationFrame(() => {
    frameScheduled = false;
    if (dirty.plan) { redraw(); dirty.plan = false; }
    if (dirty.events) { renderEvents(state.lastEvents); dirty.events = false; }
    if (dirty.history) { renderHistory(); dirty.history = false; }
    if (dirty.timing) { renderTiming(); dirty.timing = false; }
    flushLogEntries();
    state.renderCount++;
  });
}

const root = document.getElementById("root");
root.innerHTML = `
  <div class="flex items-center gap-2 px-3 py-2 border-b border-neutral-800 flex-wrap">
    <button id="btn-connect" class="px-3 py-1.5 rounded bg-sky-600 hover:bg-sky-500 text-sm font-medium">Connect</button>
    <button id="btn-stream" class="px-3 py-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-sm" disabled>Stream: off</button>
    <button id="btn-raw" class="px-3 py-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-sm" disabled>Raw: off</button>
    <button id="btn-record" class="px-3 py-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-sm" disabled>● Record</button>
    <label class="px-3 py-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-sm cursor-pointer">
      Replay JSONL <input id="file-replay" type="file" accept=".jsonl,.json,.txt" class="hidden" />
    </label>
    <button id="btn-toggle-monitor" class="px-3 py-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-sm">Hide monitor</button>
    <span id="status" class="text-xs text-neutral-400 ml-auto">not connected</span>
  </div>
  <div class="flex flex-1 min-h-0">
    <div class="w-1/2 flex items-center justify-center p-3 min-h-0">
      <canvas id="plan-canvas" width="480" height="480"></canvas>
    </div>
    <div class="w-1/2 border-l border-neutral-800 flex flex-col min-h-0 overflow-y-auto">
      <div class="p-3 border-b border-neutral-800">
        <h2 class="text-xs uppercase tracking-wide text-neutral-500 mb-2">Derived events</h2>
        <div id="events-panel" class="text-sm space-y-1 font-mono"></div>
      </div>
      <div class="p-3 border-b border-neutral-800">
        <h2 class="text-xs uppercase tracking-wide text-neutral-500 mb-2">History</h2>
        <div id="history-panel" class="grid grid-cols-2 gap-3"></div>
      </div>
      <div class="p-3 border-b border-neutral-800">
        <h2 class="text-xs uppercase tracking-wide text-neutral-500 mb-2">Timing</h2>
        <div id="timing-panel" class="text-sm space-y-1 font-mono"></div>
      </div>
      <div class="p-3">
        <h2 class="text-xs uppercase tracking-wide text-neutral-500 mb-2">Info</h2>
        <div id="info-panel" class="text-sm space-y-1 font-mono"></div>
      </div>
    </div>
  </div>
  <div id="monitor-section" class="h-40 border-t border-neutral-800 flex flex-col min-h-0">
    <div class="flex items-center gap-2 px-3 py-1 border-b border-neutral-800">
      <h2 class="text-xs uppercase tracking-wide text-neutral-500">Serial monitor</h2>
      <button id="btn-clear-log" class="text-xs text-neutral-500 hover:text-neutral-300 ml-auto">clear</button>
    </div>
    <div id="serial-monitor" class="flex-1 overflow-y-auto px-3 py-1"></div>
  </div>
`;

const canvas = document.getElementById("plan-canvas");
const ctx = canvas.getContext("2d");
const btnConnect = document.getElementById("btn-connect");
const btnStream = document.getElementById("btn-stream");
const btnRaw = document.getElementById("btn-raw");
const btnRecord = document.getElementById("btn-record");
const fileReplay = document.getElementById("file-replay");
const statusEl = document.getElementById("status");
const eventsPanel = document.getElementById("events-panel");
const historyPanel = document.getElementById("history-panel");
const timingPanel = document.getElementById("timing-panel");
const infoPanel = document.getElementById("info-panel");
const monitorSection = document.getElementById("monitor-section");
const monitorEl = document.getElementById("serial-monitor");
const btnClearLog = document.getElementById("btn-clear-log");
const btnToggleMonitor = document.getElementById("btn-toggle-monitor");

// ---- plan view rendering -----------------------------------------------
function toCanvas(x, y) {
  // sensor origin at bottom-center; +y is forward (up on screen), +x is right.
  const w = canvas.width - 2 * PAD_PX;
  const h = canvas.height - 2 * PAD_PX;
  const scale = Math.min(w / (2 * RANGE_MM * Math.sin((HALF_FOV_DEG * Math.PI) / 180)), h / RANGE_MM);
  const cx = canvas.width / 2 + x * scale;
  const cy = canvas.height - PAD_PX - y * scale;
  return [cx, cy];
}

function drawWedge() {
  const [ox, oy] = toCanvas(0, 0);
  const rad = (HALF_FOV_DEG * Math.PI) / 180;
  const [lx, ly] = toCanvas(-RANGE_MM * Math.sin(rad), RANGE_MM * Math.cos(rad));
  const [rx, ry] = toCanvas(RANGE_MM * Math.sin(rad), RANGE_MM * Math.cos(rad));
  ctx.strokeStyle = "#3f3f46";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(ox, oy);
  ctx.lineTo(lx, ly);
  ctx.moveTo(ox, oy);
  ctx.lineTo(rx, ry);
  ctx.stroke();

  ctx.fillStyle = "#71717a";
  ctx.font = "10px monospace";
  ctx.fillText(`-${HALF_FOV_DEG}°`, lx - 26, ly + 4);
  ctx.fillText(`+${HALF_FOV_DEG}°`, rx + 4, ry + 4);

  // range rings every meter, labeled straight ahead of the sensor
  for (let r = 1000; r <= RANGE_MM; r += 1000) {
    ctx.beginPath();
    for (let a = -HALF_FOV_DEG; a <= HALF_FOV_DEG; a += 2) {
      const rr = (a * Math.PI) / 180;
      const [px, py] = toCanvas(r * Math.sin(rr), r * Math.cos(rr));
      if (a === -HALF_FOV_DEG) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.stroke();
    const [lpx, lpy] = toCanvas(0, r);
    ctx.fillStyle = "#71717a";
    ctx.font = "10px monospace";
    ctx.fillText(`${r / 1000}m`, lpx + 4, lpy - 2);
  }
  // sensor marker
  ctx.fillStyle = "#71717a";
  ctx.beginPath();
  ctx.arc(ox, oy, 4, 0, 2 * Math.PI);
  ctx.fill();
}

function redraw() {
  ctx.fillStyle = "#0a0a0a";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = "#27272a";
  ctx.lineWidth = 1;
  drawWedge();

  if (state.rawOn) {
    for (const t of state.lastTargets) {
      const [px, py] = toCanvas(t.x, t.y);
      ctx.fillStyle = "#52525b";
      ctx.beginPath();
      ctx.arc(px, py, 3, 0, 2 * Math.PI);
      ctx.fill();
    }
  }

  for (const t of state.lastTracks) {
    const [px, py] = toCanvas(t.x, t.y);
    ctx.fillStyle = "#38bdf8";
    ctx.beginPath();
    ctx.arc(px, py, 6, 0, 2 * Math.PI);
    ctx.fill();
    // velocity arrow, scaled for visibility
    const vscale = 0.15;
    const [ex, ey] = toCanvas(t.x + t.vx * vscale, t.y + t.vy * vscale);
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(px, py);
    ctx.lineTo(ex, ey);
    ctx.stroke();
    ctx.fillStyle = "#e4e4e7";
    ctx.font = "11px monospace";
    ctx.fillText(`#${t.id} ${t.sp}mm/s`, px + 8, py - 8);
  }
}

// ---- events / info panels ----------------------------------------------
function renderEvents(ev) {
  if (!ev) {
    eventsPanel.innerHTML = '<span class="text-neutral-600">no data</span>';
    return;
  }
  const zoneRows = Object.entries(ev.zones || {})
    .map(([name, n]) => `<div>zone.${name}: ${n}</div>`)
    .join("");
  eventsPanel.innerHTML = `
    <div>present: <span class="${ev.present ? "text-emerald-400" : "text-neutral-500"}">${ev.present}</span></div>
    <div>count: ${ev.count}</div>
    ${zoneRows}
    <div>approach: ${ev.approach}  recede: ${ev.recede}</div>
    <div>still: ${ev.still}  walk: ${ev.walk}  fast: ${ev.fast}</div>
  `;
}

function renderInfo(info) {
  if (!info) return;
  infoPanel.innerHTML = `
    <div>mem_free: ${info.mem}</div>
    <div>frames_ok: ${info.frames_ok}</div>
    <div>frames_dropped: ${info.frames_dropped}</div>
    <div>resyncs: ${info.resyncs}</div>
    <div>up: ${info.up} ms</div>
  `;
}

// ---- history / timeseries charts ---------------------------------------
// Count-based charts read state.history and are capped at 3 (the
// LD2450's target cap) -- fixed y-scale so they stay readable at a
// glance. The latency chart reads state.lagHistory and auto-scales,
// since lag has no natural fixed ceiling.
const CHARTS = [
  { title: "Target count", data: () => state.history, yMax: 3, series: [{ key: "count", label: "count", color: "#38bdf8" }] },
  { title: "Zones", data: () => state.history, yMax: 3, series: [{ key: "near", label: "near", color: "#a78bfa" }, { key: "far", label: "far", color: "#6366f1" }] },
  { title: "Speed", data: () => state.history, yMax: 3, series: [{ key: "still", label: "still", color: "#a1a1aa" }, { key: "walk", label: "walk", color: "#fbbf24" }, { key: "fast", label: "fast", color: "#f87171" }] },
  { title: "Motion", data: () => state.history, yMax: 3, series: [{ key: "approach", label: "approach", color: "#4ade80" }, { key: "recede", label: "recede", color: "#fb923c" }] },
  {
    title: "Latency (ms)", data: () => state.lagHistory,
    yMax: () => Math.max(50, ...state.lagHistory.map((s) => s.lag)),
    series: [{ key: "lag", label: "lag", color: "#f472b6" }],
  },
];

for (const chart of CHARTS) {
  const wrap = document.createElement("div");
  const legend = chart.series.map((s) => `<span style="color:${s.color}">●</span> ${s.label}`).join("  ");
  wrap.innerHTML = `
    <div class="text-xs text-neutral-500 mb-1">${chart.title} <span class="text-[10px]">${legend}</span></div>
    <canvas width="280" height="56" class="w-full"></canvas>
  `;
  historyPanel.appendChild(wrap);
  chart._canvas = wrap.querySelector("canvas");
}

function pushHistory(ev) {
  state.history.push({
    count: ev.count || 0,
    near: (ev.zones && ev.zones.near) || 0,
    far: (ev.zones && ev.zones.far) || 0,
    still: ev.still || 0,
    walk: ev.walk || 0,
    fast: ev.fast || 0,
    approach: ev.approach || 0,
    recede: ev.recede || 0,
  });
  if (state.history.length > HISTORY_MAX) state.history.shift();
  dirty.history = true;
  requestFrame();
}

function renderHistory() {
  for (const chart of CHARTS) {
    const hist = chart.data();
    const yMax = typeof chart.yMax === "function" ? chart.yMax() : chart.yMax;
    const c = chart._canvas.getContext("2d");
    const w = chart._canvas.width, h = chart._canvas.height;
    c.fillStyle = "#0a0a0a";
    c.fillRect(0, 0, w, h);
    if (hist.length < 2) continue;
    const n = hist.length;
    for (const s of chart.series) {
      c.strokeStyle = s.color;
      c.lineWidth = 1.5;
      c.beginPath();
      hist.forEach((sample, i) => {
        const x = (i / (n - 1)) * w;
        const v = Math.max(0, Math.min(yMax, sample[s.key]));
        const y = h - 2 - (v / yMax) * (h - 4);
        if (i === 0) c.moveTo(x, y);
        else c.lineTo(x, y);
      });
      c.stroke();
    }
  }
}

// ---- timing diagnostics ------------------------------------------------
// Lag estimate: device 't' is time.ticks_ms() since its own boot, not
// wall-clock, so absolute latency needs an assumed epoch. clockOffsetMs
// is a running minimum of (browser time - device t) -- the lowest
// latency observed so far, which one-way latency can only ever exceed.
// lagMs is each sample's excess over that floor: near 0 means keeping
// pace, a rising trend means falling behind.
const LAG_WARN_MS = 250;

function updateClockSync(deviceT) {
  if (deviceT === undefined) return;
  const now = performance.now();
  const sampleOffset = now - deviceT;
  state.clockOffsetMs = state.clockOffsetMs === null ? sampleOffset : Math.min(state.clockOffsetMs, sampleOffset);
  const lag = now - state.clockOffsetMs - deviceT;
  state.lagMs = lag;
  state.lagHistory.push({ lag });
  if (state.lagHistory.length > HISTORY_MAX) state.lagHistory.shift();
  if (lag > LAG_WARN_MS) logWarn(`display lag ${lag.toFixed(0)}ms, exceeds ${LAG_WARN_MS}ms`);
  dirty.history = true;
  dirty.timing = true;
  requestFrame();
}

function renderTiming() {
  const backlog = state.batchSizes;
  const avgBacklog = backlog.length ? (backlog.reduce((a, b) => a + b, 0) / backlog.length).toFixed(2) : "-";
  const maxBacklog = backlog.length ? Math.max(...backlog) : "-";
  timingPanel.innerHTML = `
    <div>lag: <span class="${state.lagMs > LAG_WARN_MS ? "text-amber-400" : "text-neutral-300"}">${state.lagMs.toFixed(0)}ms</span></div>
    <div>backlog/read: avg ${avgBacklog}, max ${maxBacklog}</div>
    <div>render: ${state.renderFps} fps</div>
  `;
}

setInterval(() => {
  state.renderFps = state.renderCount;
  state.renderCount = 0;
  dirty.timing = true;
  requestFrame();
}, 1000);

// ---- serial monitor ------------------------------------------------
// Entries queue here (cheap) and are flushed into the DOM in one batch
// per animation frame by requestFrame() above -- under a message burst,
// this is one appendChild + one scrollTop reflow instead of one each,
// which was heavy enough to make the whole page feel unresponsive.
let pendingLogEntries = [];

function renderLogEntry(e) {
  if (e === null) {
    monitorEl.innerHTML = "";
    pendingLogEntries = [];
    return;
  }
  pendingLogEntries.push(e);
  requestFrame();
}

function flushLogEntries() {
  if (!pendingLogEntries.length) return;
  const frag = document.createDocumentFragment();
  for (const e of pendingLogEntries) {
    const div = document.createElement("div");
    div.className = `log-${e.dir}`;
    div.textContent = `${e.t.toFixed(0)}ms [${e.dir}] ${e.text}`;
    frag.appendChild(div);
  }
  pendingLogEntries = [];
  monitorEl.appendChild(frag);
  while (monitorEl.children.length > 500) monitorEl.removeChild(monitorEl.firstChild);
  monitorEl.scrollTop = monitorEl.scrollHeight;
}

subscribeLog(renderLogEntry);
btnClearLog.addEventListener("click", clearLog);

btnToggleMonitor.addEventListener("click", () => {
  // Native `hidden` loses to Tailwind's .flex class in the cascade
  // (author display rules beat the UA [hidden] rule regardless of
  // specificity) -- toggle the inline style directly instead.
  const willHide = monitorSection.style.display !== "none";
  monitorSection.style.display = willHide ? "none" : "";
  btnToggleMonitor.textContent = willHide ? "Show monitor" : "Hide monitor";
});

// ---- recording -----------------------------------------------------
function startRecording() {
  state.recording = true;
  state.recordBuf = [];
  btnRecord.textContent = "■ Stop & save";
  btnRecord.classList.add("bg-red-700", "hover:bg-red-600");
}

function stopRecording() {
  state.recording = false;
  btnRecord.textContent = "● Record";
  btnRecord.classList.remove("bg-red-700", "hover:bg-red-600");
  if (!state.recordBuf.length) return;
  const text = state.recordBuf.map((r) => JSON.stringify(r)).join("\n") + "\n";
  const blob = new Blob([text], { type: "application/x-ndjson" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `radar-session-${Date.now()}.jsonl`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

btnRecord.addEventListener("click", () => {
  if (!state.recording) startRecording();
  else stopRecording();
});

// ---- message handling ----
function handleMessage(msg) {
  // Any message but 'fatal' is proof the firmware is running -- not just
  // 'hello'. tracks/events/info/heartbeat arrive continuously, so this
  // is a far more reliable liveness signal than waiting on one specific
  // message that only gets a single reply opportunity.
  if (msg.type !== "fatal") markRunning();
  if (state.recording) state.recordBuf.push({ t_wall_ms: Date.now(), msg });
  switch (msg.type) {
    case "targets":
      state.lastTargets = msg.tg || [];
      dirty.plan = true;
      requestFrame();
      break;
    case "tracks":
      state.lastTracks = msg.tr || [];
      updateClockSync(msg.t); // pure data update; sets dirty.history/timing itself
      dirty.plan = true;
      requestFrame();
      break;
    case "events":
      state.lastEvents = msg;
      pushHistory(msg); // pure data update; sets dirty.history itself
      dirty.events = true;
      requestFrame();
      break;
    case "info":
      renderInfo(msg);
      break;
    case "fatal":
      statusEl.textContent = `device fatal: ${msg.msg}`;
      break;
    default:
      break;
  }
}

// ---- replay ----------------------------------------------------------
fileReplay.addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const text = await file.text();
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  if (state.connected) {
    statusEl.textContent = "disconnect before replaying a recording";
    return;
  }
  statusEl.textContent = `replaying ${lines.length} messages…`;
  state.replaying = true;
  for (const line of lines) {
    if (!state.replaying) break;
    let row;
    try {
      row = JSON.parse(line);
    } catch {
      continue;
    }
    handleMessage(row.msg || row);
    await new Promise((r) => setTimeout(r, 100)); // ~10Hz, matching the sensor's native rate
  }
  statusEl.textContent = "replay finished";
  state.replaying = false;
  fileReplay.value = "";
});

// ---- connect / commands ---------------------------------------------
btnConnect.addEventListener("click", async () => {
  if (state.deviceState !== null) {
    await state.link.stop();
    await state.adapter.disconnect();
    state.connected = false;
    state.deviceState = null;
    state._streamStarted = false;
    state.streaming = false;
    state.clockOffsetMs = null; // device ticks_ms() resets on its next boot
    state.lagHistory = [];
    state.batchSizes = [];
    btnConnect.textContent = "Connect";
    btnStream.disabled = true;
    btnRaw.disabled = true;
    btnRecord.disabled = true;
    statusEl.textContent = "disconnected";
    return;
  }
  try {
    // Attach the parser and listeners BEFORE opening the port -- if the
    // device is already running and streaming, bytes can start arriving
    // the instant the port opens, and anything before adapter.onData is
    // assigned is silently dropped (SerialAdapter's read loop is a no-op
    // without it).
    state.adapter = new SerialAdapter();
    state.link = new RadarLink(state.adapter);
    state.link.start();
    state.link.on("targets", handleMessage);
    state.link.on("tracks", handleMessage);
    state.link.on("events", handleMessage);
    state.link.on("info", handleMessage);
    state.link.on("fatal", handleMessage);
    state.link.on("heartbeat", markRunning);
    state.link.on("hello", onHello);
    state.link.on("repl", onRepl);
    state.link.on("_batch", (b) => {
      state.batchSizes.push(b.n);
      if (state.batchSizes.length > 50) state.batchSizes.shift();
    });

    state.deviceState = "unknown";
    state.autoRecoverArmed = true;
    statusEl.textContent = "connected -- waiting for device...";
    await state.adapter.connect({ baudRate: USB_CDC_BAUD });

    // Opening the port is one event; learning what firmware is on the
    // other end is another. Connection state is driven entirely by
    // listeners above (markRunning(), fired by any message type), never
    // by sending or awaiting a specific probe command. No command is
    // sent here at all: the device already emits a heartbeat every 5s
    // and, if streaming was left on from an earlier session, tracks/
    // events far more often than that -- something arrives on its own.
    setTimeout(() => {
      if (state.deviceState === "unknown") {
        state.deviceState = "absent";
        statusEl.textContent = "no response from device -- check port/wiring";
      }
    }, 8000);
  } catch (e) {
    statusEl.textContent = `connect failed: ${e.message}`;
  }
});

// hello is informational only (the version string) -- never required to
// reach "running". markRunning() is the actual gate, driven by any
// message type (see handleMessage).
function onHello(hello) {
  statusEl.textContent = `connected -- radar_server v${hello.version}`;
  markRunning();
}

function markRunning() {
  if (state.deviceState === "running") return;
  state.deviceState = "running";
  state.connected = true;
  if (statusEl.textContent === "connected -- waiting for device...") {
    statusEl.textContent = "connected -- device running";
  }
  btnConnect.textContent = "Disconnect";
  btnStream.disabled = false;
  btnRaw.disabled = false;
  btnRecord.disabled = false;

  if (!state._streamStarted) {
    state._streamStarted = true;
    state.link.setStream(true).then(() => {
      state.streaming = true;
      btnStream.textContent = "Stream: on";
    }).catch(() => {});
    setInterval(() => {
      if (state.connected) state.link.info().then(renderInfo).catch(() => {});
    }, 3000);
  }
}

function onRepl() {
  state.deviceState = "repl";
  state.connected = false;
  state._streamStarted = false; // re-arm: a reset firmware boots with streaming off
  state.clockOffsetMs = null; // re-arm: restartFirmware() resets the device's ticks_ms()
  if (!state.autoRecoverArmed) {
    statusEl.textContent = "device at REPL -- click Connect again to retry recovery";
    return;
  }
  state.autoRecoverArmed = false; // one-shot; never hammer Ctrl-D
  statusEl.textContent = "device at REPL -- attempting recovery...";
  state.link.restartFirmware().catch(() => {
    statusEl.textContent = "device stuck at REPL -- recovery failed, check the serial monitor";
  });
}

btnStream.addEventListener("click", async () => {
  state.streaming = !state.streaming;
  await state.link.setStream(state.streaming);
  btnStream.textContent = `Stream: ${state.streaming ? "on" : "off"}`;
});

btnRaw.addEventListener("click", async () => {
  state.rawOn = !state.rawOn;
  await state.link.setRaw(state.rawOn);
  btnRaw.textContent = `Raw: ${state.rawOn ? "on" : "off"}`;
});

redraw();
renderEvents(null);
renderTiming();
