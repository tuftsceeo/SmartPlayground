/**
 * <wand-sim> — embeddable wand game simulator (Pyodide + shadow DOM).
 *
 * The panel follows the "Wand Simulator v4" design artboard
 * (BroadcastBox/docs_and_design/simlution v4/): a white rounded shell
 * holding the wand on its tilt/press pad at the left and the controls at
 * the right, with four pop-ups available over the whole shell.
 *
 * Attributes/props: game, autostart, show-console, controls, source, muted,
 * advanced (shows the axis readout, the custom tag / radio message drawer,
 * the hardware dials and the log; off by default), log-lines (how many log
 * lines the advanced block shows, default 2)
 *
 * Events:
 *   sim-ready, sim-frame, sim-print, sim-stopped
 *   sim-error — detail.phase is one of "boot" / "load" / "run"
 *   sim-overlay-action — detail is { kind, action }, fired when a button on
 *     one of the overlays is pressed (see showOverlay below)
 *   sim-enow-sent — detail is { kind, data, mac }, fired when the running
 *     game transmits over ESP-NOW. The simulator has no second wand, so
 *     this (and the panel's radio readout) is a send's only output.
 */

import { createRenderer, dutyRgbToCss, WAND_STYLE } from "./js/renderer.js";
import { getAccel, setPadTilt, setPose, fireMove, cancelMove } from "./js/motion.js";
import { createAudio } from "./js/audio.js";
import { createControls, CONTROLS_STYLE } from "./js/controls.js";
import { icon } from "./js/icons.js";

const PYODIDE_VERSION = "0.27.0";
const PYODIDE_CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

/**
 * The four pop-ups from the "Wand Sim Overlays" artboard. `banner` ones sit
 * at the bottom of the shell with no scrim; the rest are centred cards over
 * a scrim. Copy is the artboard's, verbatim.
 */
const OVERLAYS = {
  "game-over": {
    icon: "tag", tintBg: "#fff0f6", tintFg: "#d13a7c",
    title: "Game over", message: "the stop card ended the round",
    buttons: [
      { action: "close", label: "Close", style: "ghost" },
      { action: "play-again", label: "Play again →", style: "pink" },
    ],
  },
  "cant-simulate": {
    icon: "smartphone-nfc", tintBg: "#f2eefc", tintFg: "#6c4cd1",
    title: "Can't simulate", message: "it needs two wands talking — try it on the wand",
    buttons: [
      { action: "close", label: "Got it", style: "ghost" },
      { action: "send-to-box", label: "Send to Box →", style: "teal" },
    ],
  },
  welcome: {
    icon: "wand", tintBg: "#fff8e0", tintFg: "#8a6a00",
    title: "Welcome", message: "chat an idea, or load a saved game",
    buttons: [
      { action: "load-saved", label: "Load saved code", style: "ghost" },
      { action: "start-chat", label: "Start a chat →", style: "pink" },
    ],
  },
  "new-code": {
    banner: true,
    icon: "sparkles", tintBg: "#e9fbf6", tintFg: "#12967f",
    title: "New code is ready", message: "play it to see the change",
    buttons: [{ action: "play-it", label: "Play it →", style: "pink" }],
  },
};

const SHELL_STYLE = `
:host {
  /* Flex column so .wrap can stretch and hand the pad a height to fill —
     the pad is the panel's tallest element and has nothing else to size
     against. min-height keeps the two-pane layout from collapsing when the
     host gives the element no height of its own. */
  display: flex;
  flex-direction: column;
  min-height: var(--wand-min-height, 520px);
  container-type: inline-size;
  container-name: wand-sim;
  font-family: var(--wand-font, 'Nunito', ui-sans-serif, system-ui, sans-serif);
  color: var(--wand-fg, #231f2e);
  background: var(--wand-bg, #ffffff);
  border-radius: var(--wand-radius, 24px);
  box-shadow: var(--wand-shadow, 0 18px 40px rgba(108, 76, 209, 0.18));
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
}
/* :host's box-sizing doesn't inherit into the shadow tree (box-sizing
   isn't an inherited property), so every bordered element below would size
   as content-box by default — a border adding to, rather than eating into,
   its declared width. */
*, *::before, *::after { box-sizing: border-box; }

.wrap { flex: 1; display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.console {
  font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
  background: #1f2430; color: #d7d7e0; border-radius: 12px; padding: 10px;
  margin: 0 16px 14px; max-height: 160px; overflow: auto; white-space: pre-wrap;
}

/* ── Overlays ────────────────────────────────────────────────────────── */
.ov-scrim {
  position: absolute; inset: 0; z-index: 8;
  background: rgba(35,31,46,.35);
}
.ov-card {
  position: absolute; left: 24px; right: 24px; top: 50%;
  transform: translateY(-50%); z-index: 9; background: #fff;
  border-radius: 20px; box-shadow: 0 24px 60px rgba(0,0,0,.22);
  padding: 22px; display: flex; flex-direction: column; gap: 12px;
  animation: ov-pop .15s ease;
}
.ov-card.is-banner {
  top: auto; bottom: 22px; transform: none; border: 1.5px solid #e8e6f0;
  padding: 16px 18px; flex-direction: row; align-items: center; gap: 12px;
}
.ov-head { display: flex; align-items: center; gap: 10px; }
.ov-tint {
  display: flex; width: 64px; height: 64px; flex: none; border-radius: 18px;
  align-items: center; justify-content: center;
}
.is-banner .ov-tint { width: 52px; height: 52px; border-radius: 16px; }
.ov-copy { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.ov-title { font: 900 24px 'Nunito', system-ui, sans-serif; color: #231f2e; line-height: 1.1; }
.ov-sub { font: 400 15px 'Patrick Hand', 'Nunito', system-ui, sans-serif; color: #8b859a; line-height: 1.2; }
.is-banner .ov-head { flex: 1; min-width: 0; }
.is-banner .ov-title { font: 800 14px 'Nunito', system-ui, sans-serif; text-wrap: pretty; }
.is-banner .ov-sub { font-size: 13px; }
.ov-actions { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; }
.is-banner .ov-actions { flex: none; }
.ov-btn {
  padding: 10px 15px; border-radius: 14px; cursor: pointer;
  font: 800 12px 'Nunito', system-ui, sans-serif; border: none;
  transition: all .15s;
}
.is-banner .ov-btn { padding: 9px 14px; font-size: 11.5px; }
.ov-btn.ghost { border: 1.5px solid #e8e6f0; background: #fff; color: #5b5468; }
.ov-btn.ghost:hover { border-color: #ef4d92; color: #d13a7c; background: #fff0f6; }
.ov-btn.pink {
  background: linear-gradient(135deg, #ef4d92, #d13a7c); color: #fff;
  box-shadow: 0 10px 22px rgba(239,77,146,.35);
}
.ov-btn.teal { background: linear-gradient(135deg, #22c3a6, #12967f); color: #fff; }
@keyframes ov-pop { 0% { opacity: 0; transform: scale(.94) } 100% { opacity: 1 } }
.ov-card.is-banner { animation-name: ov-pop-banner; }
@keyframes ov-pop-banner { 0% { opacity: 0; transform: scale(.94) } 100% { opacity: 1; transform: none } }
@media (prefers-reduced-motion: reduce) {
  .ov-card { animation: none; }
}
`;

const STYLE = SHELL_STYLE + WAND_STYLE + CONTROLS_STYLE;

/**
 * A Python bytes literal for `str`, hex-escaped throughout so nothing in
 * the text can terminate the literal or be re-interpreted as an escape.
 * ESP-NOW payloads are compared as bytes on the wire (freeze_dance.py's
 * MSG_GO is `b"FD_GO"`), so a str would never compare equal.
 */
function pyBytes(str) {
  let out = 'b"';
  for (const ch of String(str)) {
    for (const byte of new TextEncoder().encode(ch)) {
      out += "\\x" + byte.toString(16).padStart(2, "0");
    }
  }
  return out + '"';
}

function assetUrl(rel) {
  return new URL(rel, import.meta.url).href;
}

/**
 * The ~38 Python files below are one unit with this file: the bootstrap
 * calls sim_state functions by name, so a stale copy of any of them breaks
 * boot outright (an old sim_state.py against a new wand-sim.js raises
 * `no attribute 'set_error_callback'`). A plain static server sends no
 * Cache-Control, which leaves the browser free to heuristically cache the
 * .py files while revalidating this module — exactly that skew. "no-cache"
 * forces revalidation; it still takes a 304, so it stays cheap.
 */
async function fetchText(rel) {
  const res = await fetch(assetUrl(rel), { cache: "no-cache" });
  if (!res.ok) throw new Error(`fetch ${rel}: ${res.status}`);
  return res.text();
}

// Frequency -> color for the speaker. Not melody-specific: melody.py,
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

// How often the advanced axis readout is refreshed. The motion loop itself
// runs every frame (the Python side needs that); redrawing three bars at
// 60Hz is just churn.
const AXIS_REFRESH_MS = 100;

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
  "vendor/games/freeze_dance.py",
];

class WandSim extends HTMLElement {
  static get observedAttributes() {
    return ["game", "autostart", "show-console", "controls", "advanced", "log-lines"];
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
    this._log = [];
    this._lastAxisPush = 0;
    this._openOverlay = null;
  }

  get game() { return this.getAttribute("game") || "jump"; }
  set game(v) { this.setAttribute("game", v); }

  get autostart() { return this.hasAttribute("autostart"); }
  set autostart(v) { v ? this.setAttribute("autostart", "") : this.removeAttribute("autostart"); }

  // Gates the axis readout, the custom tag / radio message drawer, the
  // hardware dials and the log — off by default so a teacher-facing embed
  // doesn't show technical dials unless the host app opts in.
  get advanced() { return this.hasAttribute("advanced"); }
  set advanced(v) { v ? this.setAttribute("advanced", "") : this.removeAttribute("advanced"); }

  get logLines() {
    const n = parseInt(this.getAttribute("log-lines"), 10);
    return n > 0 ? n : 2;
  }
  set logLines(v) { this.setAttribute("log-lines", String(v)); }

  // Hidden by default — a teacher-facing panel shouldn't open on a wall of
  // Python traceback text. The advanced block's "Show console" toggle
  // flips this.
  get showConsole() { return this.getAttribute("show-console") === "true"; }
  set showConsole(v) { this.setAttribute("show-console", v ? "true" : "false"); }

  get muted() { return this._audio ? this._audio.isMuted() : false; }
  set muted(v) {
    this._audio?.setMuted(!!v);
    this._controls?.setMuted(!!v);
  }

  /** Per-game teacher copy (button kind / motion vocabulary / hint) for
   * a game loaded from `source`. py/runtime.py's _TEACHER_TABLE is keyed
   * by vendored module name, so source-loaded code always falls back to
   * "show every control" — which is why a custom melody.py shows the whole
   * pose-and-move wall instead of just its note tags. A host that knows
   * what its own example needs supplies that here; the tag list and
   * battery flag still come from the loaded module itself.
   * Shape: { button: "tap"|"hold"|"none", motion: [...], hint: "" } */
  get profile() { return this._profile; }
  set profile(v) {
    this._profile = v || null;
    if (this._ready) this._applyCapabilities();
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
    this._renderer?.dispose();
    this._controls?.dispose();
    this._runPython("await stop()").catch(() => {});
  }

  attributeChangedCallback(name) {
    if (name === "show-console") {
      if (this._consoleEl) this._consoleEl.style.display = this.showConsole ? "block" : "none";
      this._controls?.setConsoleShown(this.showConsole);
    }
    if (name === "advanced") this._controls?.setAdvanced(this.advanced);
    if (name === "log-lines") this._controls?.setLog(this._log, this.logLines);
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
      <div data-el="controls"></div>
      <div class="console" data-el="console"></div>
    `;
    this._root.appendChild(wrap);

    this._consoleEl = wrap.querySelector('[data-el="console"]');
    this._consoleEl.style.display = this.showConsole ? "block" : "none";

    this._audio = createAudio({
      // Fires well after boot (only once a real PWM/motor write happens),
      // so referencing this._controls here is safe even though controls
      // isn't created until a few lines below this.
      onBuzzerChange: (on, freq) => this._controls?.setBuzzerStatus(on ? `${freq} Hz` : "off"),
      onMotorChange: (on) => {
        this._controls?.setMotorStatus(on ? "on" : "off");
        this._renderer?.setMotor(on);
      },
    });
    // Unlock audio directly from a real pointer event — see unlock()'s
    // docstring in audio.js for why this can't just happen from setPwm().
    wrap.addEventListener("pointerdown", () => this._audio.unlock());

    this._controls = createControls(wrap.querySelector('[data-el="controls"]'), {
      onButton: (down) => this._setButton(down),
      onPose: (name) => { setPose(name); this._pushAccel(); },
      onMove: (kind, opts) => {
        const ms = fireMove(kind, opts);
        this._renderer.playGesture(kind, ms);
        this._pushAccel();
      },
      onTilt: (x, y) => {
        setPadTilt(x, y);
        this._renderer.setTilt3d(x * 100, y * 100);
        this._pushAccel();
      },
      onFaceFlip: (down, pose) => {
        setPose(pose);
        this._renderer.setFaceDown(down);
        this._renderer.playGesture("faceflip", 620);
        this._pushAccel();
      },
      onMute: (m) => this._audio.setMuted(m),
      onRestart: () => this.restart(),
      onToggleAdvanced: (on) => { this.advanced = on; },
      onToggleConsole: (shown) => { this.showConsole = shown; },
      onBattery: (soc) => this._runPython(`sim_state.set_battery(soc=${soc})`),
      onLux: (lux) => this._runPython(`sim_state.set_ambient_lux(${lux})`),
      onNfc: (cmd) => {
        this._logLine(`tag "${cmd}"`);
        this._runPython(`sim_state.tap_nfc(${JSON.stringify(cmd)})`);
      },
      onEnow: (msgType, data) => {
        this._logLine(data ? `heard ${msgType} "${data}"` : `heard "${msgType}"`);
        const args = data == null
          ? JSON.stringify(msgType)
          : `${JSON.stringify(msgType)}, ${pyBytes(data)}`;
        this._runPython(`sim_state.enqueue_enow(${args})`);
      },
    });

    // The wand lives inside the control panel's pad, so the renderer
    // mounts into the host the panel hands back.
    this._renderer = createRenderer(this._controls.wandHost, {
      onButtonTap: (down) => this._setButton(down),
    });

    this._controls.setConsoleShown(this.showConsole);
    this._controls.setAdvanced(this.advanced);
    this._controls.setLog(this._log, this.logLines);
    this._setStatus("loading", "loading…");
  }

  /**
   * Status is one line under the wand: which way the wand is facing, then
   * the run state. An error's real message replaces the state word rather
   * than collapsing to "error", so a real failure surfaces rather than
   * waiting on someone to hover.
   */
  _setStatus(kind, text) {
    this._controls?.setRunState(kind, text);
  }

  /** Newest-first, capped — the advanced block shows the top `logLines`. */
  _logLine(s) {
    const t = new Date().toTimeString().slice(0, 8);
    this._log = [{ t, s }].concat(this._log).slice(0, 30);
    this._controls?.setLog(this._log, this.logLines);
  }

  // ── Overlays ────────────────────────────────────────────────────────

  /**
   * Show one of the four pop-ups over the whole panel.
   *
   * kind: "game-over" | "cant-simulate" | "welcome" | "new-code"
   * opts.title / opts.message override the built-in copy (the auto-shown
   *   "cant-simulate" uses this to say which phase failed).
   * opts.buttons overrides the button row, as
   *   [{ action, label, style: "ghost"|"pink"|"teal" }].
   *
   * Every button dispatches `sim-overlay-action` with { kind, action } and
   * then closes the overlay; a host that wants it to stay open can call
   * showOverlay again from its listener.
   */
  showOverlay(kind, opts = {}) {
    const spec = OVERLAYS[kind];
    if (!spec) throw new Error(`wand-sim: no overlay named "${kind}"`);
    this.hideOverlay();

    const title = opts.title != null ? opts.title : spec.title;
    const message = opts.message != null ? opts.message : spec.message;
    const buttons = opts.buttons || spec.buttons;

    const frag = document.createDocumentFragment();
    let scrim = null;
    if (!spec.banner) {
      scrim = document.createElement("div");
      scrim.className = "ov-scrim";
      scrim.addEventListener("click", () => {
        this.dispatchEvent(new CustomEvent("sim-overlay-action", { detail: { kind, action: "close" } }));
        this.hideOverlay();
      });
      frag.appendChild(scrim);
    }

    const card = document.createElement("div");
    card.className = `ov-card${spec.banner ? " is-banner" : ""}`;
    card.setAttribute("role", spec.banner ? "status" : "dialog");
    if (!spec.banner) card.setAttribute("aria-modal", "true");
    card.innerHTML = `
      <div class="ov-head">
        <span class="ov-tint" style="background:${spec.tintBg};color:${spec.tintFg}">
          ${icon(spec.icon, spec.banner ? 32 : 40)}
        </span>
        <div class="ov-copy">
          <div class="ov-title">${title}</div>
          <div class="ov-sub">${message}</div>
        </div>
      </div>
      <div class="ov-actions">
        ${buttons.map((b) => `<button type="button" class="ov-btn ${b.style || "ghost"}" data-action="${b.action}">${b.label}</button>`).join("")}
      </div>
    `;
    for (const b of card.querySelectorAll("[data-action]")) {
      b.addEventListener("click", () => {
        this.dispatchEvent(new CustomEvent("sim-overlay-action", {
          detail: { kind, action: b.dataset.action },
        }));
        this.hideOverlay();
      });
    }
    frag.appendChild(card);

    this._root.appendChild(frag);
    this._openOverlay = { kind, nodes: [scrim, card].filter(Boolean) };
    // Focus the primary action so the pop-up is reachable by keyboard.
    if (!spec.banner) card.querySelector(".ov-btn:last-child")?.focus();
  }

  /** Which overlay is showing, or null. */
  get overlay() { return this._openOverlay?.kind || null; }

  hideOverlay() {
    if (!this._openOverlay) return;
    for (const n of this._openOverlay.nodes) n.remove();
    this._openOverlay = null;
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
        const color = on ? speakerColorForFreq(freq) : null;
        self._renderer.setSpeakerColor(color);
        // One expanding ring per note, in that note's own color — the
        // visible counterpart of a beep for anyone with sound off.
        if (on) self._renderer.ping(color);
      });
      this._pyodide.globals.set("_js_motor", (on) => self._audio.setMotor(!!on));
      this._pyodide.globals.set("_js_print", (t) => {
        const line = String(t);
        self._consoleEl.textContent += line + "\n";
        self._consoleEl.scrollTop = self._consoleEl.scrollHeight;
        self._logLine(line);
        self.dispatchEvent(new CustomEvent("sim-print", { detail: { text: line } }));
      });
      // Diagnostic trace, not a failure — a library that wouldn't load, a
      // radio message going out. This used to be wired to sim-error, which
      // meant every ESP-NOW broadcast read as a crash to the host.
      this._pyodide.globals.set("_js_log", (t) => {
        self._logLine(String(t));
      });
      // A traceback out of the running game goes through the same path as a
      // boot/load failure: the game is dead either way, and leaving only a
      // red status line behind is too quiet for something this final.
      this._pyodide.globals.set("_js_error", (t) => {
        self._fail("run", String(t));
      });
      this._pyodide.globals.set("_js_enow_sent", (kind, data, mac) => {
        self._controls?.setEnowSent(String(kind), String(data || ""));
        self.dispatchEvent(new CustomEvent("sim-enow-sent", {
          detail: { kind: String(kind), data: String(data || ""), mac: String(mac || "") },
        }));
      });

      await this._pyodide.runPythonAsync(`
import sim_state
_missing = [n for n in (
    "set_led_callback", "set_pwm_callback", "set_motor_callback",
    "set_print_callback", "set_log_callback", "set_error_callback",
    "set_enow_sent_callback",
) if not hasattr(sim_state, n)]
if _missing:
    raise RuntimeError(
        "sim_state.py is out of date with wand-sim.js (missing %s) — "
        "a cached copy is being served; reload without cache"
        % ", ".join(_missing)
    )
sim_state.set_led_callback(_js_led)
sim_state.set_pwm_callback(_js_pwm)
sim_state.set_motor_callback(_js_motor)
sim_state.set_print_callback(_js_print)
sim_state.set_log_callback(_js_log)
sim_state.set_error_callback(_js_error)
sim_state.set_enow_sent_callback(_js_enow_sent)
`);
      // Held once so per-frame accel/button pushes call methods directly
      // instead of recompiling a Python source string every tick.
      this._sim = this._pyodide.pyimport("sim_state");

      this._ready = true;
      this._setStatus("ready", "ready");
      this.dispatchEvent(new CustomEvent("sim-ready"));
      this._startMotionLoop();
      await this._loadAndMaybeStart();
    } catch (err) {
      console.error(err);
      this._fail("boot", err);
    }
  }

  /**
   * A failure surfaces three ways at once, because none of them alone is
   * enough: the status line (so it can't be missed), a `sim-error` event
   * (so the host can word it for its own audience) and the "Can't
   * simulate" overlay (so nobody sits watching a dead panel). The raw
   * message goes to the console too.
   */
  _fail(phase, err) {
    const message = err && err.message ? err.message : String(err);
    this._setStatus("error", message);
    this.showOverlay("cant-simulate", {
      message: phase === "boot"
        // boot = Pyodide itself never came up, so no game is at fault.
        ? "the practice window isn't available right now — you can still send this game to your wand"
        // load = it wouldn't compile; run = it crashed mid-play. Same advice.
        : "this game is a bit too tricky for the practice window — send it to your wand to try it for real",
    });
    this.dispatchEvent(new CustomEvent("sim-error", { detail: { message: String(err), phase } }));
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
    const loop = (t) => {
      if (this._ready) {
        this._pushAccel();
        if (t - this._lastAxisPush > AXIS_REFRESH_MS) {
          this._lastAxisPush = t;
          this._controls.setAxes(getAccel());
        }
      }
      this._raf = requestAnimationFrame(loop);
    };
    this._raf = requestAnimationFrame(loop);
  }

  /** Host-supplied profile keys win over the runtime's defaults; anything
   * it doesn't mention (nfcTags, battery) stays derived from the code. */
  _applyCapabilities() {
    if (!this._caps) return;
    // `game` lets the panel pick the ESP-NOW vocabulary this game listens
    // for; source-loaded code has no vendored name to match on.
    const base = { ...this._caps, game: this._source ? null : this.game };
    this._controls.setCapabilities(this._profile ? { ...base, ...this._profile } : base);
  }

  async _loadAndMaybeStart() {
    if (!this._ready) return;
    this._setStatus("loading", "loading game…");
    this._controls.setRestartEnabled(false);
    try {
      await this._runPython("await stop()");

      // A freshly-picked-up wand starts at rest; don't carry a pose or an
      // in-flight gesture over from whatever the previous game left it in.
      cancelMove();
      setPose("tip_up");
      this._renderer.setFaceDown(false);
      this._renderer.setTilt3d(0, 0);
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
      this._caps = caps.toJs ? caps.toJs({ dict_converter: Object.fromEntries }) : caps;
      this._applyCapabilities();
      this._setStatus("loaded", `loaded ${this._source ? "custom" : this.game}`);
      this._controls.setRestartEnabled(true);
      if (this.autostart) {
        await this.start();
      }
    } catch (err) {
      // A syntax error or unsupported import in generated/loaded source
      // throws here (compile or module-exec failure) — surface it as a
      // load-phase failure instead of an unhandled rejection, so the panel
      // doesn't get stuck on "loading game…".
      console.error(err);
      this._fail("load", err);
    }
  }

  async start() {
    if (!this._ready) return;
    this._setStatus("running", "running");
    this._consoleEl.textContent = "";
    this._log = [];
    this._controls.setLog(this._log, this.logLines);
    await this._runPython("await start()");
  }

  async stop() {
    await this._runPython("await stop()");
    this._setStatus("stopped", "stopped");
    this.dispatchEvent(new CustomEvent("sim-stopped"));
  }

  /** Stop and restart the currently loaded game fresh (same game, new
   * instance state) — the "start over" affordance for the host page. */
  async restart() {
    if (!this._ready) return;
    this.hideOverlay();
    await this.stop();
    cancelMove();
    setPose("tip_up");
    this._renderer.setFaceDown(false);
    this._renderer.setTilt3d(0, 0);
    this._controls.resetPose();
    this._pushAccel();
    await this.start();
  }
}

customElements.define("wand-sim", WandSim);
export { WandSim, OVERLAYS };
