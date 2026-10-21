/**
 * <sim-room> — the one-screen simulator: a <wand-sim> plus the output
 * panels its game uses, all on one virtual ESP-NOW bus and one clock.
 *
 * The wand is always shown. Panels come from a registry and appear only when
 * `wants(capabilities)` says the loaded game uses them; capabilities are
 * py/runtime.py get_capabilities() (party, local_splats, splats_min,
 * splats_max, uses_display, has_display_file, ...). Built in here: the
 * display panel (js/panels/display.js), and for a party game the Splat
 * panel (js/panels/splats.js), which draws the wand's own Splats from the
 * room's party host (js/party.js), and the other wands (js/panels/wands.js).
 * A game has no other wands unless its settings say it is for more than
 * one, or "+ Add a wand" adds one; each is a real <wand-sim> on the room's
 * bus once clicked.
 *
 * Attributes passed through to the inner <wand-sim>: game, autostart,
 * advanced.
 *
 * Properties:
 *   source         wand code instead of a vendored game (as <wand-sim>)
 *   displaySource  the display half (_icon.py text); null = look for a
 *                  vendored display file named after the game
 *   displayIcons   {name: icon file text | duty[768]} for the display game;
 *                  merged over the vendored game's icons. Setting it rewrites
 *                  the icon files, which is how an icon edit reaches a
 *                  running display.
 *   bus, clock     the room's bus (js/bus.js) and clock (js/clock.js)
 *   party          the party host (js/party.js), once the wand has booted
 *   wand           the inner <wand-sim>
 *   capabilities   the last capabilities, or null
 *   autostart, profile   passed to the inner <wand-sim>
 *   settings       the game's simulator settings, or null: { wand_splats
 *                  (Splats each wand starts with, 0..2, default 1), wands
 *                  (how many wands the game is for, 1..4, default 1) }.
 *                  Set it before `source`: the Splat count reaches the wand
 *                  ahead of the game loading.
 *
 * Methods passed to the inner <wand-sim>: start(), stop(), restart(),
 * showOverlay(), hideOverlay().
 *
 * Events: room-capabilities (detail: capabilities), room-radio (detail:
 * { text, type }: one line per pw_* party frame on the bus), and <wand-sim>'s own
 * events (FORWARDED below), re-dispatched from the room so a host page can
 * listen on the room itself.
 */

import "./wand-sim.js";
import { createBus, BROADCAST } from "./js/bus.js";
import { createClock } from "./js/clock.js";
import { hexToBytes } from "./js/radio.js";
import { createDisplayPanel, DISPLAY_STYLE } from "./js/panels/display.js";
import { createSplatPanel, SPLAT_STYLE } from "./js/panels/splats.js";
import { createWandsPanel, WANDS_STYLE } from "./js/panels/wands.js";
import { createPartyHost } from "./js/party.js";
import { WAND_RGB, identityName } from "./js/peers.js";
import { attachWand } from "./js/pyboot.js";

export const WAND_MAC = "02:00:00:00:0a:01";
export const DISPLAY_MAC = "02:00:00:00:0d:01";
/** The teacher/hub side: who tells the display to start the game. */
export const ROOM_MAC = "02:00:00:00:00:fe";

const PASS_ATTRS = ["game", "autostart", "advanced"];

/** <wand-sim> events the room re-dispatches (they do not leave its shadow root). */
const FORWARDED = ["sim-ready", "sim-loaded", "sim-frame", "sim-print", "sim-error",
  "sim-stopped", "sim-overlay-action", "sim-enow-sent", "sim-log"];

function simUrl(rel) {
  return new URL(rel, import.meta.url).href;
}

const PANELS = new Map();

class SimRoom extends HTMLElement {
  /**
   * Register an output panel.
   *   id       unique name
   *   slot     "panels" (beside the wand) or "strip" (below it)
   *   title    heading shown above the panel; null = none, and no padding
   *            (the panel draws its own header)
   *   wants    (capabilities, room) => bool: whether to show it
   *   create   (room, mountEl) => instance; called once, on first show
   *   update   optional (instance, capabilities, room) => void|Promise,
   *            called on every load while shown
   *   hide     optional (instance, room) => void|Promise
   */
  static registerPanel(id, spec) {
    if (PANELS.has(id)) throw new Error(`panel already registered: ${id}`);
    if (typeof spec.wants !== "function" || typeof spec.create !== "function") {
      throw new TypeError(`panel ${id} needs wants() and create()`);
    }
    PANELS.set(id, { slot: "panels", title: id, ...spec });
  }

  static get observedAttributes() { return PASS_ATTRS; }

  constructor() {
    super();
    this._root = this.attachShadow({ mode: "open" });
    this.clock = createClock();
    this.bus = createBus({ clock: this.clock });
    this.capabilities = null;
    this._source = null;
    this._displaySource = null;
    this._displayIcons = null;
    this._panels = new Map(); // id -> { spec, box, instance }
    this._manifest = null;
    this._loadSeq = 0;
    this.party = null;
    this._profile = null;
    this._autostart = null;
    this._settings = null;
  }

  get settings() { return this._settings; }
  set settings(v) {
    this._settings = v || null;
    this._applyGameSplats();
  }

  /** Splats each wand starts a newly loaded game with. */
  get gameSplats() {
    const n = this._settings?.wand_splats;
    return Number.isInteger(n) && n >= 0 && n <= 2 ? n : 1;
  }

  /** Wands the loaded game is for, this one included. */
  get gameWands() {
    const n = this._settings?.wands;
    return Number.isInteger(n) && n >= 1 ? n : 1;
  }

  _applyGameSplats() {
    this.wand?.pyodide?.pyimport("runtime").set_game_splats(this.gameSplats);
    this.panel("wands")?.setGameSplats(this.gameSplats);
  }

  get autostart() { return this.wand ? this.wand.autostart : !!this._autostart; }
  set autostart(v) {
    this._autostart = !!v;
    if (this.wand) this.wand.autostart = !!v;
  }

  get profile() { return this._profile; }
  set profile(v) {
    this._profile = v || null;
    if (this.wand) this.wand.profile = this._profile;
  }

  get game() { return this.wand ? this.wand.game : this.getAttribute("game"); }
  set game(v) { this.setAttribute("game", v); }

  get pyodide() { return this.wand ? this.wand.pyodide : null; }

  start() { return this.wand?.start(); }
  stop() {
    this.panel("wands")?.stop();
    return this.wand?.stop();
  }
  showOverlay(kind, opts) { return this.wand?.showOverlay(kind, opts); }
  hideOverlay() { return this.wand?.hideOverlay(); }

  get source() { return this._source; }
  set source(v) {
    this._source = v;
    if (this.wand) this.wand.source = v;
    this.panel("wands")?.pushSource();
  }

  get displaySource() { return this._displaySource; }
  set displaySource(v) {
    this._displaySource = v || null;
    if (this.capabilities) this._refresh();
  }

  get displayIcons() { return this._displayIcons; }
  set displayIcons(v) {
    this._displayIcons = v || null;
    const d = this.panel("display");
    if (d && this._displaySlug && v) {
      d.setIcons(this._displaySlug, v).catch((err) => console.error("display icons", err));
    }
  }

  /** A shown panel's instance, or undefined. */
  panel(id) { return this._panels.get(id)?.instance; }

  connectedCallback() {
    if (this.wand) return;
    this._root.innerHTML = `
      <style>
        :host { display: block; }
        .room { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
        .wand { flex: 0 1 500px; min-width: 0; }
        .wand wand-sim { width: 100%; }
        .panels { display: flex; flex-direction: column; gap: 16px; flex: 1 1 240px; min-width: 0; }
        .strip { display: flex; flex-direction: column; gap: 12px; margin-top: 16px; }
        .box { background: #fff; border: 1.5px solid #e8e6f0; border-radius: 16px; padding: 14px 16px;
          color: #231f2e; font-family: 'Nunito', system-ui, sans-serif; }
        .box.flush { padding: 0; }
        .box[hidden] { display: none; }
        .box-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; margin: 0 0 12px; }
        .box-head h3 { font: 800 15px 'Nunito', system-ui, sans-serif; margin: 0; }
        ${DISPLAY_STYLE}
        ${SPLAT_STYLE}
        ${WANDS_STYLE}
        /* Simple mode is the wand alone; its Splats are drawn in its pad. */
        :host(:not([advanced])) .box[data-panel="splats"],
        :host(:not([advanced])) .box[data-panel="wands"] { display: none; }
      </style>
      <div class="room">
        <div class="wand" data-slot="wand"></div>
        <div class="panels" data-slot="panels"></div>
      </div>
      <div class="strip" data-slot="strip"></div>`;
    const wand = document.createElement("wand-sim");
    for (const a of PASS_ATTRS) {
      if (this.hasAttribute(a)) wand.setAttribute(a, this.getAttribute(a));
    }
    if (this._source) wand.source = this._source;
    if (this._profile) wand.profile = this._profile;
    if (this._autostart !== null) wand.autostart = this._autostart;
    this.wand = wand;
    for (const type of FORWARDED) {
      wand.addEventListener(type, (e) => {
        this.dispatchEvent(new CustomEvent(type, { detail: e.detail }));
      });
    }
    wand.addEventListener("sim-ready", () => this._attachWand());
    wand.addEventListener("sim-loaded", () => {
      this._refresh().catch((err) => console.error("sim-room refresh", err));
    });
    this._root.querySelector('[data-slot="wand"]').appendChild(wand);
  }

  attributeChangedCallback(name, _old, value) {
    if (!this.wand) return;
    if (value === null) this.wand.removeAttribute(name);
    else this.wand.setAttribute(name, value);
    if (name === "game") this.panel("wands")?.pushSource();
  }

  restart() {
    this.party?.retap();
    this.panel("wands")?.restart();
    return this.wand?.restart();
  }

  /** Move the room's <wand-sim> into `card` (the all-wands overlay), or back with null. */
  placeWand(card) {
    const home = this._root.querySelector('[data-slot="wand"]');
    const to = card || home;
    if (this.wand.parentNode !== to) to.appendChild(this.wand);
  }

  /** Put the wand on the bus and the room clock (runs before its game loads). */
  _attachWand() {
    const py = this.wand.pyodide;
    attachWand(py, { bus: this.bus, clock: this.clock, mac: WAND_MAC, tx: (s, d, h) => this._tx(s, d, h) });
    py.pyimport("runtime").set_game_splats(this.gameSplats);
    this.party = createPartyHost({ bus: this.bus, clock: this.clock, py, wandMac: WAND_MAC });
    let queued = false;
    this.party.onChange(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        this.panel("splats")?.sync();
      });
    });
    this.party.onPwLog((text, frame) => {
      this.dispatchEvent(new CustomEvent("room-radio", { detail: { text, type: frame.type } }));
    });
  }

  /** Bus send from a Python device; returns the ACK count espnow.send uses. */
  _tx(src, dst, hex) {
    this.bus.send(src, dst, hexToBytes(hex));
    return dst === BROADCAST || this.bus.macs().includes(dst) ? 1 : 0;
  }

  async _manifestFiles() {
    if (!this._manifest) {
      const res = await fetch(simUrl("vendor/MANIFEST.json"), { cache: "no-cache" });
      if (!res.ok) throw new Error(`fetch vendor/MANIFEST.json: ${res.status}`);
      this._manifest = Object.keys((await res.json()).files);
    }
    return this._manifest;
  }

  /** {slug, src, icons} for the loaded game's display half, or null. */
  async _resolveDisplay() {
    const slug = this._source ? "custom" : this.wand.game.replace(/\.py$/, "");
    if (this._displaySource) {
      return { slug, src: this._displaySource, icons: { ...(this._displayIcons || {}) } };
    }
    if (this._source) return null;
    const files = await this._manifestFiles();
    const rel = `display/games/${slug}.py`;
    if (!files.includes(rel)) return null;
    const fetchText = async (r) => {
      const res = await fetch(simUrl(`vendor/${r}`), { cache: "no-cache" });
      if (!res.ok) throw new Error(`fetch vendor/${r}: ${res.status}`);
      return res.text();
    };
    const iconPrefix = `display/games/${slug}_icons/`;
    const icons = {};
    for (const f of files.filter((f) => f.startsWith(iconPrefix))) {
      icons[f.slice(iconPrefix.length, -3)] = await fetchText(f);
    }
    return { slug, src: await fetchText(rel), icons: { ...icons, ...(this._displayIcons || {}) } };
  }

  /** Re-read capabilities for the loaded game and show/hide panels. */
  async _refresh() {
    const seq = ++this._loadSeq;
    const display = await this._resolveDisplay();
    if (seq !== this._loadSeq) return;
    const py = this.wand.pyodide;
    const runtime = py.pyimport("runtime");
    runtime.set_display_source(display ? display.src : null);
    const capsProxy = runtime.get_capabilities();
    const caps = capsProxy.toJs({ dict_converter: Object.fromEntries });
    capsProxy.destroy();
    this.capabilities = caps;
    this._display = display;
    this._displaySlug = display ? display.slug : null;
    this.party?.setGame(this._source ? "custom" : this.wand.game.replace(/\.py$/, ""), caps);
    this.dispatchEvent(new CustomEvent("room-capabilities", { detail: caps }));
    // Show and hide every panel first: an update can take a while (the
    // display boots its own Pyodide), and a panel the new game does not use
    // must not linger meanwhile.
    const shownNow = [];
    for (const [id, spec] of PANELS) {
      const shown = !!spec.wants(caps, this);
      let entry = this._panels.get(id);
      if (shown && !entry) {
        const box = document.createElement("section");
        box.className = "box";
        box.dataset.panel = id;
        if (spec.title) {
          box.innerHTML = `<div class="box-head"><h3></h3></div>`;
          box.querySelector("h3").textContent = spec.title;
        } else {
          box.classList.add("flush");
        }
        this._root.querySelector(`[data-slot="${spec.slot}"]`).appendChild(box);
        entry = { spec, box, instance: spec.create(this, box) };
        this._panels.set(id, entry);
      }
      if (!entry) continue;
      entry.box.hidden = !shown;
      shownNow.push([entry, shown]);
    }
    for (const [{ spec, instance }, shown] of shownNow) {
      if (seq !== this._loadSeq) return;
      if (shown && spec.update) await spec.update(instance, caps, this);
      if (!shown && spec.hide) await spec.hide(instance, this);
    }
  }

  /** What the room's display should run for the current game (or null). */
  get displayGame() { return this._display || null; }
}

SimRoom.registerPanel("display", {
  title: "Icon display",
  wants: (caps) => !!caps.has_display_file,
  create: (room, box) => createDisplayPanel({
    bus: room.bus, clock: room.clock, mac: DISPLAY_MAC, mount: box,
  }),
  async update(panel, caps, room) {
    const game = room.displayGame;
    if (!game) {
      panel.setDisplayMode(false);
      return;
    }
    await panel.setGame(game.slug, game.src, game.icons);
    panel.setDisplayMode(true);
    // What the Box/teacher does on device: tell the display which game to
    // run. Unicast, so the wand does not take it as a force-switch.
    room.bus.send(ROOM_MAC, DISPLAY_MAC,
      new TextEncoder().encode(JSON.stringify({ type: "start_game", name: game.slug })));
  },
  hide(panel, room) {
    room.bus.send(ROOM_MAC, DISPLAY_MAC, new TextEncoder().encode(JSON.stringify({ type: "stop" })));
  },
});

/** The wand's own Splats as a Splat panel group. */
function wandGroup(party) {
  return {
    owner: party.wandMac, label: "this wand", rgb: WAND_RGB[identityName(party.wandMac)],
    splats: party.wandSplats,
    onButton: (i, down) => party.wandSplatButton(i, down),
    onReady: (i, up) => party.wandSplatReady(i, up),
  };
}

// The wand's Splats are drawn in its pad, below the drawn wand, in both
// modes. In advanced mode a card below the wand adds their count and links,
// and the other wands bar (js/panels/wands.js) follows it.
SimRoom.registerPanel("splats", {
  slot: "strip",
  title: "Splats on this wand",
  wants: (caps) => !!caps.party,
  create(room, box) {
    const overlay = document.createElement("div");
    overlay.className = "pad-splats";
    overlay.slot = "pad";
    const panel = createSplatPanel({
      mount: box,
      overlay,
      onLocalCount: (n) => {
        room.party.setLocalSplats(n);
        room.restart();
      },
    });
    let shape = "";
    let shown = false;
    panel.sync = () => {
      if (!shown) return;
      const group = wandGroup(room.party);
      const key = group.splats.map((s) => s.mac).join("+");
      if (key !== shape) {
        shape = key;
        panel.setGroups([group]);
        // In the wand's pad only while there is a Splat to show: the pad
        // makes room under the wand for whatever is slotted.
        if (group.splats.length) room.wand.appendChild(overlay);
        else overlay.remove();
      } else {
        panel.refresh();
      }
    };
    panel.show = () => { shown = true; };
    panel.unmount = () => {
      shown = false;
      shape = "";
      overlay.remove();
    };
    return panel;
  },
  update(panel, caps) {
    panel.setLocalCount(caps.local_splats ?? 1);
    panel.show();
    panel.sync();
  },
  hide(panel) {
    panel.unmount();
  },
});

// Advanced mode: how many other wands are in the game, and the overlay
// with all of them side by side. Shown for a party game, and for any game
// whose settings say it is for more than one wand.
SimRoom.registerPanel("wands", {
  slot: "strip",
  title: null,
  wants: (caps, room) => !!caps.party || room.gameWands > 1,
  create(room, box) {
    const panel = createWandsPanel({ mount: box, room });
    panel.setGameSplats(room.gameSplats);
    return panel;
  },
  update(panel, caps, room) {
    panel.setGame(caps);
    // Settings for a different number of wands start over with that many
    // placeholders. New code for the same number keeps the wands as they
    // are; live ones have already been handed the new code.
    if (room.gameWands !== panel.forWands) {
      panel.forWands = room.gameWands;
      panel.setFor(room.gameWands);
    }
  },
  hide(panel) {
    panel.forWands = null;
    panel.clear();
  },
});

customElements.define("sim-room", SimRoom);
export { SimRoom };
