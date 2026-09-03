/**
 * <wand-sim> — embeddable wand game simulator (Pyodide + shadow DOM).
 *
 * Attributes/props: game, autostart, show-console, controls, source, muted
 * Events: sim-ready, sim-frame, sim-print, sim-error, sim-stopped
 */

import { createRenderer } from "./js/renderer.js";
import { getAccel, setTilt, setPose, fireMove, cancelMove } from "./js/motion.js";
import { createAudio } from "./js/audio.js";
import { createControls } from "./js/controls.js";

const PYODIDE_VERSION = "0.27.0";
const PYODIDE_CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

// Palette matches Bag3/Code/BroadcastBox/ChatBroadcast/css/app.css's :root
// tokens and its existing #wand-sim / .sim-* rules (teal=tilt, purple=shake,
// gold=speaker glow, the chat.css .msg.hw teal tint+border+text recipe) —
// this is a color-and-type starting point only. The LED grid and console
// stay dark ("screen"/"terminal" look reads fine on either theme); layout
// and the actual wand-artwork compositing are a separate pass.
const STYLE = `
:host {
  display: block;
  font-family: var(--wand-font, 'Nunito', ui-sans-serif, system-ui, sans-serif);
  color: var(--wand-fg, #231f2e);
  background: var(--wand-bg, #ffffff);
  border-radius: var(--wand-radius, 22px);
  padding: 16px;
  box-shadow: var(--wand-shadow, 0 18px 40px rgba(108, 76, 209, 0.16));
  box-sizing: border-box;
}
/* :host's box-sizing doesn't inherit into the shadow tree (box-sizing
   isn't an inherited property), so every bordered element below sized it
   as content-box by default — a border added to, rather than ate into,
   its declared width/height. That's what threw off the plunger handle's
   vertical centering against its track. */
*, *::before, *::after { box-sizing: border-box; }
.wrap { display: flex; flex-direction: column; gap: 12px; }
.main { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
.wand-led-grid {
  display: grid;
  grid-template-columns: repeat(5, var(--wand-led-size, 18px));
  gap: var(--wand-grid-gap, 6px);
  padding: 12px;
  background: var(--wand-grid-bg, #0a0c10);
  border-radius: 12px;
  width: max-content;
}
.wand-led-cell {
  width: var(--wand-led-size, 18px);
  height: var(--wand-led-size, 18px);
  border-radius: var(--wand-led-radius, 4px);
  background: var(--wand-led-off, #1a1a1a);
}
.indicators { display: flex; gap: 8px; font-size: 12px; }
.ind {
  padding: 4px 10px; border-radius: 10px;
  background: #f4f2fa; color: #8b859a; font-weight: 700;
  /* A short beep (melody.py's notes are ~150ms) would otherwise snap on
     then instantly off — transitioning the color lets it read as a fade
     rather than a flash even without holding the "active" state longer. */
  transition: background 0.5s ease-out, color 0.5s ease-out;
}
.ind.active { background: #fff8e0; color: #a8531e; transition-duration: 0.05s; }
.wand-controls { flex: 1; min-width: 220px; }
.ctrl-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; align-items: center; }
.ctrl-btn {
  font: 700 12px 'Nunito', inherit; padding: 7px 12px; border-radius: 12px;
  border: 1.5px solid #e8e6f0; background: #ffffff; color: #231f2e; cursor: pointer;
}
.ctrl-btn:hover { border-color: #6c4cd1; color: #6c4cd1; }
.ctrl-btn.down, .ctrl-btn:active { background: #f2eefc; border-color: #6c4cd1; color: #6c4cd1; }
.ctrl-btn.big {
  font-size: 14px; padding: 14px 24px; border-radius: 16px;
  background: #ef4d92; border-color: #d13a7c; color: #fff;
}
.ctrl-btn.big:hover { color: #fff; }
.ctrl-btn.big.down, .ctrl-btn.big:active { background: #d13a7c; border-color: #d13a7c; color: #fff; }
/* Sticky-pose active state: soft tint + saturated same-hue border + dark
   same-hue text — same recipe ChatBroadcast's chat.css uses for .msg.hw. */
.ctrl-btn.pose.active { background: #d1fae5; border-color: #6ee7b7; color: #065f46; }
.ctrl-toolbar { display: flex; gap: 8px; margin-bottom: 4px; }
.hint { font-size: 13px; opacity: 0.85; margin: 2px 0; }
.hint[hidden], .uses-row[hidden], .zero-state[hidden] { display: none; }
.uses-row { font-size: 11px; color: #8b859a; margin-bottom: 6px; }
.ctrl-group { margin-bottom: 10px; }
.ctrl-group[hidden] { display: none; }
.group-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; color: #8b859a; margin-bottom: 4px; }
.group-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.zero-state { font-size: 13px; color: #8b859a; font-style: italic; padding: 8px 0; }
details.advanced { margin-top: 8px; border-top: 2px solid #ffd23f; padding-top: 8px; }
details.advanced summary { cursor: pointer; font-size: 12px; font-weight: 700; color: #8b859a; }
details.advanced summary:hover { color: #a8531e; }
.adv-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 8px; }
.adv-tags { display: flex; gap: 6px; align-items: center; }
.adv-tags input[type=text] {
  font: inherit; font-size: 12px; padding: 6px 10px; border-radius: 10px;
  border: 1.5px solid #e8e6f0; background: #ffffff; color: #231f2e; width: 100px;
}
.plunger { display: flex; align-items: center; gap: 10px; }
.plunger-track {
  position: relative; height: 34px; border-radius: 17px;
  background: #f4f2fa; border: 1.5px solid #e8e6f0; touch-action: none;
  overflow: hidden; cursor: grab; flex: none;
}
.plunger-fill {
  position: absolute; left: 0; top: 0; height: 100%;
  background: linear-gradient(90deg, #ddd0f7, #6c4cd1);
}
.plunger-handle {
  /* top:50% + margin-top:-half-height centers it regardless of the
     track's own box model (a hardcoded top offset had to assume a
     border width, which is exactly what was throwing it off). */
  position: absolute; top: 50%; margin-top: -14px; width: 28px; height: 28px;
  border-radius: 50%; background: #6c4cd1; border: 2px solid #5638a8;
  box-shadow: 0 2px 4px rgba(108, 76, 209, 0.35);
}
/* Fixed width so the label text changing ("Gentle" -> "BIG shake!")
   never resizes the row and shifts the track sideways. */
.plunger-label { font-size: 12px; color: #8b859a; flex: none; }
.tilt-pad {
  position: relative; width: 100px; height: 100px;
  border-radius: 50%; background: #f4f2fa; border: 1.5px solid #e8e6f0;
  touch-action: none;
}
.tilt-knob {
  position: absolute; width: 16px; height: 16px; margin: -8px 0 0 -8px;
  border-radius: 50%; background: #6c4cd1; left: 50%; top: 50%;
  pointer-events: none;
}
.nfc-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.console {
  font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
  background: #1f2430; color: #d7d7e0; border-radius: 12px; padding: 10px;
  max-height: 160px; overflow: auto; white-space: pre-wrap;
  border: 1px solid #e8e6f0;
}
.status { font-size: 12px; color: #8b859a; font-weight: 700; }
label { font-size: 12px; display: flex; gap: 6px; align-items: center; color: #8b859a; }
input[type=range] { width: 100px; }
`;

function assetUrl(rel) {
  return new URL(rel, import.meta.url).href;
}

async function fetchText(rel) {
  const res = await fetch(assetUrl(rel));
  if (!res.ok) throw new Error(`fetch ${rel}: ${res.status}`);
  return res.text();
}

const FILE_LIST = [
  "py/transform.py",
  "py/runtime.py",
  "py/shims/sim_state.py",
  "py/shims/machine.py",
  "py/shims/neopixel.py",
  "py/shims/_thread.py",
  "py/shims/network.py",
  "py/shims/espnow.py",
  "py/shims/ubluetooth.py",
  "py/shims/micropython.py",
  "py/shims/time_patch.py",
  "py/devices/lis2dw12.py",
  "py/devices/max17048.py",
  "py/devices/opt3002.py",
  "py/devices/pn532.py",
  "py/devices/nfc_reader.py",
  "py/devices/espnow_manager.py",
  "vendor/hubtype.txt",
  "vendor/lib/brightness.py",
  "vendor/lib/hubtype.py",
  "vendor/lib/leds.py",
  "vendor/lib/buzzer.py",
  "vendor/lib/game_tags.py",
  "vendor/lib/actions.py",
  "vendor/lib/battery.py",
  "vendor/games/jump.py",
  "vendor/games/shake.py",
  "vendor/games/shake_rainbow.py",
  "vendor/games/sound.py",
  "vendor/games/rainbow.py",
  "vendor/games/jumpin.py",
  "vendor/games/nfc_sound.py",
  "vendor/games/gestures.py",
  "vendor/games/simpleicecream.py",
  "vendor/games/melody.py",
  "vendor/games/cooking.py",
  "vendor/games/multiicecream.py",
];

class WandSim extends HTMLElement {
  static get observedAttributes() {
    return ["game", "autostart", "show-console", "controls"];
  }

  constructor() {
    super();
    this._root = this.attachShadow({ mode: "open" });
    this._pyodide = null;
    this._ready = false;
    this._source = null;
    this._raf = 0;
    this._audio = null;
    this._renderer = null;
    this._controls = null;
  }

  get game() { return this.getAttribute("game") || "jump"; }
  set game(v) { this.setAttribute("game", v); }

  get autostart() { return this.hasAttribute("autostart"); }
  set autostart(v) { v ? this.setAttribute("autostart", "") : this.removeAttribute("autostart"); }

  // Hidden by default — a teacher-facing panel shouldn't open on a wall of
  // Python traceback text. The controls' "Show console" toggle flips this.
  get showConsole() { return this.getAttribute("show-console") === "true"; }
  set showConsole(v) { this.setAttribute("show-console", v ? "true" : "false"); }

  get muted() { return this._audio ? this._audio.isMuted() : false; }
  set muted(v) {
    this._audio?.setMuted(!!v);
    this._controls?.setMuted(!!v);
  }

  get source() { return this._source; }
  set source(v) {
    this._source = v;
    if (this._ready) this._loadAndMaybeStart();
  }

  connectedCallback() {
    this._renderShell();
    this._boot();
  }

  disconnectedCallback() {
    cancelAnimationFrame(this._raf);
    this._audio?.dispose();
    this._runPython("await stop()").catch(() => {});
  }

  attributeChangedCallback(name) {
    if (name === "show-console") {
      if (this._consoleEl) this._consoleEl.style.display = this.showConsole ? "block" : "none";
      this._controls?.setConsoleShown(this.showConsole);
    }
    if (!this._ready) return;
    if (name === "game") this._loadAndMaybeStart();
  }

  _renderShell() {
    this._root.innerHTML = "";
    const style = document.createElement("style");
    style.textContent = STYLE;
    this._root.appendChild(style);

    const wrap = document.createElement("div");
    wrap.className = "wrap";
    wrap.innerHTML = `
      <div class="status" data-el="status">Loading Pyodide…</div>
      <div class="main">
        <div>
          <div data-el="grid"></div>
          <div class="indicators">
            <span class="ind" data-el="buzzer">buzzer</span>
            <span class="ind" data-el="motor">motor</span>
          </div>
        </div>
        <div data-el="controls"></div>
      </div>
      <div class="console" data-el="console"></div>
    `;
    this._root.appendChild(wrap);

    this._statusEl = wrap.querySelector('[data-el="status"]');
    this._consoleEl = wrap.querySelector('[data-el="console"]');
    this._consoleEl.style.display = this.showConsole ? "block" : "none";

    this._renderer = createRenderer(wrap.querySelector('[data-el="grid"]'));
    this._audio = createAudio({
      buzzerEl: wrap.querySelector('[data-el="buzzer"]'),
      motorEl: wrap.querySelector('[data-el="motor"]'),
    });
    // Unlock audio directly from a real pointer event — see unlock()'s
    // docstring in audio.js for why this can't just happen from setPwm().
    wrap.addEventListener("pointerdown", () => this._audio.unlock());

    this._controls = createControls(wrap.querySelector('[data-el="controls"]'), {
      onButton: (down) => this._setButton(down),
      onPose: (name) => { setPose(name); this._pushAccel(); },
      onMove: (kind, opts) => { fireMove(kind, opts); this._pushAccel(); },
      onTilt: (x, y) => { setTilt(x, y); this._pushAccel(); },
      onMute: (m) => this._audio.setMuted(m),
      onToggleConsole: (shown) => { this.showConsole = shown; },
      onBattery: (soc) => this._runPython(`sim_state.set_battery(soc=${soc})`),
      onLux: (lux) => this._runPython(`sim_state.set_ambient_lux(${lux})`),
      onNfc: (cmd) => this._runPython(`sim_state.tap_nfc(${JSON.stringify(cmd)})`),
      onEnow: (t) => this._runPython(`sim_state.enqueue_enow(${JSON.stringify(t)})`),
    });
    this._controls.setConsoleShown(this.showConsole);
  }

  async _boot() {
    try {
      await this._loadPyodide();
      const contents = {};
      await Promise.all(FILE_LIST.map(async (rel) => {
        contents[rel] = await fetchText(rel);
      }));

      // Write sources into Pyodide FS and bootstrap runtime.
      this._pyodide.FS.mkdirTree("/sim");
      for (const [rel, text] of Object.entries(contents)) {
        const path = "/sim/" + rel;
        const dir = path.slice(0, path.lastIndexOf("/"));
        this._pyodide.FS.mkdirTree(dir);
        this._pyodide.FS.writeFile(path, text);
      }

      await this._pyodide.runPythonAsync(`
import sys
sys.path.insert(0, "/sim/py")
sys.path.insert(0, "/sim/py/shims")
sys.path.insert(0, "/sim/py/devices")
from runtime import get_runtime, load_game, start, stop, get_commands, get_capabilities
import os
contents = {}
for root, dirs, files in os.walk("/sim"):
    for f in files:
        p = os.path.join(root, f)
        rel = p[len("/sim/"):]
        with open(p) as fh:
            contents[rel] = fh.read()
rt = get_runtime()
rt.bootstrap(file_contents=contents, workdir="/sim/vendor")
`);

      // Wire JS callbacks into sim_state
      const self = this;
      this._pyodide.globals.set("_js_led", (pixels) => {
        const arr = pixels.toJs ? pixels.toJs() : pixels;
        const flat = Array.from(arr).map((p) => {
          const t = p.toJs ? p.toJs() : p;
          return [t[0] | 0, t[1] | 0, t[2] | 0];
        });
        self._renderer.applyFrame(flat);
        self.dispatchEvent(new CustomEvent("sim-frame", { detail: { pixels: flat } }));
      });
      this._pyodide.globals.set("_js_pwm", (f, d) => self._audio.setPwm(f, d));
      this._pyodide.globals.set("_js_motor", (on) => self._audio.setMotor(!!on));
      this._pyodide.globals.set("_js_print", (t) => {
        const line = String(t);
        self._consoleEl.textContent += line + "\n";
        self._consoleEl.scrollTop = self._consoleEl.scrollHeight;
        self.dispatchEvent(new CustomEvent("sim-print", { detail: { text: line } }));
      });
      this._pyodide.globals.set("_js_log", (t) => {
        self.dispatchEvent(new CustomEvent("sim-error", { detail: { message: String(t) } }));
      });

      await this._pyodide.runPythonAsync(`
import sim_state
sim_state.set_led_callback(_js_led)
sim_state.set_pwm_callback(_js_pwm)
sim_state.set_motor_callback(_js_motor)
sim_state.set_print_callback(_js_print)
sim_state.set_log_callback(_js_log)
`);
      // Held once so per-frame accel/button pushes call methods directly
      // instead of recompiling a Python source string every tick.
      this._sim = this._pyodide.pyimport("sim_state");

      this._ready = true;
      this._statusEl.textContent = "Ready";
      this.dispatchEvent(new CustomEvent("sim-ready"));
      this._startMotionLoop();
      await this._loadAndMaybeStart();
    } catch (err) {
      console.error(err);
      this._statusEl.textContent = "Error: " + err.message;
      this.dispatchEvent(new CustomEvent("sim-error", { detail: { message: String(err) } }));
    }
  }

  async _loadPyodide() {
    if (!window.loadPyodide) {
      await new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = PYODIDE_CDN + "pyodide.js";
        s.onload = resolve;
        s.onerror = () => reject(new Error("Failed to load pyodide.js"));
        document.head.appendChild(s);
      });
    }
    this._pyodide = await window.loadPyodide({ indexURL: PYODIDE_CDN });
  }

  async _runPython(code) {
    if (!this._pyodide) return;
    return this._pyodide.runPythonAsync(code);
  }

  _setButton(down) {
    if (this._sim) this._sim.set_button(!!down);
  }

  _pushAccel() {
    if (!this._sim) return;
    const a = getAccel();
    this._sim.set_accel(a.x, a.y, a.z);
  }

  _startMotionLoop() {
    const loop = () => {
      if (this._ready) this._pushAccel();
      this._raf = requestAnimationFrame(loop);
    };
    this._raf = requestAnimationFrame(loop);
  }

  async _loadAndMaybeStart() {
    if (!this._ready) return;
    this._statusEl.textContent = "Loading game…";
    await this._runPython("await stop()");

    // A freshly-picked-up wand starts at rest; don't carry a pose or an
    // in-flight gesture over from whatever the previous game left it in.
    cancelMove();
    setPose("tip_up");
    this._controls.resetPose();
    this._pushAccel();

    const src = this._source;
    if (src) {
      // Pass source via a Python global to avoid escaping nightmares.
      this._pyodide.globals.set("_game_source", src);
      await this._runPython("load_game(_game_source)");
    } else {
      const name = this.game.replace(/\.py$/, "");
      await this._runPython(`load_game(${JSON.stringify(name)})`);
    }
    const caps = await this._pyodide.runPythonAsync("get_capabilities()");
    this._controls.setCapabilities(caps.toJs ? caps.toJs({ dict_converter: Object.fromEntries }) : caps);
    this._statusEl.textContent = `Loaded ${this._source ? "custom" : this.game}`;
    if (this.autostart) {
      await this.start();
    }
  }

  async start() {
    if (!this._ready) return;
    this._statusEl.textContent = "Running…";
    this._consoleEl.textContent = "";
    await this._runPython("await start()");
  }

  async stop() {
    await this._runPython("await stop()");
    this._statusEl.textContent = "Stopped";
    this.dispatchEvent(new CustomEvent("sim-stopped"));
  }

  /** Stop and restart the currently loaded game fresh (same game, new
   * instance state) — the "start over" affordance for the host page. */
  async restart() {
    if (!this._ready) return;
    await this.stop();
    cancelMove();
    setPose("tip_up");
    this._controls.resetPose();
    this._pushAccel();
    await this.start();
  }
}

customElements.define("wand-sim", WandSim);
export { WandSim };
