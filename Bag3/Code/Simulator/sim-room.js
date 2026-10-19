/**
 * <sim-room> — the one-screen simulator: a <wand-sim> plus the output
 * panels its game uses, all on one virtual ESP-NOW bus and one clock.
 *
 * The wand is always shown. Panels come from a registry and appear only when
 * `wants(capabilities)` says the loaded game uses them; capabilities are
 * py/runtime.py get_capabilities() (party, splats_local, splats_min,
 * splats_max, uses_display, has_display_file, ...). Built in here: the
 * display panel (js/panels/display.js). The Splat panel and the peer strip
 * register the same way (SimRoom.registerPanel), into the "panels" or
 * "strip" slot.
 *
 * Attributes passed through to the inner <wand-sim>: game, autostart,
 * advanced, show-console, log-lines.
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
 *   wand           the inner <wand-sim>
 *   capabilities   the last capabilities, or null
 *
 * Events: room-capabilities (detail: capabilities), plus everything
 * <wand-sim> fires, which bubbles out unchanged.
 */

import "./wand-sim.js";
import { createBus, BROADCAST } from "./js/bus.js";
import { createClock } from "./js/clock.js";
import { hexToBytes, bytesToHex, describePayload } from "./js/radio.js";
import { createDisplayPanel, DISPLAY_STYLE } from "./js/panels/display.js";

export const WAND_MAC = "02:00:00:00:0a:01";
export const DISPLAY_MAC = "02:00:00:00:0d:01";
/** The teacher/hub side: who tells the display to start the game. */
export const ROOM_MAC = "02:00:00:00:00:fe";

const PASS_ATTRS = ["game", "autostart", "advanced", "show-console", "log-lines"];

function simUrl(rel) {
  return new URL(rel, import.meta.url).href;
}

const PANELS = new Map();

class SimRoom extends HTMLElement {
  /**
   * Register an output panel.
   *   id       unique name
   *   slot     "panels" (beside the wand) or "strip" (below it)
   *   title    heading shown above the panel
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
  }

  get source() { return this._source; }
  set source(v) {
    this._source = v;
    if (this.wand) this.wand.source = v;
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
        .box { background: #fff; border: 1.5px solid #e8e6f0; border-radius: 16px; padding: 12px; }
        .box[hidden] { display: none; }
        .box h3 { font: 800 0.9rem 'Nunito', system-ui, sans-serif; margin: 0 0 8px; }
        ${DISPLAY_STYLE}
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
    this.wand = wand;
    wand.addEventListener("sim-ready", () => this._attachWand());
    wand.addEventListener("sim-loaded", () => {
      this._refresh().catch((err) => console.error("sim-room refresh", err));
    });
    this._root.querySelector('[data-slot="wand"]').appendChild(wand);
    this.bus.onLog((e) => this._onBusLog(e));
  }

  attributeChangedCallback(name, _old, value) {
    if (!this.wand) return;
    if (value === null) this.wand.removeAttribute(name);
    else this.wand.setAttribute(name, value);
  }

  restart() { return this.wand?.restart(); }

  /** Put the wand on the bus and the room clock (runs before its game loads). */
  _attachWand() {
    const py = this.wand.pyodide;
    const simState = py.pyimport("sim_state");
    py.globals.set("_room_tx", (src, dst, hex) => this._tx(String(src), String(dst), String(hex)));
    py.globals.set("_room_now", () => this.clock.nowMs());
    simState.set_own_mac(WAND_MAC);
    simState.set_radio_tx(py.globals.get("_room_tx"));
    py.pyimport("time_patch").set_clock_source(py.globals.get("_room_now"));
    this.bus.attach(WAND_MAC, (src, payload) => simState.deliver_enow(src, bytesToHex(payload)));
  }

  /** Bus send from a Python device; returns the ACK count espnow.send uses. */
  _tx(src, dst, hex) {
    this.bus.send(src, dst, hexToBytes(hex));
    return dst === BROADCAST || this.bus.macs().includes(dst) ? 1 : 0;
  }

  _onBusLog(e) {
    if (e.event !== "send" || e.src !== WAND_MAC) return;
    const d = this.panel("display");
    if (d) d.pushFeed(`${e.dst === BROADCAST ? "broadcast" : `to ${e.dst}`}: ${describePayload(e.payload)}`);
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
    this.dispatchEvent(new CustomEvent("room-capabilities", { detail: caps }));
    for (const [id, spec] of PANELS) {
      const shown = !!spec.wants(caps, this);
      let entry = this._panels.get(id);
      if (shown && !entry) {
        const box = document.createElement("section");
        box.className = "box";
        box.dataset.panel = id;
        box.innerHTML = `<h3></h3>`;
        box.querySelector("h3").textContent = spec.title;
        this._root.querySelector(`[data-slot="${spec.slot}"]`).appendChild(box);
        entry = { spec, box, instance: spec.create(this, box) };
        this._panels.set(id, entry);
      }
      if (!entry) continue;
      entry.box.hidden = !shown;
      if (shown && spec.update) await spec.update(entry.instance, caps, this);
      if (!shown && spec.hide) await spec.hide(entry.instance, this);
    }
  }

  /** What the room's display should run for the current game (or null). */
  get displayGame() { return this._display || null; }
}

SimRoom.registerPanel("display", {
  title: "Icon display",
  wants: (caps) => !!(caps.has_display_file || caps.uses_display),
  create: (room, box) => createDisplayPanel({
    bus: room.bus, clock: room.clock, mac: DISPLAY_MAC, mount: box,
  }),
  async update(panel, caps, room) {
    panel.clearFeed();
    const game = room.displayGame;
    if (!caps.has_display_file || !game) {
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

customElements.define("sim-room", SimRoom);
export { SimRoom };
