/**
 * Simulator control panel, laid out per the "Wand Simulator v4" design
 * artboard (BroadcastBox/docs_and_design/simlution v4/Wand Simulator v4.dc.html).
 *
 * Two panes. The left one is the wand's home: a striped pad you move over
 * to tilt the wand and click to press its button, with the four named
 * orientations labelled at its edges, a live axis readout above (advanced
 * only) and a status line plus "Turn over" below. The right one holds the
 * toolbar (sound / advanced / start over), the one-shot gestures, the tag
 * popover, and the advanced block.
 *
 * Controls stay filtered by the loaded game's capabilities
 * (py/runtime.py:get_capabilities()) so only inputs the game actually reads
 * are shown — a game that never checks for a shake doesn't offer a Shake
 * button. The pad and the wand's own button are the exception: they are the
 * wand itself, not an affordance the panel adds, so they are always live.
 */

import { icon } from "./icons.js";

const POSE_LABELS = {
  tip_up: "Upright",
  tip_down: "Upside Down",
  left_up: "Left Up",
  right_up: "Right Up",
  face_up: "Face Up",
  face_down: "Face Down",
};
const POSE_ORDER = ["tip_up", "tip_down", "left_up", "right_up", "face_up", "face_down"];

// The pad's own edge labels — shorter than POSE_LABELS, which read as
// button text; these are corner hints on a small square.
const PAD_LABELS = {
  tip_up: "Tip up",
  tip_down: "Tip down",
  left_up: "Left<br>up",
  right_up: "Right<br>up",
};

const MOVE_ORDER = ["jump", "shake", "flip"];
// "Spin" rather than "Flip" in the UI, per the artboard: what the player
// does is spin the wand over; `flip` stays the motion.js program name.
const MOVE_LABELS = { jump: "Jump", shake: "Shake", flip: "Spin" };
const MOVE_ICONS = { jump: "arrow-up", shake: "vibrate", flip: "shuffle" };

// Pale violet-leaning pastels — the tint scale the design system uses for
// all state work. Assigned per tag name so a given tag keeps its color.
const PASTELS = ["#fff0f6", "#f2eefc", "#e9fbf6", "#fff8e0"];

// Pad coordinates run -100..100 on both axes; ±45 is where the artboard
// calls an orientation, matching the dashed circle it draws.
const PAD_RANGE = 230;
const PAD_THRESHOLD = 45;
// How long the pointer has to stop moving before the free-form tilt is
// quantised to the nearest named pose (see snapToPose).
const SETTLE_MS = 140;

const STATE_LABELS = {
  loading: "loading",
  ready: "ready",
  loaded: "loaded",
  running: "running",
  stopped: "stopped",
  error: "error",
};

function hashName(s) {
  let h = 7;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

/**
 * Which named orientation a pad position reads as. Mirrors the artboard's
 * detect(): the dominant axis wins, and nothing within ±45 of centre counts
 * as tilted at all — that's a wand lying face up.
 */
export function detectPose(ax, ay, faceDown) {
  if (faceDown) return "face_down";
  if (Math.abs(ay) >= Math.abs(ax)) {
    if (ay <= -PAD_THRESHOLD) return "tip_up";
    if (ay >= PAD_THRESHOLD) return "tip_down";
  } else {
    if (ax <= -PAD_THRESHOLD) return "left_up";
    if (ax >= PAD_THRESHOLD) return "right_up";
  }
  return "face_up";
}

export const CONTROLS_STYLE = `
/* The hidden attribute has to beat the layout rules below, which all set
   display on the same elements that get hidden/shown by capability. */
[hidden] { display: none !important; }

.wand-controls { flex: 1; min-height: 0; display: flex; flex-wrap: wrap; align-items: stretch; width: 100%; }

/* ── Left pane: the wand and its pad ─────────────────────────────────── */
.sim-pane-wand {
  flex: 0 0 clamp(200px, 48%, 280px); min-width: 0;
  display: flex; flex-direction: column; gap: 6px;
  padding: 14px 0 14px 14px; box-sizing: border-box;
}
.pad-hint { font: 400 14px 'Patrick Hand', cursive; color: #8b859a; line-height: 1.2; }
.axis-row { display: flex; flex-wrap: wrap; gap: 6px 12px; }
.axis { display: flex; align-items: center; gap: 5px; }
.axis-name { font: 700 10px ui-monospace, monospace; color: #8b859a; }
.axis-track { position: relative; width: 44px; height: 6px; border-radius: 3px; background: #e8e6f0; }
.axis-fill { position: absolute; top: 0; bottom: 0; background: #22c3a6; border-radius: 3px; transition: all .12s; }
.axis-val { font: 700 10px ui-monospace, monospace; color: #5b5468; width: 30px; text-align: right; }

/* min-height covers the wand (176px wide at 439/730 is ~293px tall) plus
   .pad-wand's padding; in the two-pane layout the pad gets far more than
   this from the shell's own height. */
.pad {
  position: relative; flex: 1; min-height: 340px; border-radius: 20px;
  background: repeating-linear-gradient(45deg, #fbfaff 0 7px, #f4f2fa 7px 14px);
  border: 1.5px solid #e8e6f0; overflow: hidden; touch-action: none; cursor: pointer;
}
.pad.is-pressed { cursor: grabbing; }
.pad-labels { position: absolute; inset: 0; pointer-events: none; }
.pad-label {
  position: absolute; font: 800 10px/1.35 'Nunito', system-ui, sans-serif;
  letter-spacing: .06em; transition: color .15s; color: #c2b8d6;
}
.pad-label.is-on { color: #d13a7c; }
.pad-label-top { top: 10px; left: 12px; }
.pad-label-bottom { bottom: 10px; left: 12px; }
.pad-label-left { top: 50%; left: 12px; transform: translateY(-50%); }
.pad-label-right { top: 50%; right: 12px; transform: translateY(-50%); text-align: right; }
.pad-ring {
  position: absolute; left: 50%; top: 50%; transform: translate(-50%,-50%);
  width: 118px; height: 118px; border-radius: 50%; border: 1.5px dashed #e8e6f0;
}
/* Padding rather than inset:0 — the BUZZ badge hangs below the case, and
   the pad clips (it has to, for the striped fill and rounded corners). */
.pad-wand {
  position: absolute; inset: 0; padding: 6% 8% 10%;
  display: flex; align-items: center; justify-content: center;
  pointer-events: none;
}
/* Re-enabled on the wand itself so its drawn button stays clickable
   through the pad's pointer handling. */
.pad-wand .wand-body { pointer-events: auto; }

.pad-foot { display: flex; gap: 10px; align-items: flex-start; justify-content: space-between; }
.status { display: flex; gap: 6px; align-items: center; font: 700 11px 'Nunito', system-ui, sans-serif; color: #5b5468; min-width: 0; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: #22c3a6; flex: none; transition: background .2s; }
.status-text { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.status.is-loading .status-dot { background: #ffd23f; animation: status-pulse 1s ease-in-out infinite; }
.status.is-error { color: #b3261e; }
.status.is-error .status-dot { background: #b3261e; }
.status.is-stopped .status-dot { background: #c2b8d6; }
@keyframes status-pulse { 50% { opacity: .35 } }

/* ── Right pane: the controls ────────────────────────────────────────── */
.sim-pane-ctrl {
  flex: 1; min-width: 190px;
  display: flex; flex-direction: column; gap: 9px;
  padding: 14px 16px 14px 10px; box-sizing: border-box;
}
.ctrl-toolbar { display: flex; align-items: center; justify-content: flex-end; gap: 4px; }
.icon-btn {
  border: 1.5px solid #e8e6f0; background: #fff; border-radius: 14px;
  padding: 8px 10px; cursor: pointer; color: #5b5468;
  display: inline-flex; align-items: center; justify-content: center;
  transition: all .15s;
}
.icon-btn:hover { color: #6c4cd1; border-color: #6c4cd1; }
.icon-btn.is-active { background: #fff0f6; color: #d13a7c; border-color: transparent; }
.icon-btn:disabled { opacity: .7; cursor: not-allowed; }
.icon-btn:disabled:hover { color: #5b5468; border-color: #e8e6f0; }

.hint { font: 400 14px 'Patrick Hand', cursive; color: #8b859a; line-height: 1.25; }

/* Stacked icon-over-label button — Jump, Spin, Shake, Turn over. */
.btn-stack {
  display: flex; flex-direction: column; align-items: center; gap: 5px;
  padding: 8px 0; border-radius: 14px; border: 1.5px solid #e8e6f0;
  background: #fff; color: #5b5468;
  font: 800 10.5px 'Nunito', system-ui, sans-serif; cursor: pointer;
  transition: all .15s;
}
.btn-stack:hover { border-color: #ef4d92; color: #d13a7c; background: #fff0f6; }
.btn-stack.is-active { border-color: #6c4cd1; background: #f2eefc; color: #6c4cd1; }
.pad-foot .btn-stack { flex: 1; min-width: 0; padding: 4px 0; }

.move-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 7px; margin-top: 12px; }
.move-grid > .btn-stack:only-child { grid-column: span 2; }
/* Wraps: the artboard draws the button, label, slider and value on one
   row at widths that together exceed the control pane at its own 500px
   shell, so the strength group drops below the button when it has to. */
.shake-row { display: flex; flex-flow: row wrap; gap: 9px; align-items: center; margin-top: 12px; }
.shake-row .btn-stack { flex: none; width: 100px; }
.shake-strength { flex: 1 1 150px; display: flex; align-items: center; gap: 8px; min-width: 0; }
.shake-strength input[type=range] { flex: 1 1 auto; min-width: 56px; max-width: 84px; }
.shake-strength > span:first-child { font: 700 11px 'Nunito', system-ui, sans-serif; color: #5b5468; flex: none; }
.shake-val { font: 700 11px ui-monospace, monospace; color: #231f2e; width: 22px; text-align: right; flex: none; }

/* ── Tag popover ─────────────────────────────────────────────────────── */
.tag-wrap { position: relative; margin-top: 8px; }
.btn-wide {
  width: 100%; display: flex; align-items: center; justify-content: center;
  gap: 7px; padding: 9px 0; border-radius: 14px; cursor: pointer;
  transition: all .15s; font: 800 11px 'Nunito', system-ui, sans-serif;
  border: 1.5px solid #e8e6f0; background: #fff; color: #5b5468;
}
.btn-wide:hover { border-color: #ef4d92; color: #d13a7c; background: #fff0f6; }
.btn-wide.is-active { border-color: #ef4d92; background: #fff0f6; color: #d13a7c; }
.tag-scrim { position: absolute; inset: -2000px; z-index: 5; cursor: default; }
.tag-pop {
  position: absolute; right: 0; top: calc(100% + 8px); z-index: 6; width: 212px;
  box-sizing: border-box; background: #fff; border: 1.5px solid #e8e6f0;
  border-radius: 20px; box-shadow: 0 24px 60px rgba(0,0,0,.22); padding: 12px;
  display: flex; flex-direction: column; gap: 9px;
}
.tag-pop-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.tag-pop-head span { font: 400 14px 'Patrick Hand', cursive; color: #8b859a; line-height: 1; }
.btn-bare {
  display: flex; align-items: center; justify-content: center; background: none;
  border: 0; padding: 0; color: #8b859a; cursor: pointer; flex: none;
}
.btn-bare:hover { color: #6c4cd1; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; max-height: 132px; overflow-y: auto; }
.tag-chip {
  flex: none; display: flex; align-items: center; gap: 5px; padding: 6px 11px;
  border-radius: 20px; border: 1.5px solid #e8e6f0;
  font: 700 11px 'Nunito', system-ui, sans-serif; color: #3a3345;
  cursor: pointer; transition: all .15s;
}
.tag-chip:hover { border-color: #ef4d92; color: #d13a7c; }
.field-row { display: flex; gap: 6px; }
.field-row.divided { border-top: 1px solid #f4f2fa; padding-top: 9px; }
.field {
  flex: 1; min-width: 0; padding: 8px 11px; border-radius: 12px;
  border: 1.5px solid #e8e6f0; background: #fafafd; color: #231f2e;
  font: 600 11.5px 'Nunito', system-ui, sans-serif;
}
.field:focus { border-color: #ef4d92; box-shadow: 0 0 0 3px rgba(233,78,155,.14); background: #fff; outline: none; }
.btn-pink, .btn-purple {
  padding: 0 13px; border-radius: 12px; border: none; color: #fff;
  font: 800 11px 'Nunito', system-ui, sans-serif; cursor: pointer; flex: none;
}
.btn-pink { background: linear-gradient(135deg, #ef4d92, #d13a7c); }
.btn-purple { background: linear-gradient(135deg, #6c4cd1, #4f36a3); }

.zero-state { font: 400 14px 'Patrick Hand', cursive; color: #c2b8d6; padding: 8px 0; }

/* ── Advanced ────────────────────────────────────────────────────────── */
.adv-block { display: flex; flex-direction: column; gap: 6px; margin-top: auto; }
.uses-row { font: 700 11px ui-monospace, monospace; color: #c2b8d6; }
.drawer-toggle {
  width: 100%; display: flex; justify-content: space-between; align-items: center;
  background: none; border: 0; padding: 2px 0; color: #8b859a;
  font: 800 11px 'Nunito', system-ui, sans-serif; cursor: pointer;
  border-top: 1px solid #f4f2fa;
}
.drawer-toggle:hover { color: #6c4cd1; }
.drawer-body { display: flex; flex-direction: column; gap: 7px; padding: 8px 0 0; }
.dial-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.dial-row label { font: 700 11px 'Nunito', system-ui, sans-serif; color: #8b859a; display: flex; gap: 6px; align-items: center; }
.dial-row input[type=range] { width: 84px; }
.ctrl-btn {
  font: 700 11px 'Nunito', system-ui, sans-serif; padding: 6px 11px;
  border-radius: 12px; border: 1.5px solid #e8e6f0; background: #fff;
  color: #5b5468; cursor: pointer; transition: all .15s;
}
.ctrl-btn:hover { border-color: #6c4cd1; color: #6c4cd1; }
.adv-status { font: 700 11px ui-monospace, monospace; color: #8b859a; }
.log { font: 400 10px/1.5 ui-monospace, monospace; color: #8b859a; overflow: hidden; }
.log-line { display: flex; gap: 8px; }
.log-line > span:first-child { color: #c2b8d6; flex: none; }

input[type=range] { accent-color: #ef4d92; }

/* One column once the shell is too narrow for two panes — ChatBroadcast's
   preview column is user-resizable down past this. */
@container wand-sim (max-width: 420px) {
  .sim-pane-wand { flex: 1 1 100%; padding: 14px 14px 0; }
  .sim-pane-ctrl { flex: 1 1 100%; padding: 9px 14px 14px; }
}
/* Narrower than the wand wants: shrink the wand rather than clip it. */
@container wand-sim (max-width: 300px) {
  .sim-pane-wand { --wand-art-width: 132px; }
  .pad { min-height: 260px; }
}
`;

export function createControls(container, handlers = {}) {
  const root = container;
  root.classList.add("wand-controls");
  root.innerHTML = `
    <div class="sim-pane-wand">
      <div class="pad-hint" data-el="pad-hint">move to tilt · click to press</div>
      <div class="axis-row" data-el="axes" data-adv hidden></div>
      <div class="pad" data-el="pad" title="Move to tilt · click to press the button">
        <div class="pad-labels" data-el="pad-labels" data-adv hidden>
          ${POSE_ORDER.filter((n) => PAD_LABELS[n]).map((n) => {
            const pos = { tip_up: "top", tip_down: "bottom", left_up: "left", right_up: "right" }[n];
            return `<span class="pad-label pad-label-${pos}" data-pad-label="${n}">${PAD_LABELS[n]}</span>`;
          }).join("")}
          <span class="pad-ring"></span>
        </div>
        <div class="pad-wand" data-el="wand"></div>
      </div>
      <div class="pad-foot">
        <div class="status" data-el="status">
          <span class="status-dot"></span><span class="status-text" data-el="status-text"></span>
        </div>
        <button type="button" class="btn-stack" data-act="face-flip"
                title="Turn the wand over">${icon("shakePhone", 18)}Turn over</button>
      </div>
    </div>

    <div class="sim-pane-ctrl">
      <div class="ctrl-toolbar">
        <button type="button" class="icon-btn" data-act="mute" aria-pressed="false"></button>
        <button type="button" class="icon-btn" data-act="advanced" aria-pressed="false"
                title="Advanced — axes, custom tags, dials, log">${icon("code", 18)}</button>
        <button type="button" class="icon-btn" data-act="restart"
                title="Start over">${icon("mop-sparkles", 18)}</button>
      </div>

      <div class="hint" data-el="hint" hidden></div>

      <div class="move-grid" data-el="move-grid" hidden>
        <button type="button" class="btn-stack" data-move="jump" title="Toss the wand up">${icon("arrow-up", 18)}Jump</button>
        <button type="button" class="btn-stack" data-move="flip" title="Spin it over once">${icon("shuffle", 18)}Spin</button>
      </div>

      <div class="shake-row" data-el="shake-row" hidden>
        <button type="button" class="btn-stack" data-move="shake" title="Shake it back and forth">${icon("vibrate", 18)}Shake</button>
        <div class="shake-strength">
          <span>How hard</span>
          <input type="range" min="5" max="100" value="60" data-act="shake" title="Shake strength">
          <span class="shake-val" data-el="shake-val">60</span>
        </div>
      </div>

      <div class="tag-wrap" data-el="tag-wrap" hidden>
        <button type="button" class="btn-wide" data-act="tag-menu"
                title="Touch a tag to the wand">${icon("smartphone-nfc", 18)}Tap a tag</button>
        <div data-el="tag-pop" hidden>
          <div class="tag-scrim" data-act="tag-close" title="Close"></div>
          <div class="tag-pop">
            <div class="tag-pop-head">
              <span>hold a card on the wand</span>
              <button type="button" class="btn-bare" data-act="tag-close" title="Close">${icon("close", 14)}</button>
            </div>
            <div class="tag-list" data-el="tag-list"></div>
            <div class="field-row divided">
              <input class="field" data-act="free-tag-input" placeholder="type any tag word">
              <button type="button" class="btn-pink" data-act="free-tag-send">Scan</button>
            </div>
          </div>
        </div>
      </div>

      <div class="zero-state" data-el="zero-state" hidden>
        this game has no player controls — just watch it play
      </div>

      <div class="adv-block" data-adv hidden>
        <div class="uses-row" data-el="uses" hidden></div>

        <button type="button" class="drawer-toggle" data-act="drawer-msg">
          Custom tag or radio message<span data-el="caret-msg">▼</span>
        </button>
        <div class="drawer-body" data-el="drawer-msg" hidden>
          <div class="field-row">
            <input class="field" data-act="free-tag-input2" placeholder="type any tag word">
            <button type="button" class="btn-pink" data-act="free-tag-send2">Scan</button>
          </div>
          <div class="field-row">
            <input class="field" data-act="enow-input" placeholder="message from another wand">
            <button type="button" class="btn-purple" data-act="enow-send">Send</button>
          </div>
        </div>

        <button type="button" class="drawer-toggle" data-act="drawer-dials">
          Hardware dials and log<span data-el="caret-dials">▼</span>
        </button>
        <div class="drawer-body" data-el="drawer-dials" hidden>
          <div class="dial-row">
            <label>Battery <input type="range" data-act="battery" min="0" max="100" value="85"></label>
            <label>Ambient lux <input type="range" data-act="lux" min="10" max="20000" value="500"></label>
          </div>
          <div class="dial-row">
            <button type="button" class="ctrl-btn" data-act="toggle-console" aria-pressed="false">Show console</button>
            <span class="adv-status">Buzzer: <span data-el="adv-buzzer">off</span></span>
            <span class="adv-status">Motor: <span data-el="adv-motor">off</span></span>
          </div>
        </div>

        <div class="log" data-el="log"></div>
      </div>
    </div>
  `;

  const q = (sel) => root.querySelector(sel);
  const el = {
    padHint: q('[data-el="pad-hint"]'),
    axes: q('[data-el="axes"]'),
    pad: q('[data-el="pad"]'),
    padLabels: q('[data-el="pad-labels"]'),
    wand: q('[data-el="wand"]'),
    status: q('[data-el="status"]'),
    statusText: q('[data-el="status-text"]'),
    hint: q('[data-el="hint"]'),
    moveGrid: q('[data-el="move-grid"]'),
    shakeRow: q('[data-el="shake-row"]'),
    shakeVal: q('[data-el="shake-val"]'),
    tagWrap: q('[data-el="tag-wrap"]'),
    tagPop: q('[data-el="tag-pop"]'),
    tagList: q('[data-el="tag-list"]'),
    zeroState: q('[data-el="zero-state"]'),
    uses: q('[data-el="uses"]'),
    log: q('[data-el="log"]'),
    advBuzzer: q('[data-el="adv-buzzer"]'),
    advMotor: q('[data-el="adv-motor"]'),
  };
  const muteBtn = q('[data-act="mute"]');
  const advBtn = q('[data-act="advanced"]');
  const restartBtn = q('[data-act="restart"]');
  const consoleBtn = q('[data-act="toggle-console"]');
  const shakeRange = q('[data-act="shake"]');

  const timers = {};
  let muted = false;
  let advanced = false;
  let consoleShown = false;
  let faceDown = false;
  let pressed = false;
  let hovering = false;
  let padX = 0;
  let padY = 0;
  let pose = "face_up";
  let runKind = "loading";
  let runText = "loading";
  let logLines = 2;

  // ── Status line + pad hint ──────────────────────────────────────────
  function renderStatus() {
    el.status.className = `status is-${runKind}`;
    // An error's message gets the whole line: which way the wand is facing
    // is not what someone reading a failure needs to know.
    el.statusText.textContent = runKind === "error"
      ? runText
      : `${POSE_LABELS[pose] || pose} — ${runText}`;
    el.status.title = el.statusText.textContent;
  }
  function renderPadHint() {
    el.padHint.textContent = pressed
      ? "button down"
      : hovering
        ? "click to press"
        : "move to tilt · click to press";
  }

  /** kind: loading | ready | loaded | running | stopped | error. `text`
   * overrides the short label — an error's real message must stay visible
   * rather than collapse to the word "error". */
  function setRunState(kind, text) {
    runKind = kind;
    runText = text || STATE_LABELS[kind] || kind;
    renderStatus();
  }

  function setPoseDisplay(name) {
    pose = name;
    for (const label of el.padLabels.querySelectorAll("[data-pad-label]")) {
      label.classList.toggle("is-on", label.dataset.padLabel === name);
    }
    renderStatus();
  }

  // ── Pad: tilt while moving, snap to a named pose on settle ──────────
  //
  // The free-form tilt gives the wand something continuous to follow, but
  // a normalized in-between vector sits under the thresholds an
  // orientation-reading game tests (simpleicecream.py's scoop, say). So
  // once the pointer stops, the tilt is quantised to whichever pose the
  // pad position reads as, which lands the exact gravity vector from
  // motion.js's POSES table.
  function snapToPose() {
    const name = detectPose(padX, padY, faceDown);
    setPoseDisplay(name);
    handlers.onPose?.(name);
  }

  function padFromEvent(e) {
    const r = el.pad.getBoundingClientRect();
    if (!r.width || !r.height) return;
    padX = Math.max(-100, Math.min(100, Math.round(((e.clientX - r.left) / r.width - 0.5) * PAD_RANGE)));
    padY = Math.max(-100, Math.min(100, Math.round(((e.clientY - r.top) / r.height - 0.5) * PAD_RANGE)));
    hovering = true;
    renderPadHint();
    setPoseDisplay(detectPose(padX, padY, faceDown));
    handlers.onTilt?.(padX / 100, padY / 100);
    clearTimeout(timers.settle);
    timers.settle = setTimeout(snapToPose, SETTLE_MS);
  }

  el.pad.addEventListener("pointermove", padFromEvent);
  el.pad.addEventListener("pointerdown", (e) => {
    // The whole pad presses the button, the drawn wand included — but the
    // drawn button itself has its own handler (see js/renderer.js), so
    // skip only that one element rather than the whole wand, which would
    // leave its case and LED panel as a dead zone.
    if (e.target.classList?.contains("wand-btn")) return;
    padFromEvent(e);
    pressed = true;
    el.pad.classList.add("is-pressed");
    renderPadHint();
    handlers.onButton?.(true);
  });
  const padRelease = () => {
    if (!pressed) return;
    pressed = false;
    el.pad.classList.remove("is-pressed");
    renderPadHint();
    handlers.onButton?.(false);
  };
  el.pad.addEventListener("pointerup", padRelease);
  el.pad.addEventListener("pointercancel", padRelease);
  el.pad.addEventListener("pointerleave", () => {
    hovering = false;
    renderPadHint();
    padRelease();
    clearTimeout(timers.settle);
    snapToPose();
  });

  /** Live accelerometer readout — real sampled values, not pad position. */
  function setAxes(a) {
    if (el.axes.hidden) return;
    const bar = (name, val) => {
      const v = Math.round(val * 100);
      const left = v < 0 ? 50 + v / 2 : 50;
      return `<div class="axis"><span class="axis-name">${name}</span>` +
        `<div class="axis-track"><div class="axis-fill" style="left:${left}%;width:${Math.abs(v) / 2}%"></div></div>` +
        `<span class="axis-val">${v > 0 ? "+" : ""}${v}</span></div>`;
    };
    el.axes.innerHTML = bar("X", a.x) + bar("Y", a.y) + bar("Z", a.z);
  }

  // ── Toolbar ─────────────────────────────────────────────────────────
  function applyMuteVisual() {
    muteBtn.classList.toggle("is-active", !muted);
    muteBtn.setAttribute("aria-pressed", String(!muted));
    const label = muted ? "Turn the simulator's sound on" : "Turn the simulator's sound off";
    muteBtn.setAttribute("aria-label", label);
    muteBtn.title = label;
    muteBtn.innerHTML = icon(muted ? "volume-x" : "volume-2", 18);
  }
  muteBtn.addEventListener("click", () => {
    muted = !muted;
    applyMuteVisual();
    handlers.onMute?.(muted);
  });
  function setMuted(v) {
    muted = !!v;
    applyMuteVisual();
  }
  applyMuteVisual();

  advBtn.addEventListener("click", () => handlers.onToggleAdvanced?.(!advanced));
  /** Driven from the host's `advanced` attribute, not toggled locally, so
   * the attribute stays the single source of truth. */
  function setAdvanced(v) {
    advanced = !!v;
    advBtn.classList.toggle("is-active", advanced);
    advBtn.setAttribute("aria-pressed", String(advanced));
    for (const node of root.querySelectorAll("[data-adv]")) node.hidden = !advanced;
    if (advanced) renderLog();
  }

  // Restart always means the same thing (this game, from the top) whether
  // it's mid-run, finished or errored, so it needs no play/pause state.
  restartBtn.addEventListener("click", () => handlers.onRestart?.());
  function setRestartEnabled(v) { restartBtn.disabled = !v; }
  setRestartEnabled(false);

  function applyConsoleVisual() {
    consoleBtn.setAttribute("aria-pressed", String(consoleShown));
    consoleBtn.textContent = consoleShown ? "Hide console" : "Show console";
  }
  consoleBtn.addEventListener("click", () => {
    consoleShown = !consoleShown;
    applyConsoleVisual();
    handlers.onToggleConsole?.(consoleShown);
  });
  function setConsoleShown(v) {
    consoleShown = !!v;
    applyConsoleVisual();
  }
  applyConsoleVisual();

  // ── Turn over ───────────────────────────────────────────────────────
  const faceBtn = q('[data-act="face-flip"]');
  faceBtn.addEventListener("click", () => {
    faceDown = !faceDown;
    faceBtn.classList.toggle("is-active", faceDown);
    const name = detectPose(padX, padY, faceDown);
    setPoseDisplay(name);
    handlers.onFaceFlip?.(faceDown, name);
  });

  // ── Moves ───────────────────────────────────────────────────────────
  for (const b of root.querySelectorAll("[data-move]")) {
    b.addEventListener("click", () => {
      const kind = b.dataset.move;
      const opts = kind === "shake" ? { intensity: Number(shakeRange.value) / 100 } : undefined;
      handlers.onMove?.(kind, opts);
    });
  }
  shakeRange.addEventListener("input", () => { el.shakeVal.textContent = shakeRange.value; });

  // ── Tags ────────────────────────────────────────────────────────────
  const tagMenuBtn = q('[data-act="tag-menu"]');
  function setTagMenu(open) {
    el.tagPop.hidden = !open;
    tagMenuBtn.classList.toggle("is-active", open);
  }
  tagMenuBtn.addEventListener("click", () => setTagMenu(el.tagPop.hidden));
  for (const b of root.querySelectorAll('[data-act="tag-close"]')) {
    b.addEventListener("click", () => setTagMenu(false));
  }

  function renderTags(tags) {
    el.tagList.innerHTML = "";
    for (const cmd of tags) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "tag-chip";
      b.title = "Touch this tag to the wand";
      b.style.background = PASTELS[hashName(cmd) % PASTELS.length];
      b.innerHTML = `${icon("nfcCard", 13)}${cmd}`;
      b.addEventListener("click", () => {
        handlers.onNfc?.(cmd);
        setTagMenu(false);
      });
      el.tagList.appendChild(b);
    }
  }

  // Both free-tag fields (popover + advanced drawer) do the same thing.
  for (const [inputSel, sendSel] of [
    ['[data-act="free-tag-input"]', '[data-act="free-tag-send"]'],
    ['[data-act="free-tag-input2"]', '[data-act="free-tag-send2"]'],
  ]) {
    const input = q(inputSel);
    const send = () => {
      const cmd = input.value.trim().toLowerCase();
      if (!cmd) return;
      handlers.onNfc?.(cmd);
      setTagMenu(false);
    };
    q(sendSel).addEventListener("click", send);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
  }

  const enowInput = q('[data-act="enow-input"]');
  const sendEnow = () => {
    const msg = enowInput.value.trim();
    if (!msg) return;
    handlers.onEnow?.(msg);
  };
  q('[data-act="enow-send"]').addEventListener("click", sendEnow);
  enowInput.addEventListener("keydown", (e) => { if (e.key === "Enter") sendEnow(); });

  // ── Advanced drawers ────────────────────────────────────────────────
  for (const key of ["msg", "dials"]) {
    const toggle = q(`[data-act="drawer-${key}"]`);
    const body = q(`[data-el="drawer-${key}"]`);
    const caret = q(`[data-el="caret-${key}"]`);
    toggle.addEventListener("click", () => {
      body.hidden = !body.hidden;
      caret.textContent = body.hidden ? "▼" : "▲";
    });
  }

  q('[data-act="battery"]').addEventListener("input", (e) => handlers.onBattery?.(Number(e.target.value)));
  q('[data-act="lux"]').addEventListener("input", (e) => handlers.onLux?.(Number(e.target.value)));

  // The raw Hz / on-off detail lives in the advanced drawer rather than on
  // the wand, which shows the same state as color and a BUZZ badge.
  function setBuzzerStatus(text) { el.advBuzzer.textContent = text; }
  function setMotorStatus(text) { el.advMotor.textContent = text; }

  // ── Log ─────────────────────────────────────────────────────────────
  let log = [];
  function renderLog() {
    if (el.log.hidden || !advanced) return;
    el.log.innerHTML = log.slice(0, logLines)
      .map((l) => `<div class="log-line"><span>${l.t}</span><span>${l.s}</span></div>`)
      .join("");
  }
  /** lines: newest-first [{ t, s }]. */
  function setLog(lines, maxLines) {
    log = lines || [];
    if (maxLines) logLines = maxLines;
    renderLog();
  }

  // ── Capability-driven layout ────────────────────────────────────────
  function setCapabilities(caps) {
    const motion = new Set(caps?.motion || []);
    const poseNames = POSE_ORDER.filter((n) => motion.has(n));
    const moveNames = MOVE_ORDER.filter((n) => motion.has(n));
    const buttonKind = caps?.button || "none";
    const tags = caps?.nfcTags || [];

    el.hint.textContent = caps?.hint || "";
    el.hint.hidden = !caps?.hint;

    const uses = [];
    if (poseNames.length) uses.push("orientation");
    if (moveNames.length) uses.push("motion");
    if (buttonKind !== "none") uses.push(buttonKind === "hold" ? "hold button" : "button");
    if (tags.length) uses.push("tags");
    el.uses.textContent = uses.length ? "Uses: " + uses.join(", ") : "";
    el.uses.hidden = uses.length === 0;

    // Pad edge labels only for orientations this game reads, so the pad
    // doesn't advertise a pose that does nothing.
    for (const label of el.padLabels.querySelectorAll("[data-pad-label]")) {
      label.hidden = !motion.has(label.dataset.padLabel);
    }
    faceBtn.hidden = !(motion.has("face_up") || motion.has("face_down"));

    for (const b of root.querySelectorAll("[data-move]")) {
      if (b.dataset.move === "shake") continue;
      b.hidden = !motion.has(b.dataset.move);
    }
    el.moveGrid.hidden = !(motion.has("jump") || motion.has("flip"));
    el.shakeRow.hidden = !motion.has("shake");

    renderTags(tags);
    el.tagWrap.hidden = tags.length === 0;

    el.zeroState.hidden = !(poseNames.length === 0 && moveNames.length === 0 &&
      buttonKind === "none" && tags.length === 0);
  }

  /** A freshly-picked-up wand is upright and face up. */
  function resetPose() {
    faceDown = false;
    faceBtn.classList.remove("is-active");
    padX = 0;
    padY = 0;
    setPoseDisplay("tip_up");
  }

  function dispose() {
    Object.keys(timers).forEach((k) => clearTimeout(timers[k]));
  }

  renderStatus();
  renderPadHint();

  return {
    setCapabilities, setMuted, setConsoleShown, setRestartEnabled, resetPose,
    setBuzzerStatus, setMotorStatus, setAdvanced, setRunState, setAxes, setLog,
    dispose, wandHost: el.wand, root,
  };
}
