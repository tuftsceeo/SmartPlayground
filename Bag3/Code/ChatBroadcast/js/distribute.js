/**
 * distribute.js — "Distribute code" overlay for a Broadcast Dial.
 *
 * After a send, the Dial scans for nearby wands and stations
 * (`fleet.scan` → `status_report` … `status_done`), the user picks devices,
 * and `fleet.distribute` has the Dial push a getcode to each one, staggered.
 * Per-device results arrive as `dist_progress`, then `dist_done`.
 * Wire contract: BroadcastDial/README.md "Fleet commands".
 *
 * Wands and icon displays hold at most three custom games (lib/game_slots.py)
 * and report them as status_report `g`: [[slug, mode], ...], with `role`.
 * If a selected device is full and lacks this game, the teacher picks a slot
 * (1 = oldest, as `g` is ordered); fleet.distribute carries `replace` as
 * {mac: slug in that slot} so each full device drops its own game there.
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

/** Custom games a wand or icon display keeps (lib/game_slots.py MAX). */
export const SLOT_MAX = 3;
/** Above this many games on the controller, suggest a clean-up. */
export const CONTROLLER_GAMES_NOTE = 10;

/** status_report `g` mode letter → short label ("" for an ordinary game). */
export const MODE_LABEL = { s: "solo", h: "host game", l: "lobby", o: "", x: "won't load" };

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
  /**
   * kinds: status_report kinds (roles.js hubtype) the game has code for, or
   * null when unknown (a game picked from the controller's list). A device
   * of another kind starts unselected; only an override may select it.
   */
  constructor(kinds = null) {
    this.kinds = kinds ? new Set(kinds) : null;
    this.rows = []; // {mac, kind, battery, rssi, selected, status, why}
    this.scanning = false;
    this.running = false;
    this.done = 0;
    this.total = 0;
  }

  _row(mac) {
    return this.rows.find((r) => norm(r.mac) === norm(mac));
  }

  /** True when the game has code for this row's kind (or kinds are unknown). */
  fits(row) {
    return !this.kinds || this.kinds.has(row?.kind);
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
      Object.assign(row, {
        kind: obj.kind ?? row.kind, battery: obj.battery, rssi: obj.rssi,
        role: obj.role ?? row.role, games: Array.isArray(obj.g) ? obj.g : row.games,
      });
      return;
    }
    const kind = obj.kind ?? null;
    this.rows.push({
      mac: obj.mac, kind, battery: obj.battery ?? null,
      rssi: obj.rssi ?? null, role: obj.role ?? null,
      games: Array.isArray(obj.g) ? obj.g : null,
      selected: this.fits({ kind }), status: "", why: null,
    });
  }

  /** Selected rows whose slots are full and do not already hold `slug`. */
  fullRows(slug) {
    return this.rows.filter((r) => r.selected && Array.isArray(r.games)
      && r.games.length >= SLOT_MAX && !r.games.some((e) => e[0] === slug));
  }

  /**
   * The slots the teacher can clear: one entry per slot index held by any
   * full row, each with the games in it ({slug, mode, macs}, most widely
   * held first). Empty when no selected device is full.
   */
  slotOptions(slug) {
    const rows = this.fullRows(slug);
    const out = [];
    for (let i = 0; i < SLOT_MAX; i++) {
      const by = new Map();
      for (const r of rows) {
        const e = r.games[i];
        if (!e) continue;
        const g = by.get(e[0]) || { slug: e[0], mode: e[1], macs: [] };
        g.macs.push(r.mac);
        by.set(e[0], g);
      }
      if (by.size) {
        out.push({ index: i, games: [...by.values()]
          .sort((a, b) => b.macs.length - a.macs.length || a.slug.localeCompare(b.slug)) });
      }
    }
    return out;
  }

  /** fleet.distribute `replace` for slot i: {mac: slug} over the full rows. */
  replaceFor(slug, i) {
    const map = {};
    for (const r of this.fullRows(slug)) if (r.games[i]) map[r.mac] = r.games[i][0];
    return map;
  }

  endScan() {
    this.scanning = false;
  }

  /** override: allow selecting a device the game has no code for. */
  toggle(mac, on, override = false) {
    const row = this._row(mac);
    if (!row || this.running) return;
    if (on && !override && !this.fits(row)) return;
    row.selected = on;
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

/** "Games 2 of 3: a (host game), b" for a card; "" if the device does not report slots. */
export function slotsText(games, slug) {
  if (!Array.isArray(games)) return "";
  const names = games.map(([g, m]) => (MODE_LABEL[m] ? `${g} (${MODE_LABEL[m]})` : g)
    + (g === slug ? " ✓" : ""));
  return `Games ${games.length} of ${SLOT_MAX}${names.length ? ": " + names.join(", ") : ""}`;
}

function slotsLine(r, slug) {
  const t = slotsText(r.games, slug);
  return t ? `<span class="dist-slots${r.games.length >= SLOT_MAX ? " full" : ""}">${esc(t)}</span>` : "";
}

/** Why a device is greyed out: the game has no code for its kind. */
export function unfitText(kind, simple) {
  const what = kind ? `${kindName(kind).toLowerCase()} code` : "code for this device";
  return simple ? `This game has no ${what}.`
    : `This game has no ${what}; sending will fail.`;
}

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
    this.picking = false; // the replace picker is showing
    this._unsub = [];
    this.el = (id) => document.getElementById(id);
    this.el("btn-dist-close-x").addEventListener("click", () => this.close());
    this.el("btn-dist-rescan").addEventListener("click", () => this.scan());
    this.el("btn-dist-send").addEventListener("click", () => {
      if (this.state.allFinished()) this.close();
      else this.distribute();
    });
    this.el("dist-cards").addEventListener("click", (e) => this._onCardClick(e));
    this.el("dist-replace").addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      this.picking = false;
      if (b.dataset.slot) this.distribute(Number(b.dataset.slot));
      else this.render();
    });
  }

  get device() {
    return this.app.device;
  }

  /** Open for `slug`; waits for the teacher hub to be back from its reboot, then scans. */
  /** kinds: device kinds the game has code for (null: unknown, no filter). */
  async open(slug, prettyName, kinds = null) {
    this.slug = slug;
    this.pretty = prettyName || "";
    this.state = new DistributeState(kinds);
    this.picking = false;
    // _boxGames is the list fetched before this send; count the new game too.
    const held = (this.app._boxGames || []).map((g) => g.slug);
    const n = held.length + (held.includes(slug) ? 0 : 1);
    const note = this.el("dist-note");
    note.textContent = n > CONTROLLER_GAMES_NOTE
      ? `The ${this.app.deviceShort?.() || "Dial"} holds ${n} games. You can delete old ones from its games list.` : "";
    note.classList.toggle("hidden", n <= CONTROLLER_GAMES_NOTE);
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

  /** slot: the slot index full devices clear; undefined asks first if one is needed. */
  async distribute(slot) {
    if (slot === undefined && this.state.slotOptions(this.slug).length) {
      this.picking = true;
      this.render();
      return;
    }
    const replace = slot === undefined ? null : this.state.replaceFor(this.slug, slot);
    const macs = this.state.startDistribute();
    if (!macs.length) return;
    this._setStatus(isSimple() ? "" : "Sending code…");
    this.render();
    const cmd = { cmd: "fleet.distribute", slug: this.slug, macs };
    if (replace && Object.keys(replace).length) cmd.replace = replace;
    try {
      await this.device.sendCmd(cmd);
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
    if (this.picking) return;
    const t = e.target;
    const card = t.closest(".dcard");
    const mac = card?.dataset.mac;
    if (!mac) return;
    if (t.matches("input.dist-check")) {
      this.state.toggle(mac, t.checked, !isSimple());
      this.render();
    } else if (t.closest(".dist-find")) {
      this.device.sendCmd({ cmd: "fleet.find", mac })
        .catch((err) => this.toast(`Find failed: ${err.message}`, true));
    } else if (t.closest(".dist-rename")) {
      this._editName(card, mac);
    } else if (!t.closest("button, input")) {
      const row = this.state._row(mac);
      this.state.toggle(mac, !row?.selected, !isSimple());
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
      const unfit = !s.fits(r);
      // Simple mode cannot pick a device the game has no code for.
      const locked = unfit && isSimple() && !r.selected;
      const card = document.createElement("div");
      card.className = `dcard${r.selected && !r.status ? " sel" : ""}${r.status ? ` dist-${r.status}` : ""}`
        + `${unfit && !r.status ? " dist-unfit" : ""}`;
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
        : `<span>${esc(sub)}${r.role === "splat_host" ? " · Splat host" : ""} <span class="dist-sig dist-sig-${signalLevel(r.rssi)}" title="${r.rssi ?? "?"} dBm"><i></i><i></i><i></i></span></span>`
          + (unfit ? `<span class="dist-unfit-note">${esc(unfitText(r.kind, isSimple()))}</span>` : "")
          + slotsLine(r, this.slug);
      card.innerHTML =
        `<input type="checkbox" class="dist-check" ${r.selected ? "checked" : ""} ${r.status ? "hidden" : ""} ${locked ? "disabled" : ""} aria-label="Send to ${esc(name)}">`
        + `<span class="dicon" style="color:${color}">${iconSvg(kindIcon(r.kind), { size: 36, strokeWidth: 2 })}</span>`
        + `<div class="dname"><div class="dname-row"><b title="${esc(r.mac)}">${esc(name)}</b>`
        + (r.status ? "" : `<button type="button" class="dist-rename" title="Rename (saved in this browser)" aria-label="Rename ${esc(name)}">✎</button>`)
        + `</div>${detail}</div>${tail}`;
      wrap.appendChild(card);
    }
  }

  /** "Which game should full devices give up?" One choice for all of them. */
  _renderPicker() {
    const box = this.el("dist-replace");
    box.classList.toggle("hidden", !this.picking);
    if (!this.picking) return;
    const rows = this.state.fullRows(this.slug);
    const full = rows.length;
    const noun = deviceNoun(rows);
    const one = noun.replace(/s$/, "");
    const what = this.pretty ? esc(this.pretty) : "the new game";
    const opts = this.state.slotOptions(this.slug);
    const name = (r) => getNickname(r.mac) || deviceLabel(r.mac, r.kind);
    const rowsByMac = new Map(rows.map((r) => [r.mac, r]));
    const nice = (g) => esc(String(g).replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()));
    box.innerHTML = `<div class="dist-replace-head">`
      + `<h3>${full === 1 ? `This ${one} is full` : `${full} ${noun} are full`}</h3>`
      + `<p>Each ${one} holds ${SLOT_MAX} games. Pick a slot to clear for ${what}.</p></div>`
      + `<div class="dist-replace-list">`
      + opts.map((o) => `<button type="button" class="dist-replace-opt${o.games.some((g) => g.mode === "x") ? " broken" : ""}" data-slot="${o.index}">`
        + `<span class="dist-replace-slot">Slot ${o.index + 1}${o.index === 0 ? " · oldest" : ""}</span>`
        + `<span class="dist-replace-label">Removes:</span>`
        + o.games.map((g) => `<span class="dist-replace-game"><span class="dist-replace-name">${nice(g.slug)}</span>`
          + `<span class="dist-replace-count">${full > 1 && g.macs.length === full ? `on all ${full}`
            : `on ${esc(g.macs.map((m) => name(rowsByMac.get(m))).join(", "))}`}</span></span>`).join("")
        + (o.games.some((g) => g.mode === "x") ? `<span class="dist-replace-tag">Has a broken game</span>` : "")
        + `</button>`).join("")
      + `</div>`
      + `<div class="dist-replace-foot"><button type="button" class="btn-secondary btn-compact">Cancel</button></div>`;
  }

  render() {
    if (this._editing) return; // _editName re-renders when it finishes
    const s = this.state;
    this._renderCards();
    this._renderPicker();
    const finished = s.allFinished();
    const noun = deviceNoun(s.running || finished ? this._sentRows() : s.rows);
    this.el("dist-title").textContent = s.running
      ? `Sending to ${noun}…`
      : `Send ${this.pretty || "the game"} to ${noun}`;
    this.el("btn-dist-rescan").disabled = s.scanning || s.running;
    const selNoun = deviceNoun(s.rows.filter((r) => r.selected));
    const send = this.el("btn-dist-send");
    send.classList.toggle("hidden", this.picking
      || (!s.running && !finished && (s.selectedMacs().length === 0 || s.scanning)));
    send.disabled = s.running;
    send.textContent = s.running ? "Sending…" : finished ? "Done" : `Send to ${selNoun}`;
  }
}
