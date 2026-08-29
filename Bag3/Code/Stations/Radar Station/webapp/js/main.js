/**
 * main.js -- Radar Station Viewer. Web Serial + 2D plan view of raw
 * targets, tracked objects, derived events. Records/replays JSONL.
 */

import { SerialAdapter } from "./device/serialAdapter.js";
import { RadarLink } from "./device/radarLink.js";
import { subscribe as subscribeLog, getEntries, clear as clearLog } from "./device/serialLog.js";

const RANGE_MM = 6000; // LD2450 max range
const HALF_FOV_DEG = 60;
const PAD_PX = 24;

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
  recording: false,
  recordBuf: [], // [{t_wall_ms, msg}]
  replaying: false,
};

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
    <span id="status" class="text-xs text-neutral-400 ml-auto">not connected</span>
  </div>
  <div class="flex flex-1 min-h-0">
    <div class="flex-1 flex items-center justify-center p-3 min-h-0">
      <canvas id="plan-canvas" width="720" height="640"></canvas>
    </div>
    <div class="w-72 border-l border-neutral-800 flex flex-col min-h-0">
      <div class="p-3 border-b border-neutral-800">
        <h2 class="text-xs uppercase tracking-wide text-neutral-500 mb-2">Derived events</h2>
        <div id="events-panel" class="text-sm space-y-1 font-mono"></div>
      </div>
      <div class="p-3 flex-1 overflow-hidden flex flex-col min-h-0">
        <h2 class="text-xs uppercase tracking-wide text-neutral-500 mb-2">Info</h2>
        <div id="info-panel" class="text-sm space-y-1 font-mono"></div>
      </div>
    </div>
  </div>
  <div class="h-40 border-t border-neutral-800 flex flex-col min-h-0">
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
const infoPanel = document.getElementById("info-panel");
const monitorEl = document.getElementById("serial-monitor");
const btnClearLog = document.getElementById("btn-clear-log");

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
  // range rings every meter
  for (let r = 1000; r <= RANGE_MM; r += 1000) {
    ctx.beginPath();
    for (let a = -HALF_FOV_DEG; a <= HALF_FOV_DEG; a += 2) {
      const rr = (a * Math.PI) / 180;
      const [px, py] = toCanvas(r * Math.sin(rr), r * Math.cos(rr));
      if (a === -HALF_FOV_DEG) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.stroke();
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

// ---- serial monitor ------------------------------------------------
function renderLogEntry(e) {
  if (e === null) {
    monitorEl.innerHTML = "";
    return;
  }
  const div = document.createElement("div");
  div.className = `log-${e.dir}`;
  div.textContent = `${e.t.toFixed(0)}ms [${e.dir}] ${e.text}`;
  monitorEl.appendChild(div);
  if (monitorEl.children.length > 500) monitorEl.removeChild(monitorEl.firstChild);
  monitorEl.scrollTop = monitorEl.scrollHeight;
}
subscribeLog(renderLogEntry);
btnClearLog.addEventListener("click", clearLog);

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
  if (state.recording) state.recordBuf.push({ t_wall_ms: Date.now(), msg });
  switch (msg.type) {
    case "targets":
      state.lastTargets = msg.tg || [];
      redraw();
      break;
    case "tracks":
      state.lastTracks = msg.tr || [];
      redraw();
      break;
    case "events":
      state.lastEvents = msg;
      renderEvents(msg);
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
    btnConnect.textContent = "Connect";
    btnStream.disabled = true;
    btnRaw.disabled = true;
    btnRecord.disabled = true;
    statusEl.textContent = "disconnected";
    return;
  }
  try {
    state.adapter = new SerialAdapter();
    await state.adapter.connect({ baudRate: 115200 });
    state.link = new RadarLink(state.adapter);
    state.link.start();
    state.deviceState = "unknown";
    state.autoRecoverArmed = true;
    statusEl.textContent = "connected -- waiting for device...";

    // Opening the port is one event; learning what firmware is on the
    // other end is another. Connection state is driven entirely by
    // listeners below, never by awaiting a single reply.
    state.link.on("targets", handleMessage);
    state.link.on("tracks", handleMessage);
    state.link.on("events", handleMessage);
    state.link.on("info", handleMessage);
    state.link.on("fatal", handleMessage);
    state.link.on("hello", onHello);
    state.link.on("repl", onRepl);

    // Fire-and-forget nudge, not a gate: onHello fires whether this
    // reply arrives, times out, or the device already sent an
    // unsolicited hello first.
    state.link.hello({ timeoutMs: 4000 }).catch(() => {});

    setTimeout(() => {
      if (state.deviceState === "unknown") {
        state.deviceState = "absent";
        statusEl.textContent = "no response from device -- check port/wiring";
      }
    }, 4000);
  } catch (e) {
    statusEl.textContent = `connect failed: ${e.message}`;
  }
});

function onHello(hello) {
  state.deviceState = "running";
  state.connected = true;
  statusEl.textContent = `connected -- radar_server v${hello.version}`;
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
