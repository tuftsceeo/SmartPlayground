/**
 * Wand-face renderer — builds the wand in CSS/DOM per the
 * "Wand v4" design artboard (BroadcastBox/docs_and_design/simlution v4/
 * Wand v4.dc.html): gradient case, white front face carrying a mic dot, a
 * speaker cone and a dark 5x5 LED panel over a physical button, a plain
 * purple back face with a "hidden face" mini inset, and a "BUZZ" badge for
 * the vibration motor.
 *
 * It replaces an earlier pass that inlined assets/wand/WAND_FRONT.svg and
 * drove its named layers; that file is still in assets/wand/ but is no
 * longer rendered.
 *
 * Incoming LED bytes are the wand's actual NeoPixel duty cycle — leds.py
 * has already applied brightness.MULTIPLIER (max 0.5, see brightness.py)
 * before emit_led_frame() sends them here. A WS2812's duty cycle is a
 * *linear* light quantity, but a CSS color is sRGB-encoded (gamma ~2.2), so
 * using the duty byte directly reads far dimmer than the real LED looks.
 * Converting it through the same linear -> sRGB curve the Icon Display
 * Station pipeline uses (webapp/js/pipeline/ledcolor.js's linearToSrgb,
 * ledDisplay.js's authoredToDisplay) shows the color the LED actually
 * appears to emit.
 */

export function linearToSrgb(c) {
  // c in [0,1] linear -> [0,1] sRGB-encoded (IEC 61966-2-1).
  const v = c <= 0.0031308 ? c * 12.92 : 1.055 * c ** (1 / 2.4) - 0.055;
  return Math.min(1, Math.max(0, v));
}

export function dutyToDisplayByte(duty, gain = 1) {
  const linear = Math.min(1, Math.max(0, (duty * gain) / 255));
  return Math.round(linearToSrgb(linear) * 255);
}

export function dutyRgbToCss([r, g, b], gain = 1) {
  return `rgb(${dutyToDisplayByte(r, gain)},${dutyToDisplayByte(g, gain)},${dutyToDisplayByte(b, gain)})`;
}

// The artboard's unlit pixel: the product ink color, not black, so an off
// LED still reads as a pixel sitting in the panel rather than a hole in it.
const LED_OFF = "#231f2e";
const LED_OFF_GLOW = "inset 0 0 0 1px rgba(255,255,255,.05)";
const SPEAKER_IDLE = "#2d2d2d";

// Button shadow/transform pairs, from the artboard's btnShadow/btnPress.
const BTN_UP_SHADOW = "0 5px 0 #17141f, 0 7px 10px rgba(23,20,31,.3)";
const BTN_DOWN_SHADOW = "0 1px 0 #17141f, 0 2px 4px rgba(23,20,31,.3)";

// Marks thrown off the case while the motor runs ("agitrons", the comic
// convention for a vibrating object).
const AGITRON_MARKS = ["≡", "≈", "~", "∴", "·"];

/** Keyframe + easing per gesture, from the artboard's playAnim() calls. */
const GESTURE_ANIM = {
  jump: ["wandJump", "cubic-bezier(.3,.7,.4,1)"],
  shake: ["wandShake", "ease-in-out"],
  flip: ["wandFlip", "cubic-bezier(.4,.05,.3,1)"],
  faceflip: ["wandFlip", "cubic-bezier(.4,.1,.3,1)"],
};

// Front-face markup, reused verbatim for the full-size face and the small
// "hidden face" inset — the inset is the same wand, just scaled, so its LED
// cells and speaker dot are driven from the same applyFrame call.
function faceMarkup(scope) {
  const cells = new Array(25)
    .fill(0)
    .map((_, i) => `<div class="wand-led" data-${scope}-led="${i}"></div>`)
    .join("");
  return `
    <div class="wand-face">
      <div class="wand-face-top">
        <div class="wand-mic"></div>
        <div class="wand-speaker">
          <div class="wand-speaker-mesh">
            <div class="wand-speaker-dot" data-${scope}-speaker></div>
          </div>
        </div>
      </div>
      <div class="wand-face-mid">
        <div class="wand-panel">${cells}</div>
        <div class="wand-btn-well">
          <button type="button" class="wand-btn" data-${scope}-btn
                  aria-label="Wand button — tap, or hold for 0.45s"
                  title="Tap, or hold for 0.45s"></button>
        </div>
      </div>
    </div>`;
}

/**
 * Shadow-DOM CSS for everything this module builds. wand-sim.js
 * concatenates it into its own <style> so the rules live next to the DOM
 * that uses them.
 */
export const WAND_STYLE = `
/* ── Stage: gesture animation outside, 3D tilt inside, so a tilt change
   mid-gesture doesn't restart the keyframes ───────────────────────────── */
.wand-stage { position: relative; display: flex; align-items: center; justify-content: center; }
.wand-gesture { will-change: transform; }
.wand-tilt {
  transition: transform .22s cubic-bezier(.3,1.2,.5,1);
  transform-style: preserve-3d;
}
.wand-body { position: relative; pointer-events: auto; }

/* ── Case ───────────────────────────────────────────────────────────── */
.wand-case {
  position: relative; aspect-ratio: 439/730;
  border-radius: 13% / 7.8%; padding: 3.4% 3.6% 4.4%;
  background: linear-gradient(105deg, #a98bb7 0%, #bb9fc9 38%, #e9d9f4 100%);
  box-shadow:
    0 16px 30px rgba(108,76,209,.24),
    inset 0 1.5px 0 rgba(255,255,255,.6),
    inset 0 -2px 0 rgba(83,60,102,.35);
}
/* Width-driven, with height following from aspect-ratio. The pad it sits
   in is sized to suit (see .pad's min-height and the container queries in
   js/controls.js), rather than the wand trying to fit an unknown height --
   its wrappers carry no height of their own for a percentage to resolve
   against. --wand-art-width is the knob a host or a container query turns. */
.wand-case-main { width: var(--wand-art-width, 176px); }
.wand-case-mini { width: 66px; }

.wand-face {
  width: 100%; height: 100%; border-radius: 11.2% / 6.7%;
  background: linear-gradient(168deg, #ffffff 0%, #fdfdff 60%, #f4f2fa 100%);
  box-shadow: inset 0 2px 0 rgba(255,255,255,.9), 0 1px 3px rgba(83,60,102,.28);
  display: flex; flex-direction: column; padding: 7% 7.5% 6.5%;
}
.wand-back {
  width: 100%; height: 100%; border-radius: 11.2% / 6.7%;
  background: linear-gradient(105deg, #a68ab5 0%, #b699c6 40%, #d9c8ea 100%);
  box-shadow: inset 0 1.5px 0 rgba(255,255,255,.35), 0 1px 3px rgba(83,60,102,.25);
}
.wand-face[hidden], .wand-back[hidden], .wand-mini[hidden] { display: none; }

.wand-face-top { display: flex; align-items: flex-start; justify-content: space-between; width: 100%; }
.wand-mic {
  width: 7%; aspect-ratio: 1; border-radius: 50%;
  background: radial-gradient(circle at 34% 30%, #4a4550, #1d1a24);
  box-shadow: inset 0 -1px 1px rgba(0,0,0,.5);
}
.wand-speaker {
  width: 27%; aspect-ratio: 1; border-radius: 50%;
  background: radial-gradient(circle at 36% 28%, #3b3644 0%, #1a1720 55%, #0f0d14 100%);
  display: flex; align-items: center; justify-content: center;
}
.wand-speaker-mesh {
  width: 80%; height: 80%; border-radius: 50%;
  background: repeating-radial-gradient(circle, #302b39 0 1.5px, #14111a 1.5px 4px);
  display: flex; align-items: center; justify-content: center;
}
/* A melody.py note is ~150ms, so the dot fades rather than snapping. The
   LED panel deliberately gets a much shorter transition: game state (shake
   level, gesture training) should update as crisply as the real LEDs do. */
.wand-speaker-dot {
  width: 46%; height: 46%; border-radius: 50%;
  transition: background .4s ease-out, box-shadow .4s ease-out;
  background: ${SPEAKER_IDLE};
}

.wand-face-mid {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 9%; width: 100%; padding-top: 5%;
}
.wand-panel {
  width: 84%; aspect-ratio: 1; border-radius: 12%; background: #141119;
  box-shadow: inset 0 3px 10px rgba(0,0,0,.75), 0 0 0 1.5px rgba(83,60,102,.25);
  padding: 6.5%; display: grid; grid-template-columns: repeat(5, 1fr); gap: 6%;
}
.wand-led {
  aspect-ratio: 1; border-radius: 26%;
  transition: background .1s, box-shadow .1s;
  background: ${LED_OFF}; box-shadow: ${LED_OFF_GLOW};
}
.wand-btn-well {
  width: 52%; aspect-ratio: 1; border-radius: 50%; background: #f4f2fa;
  box-shadow: inset 0 2px 5px rgba(83,60,102,.3);
  display: flex; align-items: center; justify-content: center;
}
.wand-btn {
  width: 78%; height: 78%; border-radius: 50%; border: none; padding: 0;
  cursor: pointer; transition: transform .07s, box-shadow .07s;
  background: radial-gradient(circle at 34% 26%, #6a6472 0%, #332e3d 46%, #17141f 100%);
  box-shadow: ${BTN_UP_SHADOW};
}
.wand-btn:focus-visible { outline: 2px solid #ef4d92; outline-offset: 3px; }

/* ── "The hidden face": a live thumbnail of the front while the wand is
   turned over, so LED output stays readable face-down ─────────────────── */
.wand-mini {
  position: absolute; right: 5%; bottom: 5%;
  display: flex; flex-direction: column; align-items: flex-end; gap: 4px;
}
.wand-mini .wand-case {
  box-shadow: 0 0 0 4px #fff, 0 10px 20px rgba(108,76,209,.24);
}
.wand-mini .wand-face { background: linear-gradient(168deg, #ffffff 0%, #f4f2fa 100%); box-shadow: none; }
.wand-mini .wand-mic { background: #2a2632; box-shadow: none; }
.wand-mini .wand-speaker { background: #17141f; }
.wand-mini .wand-speaker-mesh { background: none; }
.wand-mini .wand-panel { box-shadow: none; }
.wand-mini .wand-btn-well { box-shadow: inset 0 1px 2px rgba(83,60,102,.3); }
/* Not interactive at this size — the full-size button is the control. */
.wand-mini .wand-btn { cursor: default; pointer-events: none; }
/* Reads against the back face's purple, not the pad's near-white, so it
   takes the darker ink rather than the muted grey used elsewhere. */
.wand-mini-caption {
  font: 400 13px 'Patrick Hand', 'Nunito', system-ui, sans-serif; color: #5b5468;
  line-height: 1; white-space: nowrap;
}

/* ── Motor + buzzer feedback ─────────────────────────────────────────── */
.wand-buzz {
  position: absolute; left: 0; right: 0; bottom: -4%;
  display: flex; justify-content: center; pointer-events: none;
}
.wand-buzz > span {
  padding: 3px 11px; border-radius: 20px; background: #f2eefc;
  border: 1.5px solid #ded8ec; color: #6c4cd1;
  font: 800 9px 'Nunito', system-ui, sans-serif; letter-spacing: .1em;
  transition: opacity .2s; opacity: 0;
}
.wand-agitron {
  position: absolute; pointer-events: none; font-weight: 800; color: #c2b8d6;
  animation: agitron .5s ease-out forwards;
}
.wand-ping {
  position: absolute; pointer-events: none; border-radius: 50%;
  right: 2%; top: 3%; width: 29%; aspect-ratio: 1;
  animation: ping .55s ease-out forwards;
}

@keyframes wandJump {
  0%   { transform: translateY(0) }
  22%  { transform: translateY(-46px) scaleY(1.04) }
  45%  { transform: translateY(2px) scaleY(.96) }
  62%  { transform: translateY(-14px) }
  80%  { transform: translateY(0) scaleY(1.02) }
  100% { transform: translateY(0) }
}
@keyframes wandShake {
  0%,100% { transform: translateX(0) rotate(0deg) }
  12% { transform: translateX(-13px) rotate(-4deg) }
  25% { transform: translateX(12px) rotate(4deg) }
  37% { transform: translateX(-11px) rotate(-3.4deg) }
  50% { transform: translateX(10px) rotate(3deg) }
  62% { transform: translateX(-7px) rotate(-2deg) }
  75% { transform: translateX(6px) rotate(1.6deg) }
  88% { transform: translateX(-3px) rotate(-.8deg) }
}
@keyframes wandFlip { 0% { transform: rotateY(0deg) } 100% { transform: rotateY(360deg) } }
@keyframes agitron {
  0%   { opacity: 0; transform: translate(0,0) scale(.5) }
  25%  { opacity: 1 }
  100% { opacity: 0; transform: translate(var(--dx), var(--dy)) scale(1.15) }
}
@keyframes ping {
  0%   { opacity: .85; transform: scale(.55) }
  100% { opacity: 0; transform: scale(1.5) }
}
@media (prefers-reduced-motion: reduce) {
  .wand-gesture { animation: none !important; }
  .wand-agitron, .wand-ping { animation-duration: .01ms; }
}
`;

/**
 * Builds the wand into `container` and returns handles for driving it.
 *
 * opts.displayGain — gain applied in linear space before sRGB encoding
 *   (physically what running the LED harder would do). Defaults to 1 since
 *   the gamma correction above already renders duty values at their real
 *   perceived brightness.
 * opts.onButtonTap(down) — fires from a real press on the drawn button.
 */
export function createRenderer(container, opts = {}) {
  const root = container;
  root.classList.add("wand-stage");

  let displayGain = opts.displayGain != null ? opts.displayGain : 1;

  root.innerHTML = `
    <div class="wand-gesture" data-el="gesture">
      <div class="wand-tilt" data-el="tilt">
        <div class="wand-body" data-el="body">
          <div class="wand-case wand-case-main">
            ${faceMarkup("main")}
            <div class="wand-back" data-el="back" hidden></div>
            <div class="wand-mini" data-el="mini" hidden>
              <div class="wand-mini-caption">the hidden face</div>
              <div class="wand-case wand-case-mini">${faceMarkup("mini")}</div>
            </div>
            <div class="wand-buzz"><span data-el="buzz">≋ BUZZ</span></div>
          </div>
        </div>
      </div>
    </div>`;

  const gestureEl = root.querySelector('[data-el="gesture"]');
  const tiltEl = root.querySelector('[data-el="tilt"]');
  const bodyEl = root.querySelector('[data-el="body"]');
  const frontEl = root.querySelector(".wand-face");
  const backEl = root.querySelector('[data-el="back"]');
  const miniEl = root.querySelector('[data-el="mini"]');
  const buzzEl = root.querySelector('[data-el="buzz"]');
  const btnEl = root.querySelector("[data-main-btn]");

  // Both faces' cells are driven together so the mini stays live.
  const ledEls = [];
  for (let i = 0; i < 25; i++) {
    ledEls.push([
      root.querySelector(`[data-main-led="${i}"]`),
      root.querySelector(`[data-mini-led="${i}"]`),
    ]);
  }
  const speakerEls = [
    root.querySelector("[data-main-speaker]"),
    root.querySelector("[data-mini-speaker]"),
  ];
  const miniBtnEl = root.querySelector("[data-mini-btn]");

  const timers = {};
  let seq = 0;
  let tapPressed = false;

  /** De-duped so a stray extra pointerdown/pointerup pair from the pointer
   * capture dance doesn't double-fire into the Python side. */
  function setTapPressed(down) {
    if (tapPressed === down) return;
    tapPressed = down;
    opts.onButtonTap?.(down);
  }

  btnEl.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    setTapPressed(true);
  });
  // Released window-wide: the pointer may well be off the button (or the
  // wand mid-animation) by the time it comes up.
  const release = () => setTapPressed(false);
  window.addEventListener("pointerup", release);
  window.addEventListener("pointercancel", release);
  // Keyboard activation has no pointerdown/up pair of its own, so a press
  // and its release are synthesised around the click.
  btnEl.addEventListener("keydown", (e) => {
    if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      setTapPressed(true);
    }
  });
  btnEl.addEventListener("keyup", (e) => {
    if (e.key === " " || e.key === "Enter") setTapPressed(false);
  });

  function applyFrame(pixels) {
    const list = pixels || [];
    for (let i = 0; i < 25; i++) {
      const p = list[i] || [0, 0, 0];
      const lit = (p[0] || 0) + (p[1] || 0) + (p[2] || 0) > 0;
      const css = lit ? dutyRgbToCss(p, displayGain) : LED_OFF;
      const glow = lit
        ? `0 0 10px ${css}, inset 0 0 4px rgba(255,255,255,.45)`
        : LED_OFF_GLOW;
      for (const el of ledEls[i]) {
        el.style.background = css;
        el.style.boxShadow = glow;
      }
    }
  }

  function setDisplayGain(g) {
    displayGain = Number(g) || 1;
  }

  function setButtonDown(down) {
    const shadow = down ? BTN_DOWN_SHADOW : BTN_UP_SHADOW;
    btnEl.style.boxShadow = shadow;
    btnEl.style.transform = down ? "translateY(4px)" : "none";
    // The mini's button is a fraction of the size, so the full 4px travel
    // would swallow it — 2px reads as the same press at that scale.
    miniBtnEl.style.boxShadow = down ? "0 0 0 #17141f" : "0 2px 0 #17141f";
    miniBtnEl.style.transform = down ? "translateY(2px)" : "none";
  }

  /** cssColor: a CSS color while the buzzer plays, or null/falsy for idle. */
  function setSpeakerColor(cssColor) {
    for (const el of speakerEls) {
      el.style.background = cssColor || SPEAKER_IDLE;
      el.style.boxShadow = cssColor ? `0 0 16px ${cssColor}` : "none";
    }
  }

  /** 3D tilt from the pad's -100..100 coordinates. */
  function setTilt3d(ax, ay) {
    tiltEl.style.transform =
      `perspective(950px) rotateY(${ax * 0.42}deg) rotateX(${-ay * 0.42}deg)`;
  }

  /**
   * Turn the wand over. The face swap lands partway through the flip
   * animation, so the case is edge-on when the front becomes the back
   * rather than cutting between them face-on.
   */
  function setFaceDown(down) {
    clearTimeout(timers.face);
    timers.face = setTimeout(() => {
      frontEl.hidden = !!down;
      backEl.hidden = !down;
      miniEl.hidden = !down;
    }, 300);
  }

  /**
   * Play a gesture animation for `ms`. The duration is the motion
   * program's own (js/motion.js's fireMove returns it), not a fixed
   * design value — the wand should stop moving when the accelerometer
   * stops reporting movement.
   */
  function playGesture(kind, ms) {
    const spec = GESTURE_ANIM[kind];
    if (!spec) return;
    const [name, easing] = spec;
    // Clearing and re-setting on a later frame is what restarts a
    // same-named animation; assigning over itself is a no-op.
    gestureEl.style.animation = "none";
    clearTimeout(timers.animOn);
    clearTimeout(timers.animOff);
    timers.animOn = setTimeout(() => {
      gestureEl.style.animation = `${name} ${ms}ms ${easing}`;
    }, 20);
    timers.animOff = setTimeout(() => {
      gestureEl.style.animation = "none";
    }, ms + 60);
  }

  /** Motor state: the BUZZ badge, plus agitrons for as long as it runs.
   * main.py's on_scan_complete() buzz is ~60ms and a game's can be much
   * longer, so this re-spawns rather than firing once on the rising edge. */
  function setMotor(on) {
    buzzEl.style.opacity = on ? "1" : "0";
    clearInterval(timers.agitron);
    if (!on) return;
    spawnAgitrons();
    timers.agitron = setInterval(spawnAgitrons, 240);
  }

  function spawnAgitrons() {
    const made = [];
    for (let k = 0; k < 7; k++) {
      const id = ++seq;
      const side = k % 2 ? 1 : -1;
      const up = k < 4 ? -1 : 1;
      const el = document.createElement("div");
      el.className = "wand-agitron";
      el.textContent = AGITRON_MARKS[k % AGITRON_MARKS.length];
      el.style.left = `${side < 0 ? -6 + Math.random() * 8 : 96 + Math.random() * 8}%`;
      el.style.top = `${10 + Math.random() * 72}%`;
      el.style.fontSize = `${11 + Math.random() * 8}px`;
      el.style.transform = `rotate(${Math.round(-30 + Math.random() * 60)}deg)`;
      el.style.setProperty("--dx", `${Math.round(side * (12 + Math.random() * 16))}px`);
      el.style.setProperty("--dy", `${Math.round(up * (6 + Math.random() * 14))}px`);
      el.dataset.id = String(id);
      bodyEl.appendChild(el);
      made.push(el);
    }
    setTimeout(() => made.forEach((el) => el.remove()), 520);
  }

  /** An expanding ring, one per note, in that note's speaker color. */
  function ping(color) {
    const el = document.createElement("div");
    el.className = "wand-ping";
    el.style.border = `3px solid ${color}`;
    bodyEl.appendChild(el);
    setTimeout(() => el.remove(), 560);
  }

  /** Drop the window-level listeners and pending timers. */
  function dispose() {
    window.removeEventListener("pointerup", release);
    window.removeEventListener("pointercancel", release);
    clearInterval(timers.agitron);
    Object.keys(timers).forEach((k) => clearTimeout(timers[k]));
  }

  setSpeakerColor(null);
  setButtonDown(false);

  return {
    applyFrame, setDisplayGain, setButtonDown, setSpeakerColor,
    setTilt3d, setFaceDown, playGesture, setMotor, spawnAgitrons, ping,
    dispose,
  };
}
