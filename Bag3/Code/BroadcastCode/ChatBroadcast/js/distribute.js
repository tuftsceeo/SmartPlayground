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

import { iconSvg } from "./icons.js";

/** Simple mode is every mode but advanced; the body class is set by app.js. */
const isSimple = () => !document.body.classList.contains("ui-advanced");

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

/**
 * What to call a set of rows: "wands" when every kind is wand, "stations"
 * when every kind is known and not a wand, otherwise "devices".
 * @param {{kind: string|null}[]} rows
 */
export function deviceNoun(rows) {
  if (!rows.length) return "devices";
  if (rows.every((r) => r.kind === "wand")) return "wands";
  if (rows.every((r) => r.kind && r.kind !== "wand")) return "stations";
  return "devices";
}

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

  /** True once a run has started and every queued row is done or failed. */
  allFinished() {
    const sent = this.rows.filter((r) => r.status);
    return !this.running && sent.length > 0
      && sent.every((r) => r.status === "done" || r.status === "failed");
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
  queued: "Waiting",
  pulling: "Getting it",
  done: "Ready",
  failed: "Failed",
};
const STATUS_GLYPH = { queued: "spinner", pulling: "download", done: "check", failed: "warning" };

/** Card icon for a status_report kind. */
function kindIcon(kind) {
  if (kind === "wand") return "wand";
  if (kind === "icon_display") return "iconDisplay";
  return "station";
}

/**
 * DOM controller. `app` supplies `device` (the BboxDeviceLink) and
 * `link.state`; `toast` reports errors. Status lines are short in simple
 * mode and full sentences in advanced mode.
 */
export class DistributeOverlay {
  constructor({ app, showOverlay, hideOverlay, toast }) {
    this.app = app;
    this.showOverlay = showOverlay;
    this.hideOverlay = hideOverlay;
    this.toast = toast;
    this.state = new DistributeState();
    this.slug = null;
    this.pretty = "";
    this._unsub = [];
    this.el = (id) => document.getElementById(id);
    this.el("btn-dist-close-x").addEventListener("click", () => this.close());
    this.el("btn-dist-rescan").addEventListener("click", () => this.scan());
    this.el("btn-dist-send").addEventListener("click", () => {
      if (this.state.allFinished()) this.close();
      else this.distribute();
    });
    this.el("dist-cards").addEventListener("click", (e) => this._onCardClick(e));
  }

  get device() {
    return this.app.device;
  }

  /** Open for `slug`; waits for the teacher hub to be back from its reboot, then scans. */
  async open(slug, prettyName) {
    this.slug = slug;
    this.pretty = prettyName || "";
    this.state = new DistributeState();
    this._setStatus(isSimple() ? "Reconnecting…" : "Waiting for the teacher hub to restart…");
    this.render();
    this.showOverlay("distribute-overlay");
    if (!(await this._waitLive())) {
      this._setStatus(isSimple() ? "Not connected."
        : "The teacher hub did not come back. Reconnect it, then press Refresh.");
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
        const rows = this.state.rows;
        const one = deviceNoun(rows).replace(/s$/, "");
        if (isSimple()) {
          this._setStatus(rows.length ? `Tap a ${one} to choose it.` : "No devices found.");
        } else {
          this._setStatus(rows.length ? `Pick the ${deviceNoun(rows)} to update.`
            : "No devices answered. Check they are on, then press Refresh.");
        }
        this.render();
      }),
      d.on("dist_progress", (o) => { this.state.applyProgress(o); this.render(); }),
      d.on("dist_done", (o) => {
        this.state.finish(o);
        this._setStatus(isSimple() ? ""
          : `${o?.ok ?? 0} of ${o?.total ?? this.state.total} ${deviceNoun(this._sentRows())} updated.`);
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
    this._setStatus(isSimple() ? "Looking…" : "Looking for wands and stations…");
    this.render();
    try {
      await this.device.sendCmd({ cmd: "fleet.scan" });
    } catch (e) {
      this.state.endScan();
      this._setStatus(isSimple() ? "Scan failed." : `Scan failed: ${e.message}`);
      this.toast(`Scan failed: ${e.message}`, true);
      this.render();
    }
  }

  async distribute() {
    const macs = this.state.startDistribute();
    if (!macs.length) return;
    this._setStatus(isSimple() ? "" : "Sending code…");
    this.render();
    try {
      await this.device.sendCmd({ cmd: "fleet.distribute", slug: this.slug, macs });
    } catch (e) {
      this.state.abort(e.message);
      this._setStatus(isSimple() ? "Failed." : `Distribute failed: ${e.message}`);
      this.toast(`Distribute failed: ${e.message}`, true);
      this.render();
    }
  }

  /** Rows in the current or last run. */
  _sentRows() {
    return this.state.rows.filter((r) => r.status);
  }

  _onCardClick(e) {
    const t = e.target;
    const card = t.closest(".dcard");
    const mac = card?.dataset.mac;
    if (!mac) return;
    if (t.matches("input.dist-check")) {
      this.state.toggle(mac, t.checked);
      this.render();
    } else if (t.closest(".dist-find")) {
      this.device.sendCmd({ cmd: "fleet.find", mac })
        .catch((err) => this.toast(`Find failed: ${err.message}`, true));
    } else if (t.closest(".dist-rename")) {
      this._editName(card, mac);
    } else if (!t.closest("button, input")) {
      const row = this.state._row(mac);
      this.state.toggle(mac, !row?.selected);
      this.render();
    }
  }

  /** Swap the card's name for a text input; Enter or blur saves, Escape cancels. */
  _editName(card, mac) {
    const cell = card.querySelector(".dname-row");
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

  /** One card per device; only the chosen ones while sending and after. */
  _renderCards() {
    const s = this.state;
    const wrap = this.el("dist-cards");
    wrap.textContent = "";
    const rows = s.running || s.allFinished() ? this._sentRows() : s.rows;
    for (const r of rows) {
      const label = deviceLabel(r.mac, r.kind);
      const nick = getNickname(r.mac);
      const name = nick || label;
      const sub = nick ? `${label} · ${kindName(r.kind)}` : kindName(r.kind);
      const card = document.createElement("div");
      card.className = `dcard${r.selected && !r.status ? " sel" : ""}${r.status ? ` dist-${r.status}` : ""}`;
      card.dataset.mac = r.mac;
      const color = r.status === "failed" ? "#b0281c" : r.status === "done" ? "#1c9a82"
        : r.status ? "#6c4cd1" : r.selected ? "#231f2e" : "#c9c4dc";
      let tail;
      if (r.status) {
        tail = `<span class="dstatus dstatus-${r.status}" title="${esc(r.why || "")}">`
          + `${iconSvg(STATUS_GLYPH[r.status], { size: 22, strokeWidth: 2.5 })}${STATUS_TEXT[r.status]}</span>`;
      } else {
        const batt = r.battery == null ? ""
          : `<span class="dbatt">${iconSvg("battery", { size: 20, strokeWidth: 2 })}${r.battery}%</span>`;
        tail = `${batt}<button type="button" class="dist-find" title="Find Me" aria-label="Find Me ${esc(name)}">`
          + `${iconSvg("locate", { size: 18, strokeWidth: 2 })}Find Me</button>`;
      }
      const detail = r.status
        ? `<div class="dbar"><div class="dbar-fill dbar-${r.status}"></div></div>`
        : `<span>${esc(sub)} <span class="dist-sig dist-sig-${signalLevel(r.rssi)}" title="${r.rssi ?? "?"} dBm"><i></i><i></i><i></i></span></span>`;
      card.innerHTML =
        `<input type="checkbox" class="dist-check" ${r.selected ? "checked" : ""} ${r.status ? "hidden" : ""} aria-label="Send to ${esc(name)}">`
        + `<span class="dicon" style="color:${color}">${iconSvg(kindIcon(r.kind), { size: 36, strokeWidth: 2 })}</span>`
        + `<div class="dname"><div class="dname-row"><b title="${esc(r.mac)}">${esc(name)}</b>`
        + (r.status ? "" : `<button type="button" class="dist-rename" title="Rename (saved in this browser)" aria-label="Rename ${esc(name)}">✎</button>`)
        + `</div>${detail}</div>${tail}`;
      wrap.appendChild(card);
    }
  }

  render() {
    if (this._editing) return; // _editName re-renders when it finishes
    const s = this.state;
    this._renderCards();
    const finished = s.allFinished();
    const noun = deviceNoun(s.running || finished ? this._sentRows() : s.rows);
    this.el("dist-title").textContent = s.running
      ? `Sending to ${noun}…`
      : `Send ${this.pretty || "the game"} to ${noun}`;
    this.el("btn-dist-rescan").disabled = s.scanning || s.running;
    const selNoun = deviceNoun(s.rows.filter((r) => r.selected));
    const send = this.el("btn-dist-send");
    send.classList.toggle("hidden", !s.running && !finished && (s.selectedMacs().length === 0 || s.scanning));
    send.disabled = s.running;
    send.textContent = s.running ? "Sending…" : finished ? "Done" : `Send to ${selNoun}`;
  }
}
