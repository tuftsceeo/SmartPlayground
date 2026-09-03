/**
 * <wand-sim> — embeddable wand game simulator (Pyodide + shadow DOM).
 *
 * Attributes/props: game, autostart, show-console, controls, source, muted
 * Events: sim-ready, sim-frame, sim-print, sim-error, sim-stopped
 */

import { createRenderer } from "./js/renderer.js";
import { getAccel, setTilt, startShake, stopShake, setShakeIntensity, triggerJump, tick } from "./js/motion.js";
import { createAudio } from "./js/audio.js";
import { createControls } from "./js/controls.js";

const PYODIDE_VERSION = "0.27.0";
const PYODIDE_CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

const STYLE = `
:host {
  display: block;
  font-family: var(--wand-font, ui-sans-serif, system-ui, sans-serif);
  color: var(--wand-fg, #e8e8e8);
  background: var(--wand-bg, #12141a);
  border-radius: var(--wand-radius, 12px);
  padding: 12px;
  box-sizing: border-box;
}
.wrap { display: flex; flex-direction: column; gap: 12px; }
.main { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
.wand-led-grid {
  display: grid;
  grid-template-columns: repeat(5, var(--wand-led-size, 18px));
  gap: var(--wand-grid-gap, 6px);
  padding: 12px;
  background: var(--wand-grid-bg, #0a0c10);
  border-radius: 8px;
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
  padding: 4px 8px; border-radius: 6px;
  background: #1c2030; opacity: 0.55;
}
.ind.active { opacity: 1; background: #3a2a10; color: #ffd27a; }
.wand-controls { flex: 1; min-width: 220px; }
.ctrl-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; align-items: center; }
.ctrl-btn {
  font: inherit; font-size: 12px; padding: 6px 10px; border-radius: 6px;
  border: 1px solid #333; background: #1c2030; color: inherit; cursor: pointer;
}
.ctrl-btn.down, .ctrl-btn:active { background: #3a5080; }
.tilt-pad {
  position: relative; width: 100px; height: 100px;
  border-radius: 50%; background: #1c2030; border: 1px solid #333;
  touch-action: none;
}
.tilt-knob {
  position: absolute; width: 16px; height: 16px; margin: -8px 0 0 -8px;
  border-radius: 50%; background: #7eb6ff; left: 50%; top: 50%;
  pointer-events: none;
}
.nfc-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.console {
  font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
  background: #0a0c10; border-radius: 8px; padding: 8px;
  max-height: 160px; overflow: auto; white-space: pre-wrap;
}
.status { font-size: 12px; opacity: 0.7; }
label { font-size: 12px; display: flex; gap: 6px; align-items: center; }
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

  get showConsole() { return this.getAttribute("show-console") !== "false"; }
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
    if (!this._ready) return;
    if (name === "game" || name === "show-console") {
      if (name === "show-console") {
        this._consoleEl.style.display = this.showConsole ? "block" : "none";
      }
      if (name === "game") this._loadAndMaybeStart();
    }
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

    this._controls = createControls(wrap.querySelector('[data-el="controls"]'), {
      onButton: (down) => this._setButton(down),
      onJump: () => { triggerJump(); this._pushAccel(); },
      onTilt: (x, y) => { setTilt(x, y); this._pushAccel(); },
      onShake: (on, intensity) => {
        if (on) { setShakeIntensity(intensity); startShake(intensity); }
        else stopShake();
        this._pushAccel();
      },
      onMute: (m) => this._audio.setMuted(m),
      onBattery: (soc) => this._runPython(`sim_state.set_battery(soc=${soc})`),
      onLux: (lux) => this._runPython(`sim_state.set_ambient_lux(${lux})`),
      onNfc: (cmd) => this._runPython(`sim_state.tap_nfc(${JSON.stringify(cmd)})`),
      onEnow: (t) => this._runPython(`sim_state.enqueue_enow(${JSON.stringify(t)})`),
    });
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
from runtime import get_runtime, load_game, start, stop, get_commands
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
    this._runPython(`sim_state.set_button(${down ? "True" : "False"})`);
  }

  _pushAccel() {
    const a = getAccel();
    this._runPython(`sim_state.set_accel(${a.x}, ${a.y}, ${a.z})`);
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
    const src = this._source;
    if (src) {
      // Pass source via a Python global to avoid escaping nightmares.
      this._pyodide.globals.set("_game_source", src);
      await this._runPython("load_game(_game_source)");
    } else {
      const name = this.game.replace(/\.py$/, "");
      await this._runPython(`load_game(${JSON.stringify(name)})`);
    }
    const cmds = await this._pyodide.runPythonAsync("get_commands()");
    const list = cmds.toJs ? Array.from(cmds.toJs()) : Array.from(cmds || []);
    this._controls.setNfcTags(list);
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
}

customElements.define("wand-sim", WandSim);
export { WandSim };
