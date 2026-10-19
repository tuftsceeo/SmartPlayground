/**
 * Display panel for <sim-room>: the 16x16 icon display beside the wand.
 *
 * With a display file (the game's _icon.py) it boots a second Pyodide
 * running py/icon_host.py, which copies IconDisplay/main.py's idle loop and
 * runs the display game against a simulated Matrix. Frames come back as the
 * logical 768-byte src plus intensity and are drawn with iconmaker's
 * renderPreview(). The display sits on the room's bus with its own MAC, so
 * it hears the wand's broadcasts and its replies reach the wand.
 *
 * Without a display file it shows only the feed: every message the wand
 * transmits, decoded. The feed is shown in both modes.
 */

import { PYODIDE_CDN } from "../../wand-sim.js";
import { hexToBytes, bytesToHex } from "../radio.js";
import { loadPyodideNoJspi } from "../pyboot.js";

const PREVIEW_URL = "../../../BroadcastCode/ChatBroadcast/iconmaker/js/pipeline/preview.js";
const FEED_LIMIT = 60;
const W = 16;

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
.display-panel { display: flex; flex-direction: column; gap: 8px; }
.display-panel canvas { width: 192px; height: 192px; border-radius: 12px;
  background: #111; align-self: center; image-rendering: auto; }
.display-panel .display-status { font-size: 0.8rem; color: #8b859a; text-align: center; }
.display-panel .feed { font: 12px/1.35 ui-monospace, monospace; max-height: 160px;
  overflow-y: auto; background: #f7f7fb; border-radius: 8px; padding: 6px 8px;
  margin: 0; white-space: pre-wrap; word-break: break-all; }
.display-panel .feed:empty::before { content: "no messages yet"; color: #8b859a; }
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

export function createDisplayPanel({ bus, clock, mac, mount }) {
  const root = document.createElement("div");
  root.className = "display-panel";
  root.innerHTML = `
    <canvas data-el="display-canvas" hidden></canvas>
    <div class="display-status" data-el="display-status"></div>
    <pre class="feed" data-el="display-feed"></pre>`;
  mount.appendChild(root);
  const canvas = root.querySelector('[data-el="display-canvas"]');
  const statusEl = root.querySelector('[data-el="display-status"]');
  const feedEl = root.querySelector('[data-el="display-feed"]');

  let py = null;
  let host = null;
  let booting = null;
  let detach = null;
  let renderer = null;
  let frameCount = 0;
  let lastFrameHex = "";
  const printLog = [];

  function setStatus(text) {
    statusEl.textContent = text;
  }

  async function draw(srcHex, intensity) {
    lastFrameHex = srcHex;
    frameCount++;
    root.dataset.frames = String(frameCount);
    const bytes = hexToBytes(srcHex);
    const pixels = [];
    for (let i = 0; i < bytes.length; i += 3) pixels.push([bytes[i], bytes[i + 1], bytes[i + 2]]);
    if (!renderer) {
      try {
        const mod = await loadPreview();
        renderer = (px, inten) => mod.renderPreview(px, inten, canvas);
      } catch (err) {
        console.warn("display panel: renderPreview unavailable, drawing plain squares", err);
        renderer = (px, inten) => drawSquares(canvas, px, inten);
      }
    }
    // A later frame may have arrived while the renderer loaded.
    if (srcHex === lastFrameHex) renderer(pixels, Number(intensity));
  }

  async function boot() {
    if (booting) return booting;
    booting = (async () => {
      setStatus("starting the display…");
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
        draw(String(hex), inten).catch((err) => console.error("display panel draw failed", err));
      });
      py.globals.set("_disp_print", (line) => {
        printLog.push(String(line));
        if (printLog.length > 400) printLog.splice(0, printLog.length - 400);
        root.dispatchEvent(new CustomEvent("display-print", { detail: { text: String(line) }, bubbles: true, composed: true }));
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
      canvas.hidden = false;
      setStatus("display ready");
      root.dataset.ready = "1";
    })();
    try {
      await booting;
    } catch (err) {
      booting = null;
      setStatus(`display failed to start: ${err.message || err}`);
      root.dataset.error = String(err.message || err);
      throw err;
    }
    return booting;
  }

  return {
    root,
    get ready() { return root.dataset.ready === "1"; },
    get lastFrameHex() { return lastFrameHex; },
    get prints() { return printLog.slice(); },
    boot,

    /** Install the display game and its icons ({name: file text | duty[768]}). */
    async setGame(slug, src, icons = {}) {
      await boot();
      py.globals.set("_disp_slug", slug);
      py.globals.set("_disp_src", src);
      py.globals.set("_disp_icons", py.toPy(icons));
      await py.runPythonAsync("_host.set_game(_disp_slug, _disp_src)\n_host.set_icons(_disp_slug, _disp_icons)");
    },

    /** Rewrite a game's icons; the next draw reads the new files. */
    async setIcons(slug, icons) {
      await boot();
      py.globals.set("_disp_slug", slug);
      py.globals.set("_disp_icons", py.toPy(icons));
      await py.runPythonAsync("_host.set_icons(_disp_slug, _disp_icons)");
    },

    /** Show or hide the panel's drawn display (the feed always shows). */
    setDisplayMode(on) {
      canvas.hidden = !on || !this.ready;
      if (!on) setStatus("no display file: showing the wand's messages");
    },

    pushFeed(line) {
      const at = (clock.nowMs() / 1000).toFixed(1);
      feedEl.textContent += `${at}s  ${line}\n`;
      const lines = feedEl.textContent.split("\n");
      if (lines.length > FEED_LIMIT + 1) feedEl.textContent = lines.slice(-FEED_LIMIT - 1).join("\n");
      feedEl.scrollTop = feedEl.scrollHeight;
    },

    clearFeed() { feedEl.textContent = ""; },

    async destroy() {
      if (detach) detach();
      if (py && host) await py.runPythonAsync("await _host.stop()");
      root.remove();
    },
  };
}
