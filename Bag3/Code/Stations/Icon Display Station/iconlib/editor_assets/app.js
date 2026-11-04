/* Icon editor frontend. No framework, no build step -- talks to icon_editor.py's
 * JSON API and does everything else with plain DOM + canvas.
 */
const W = 16, H = 16;
let state = null;
let overlayUndoStack = [];
let lastClickedIndex = null;

const $ = (sel) => document.querySelector(sel);

// ── forward model (mirrors iconlib/ledcolor.py predict_led_appearance) ──
function srgbEncode(c) {
  c = Math.min(1, Math.max(0, c));
  return c <= 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
}
function predictLedAppearance(rgb, intensity) {
  return rgb.map((c) => {
    const duty = Math.trunc(c * intensity);
    const linear = duty / 255;
    return Math.round(srgbEncode(linear) * 255);
  });
}

async function api(path, body) {
  const opts = body === undefined
    ? {}
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const res = await fetch(path, opts);
  return res.json();
}

function setStatus(msg, isError) {
  const el = $("#status");
  el.textContent = msg;
  el.style.color = isError ? "var(--bad)" : "var(--dim)";
}

async function loadState() {
  state = await api("/api/state");
  render();
}

function render() {
  $("#icon-name").textContent = "Icon Editor — " + state.name;
  $("#mode-badge").textContent = state.mode + " · " + state.fills.length + " segments";
  $("#segments-slider").value = state.max_segments;
  $("#segments-value").textContent = state.max_segments;
  $("#source-img").src = state.source_data_url;
  $("#segmented-img").src = state.segmented_data_url;
  renderSegmentList();
  renderPreview();
  renderGrid();
  renderProblems();
}

function rgbToHex([r, g, b]) {
  return "#" + [r, g, b].map((c) => c.toString(16).padStart(2, "0")).join("");
}
function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function renderSegmentList() {
  const container = $("#segment-list");
  container.innerHTML = "";
  state.fills.forEach((fill, i) => {
    const d = state.decisions[i];
    const won = state.cells_won[i];
    const row = document.createElement("div");
    row.className = "seg-row";

    const swatch = document.createElement("div");
    swatch.className = "seg-swatch";
    swatch.style.background = rgbToHex(fill.rgb);
    row.appendChild(swatch);

    const meta = document.createElement("div");
    meta.className = "seg-meta";
    const pct = (fill.frac * 100).toFixed(1);
    const warn = d.role === "color" && won < state.limits.MIN_FEATURE_CELLS;
    meta.innerHTML = `seg ${i} · src rgb(${fill.rgb.join(",")}) · ${pct}% of pixels<br>` +
      `<span class="${warn ? "warn" : ""}">cells won: ${won}${warn ? " (below min " + state.limits.MIN_FEATURE_CELLS + ")" : ""}</span>`;
    row.appendChild(meta);

    const roleSel = document.createElement("select");
    ["color", "off", "merge"].forEach((r) => {
      const opt = document.createElement("option");
      opt.value = r; opt.textContent = r;
      if (d.role === r) opt.selected = true;
      roleSel.appendChild(opt);
    });
    row.appendChild(roleSel);

    const controls = document.createElement("div");
    controls.className = "seg-controls";

    const colorInput = document.createElement("input");
    colorInput.type = "color";
    colorInput.value = rgbToHex(d.color || fill.rgb);
    colorInput.disabled = d.role !== "color";
    controls.appendChild(colorInput);

    const mergeSel = document.createElement("select");
    mergeSel.style.display = d.role === "merge" ? "" : "none";
    state.fills.forEach((f2, j) => {
      if (j === i) return;
      const opt = document.createElement("option");
      opt.value = j; opt.textContent = "-> seg " + j;
      if (d.merge_into === j) opt.selected = true;
      mergeSel.appendChild(opt);
    });
    controls.appendChild(mergeSel);

    const prioLabel = document.createElement("label");
    prioLabel.style.fontSize = "11px"; prioLabel.style.color = "var(--dim)";
    prioLabel.textContent = "priority ";
    const prioInput = document.createElement("input");
    prioInput.type = "range"; prioInput.min = "0.1"; prioInput.max = "3.0"; prioInput.step = "0.1";
    prioInput.value = d.priority;
    const prioVal = document.createElement("span");
    prioVal.textContent = Number(d.priority).toFixed(1);
    prioLabel.appendChild(prioInput);
    prioLabel.appendChild(prioVal);
    controls.appendChild(prioLabel);

    const swatches = document.createElement("div");
    swatches.className = "palette-swatches";
    Object.entries(state.palette).forEach(([name, rgb]) => {
      const b = document.createElement("button");
      b.title = name;
      b.style.background = rgbToHex(rgb);
      b.onclick = () => {
        colorInput.value = rgbToHex(rgb);
        pushDecision(i, { role: "color", color: rgb });
      };
      swatches.appendChild(b);
    });
    controls.appendChild(swatches);

    row.appendChild(controls);
    container.appendChild(row);

    roleSel.onchange = () => {
      const role = roleSel.value;
      colorInput.disabled = role !== "color";
      mergeSel.style.display = role === "merge" ? "" : "none";
      pushDecision(i, {
        role,
        color: role === "color" ? hexToRgb(colorInput.value) : null,
        merge_into: role === "merge" ? Number(mergeSel.value || 0) : undefined,
      });
    };
    colorInput.oninput = () => {
      applyColorLocally(i, hexToRgb(colorInput.value));
    };
    colorInput.onchange = () => {
      pushDecision(i, { role: "color", color: hexToRgb(colorInput.value) });
    };
    mergeSel.onchange = () => {
      pushDecision(i, { role: "merge", merge_into: Number(mergeSel.value) });
    };
    prioInput.oninput = () => { prioVal.textContent = Number(prioInput.value).toFixed(1); };
    prioInput.onchange = () => {
      pushDecision(i, { role: d.role, color: d.color, priority: Number(prioInput.value) });
    };
  });
}

// Fast path: recolor cells this segment currently wins directly on the
// canvas (using the last-known winner grid) while dragging the picker, no
// server round trip. onchange (picker closed) always confirms with the
// server, which is authoritative for rasterization/priority effects.
function applyColorLocally(segIdx, rgb) {
  state.decisions[segIdx].color = rgb;
  for (let k = 0; k < W * H; k++) {
    if (state.winner[k] === segIdx) {
      const overlay = state.overlay[String(k)];
      state.pixels[k] = overlay || rgb;
    }
  }
  renderPreview();
  renderGrid();
}

async function pushDecision(i, patch) {
  const d = state.decisions[i];
  Object.assign(d, patch);
  setStatus("recomputing…");
  const resp = await api("/api/decisions", { decisions: state.decisions });
  state = resp;
  render();
  setStatus("");
}

function renderPreview() {
  const canvas = $("#preview-canvas");
  const ctx = canvas.getContext("2d");
  const scale = canvas.width / W;
  ctx.fillStyle = "#0a0a0c";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  for (let row = 0; row < H; row++) {
    for (let col = 0; col < W; col++) {
      const rgb = state.pixels[row * W + col];
      if (rgb[0] === 0 && rgb[1] === 0 && rgb[2] === 0) continue;
      const seen = predictLedAppearance(rgb, state.intensity);
      const cx = col * scale + scale / 2, cy = row * scale + scale / 2;
      ctx.save();
      ctx.shadowColor = `rgb(${seen.join(",")})`;
      ctx.shadowBlur = scale * 0.6;
      ctx.fillStyle = `rgb(${seen.join(",")})`;
      ctx.beginPath();
      ctx.arc(cx, cy, scale * 0.32, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  }
}

function renderGrid() {
  const canvas = $("#grid-canvas");
  const ctx = canvas.getContext("2d");
  const scale = canvas.width / W;
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  for (let row = 0; row < H; row++) {
    for (let col = 0; col < W; col++) {
      const idx = row * W + col;
      const rgb = state.pixels[idx];
      ctx.fillStyle = `rgb(${rgb.join(",")})`;
      ctx.fillRect(col * scale + 1, row * scale + 1, scale - 2, scale - 2);
      if (idx === lastClickedIndex) {
        ctx.strokeStyle = "#5aa9ff";
        ctx.lineWidth = 2;
        ctx.strokeRect(col * scale + 1, row * scale + 1, scale - 2, scale - 2);
      }
    }
  }
}

function renderProblems() {
  const ul = $("#problems");
  ul.innerHTML = "";
  state.problems.forEach((p) => {
    const li = document.createElement("li");
    li.textContent = p;
    ul.appendChild(li);
  });
}

async function pushOverlay() {
  const resp = await api("/api/overlay", { overlay: state.overlay });
  state = resp;
  render();
}

function initGridClicks() {
  const canvas = $("#grid-canvas");
  canvas.addEventListener("click", (ev) => {
    const rect = canvas.getBoundingClientRect();
    const col = Math.floor((ev.clientX - rect.left) / (rect.width / W));
    const row = Math.floor((ev.clientY - rect.top) / (rect.height / H));
    const idx = row * W + col;
    lastClickedIndex = idx;
    const rgb = hexToRgb($("#brush-color").value);
    overlayUndoStack.push({ idx, prev: state.overlay[String(idx)] || null });
    state.overlay[String(idx)] = rgb;
    pushOverlay();
  });
}

function initControls() {
  $("#segments-slider").addEventListener("change", async (ev) => {
    setStatus("re-segmenting…");
    state = await api("/api/segments", { max_segments: Number(ev.target.value) });
    render();
    setStatus("");
  });
  $("#segments-slider").addEventListener("input", (ev) => {
    $("#segments-value").textContent = ev.target.value;
  });
  $("#save-btn").addEventListener("click", async () => {
    const r = await api("/api/save", {});
    setStatus(r.ok ? "saved " + r.map_path : "save failed: " + r.error, !r.ok);
  });
  $("#export-btn").addEventListener("click", async () => {
    const r = await api("/api/save", {});
    setStatus(r.ok ? "exported " + r.icon_path + " and " + r.preview_path : "export failed: " + r.error, !r.ok);
  });
  $("#push-btn").addEventListener("click", async () => {
    const port = prompt("Serial port for mpremote:", "/dev/cu.usbmodem1101");
    if (!port) return;
    setStatus("pushing…");
    const r = await api("/api/push", { port });
    setStatus(r.ok ? "pushed" : "push failed: " + (r.error || r.stderr), !r.ok);
  });
  $("#brush-clear").addEventListener("click", () => {
    if (lastClickedIndex === null) return;
    overlayUndoStack.push({ idx: lastClickedIndex, prev: state.overlay[String(lastClickedIndex)] || null });
    delete state.overlay[String(lastClickedIndex)];
    pushOverlay();
  });
  $("#undo-btn").addEventListener("click", () => {
    const last = overlayUndoStack.pop();
    if (!last) return;
    if (last.prev) state.overlay[String(last.idx)] = last.prev;
    else delete state.overlay[String(last.idx)];
    pushOverlay();
  });
}

initControls();
initGridClicks();
loadState();
