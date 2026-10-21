/**
 * Icon displays for <sim-room>: 16x16 icon displays, about the size of the
 * wand's screen, standing in the wand's controls pane under the gesture
 * buttons (wand-sim's "ctrl" slot), each its own device on the room's bus.
 *
 * A display starts as a placeholder: the outline of a display with "?" and
 * "Click to Add Display" that runs nothing and is not on the radio. Clicking it, or loading a
 * game with a display file, wakes it: it boots its own Pyodide running
 * py/icon_host.py, which copies IconDisplay/main.py's idle loop and runs the
 * display game against a simulated Matrix. Frames come back as the logical
 * 768-byte src plus intensity and are drawn with iconmaker's
 * renderPreview(). Each display has its own MAC, so it hears the wand's
 * broadcasts and its replies reach the wand. Its prints go out as
 * display-print events (detail: { text, mac }).
 *
 * A game with a display file wakes every display, adding one if there are
 * none, and the room unicasts start_game to each. A game without one takes
 * away the displays it added and sends stop to the rest. Advanced mode adds
 * a strip card to add displays (up to MAX_DISPLAYS) and a button on each to
 * take it away; simple mode shows the displays only while the game uses
 * them.
 *
 *   createDisplaysPanel({ mount, room })
 *     .sync(game, stale)   the room loaded a game; game = room.displayGame
 *     .setIcons(slug, icons)
 *     .placeIn(el)         move the displays into el (the all-wands dialog), or back with null
 *     .add()               add a placeholder display
 *     .displays, .full     the devices, in order; whether there are MAX_DISPLAYS
 *
 *   createDisplayDevice({ bus, clock, mac, onLive })
 *     .el, .live, .ready, .lastFrameHex, .prints, wake(), setGame(), setIcons(), destroy()
 */

import { PYODIDE_CDN } from "../../wand-sim.js";
import { hexToBytes, bytesToHex } from "../radio.js";
import { loadPyodideNoJspi } from "../pyboot.js";
import { icon } from "../icons.js";

const PREVIEW_URL = "../../../BroadcastCode/ChatBroadcast/iconmaker/js/pipeline/preview.js";
const W = 16;

export const MAX_DISPLAYS = 4;

/** The teacher/hub side: who tells a display to start the game. */
export const ROOM_MAC = "02:00:00:00:00:fe";

export function displayMac(i) {
  return `02:00:00:00:0d:${(i + 1).toString(16).padStart(2, "0")}`;
}

/** Files the display's Pyodide needs, relative to the Simulator root. */
export const DISPLAY_FILES = [
  "py/transform.py",
  "py/icon_host.py",
  "py/shims/sim_state.py",
  "py/shims/machine.py",
  "py/shims/neopixel.py",
  "py/shims/_thread.py",
  "py/shims/network.py",
  "py/shims/espnow.py",
  "py/shims/micropython.py",
  "py/shims/time_patch.py",
  "vendor/display/lib/icon_store.py",
  "vendor/display/lib/display_tags.py",
  "vendor/display/lib/shapes.py",
  "vendor/display/lib/espnow_manager.py",
];

function simUrl(rel) {
  return new URL(`../../${rel}`, import.meta.url).href;
}

export const DISPLAY_STYLE = `
.display-shelf { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 12px; }
.display-shelf:empty { display: none; }
.display-dev { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.display-dev .rm { align-self: flex-end; }
.display-case { position: relative; width: 128px; height: 128px; box-sizing: border-box; padding: 7px;
  border-radius: 16px; background: #231f2e; display: flex; align-items: center; justify-content: center; }
.display-case canvas { display: block; width: 114px; height: 114px; border-radius: 8px; background: #000; }
.display-case canvas[hidden] { display: none; }
button.display-case { flex-direction: column; gap: 8px; border: 3px solid #c2b8d6; background: #fff; cursor: pointer;
  padding: 0; font: 900 44px/1 'Nunito', system-ui, sans-serif; color: #8b859a; }
button.display-case b { font: 800 12px/1.2 'Nunito', system-ui, sans-serif; color: #231f2e; }
button.display-case:hover { border-color: #6c4cd1; color: #6c4cd1; }
button.display-case:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(108,76,209,.2); }
.display-dev .display-status { min-height: 16px; font: 700 11px/1.4 'Nunito', system-ui, sans-serif; color: #5b5468; text-align: center; }
.displays-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; min-height: 64px;
  padding: 10px 12px 10px 16px; box-sizing: border-box; }
.displays-bar .lead { width: 18px; height: 18px; box-sizing: border-box; border-radius: 5px; border: 2px solid #6c4cd1; }
.displays-bar .count { font: 800 14px 'Nunito', system-ui, sans-serif; color: #231f2e; }
.displays-bar .note { font: 700 12px 'Nunito', system-ui, sans-serif; color: #5b5468; }
.displays-bar .wbtn { margin-left: auto; }
.wand-card .display-dev { align-self: flex-start; }
.wand-card .chip.display { background: #f2eefc; color: #6c4cd1; }
:host(:not([advanced])) .box[data-panel="displays"],
:host(:not([advanced])) .display-dev .rm { display: none; }
:host(:not([advanced])) .display-shelf:not(.in-game) { display: none; }
`;

let previewModule = null;
async function loadPreview() {
  if (!previewModule) {
    previewModule = import(new URL(PREVIEW_URL, import.meta.url).href);
  }
  return previewModule;
}

/** Plain-squares fallback when iconmaker is not served alongside. */
function drawSquares(canvas, pixels, intensity) {
  const cell = 12;
  canvas.width = W * cell;
  canvas.height = W * cell;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#111";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const k = Math.min(1, intensity / 0.5);
  pixels.forEach(([r, g, b], i) => {
    if (!(r || g || b)) return;
    ctx.fillStyle = `rgb(${Math.round(r * k)}, ${Math.round(g * k)}, ${Math.round(b * k)})`;
    ctx.fillRect((i % W) * cell + 1, Math.floor(i / W) * cell + 1, cell - 2, cell - 2);
  });
}

export function createDisplayDevice({ bus, clock, mac, onLive }) {
  const el = document.createElement("div");
  el.className = "display-dev";
  el.dataset.mac = mac;
  const ghost = document.createElement("button");
  ghost.type = "button";
  ghost.className = "display-case";
  ghost.innerHTML = `?<b>Click to Add Display</b>`;
  ghost.addEventListener("click", () => { wake().catch(() => {}); });
  const statusEl = document.createElement("div");
  statusEl.className = "display-status";
  statusEl.setAttribute("aria-live", "polite");
  el.append(ghost, statusEl);

  let face = null;
  let canvas = null;
  let py = null;
  let host = null;
  let booting = null;
  let detach = null;
  let renderer = null;
  let ready = false;
  let lastFrameHex = "";
  const printLog = [];

  function setStatus(text) {
    statusEl.textContent = text;
  }

  async function draw(srcHex, intensity) {
    lastFrameHex = srcHex;
    const bytes = hexToBytes(srcHex);
    const pixels = [];
    for (let i = 0; i < bytes.length; i += 3) pixels.push([bytes[i], bytes[i + 1], bytes[i + 2]]);
    if (!renderer) {
      try {
        const mod = await loadPreview();
        renderer = (px, inten) => mod.renderPreview(px, inten, canvas);
      } catch (err) {
        console.warn("icon display: renderPreview unavailable, drawing plain squares", err);
        renderer = (px, inten) => drawSquares(canvas, px, inten);
      }
    }
    // A later frame may have arrived while the renderer loaded.
    if (srcHex === lastFrameHex) {
      renderer(pixels, Number(intensity));
      canvas.hidden = false;
    }
  }

  async function boot() {
    if (!window.loadPyodide) {
      await new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = PYODIDE_CDN + "pyodide.js";
        s.onload = resolve;
        s.onerror = () => reject(new Error("Failed to load pyodide.js"));
        document.head.appendChild(s);
      });
    }
    py = await loadPyodideNoJspi(window.loadPyodide, { indexURL: PYODIDE_CDN });
    const texts = await Promise.all(DISPLAY_FILES.map(async (rel) => {
      const res = await fetch(simUrl(rel), { cache: "no-cache" });
      if (!res.ok) throw new Error(`fetch ${rel}: ${res.status}`);
      return [rel, await res.text()];
    }));
    for (const [rel, text] of texts) {
      const path = "/sim/" + rel;
      py.FS.mkdirTree(path.slice(0, path.lastIndexOf("/")));
      py.FS.writeFile(path, text);
    }
    py.globals.set("_disp_frame", (hex, inten) => {
      draw(String(hex), inten).catch((err) => console.error("icon display draw failed", err));
    });
    py.globals.set("_disp_print", (line) => {
      printLog.push(String(line));
      if (printLog.length > 400) printLog.splice(0, printLog.length - 400);
      el.dispatchEvent(new CustomEvent("display-print", { detail: { text: String(line), mac }, bubbles: true, composed: true }));
    });
    py.globals.set("_disp_tx", (src, dst, hex) => {
      const payload = hexToBytes(String(hex));
      bus.send(String(src), String(dst), payload);
      return String(dst) === "ff:ff:ff:ff:ff:ff" || bus.macs().includes(String(dst)) ? 1 : 0;
    });
    py.globals.set("_disp_now", () => clock.nowMs());
    await py.runPythonAsync(`
import sys
sys.path.insert(0, "/sim/py")
from icon_host import get_host
_host = get_host()
_host.set_frame_callback(_disp_frame)
_host.set_print_callback(_disp_print)
_host.bootstrap(workdir="/sim/display_fs", mac=${JSON.stringify(mac)})
import time_patch
time_patch.set_clock_source(_disp_now)
_host.sim_state.set_radio_tx(_disp_tx)
`);
    host = py.globals.get("_host");
    const simState = py.pyimport("sim_state");
    detach = bus.attach(mac, (src, payload) => simState.deliver_enow(src, bytesToHex(payload)));
    // Assigned, not returned: a returned Task becomes a JS promise that
    // only settles when the idle loop ends.
    await py.runPythonAsync("_disp_task = await _host.start()");
    ready = true;
    el.dataset.ready = "1";
    setStatus("");
  }

  /** Turn the placeholder into a running display (once). */
  async function wake() {
    if (!booting) {
      face = document.createElement("div");
      face.className = "display-case";
      face.setAttribute("role", "img");
      face.setAttribute("aria-label", "Icon display");
      canvas = document.createElement("canvas");
      canvas.dataset.el = "display-canvas";
      canvas.hidden = true;
      face.appendChild(canvas);
      ghost.replaceWith(face);
      setStatus("starting the display…");
      booting = boot().catch((err) => {
        setStatus(`display failed to start: ${err.message || err}`);
        el.dataset.error = String(err.message || err);
        throw err;
      });
      booting.then(() => onLive?.(), () => {});
    }
    return booting;
  }

  return {
    el,
    mac,
    get live() { return !!booting; },
    get ready() { return ready; },
    get lastFrameHex() { return lastFrameHex; },
    get prints() { return printLog.slice(); },
    wake,

    /** Install the display game and its icons ({name: file text | duty[768]}). */
    async setGame(slug, src, icons = {}) {
      await wake();
      py.globals.set("_disp_slug", slug);
      py.globals.set("_disp_src", src);
      py.globals.set("_disp_icons", py.toPy(icons));
      await py.runPythonAsync("_host.set_game(_disp_slug, _disp_src)\n_host.set_icons(_disp_slug, _disp_icons)");
    },

    /** Rewrite a game's icons; the next draw reads the new files. */
    async setIcons(slug, icons) {
      if (!ready) return;
      py.globals.set("_disp_slug", slug);
      py.globals.set("_disp_icons", py.toPy(icons));
      await py.runPythonAsync("_host.set_icons(_disp_slug, _disp_icons)");
    },

    async destroy() {
      el.remove();
      if (detach) detach();
      detach = null;
      if (py && host) await py.runPythonAsync("await _host.stop()");
    },
  };
}

export function createDisplaysPanel({ mount, room }) {
  // The displays stand in the wand's controls pane, under the gesture
  // buttons (wand-sim's "ctrl" slot); the bar is an advanced strip card.
  const shelf = document.createElement("div");
  shelf.className = "display-shelf";
  shelf.slot = "ctrl";
  room.wand.appendChild(shelf);
  const bar = document.createElement("div");
  bar.className = "displays-bar";
  bar.innerHTML = `<span class="lead" aria-hidden="true"></span>
    <span class="count" data-el="count"></span>
    <span class="note" data-el="note"></span>
    <button type="button" class="wbtn" data-el="add">+ Add a display</button>`;
  mount.append(bar);
  const addBtn = bar.querySelector('[data-el="add"]');
  addBtn.addEventListener("click", () => add(false));

  /** [{ dev, auto, card }] in order; auto = added for the game, taken away after it. */
  let list = [];
  let game = null;
  let placedIn = null;

  function send(mac, msg) {
    room.bus.send(ROOM_MAC, mac, new TextEncoder().encode(JSON.stringify(msg)));
  }

  /** What the Box/teacher does on device: tell the display which game to
   * run. Unicast, so the wand does not take it as a force-switch. */
  async function startOn(d, g, stale) {
    await d.dev.setGame(g.slug, g.src, g.icons);
    if (stale?.() || !list.includes(d)) return;
    send(d.dev.mac, { type: "start_game", name: g.slug });
  }

  function draw() {
    const n = list.length;
    bar.querySelector('[data-el="count"]').textContent = n === 0 ? "No icon displays."
      : n === 1 ? "1 icon display" : `${n} icon displays`;
    bar.querySelector('[data-el="note"]').textContent = n && !game
      ? `This game has no display file: ${n === 1 ? "it shows" : "they show"} the ready icon.` : "";
    addBtn.hidden = n >= MAX_DISPLAYS;
    room.panel("wands")?.redraw();
  }

  function freeMac() {
    for (let i = 0; ; i++) {
      const mac = displayMac(i);
      if (!list.some((d) => d.dev.mac === mac)) return mac;
    }
  }

  function wrap(d) {
    const rm = document.createElement("button");
    rm.type = "button";
    rm.className = "wbtn small sq rm";
    rm.setAttribute("aria-label", "Take this display away");
    rm.innerHTML = icon("close", 15);
    rm.addEventListener("click", () => remove(d));
    d.dev.el.prepend(rm);
  }

  function add(auto) {
    if (list.length >= MAX_DISPLAYS) return null;
    const d = { auto };
    d.dev = createDisplayDevice({
      bus: room.bus, clock: room.clock, mac: freeMac(),
      // Woken by a click while a display game is loaded: it joins that game.
      onLive: () => { if (game && list.includes(d)) startOn(d, game).catch((err) => console.error("icon display", err)); },
    });
    wrap(d);
    list.push(d);
    place(d);
    draw();
    return d;
  }

  function remove(d) {
    list = list.filter((x) => x !== d);
    d.card?.remove();
    d.dev.destroy().catch((err) => console.error("icon display stop", err));
    draw();
  }

  function place(d) {
    if (placedIn) {
      d.card = document.createElement("div");
      d.card.className = "wand-card";
      d.card.innerHTML = `<div class="chips"><span class="chip display">Icon display</span></div>`;
      d.card.appendChild(d.dev.el);
      placedIn.appendChild(d.card);
    } else {
      shelf.appendChild(d.dev.el);
    }
  }

  draw();
  return {
    get displays() { return list.map((d) => d.dev); },
    get full() { return list.length >= MAX_DISPLAYS; },
    add: () => { add(false); },

    async sync(g, stale) {
      game = g;
      shelf.classList.toggle("in-game", !!g);
      draw();
      if (!g) {
        for (const d of list.filter((x) => x.auto)) remove(d);
        for (const d of list) if (d.dev.ready) send(d.dev.mac, { type: "stop" });
        return;
      }
      if (!list.length) add(true);
      await Promise.all(list.map((d) => startOn(d, g, stale)));
    },

    async setIcons(slug, icons) {
      await Promise.all(list.map((d) => d.dev.setIcons(slug, icons)));
    },

    placeIn(el) {
      placedIn = el;
      for (const d of list) {
        d.card?.remove();
        d.card = null;
        place(d);
      }
    },
  };
}
