/**
 * distribute.js — "Distribute code" overlay for a Broadcast Dial.
 *
 * After a send, the Dial scans for nearby wands and stations
 * (`fleet.scan` → `status_report` … `status_done`), the user picks devices,
 * and `fleet.distribute` has the Dial push a getcode to each one, staggered.
 * Per-device results arrive as `dist_progress`, then `dist_done`.
 * Wire contract: BroadcastDial/README.md "Fleet commands".
 *
 * DistributeState holds the rows and is DOM-free (tools/distribute_test.mjs);
 * DistributeOverlay paints it into #distribute-overlay.
 */

/** status_report `kind` (sender's HUB_TYPE) → label prefix and name. */
const KINDS = {
  wand: { prefix: "W", name: "Wand" },
  icon_display: { prefix: "D", name: "Icon display" },
};

const LIVE_WAIT_MS = 30000;
const LIVE_POLL_MS = 500;

/** "W-EEFF" style label: kind prefix + last 4 hex digits of the MAC. */
export function deviceLabel(mac, kind) {
  const prefix = KINDS[kind]?.prefix || "?";
  const clean = String(mac || "").replace(/:/g, "").toUpperCase();
  return `${prefix}-${clean.slice(-4)}`;
}

export function kindName(kind) {
  return KINDS[kind]?.name || kind || "Unknown";
}

/** RSSI (dBm) → 0..3 bars, -1 unknown. Same thresholds as the M5Paper Remote. */
export function signalLevel(rssi) {
  if (rssi == null) return -1;
  if (rssi >= -55) return 3;
  if (rssi >= -68) return 2;
  if (rssi >= -80) return 1;
  return 0;
}

const norm = (mac) => String(mac || "").replace(/:/g, "").toUpperCase();

/** Nicknames are per browser: localStorage, keyed by normalized MAC. */
const NICK_KEY = "chatbroadcast.deviceNicknames";

function loadNicknames() {
  try {
    return JSON.parse(localStorage.getItem(NICK_KEY)) || {};
  } catch {
    return {};
  }
}

export function getNickname(mac) {
  return loadNicknames()[norm(mac)] || "";
}

/** Empty or whitespace-only clears the nickname. */
export function setNickname(mac, name) {
  const all = loadNicknames();
  const clean = String(name || "").trim().slice(0, 40);
  if (clean) all[norm(mac)] = clean;
  else delete all[norm(mac)];
  try {
    localStorage.setItem(NICK_KEY, JSON.stringify(all));
  } catch {}
}

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

export class DistributeState {
  constructor() {
    this.rows = []; // {mac, kind, battery, rssi, selected, status, why}
    this.scanning = false;
    this.running = false;
    this.done = 0;
    this.total = 0;
  }

  _row(mac) {
    return this.rows.find((r) => norm(r.mac) === norm(mac));
  }

  startScan() {
    this.rows = [];
    this.scanning = true;
    this.done = 0;
    this.total = 0;
  }

  /** Add or refresh a row from a status_report. New rows start selected. */
  upsertReport(obj) {
    if (!obj?.mac) return;
    const row = this._row(obj.mac);
    if (row) {
      Object.assign(row, { kind: obj.kind ?? row.kind, battery: obj.battery, rssi: obj.rssi });
      return;
    }
    this.rows.push({
      mac: obj.mac, kind: obj.kind ?? null, battery: obj.battery ?? null,
      rssi: obj.rssi ?? null, selected: true, status: "", why: null,
    });
  }

  endScan() {
    this.scanning = false;
  }

  toggle(mac, on) {
    const row = this._row(mac);
    if (row && !this.running) row.selected = on;
  }

  setAll(on) {
    if (this.running) return;
    for (const r of this.rows) r.selected = on;
  }

  selectedMacs() {
    return this.rows.filter((r) => r.selected).map((r) => r.mac);
  }

  /** Mark the selection queued; returns the MACs to send. */
  startDistribute() {
    const macs = this.selectedMacs();
    for (const r of this.rows) {
      r.status = r.selected ? "queued" : "";
      r.why = null;
    }
    this.running = macs.length > 0;
    this.done = 0;
    this.total = macs.length;
    return macs;
  }

  /** dist_progress: ok null = pushed, true = updated, false = failed. */
  applyProgress(obj) {
    const row = this._row(obj?.mac);
    if (row) {
      row.status = obj.ok == null ? "pulling" : obj.ok ? "done" : "failed";
      row.why = obj.ok === false ? obj.why || null : null;
    }
    if (typeof obj?.done === "number") this.done = obj.done;
    if (typeof obj?.total === "number") this.total = obj.total;
  }

  finish(obj) {
    if (typeof obj?.done === "number") this.done = obj.done;
    this.running = false;
  }

  /** The Dial refused or the link failed: unfinished rows fail with why. */
  abort(why) {
    for (const r of this.rows) {
      if (r.status === "queued" || r.status === "pulling") {
        r.status = "failed";
        r.why = why;
      }
    }
    this.running = false;
  }
}

const STATUS_TEXT = {
  "": "",
  queued: "Waiting",
  pulling: "Getting code…",
  done: "Updated",
  failed: "Failed",
};

/**
 * DOM controller. `app` supplies `device` (the BboxDeviceLink) and
 * `link.state`; `toast` reports errors.
 */
export class DistributeOverlay {
  constructor({ app, showOverlay, hideOverlay, toast }) {
    this.app = app;
    this.showOverlay = showOverlay;
    this.hideOverlay = hideOverlay;
    this.toast = toast;
    this.state = new DistributeState();
    this.slug = null;
    this._unsub = [];
    this.el = (id) => document.getElementById(id);
    this.el("btn-dist-close-x").addEventListener("click", () => this.close());
    this.el("btn-dist-rescan").addEventListener("click", () => this.scan());
    this.el("btn-dist-all").addEventListener("click", () => {
      const all = this.state.rows.every((r) => r.selected);
      this.state.setAll(!all);
      this.render();
    });
    this.el("btn-dist-send").addEventListener("click", () => this.distribute());
    this.el("dist-table").addEventListener("click", (e) => this._onTableClick(e));
  }

  get device() {
    return this.app.device;
  }

  /** Open for `slug`; waits for the Dial to be back from its reboot, then scans. */
  async open(slug, prettyName) {
    this.slug = slug;
    this.el("dist-title").textContent = prettyName ? `Distribute "${prettyName}"` : "Distribute code";
    this.state = new DistributeState();
    this._setStatus("Waiting for the Dial to restart…");
    this.render();
    this.showOverlay("distribute-overlay");
    if (!(await this._waitLive())) {
      this._setStatus("The Dial did not come back. Reconnect it, then press Rescan.");
      return;
    }
    await this.scan();
  }

  close() {
    if (this.state.running) {
      this.device?.sendCmd({ cmd: "fleet.cancel" }).catch(() => {});
    }
    for (const off of this._unsub) off();
    this._unsub = [];
    this._listening = null;
    this.hideOverlay("distribute-overlay");
  }

  async _waitLive() {
    const end = Date.now() + LIVE_WAIT_MS;
    while (Date.now() < end) {
      if (this.app.link?.state === "live" && this.device?.isRunning?.()) return true;
      await new Promise((r) => setTimeout(r, LIVE_POLL_MS));
    }
    return false;
  }

  _listen() {
    for (const off of this._unsub) off();
    const d = this.device;
    this._unsub = [
      d.on("status_report", (o) => { this.state.upsertReport(o); this.render(); }),
      d.on("status_done", () => {
        this.state.endScan();
        this._setStatus(this.state.rows.length
          ? "Pick the devices to update."
          : "No devices answered. Check they are on, then Rescan.");
        this.render();
      }),
      d.on("dist_progress", (o) => { this.state.applyProgress(o); this.render(); }),
      d.on("dist_done", (o) => {
        this.state.finish(o);
        this._setStatus(`${o?.ok ?? 0} of ${o?.total ?? this.state.total} devices updated.`);
        this.render();
      }),
    ];
  }

  async scan() {
    if (this.state.running) return;
    // Listeners go on the link in use now: a reconnect can replace it.
    if (this._listening !== this.device) {
      this._listen();
      this._listening = this.device;
    }
    this.state.startScan();
    this._setStatus("Looking for wands and stations…");
    this.render();
    try {
      await this.device.sendCmd({ cmd: "fleet.scan" });
    } catch (e) {
      this.state.endScan();
      this._setStatus(`Scan failed: ${e.message}`);
      this.render();
    }
  }

  async distribute() {
    const macs = this.state.startDistribute();
    if (!macs.length) return;
    this._setStatus("Sending code…");
    this.render();
    try {
      await this.device.sendCmd({ cmd: "fleet.distribute", slug: this.slug, macs });
    } catch (e) {
      this.state.abort(e.message);
      this._setStatus(`Distribute failed: ${e.message}`);
      this.toast(`Distribute failed: ${e.message}`, true);
      this.render();
    }
  }

  _onTableClick(e) {
    const t = e.target;
    const mac = t.closest("tr")?.dataset.mac;
    if (!mac) return;
    if (t.matches("input.dist-check")) {
      this.state.toggle(mac, t.checked);
      this.render();
    } else if (t.closest(".dist-rename")) {
      this._editName(t.closest("tr"), mac);
    } else if (t.closest(".dist-find")) {
      this.device.sendCmd({ cmd: "fleet.find", mac })
        .catch((err) => this.toast(`Find failed: ${err.message}`, true));
    }
  }

  /** Swap the name cell for a text input; Enter or blur saves, Escape cancels. */
  _editName(tr, mac) {
    const cell = tr.querySelector(".dist-name-cell");
    if (!cell || cell.querySelector("input")) return;
    const input = document.createElement("input");
    input.type = "text";
    input.className = "dist-nick-input";
    input.maxLength = 40;
    input.value = getNickname(mac);
    input.placeholder = deviceLabel(mac, this.state._row(mac)?.kind);
    let done = false;
    this._editing = true;
    const finish = (save) => {
      if (done) return;
      done = true;
      this._editing = false;
      if (save) setNickname(mac, input.value);
      this.render();
    };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") finish(true);
      else if (e.key === "Escape") finish(false);
    });
    input.addEventListener("blur", () => finish(true));
    cell.textContent = "";
    cell.appendChild(input);
    input.focus();
    input.select();
  }

  _setStatus(text) {
    this.el("dist-status").textContent = text;
  }

  render() {
    if (this._editing) return; // _editName re-renders when it finishes
    const s = this.state;
    const body = this.el("dist-rows");
    body.textContent = "";
    for (const r of s.rows) {
      const label = deviceLabel(r.mac, r.kind);
      const nick = getNickname(r.mac);
      const tr = document.createElement("tr");
      tr.dataset.mac = r.mac;
      tr.className = r.status ? `dist-${r.status}` : "";
      const cells = [
        `<input type="checkbox" class="dist-check" ${r.selected ? "checked" : ""} ${s.running ? "disabled" : ""} aria-label="Select ${esc(nick || label)}">`,
        `<div class="dist-name-cell"><span class="dist-name" title="${r.mac}">${esc(nick || label)}</span>`
          + `<button type="button" class="dist-rename" title="Rename (saved in this browser)" aria-label="Rename ${esc(nick || label)}">✎</button></div>`
          + `<span class="dist-kind">${nick ? `${label} · ` : ""}${kindName(r.kind)}</span>`,
        r.battery == null ? "—" : `${r.battery}%`,
        `<span class="dist-sig dist-sig-${signalLevel(r.rssi)}" title="${r.rssi ?? "?"} dBm"><i></i><i></i><i></i></span>`,
        `<span class="dist-state" title="${r.why || ""}">${STATUS_TEXT[r.status] || ""}${r.why ? ` (${r.why})` : ""}</span>`,
        `<button type="button" class="btn-secondary btn-compact dist-find">Find</button>`,
      ];
      tr.innerHTML = cells.map((c) => `<td>${c}</td>`).join("");
      body.appendChild(tr);
    }
    const nSel = s.selectedMacs().length;
    this.el("dist-table").classList.toggle("hidden", s.rows.length === 0);
    this.el("btn-dist-all").classList.toggle("hidden", s.rows.length === 0 || s.running);
    this.el("btn-dist-rescan").disabled = s.scanning || s.running;
    const send = this.el("btn-dist-send");
    send.classList.toggle("hidden", nSel === 0 || s.scanning || s.running);
    send.textContent = `Distribute to ${nSel} device${nSel === 1 ? "" : "s"}`;
    const showProg = s.total > 0;
    this.el("dist-progress-wrap").classList.toggle("hidden", !showProg);
    if (showProg) {
      this.el("dist-progress-bar").style.width = `${Math.round((100 * s.done) / s.total)}%`;
      this.el("dist-progress-label").textContent = `${s.done} of ${s.total} devices finished`;
    }
  }
}
