/**
 * <wand-sim> — embeddable wand game simulator (Pyodide + shadow DOM).
 *
 * Attributes/props: game, autostart, show-console, controls, source, muted
 * Events: sim-ready, sim-frame, sim-print, sim-error, sim-stopped
 */

import { createRenderer, dutyRgbToCss } from "./js/renderer.js";
import { getAccel, setTilt, setPose, fireMove, cancelMove } from "./js/motion.js";
import { createAudio } from "./js/audio.js";
import { createControls } from "./js/controls.js";

const PYODIDE_VERSION = "0.27.0";
const PYODIDE_CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

// Lucide icons (ISC license, https://lucide.dev), inlined so their
// stroke="currentColor" picks up .status's own text color per state
// (see the .status-* CSS rules below) instead of a separate asset per icon.
const LUCIDE_LOADER_CIRCLE = `<svg class="icon-lucide" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>`;
const LUCIDE_CIRCLE_CHECK = `<svg class="icon-lucide" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m16 9-5.5 5.5L8 12"/></svg>`;
const LUCIDE_CIRCLE_PLAY = `<svg class="icon-lucide" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 9.003a1 1 0 0 1 1.517-.859l4.997 2.997a1 1 0 0 1 0 1.718l-4.997 2.997A1 1 0 0 1 9 14.996z"/><circle cx="12" cy="12" r="10"/></svg>`;
const LUCIDE_CIRCLE_STOP = `<svg class="icon-lucide" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>`;
const LUCIDE_TRIANGLE_ALERT = `<svg class="icon-lucide" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`;

const STATUS_ICONS = {
  loading: LUCIDE_LOADER_CIRCLE,
  ready: LUCIDE_CIRCLE_CHECK,
  loaded: LUCIDE_CIRCLE_CHECK,
  running: LUCIDE_CIRCLE_PLAY,
  stopped: LUCIDE_CIRCLE_STOP,
  error: LUCIDE_TRIANGLE_ALERT,
};

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
.wand-art { width: var(--wand-art-width, 200px); }
/* Speaker fill fades rather than snapping (same reasoning as .ind below —
   a melody.py note is ~150ms). The LED matrix deliberately has no
   transition: game state (shake level, gesture training, ...) should
   update as crisply as the real LEDs would. */
.wand-art svg #_SPEAKER { transition: fill 0.4s ease-out; }
.indicators { display: flex; gap: 12px; }
/* Not buttons — just a live readout under the wand art, so no chip
   border/background, and sized like the pose/move gesture icons (64px)
   since these are the same kind of illustration, just smaller-scope.
   Fixed box, no active-state scale/transform: the icon swap alone
   (no_sound<->sound, no_vibrate<->vibrate) conveys state — anything that
   resizes or reflows the box reads as the same "wiggle" the label-width
   fix elsewhere in this file was written to avoid. */
.ind { display: inline-flex; align-items: center; }
/* Icon-only — no Hz/on-off text here; that's a technical detail a
   kindergarten-teacher audience doesn't need on the main panel (it's in
   the Advanced drawer instead, via setBuzzerStatus/setMotorStatus). */
.ind-icon { width: 64px; height: 64px; object-fit: contain; flex: none; }
/* Status line: icon + hover/title tooltip, no printed text — except for
   an error, which stays visible (never hover-only) so a real failure
   can't go unnoticed. */
.status { display: flex; align-items: center; gap: 6px; color: #8b859a; }
.status-loading .icon-lucide { animation: status-spin 1s linear infinite; }
.status-error { color: #b3261e; }
.status-text { font-size: 12px; font-weight: 700; }
@keyframes status-spin { to { transform: rotate(360deg); } }
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
/* Icon above label when a pose/move has a gesture illustration (see
   assets/wand/WandGestures/); icon-less ones (face_up/face_down, flip)
   just show centered text, same as before. */
.ctrl-btn.pose, .ctrl-btn.move { display: inline-flex; flex-direction: column; align-items: center; gap: 4px; font-size: 10px; }
.ctrl-icon { width: 64px; height: 64px; object-fit: contain; }
.ctrl-toolbar { display: flex; gap: 8px; margin-bottom: 4px; }
/* Icon-only toolbar buttons (mute): no visible label, hover/focus shows
   the native title tooltip instead — matches the icon-first, low-text
   design used throughout for a pre-reader audience. */
.ctrl-btn.icon-only { display: inline-flex; align-items: center; justify-content: center; padding: 7px; }
.icon-lucide { width: 18px; height: 18px; display: block; }
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
.adv-status { font-size: 12px; color: #8b859a; }
.adv-tags { display: flex; gap: 6px; align-items: center; }
.adv-tags input[type=text] {
  font: inherit; font-size: 12px; padding: 6px 10px; border-radius: 10px;
  border: 1.5px solid #e8e6f0; background: #ffffff; color: #231f2e; width: 100px;
}
.plunger { display: flex; align-items: center; gap: 8px; }
.ctrl-icon-inline { width: 28px; height: 28px; object-fit: contain; flex: none; }
/* Fixed width so the label text changing ("Gentle" -> "BIG shake!")
   never resizes the row and shifts the slider sideways. */
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

// Frequency -> color for the SPEAKER glow. Not melody-specific: melody.py,
// sound.py, and nfc_sound.py all share this exact table (vendor/lib/
// buzzer.py's NOTE_FREQ paired with vendor/lib/leds.py's RED/ORANGE/...).
// Games whose beeps aren't musical notes (jump, rainbow, ...) fall back to
// gold rather than a mismatched note color.
const NOTE_COLOR_HZ = [
  [262, [130, 0, 0]],     // RED
  [294, [120, 40, 0]],    // ORANGE
  [330, [110, 120, 0]],   // YELLOW
  [349, [0, 230, 0]],     // GREEN
  [392, [0, 20, 255]],    // BLUE
  [440, [50, 0, 250]],    // PURPLE
  [494, [200, 80, 120]],  // PINK
  [523, [140, 150, 150]], // WHITE
];
const SPEAKER_FALLBACK_RGB = [255, 210, 63]; // gold
const NOTE_MATCH_TOLERANCE_HZ = 15;

function speakerColorForFreq(freq) {
  let best = SPEAKER_FALLBACK_RGB;
  let bestDist = Infinity;
  for (const [hz, rgb] of NOTE_COLOR_HZ) {
    const d = Math.abs(hz - freq);
    if (d < bestDist) {
      bestDist = d;
      best = d <= NOTE_MATCH_TOLERANCE_HZ ? rgb : SPEAKER_FALLBACK_RGB;
    }
  }
  return dutyRgbToCss(best, 1);
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
      <div class="status" data-el="status"></div>
      <div class="main">
        <div>
          <div data-el="grid"></div>
          <div class="indicators">
            <span class="ind" data-el="buzzer" title="Buzzer"><img class="ind-icon" alt="Buzzer"></span>
            <span class="ind" data-el="motor" title="Motor"><img class="ind-icon" alt="Motor"></span>
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
    this._setStatus("loading", "Loading…");

    this._renderer = createRenderer(wrap.querySelector('[data-el="grid"]'), {
      svgUrl: assetUrl("assets/wand/WAND_FRONT.svg"),
    });
    this._audio = createAudio({
      buzzerEl: wrap.querySelector('[data-el="buzzer"]'),
      motorEl: wrap.querySelector('[data-el="motor"]'),
      // Fires well after boot (only once a real PWM/motor write happens),
      // so referencing this._controls here is safe even though controls
      // isn't created until a few lines below this.
      onBuzzerChange: (on, freq) => this._controls?.setBuzzerStatus(on ? `${freq} Hz` : "off"),
      onMotorChange: (on) => this._controls?.setMotorStatus(on ? "on" : "off"),
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

  /**
   * Icon-only status readout with the full text on hover/aria-label —
   * except "error", which stays visibly printed since a real failure
   * must surface loudly rather than wait on someone hovering over it.
   */
  _setStatus(kind, text) {
    this._statusEl.className = `status status-${kind}`;
    this._statusEl.title = text;
    this._statusEl.setAttribute("aria-label", text);
    this._statusEl.innerHTML = STATUS_ICONS[kind] || "";
    if (kind === "error") {
      const label = document.createElement("span");
      label.className = "status-text";
      label.textContent = text;
      this._statusEl.appendChild(label);
    }
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
      this._pyodide.globals.set("_js_pwm", (f, d) => {
        self._audio.setPwm(f, d);
        const freq = Number(f) || 0;
        const on = freq > 20 && (Number(d) || 0) > 0;
        self._renderer.setSpeakerColor(on ? speakerColorForFreq(freq) : null);
      });
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
      this._setStatus("ready", "Ready");
      this.dispatchEvent(new CustomEvent("sim-ready"));
      this._startMotionLoop();
      await this._loadAndMaybeStart();
    } catch (err) {
      console.error(err);
      this._setStatus("error", "Error: " + err.message);
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
    this._renderer.setButtonDown(!!down);
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
    this._setStatus("loading", "Loading game…");
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
    this._setStatus("loaded", `Loaded ${this._source ? "custom" : this.game}`);
    if (this.autostart) {
      await this.start();
    }
  }

  async start() {
    if (!this._ready) return;
    this._setStatus("running", "Running");
    this._consoleEl.textContent = "";
    await this._runPython("await start()");
  }

  async stop() {
    await this._runPython("await stop()");
    this._setStatus("stopped", "Stopped");
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
