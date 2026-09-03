/**
 * Simulator control panel — filtered by the loaded game's capabilities
 * (py/runtime.py:get_capabilities()) so only inputs the game actually
 * reads are shown. Fixed group order regardless of what's present:
 * poses -> moves -> button -> tags. Everything else (battery, ambient
 * lux, raw tilt pad, freeform tag entry, ESPNow) lives in a collapsed
 * "Advanced" drawer.
 */

// Lucide icons (ISC license, https://lucide.dev), inlined so their
// stroke="currentColor" picks up the button's own text color — including
// its :hover/.down states — instead of a separate icon asset per state.
const LUCIDE_VOLUME_2 = `<svg class="icon-lucide" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.364 18.364a9 9 0 0 0 0-12.728"/></svg>`;
const LUCIDE_VOLUME_OFF = `<svg class="icon-lucide" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 9a5 5 0 0 1 .95 2.293"/><path d="M19.364 5.636a9 9 0 0 1 1.889 9.96"/><path d="m2 2 20 20"/><path d="m7 7-.587.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298V11"/><path d="M9.828 4.172A.686.686 0 0 1 11 4.657v.686"/></svg>`;

const POSE_LABELS = {
  tip_up: "Tip up",
  tip_down: "Tip down",
  left_up: "Left side up",
  right_up: "Right side up",
  face_up: "LEDs up",
  face_down: "LEDs down",
};
const POSE_ORDER = ["tip_up", "tip_down", "left_up", "right_up", "face_up", "face_down"];

// assets/wand/WandGestures/*.svg — hand-authored gesture illustrations.
// face_up/face_down have no icon yet (2D art can't show wand-facing
// depth convincingly per the author) and stay text-only. These are
// transition/rotation illustrations, not static single-pose portraits —
// used here as "move it like this" cues rather than literal snapshots.
const POSE_ICONS = {
  tip_up: "leftup_to_upright.svg",
  tip_down: "clockwise_to_upsidedown.svg",
  left_up: "upright_to_leftup.svg",
  right_up: "upright_to_rightup.svg",
};

const MOVE_LABELS = { jump: "Jump", shake: "Shake", flip: "Flip" };
const MOVE_ORDER = ["jump", "shake", "flip"];
// jump/shake mappings are the author's own call; flip has no clear match
// (it goes between whichever pose pair is opposite, not one fixed
// motion) so it stays icon-less rather than force a confusing pick.
const MOVE_ICONS = {
  jump: "shake_up_down.svg",
  shake: "wiggle_roll.svg",
};

function gestureIconUrl(file) {
  return new URL(`../assets/wand/WandGestures/${file}`, import.meta.url).href;
}

const BUTTON_LABEL = { tap: "Tap the button", hold: "Hold the button" };

// PLUNGER_LABEL_W is fixed so the widest label ("BIG shake!") doesn't
// change the control's width and shift it sideways in the row as the
// label text changes underneath it.
const PLUNGER_LABEL_W = 90;

function plungerLabel(intensity) {
  if (intensity < 0.05) return "Pull & let go";
  if (intensity < 0.35) return "Gentle";
  if (intensity < 0.7) return "Medium";
  return "BIG shake!";
}

/**
 * Non-latching, magnitude-by-release control: a plain range slider (same
 * native element as the Advanced drawer's Battery/Ambient lux, styled
 * identically by the same bare `input[type=range]` rule) fronted by the
 * wiggle_roll icon as its label. Drag it, release, and the value at the
 * moment of release becomes the gesture's intensity (0..1), passed to
 * `onRelease` — then it resets to 0 on its own. It never holds a "current"
 * value the way Battery/Lux do, since the underlying gesture is a
 * one-shot burst, not a held state.
 */
function createPlunger(onRelease) {
  const wrap = document.createElement("div");
  wrap.className = "plunger";
  wrap.innerHTML = `
    <img class="ctrl-icon-inline" alt="Shake" src="${gestureIconUrl("wiggle_roll.svg")}">
    <input type="range" min="0" max="100" value="0" data-act="plunger-range">
    <div class="plunger-label" style="width:${PLUNGER_LABEL_W}px">Pull &amp; let go</div>
  `;
  const range = wrap.querySelector('[data-act="plunger-range"]');
  const label = wrap.querySelector(".plunger-label");

  let lastIntensity = 0;

  range.addEventListener("input", () => {
    lastIntensity = Number(range.value) / 100;
    label.textContent = plungerLabel(lastIntensity);
  });
  // "change" covers both a released drag and a keyboard-committed step —
  // either way, that's the release point.
  range.addEventListener("change", () => {
    // A stray tap with no real pull shouldn't register as a shake.
    if (lastIntensity > 0.02) onRelease?.(lastIntensity);
    range.value = 0;
    label.textContent = "Pull & let go";
    lastIntensity = 0;
  });

  return wrap;
}

export function createControls(container, handlers = {}) {
  const root = container;
  root.classList.add("wand-controls");
  root.innerHTML = `
    <div class="ctrl-toolbar">
      <button type="button" data-act="mute" class="ctrl-btn icon-only" aria-pressed="false" aria-label="Mute" title="Mute">${LUCIDE_VOLUME_2}</button>
    </div>

    <div class="ctrl-group" data-group="poses" hidden>
      <div class="group-label">Orientation</div>
      <div class="group-row" data-el="poses"></div>
    </div>
    <div class="ctrl-group" data-group="moves" hidden>
      <div class="group-label">Moves</div>
      <div class="group-row" data-el="moves"></div>
    </div>
    <div class="ctrl-group" data-group="button" hidden>
      <div class="group-label">Button</div>
      <div class="group-row">
        <button type="button" data-act="button" class="ctrl-btn big">Press</button>
      </div>
    </div>
    <div class="ctrl-group" data-group="tags" hidden>
      <div class="group-label">Tags</div>
      <div class="group-row">
        <img class="ctrl-icon-inline" alt="NFC tag" src="${gestureIconUrl("readNFC.svg")}">
        <div class="nfc-tags" data-el="nfc-tags"></div>
      </div>
    </div>

    <div class="zero-state" data-el="zero-state" hidden>This game has no player controls — just watch it play.</div>

    <details class="advanced">
      <summary>Advanced</summary>
      <div class="hint" data-el="hint"></div>
      <div class="uses-row" data-el="uses"></div>
      <div class="adv-row">
        <button type="button" data-act="toggle-console" class="ctrl-btn" aria-pressed="false">Show console</button>
      </div>
      <div class="adv-row">
        <label>Battery <input type="range" data-act="battery" min="0" max="100" value="85"></label>
        <label>Ambient lux <input type="range" data-act="lux" min="10" max="20000" value="500"></label>
      </div>
      <div class="adv-row">
        <div class="tilt-pad" data-act="tilt" title="Free-form tilt (bypasses named poses)">
          <div class="tilt-knob"></div>
        </div>
        <div class="adv-tags">
          <label>Tap any tag
            <input type="text" data-act="free-tag-input" placeholder="e.g. stop">
          </label>
          <button type="button" data-act="free-tag-send" class="ctrl-btn">Tap</button>
        </div>
      </div>
      <div class="adv-row">
        <button type="button" data-act="stop" class="ctrl-btn">ESPNow: stop</button>
        <button type="button" data-act="start_game" class="ctrl-btn">ESPNow: start_game</button>
      </div>
      <div class="adv-row">
        <span class="adv-status">Buzzer: <span data-el="adv-buzzer-status">off</span></span>
        <span class="adv-status">Motor: <span data-el="adv-motor-status">off</span></span>
      </div>
    </details>
  `;

  const hintEl = root.querySelector('[data-el="hint"]');
  const usesEl = root.querySelector('[data-el="uses"]');
  const posesGroup = root.querySelector('[data-group="poses"]');
  const posesRow = root.querySelector('[data-el="poses"]');
  const movesGroup = root.querySelector('[data-group="moves"]');
  const movesRow = root.querySelector('[data-el="moves"]');
  const buttonGroup = root.querySelector('[data-group="button"]');
  const btn = root.querySelector('[data-act="button"]');
  const tagsGroup = root.querySelector('[data-group="tags"]');
  const nfcBox = root.querySelector('[data-el="nfc-tags"]');
  const zeroState = root.querySelector('[data-el="zero-state"]');

  const battery = root.querySelector('[data-act="battery"]');
  const lux = root.querySelector('[data-act="lux"]');
  const tilt = root.querySelector('[data-act="tilt"]');
  const knob = tilt.querySelector(".tilt-knob");
  const freeTagInput = root.querySelector('[data-act="free-tag-input"]');
  const freeTagSend = root.querySelector('[data-act="free-tag-send"]');

  // ── Persistent toolbar: mute (icon-only, the console toggle below
  // lives in the Advanced drawer instead) ─────────────────────────────
  const muteBtn = root.querySelector('[data-act="mute"]');
  let muted = false;
  function applyMuteVisual() {
    muteBtn.classList.toggle("down", muted);
    muteBtn.setAttribute("aria-pressed", String(muted));
    const label = muted ? "Unmute" : "Mute";
    muteBtn.setAttribute("aria-label", label);
    muteBtn.title = label;
    muteBtn.innerHTML = muted ? LUCIDE_VOLUME_OFF : LUCIDE_VOLUME_2;
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

  const consoleBtn = root.querySelector('[data-act="toggle-console"]');
  let consoleShown = false;
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

  // ── Button (tap or hold — same widget either way) ──────────────────
  btn.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    btn.setPointerCapture(e.pointerId);
    btn.classList.add("down");
    handlers.onButton?.(true);
  });
  const releaseBtn = (e) => {
    if (e.pointerId != null && btn.hasPointerCapture?.(e.pointerId)) {
      btn.releasePointerCapture(e.pointerId);
    }
    btn.classList.remove("down");
    handlers.onButton?.(false);
  };
  btn.addEventListener("pointerup", releaseBtn);
  btn.addEventListener("pointercancel", releaseBtn);

  // ── Poses: sticky, one active at a time ─────────────────────────────
  let activePose = "tip_up";
  /** Fills a button with an icon (if one exists for `name`) above its
   * text label; icon-less buttons just get the text, unchanged. */
  function fillIconButton(b, iconFile, label) {
    if (iconFile) {
      const img = document.createElement("img");
      img.className = "ctrl-icon";
      img.src = gestureIconUrl(iconFile);
      img.alt = "";
      b.appendChild(img);
    }
    b.appendChild(document.createTextNode(label));
  }

  function renderPoses(names) {
    posesRow.innerHTML = "";
    for (const name of names) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "ctrl-btn pose";
      fillIconButton(b, POSE_ICONS[name], POSE_LABELS[name] || name);
      b.classList.toggle("active", name === activePose);
      b.addEventListener("click", () => {
        activePose = name;
        for (const sib of posesRow.querySelectorAll(".pose")) sib.classList.remove("active");
        b.classList.add("active");
        handlers.onPose?.(name);
      });
      posesRow.appendChild(b);
    }
  }

  // ── Moves: one-shot gestures. Shake is a plunger (release-point
  // intensity), since shake.py's fill amount depends on how hard you
  // shake — jump/flip are plain buttons since neither game reads a
  // continuous magnitude for them (jump.py just counts freefall events).
  function renderMoves(names) {
    movesRow.innerHTML = "";
    for (const name of names) {
      if (name === "shake") {
        movesRow.appendChild(createPlunger((intensity) => handlers.onMove?.("shake", { intensity })));
        continue;
      }
      const b = document.createElement("button");
      b.type = "button";
      b.className = "ctrl-btn move";
      fillIconButton(b, MOVE_ICONS[name], MOVE_LABELS[name] || name);
      b.addEventListener("click", () => handlers.onMove?.(name));
      movesRow.appendChild(b);
    }
  }

  // ── Tags ──────────────────────────────────────────────────────────
  function renderTags(tags) {
    nfcBox.innerHTML = "";
    for (const cmd of tags) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "ctrl-btn";
      b.textContent = cmd;
      b.addEventListener("click", () => handlers.onNfc?.(cmd));
      nfcBox.appendChild(b);
    }
  }

  // ── Capability-driven layout ─────────────────────────────────────────
  function setCapabilities(caps) {
    const motion = new Set(caps?.motion || []);
    const poseNames = POSE_ORDER.filter((n) => motion.has(n));
    const moveNames = MOVE_ORDER.filter((n) => motion.has(n));
    const buttonKind = caps?.button || "none";
    const tags = caps?.nfcTags || [];

    hintEl.textContent = caps?.hint || "";
    hintEl.hidden = !caps?.hint;

    const uses = [];
    if (poseNames.length) uses.push("orientation");
    if (moveNames.length) uses.push("motion");
    if (buttonKind !== "none") uses.push(buttonKind === "hold" ? "hold button" : "button");
    if (tags.length) uses.push("tags");
    usesEl.textContent = uses.length ? "Uses: " + uses.join(", ") : "";
    usesEl.hidden = uses.length === 0;

    renderPoses(poseNames);
    posesGroup.hidden = poseNames.length === 0;

    renderMoves(moveNames);
    movesGroup.hidden = moveNames.length === 0;

    buttonGroup.hidden = buttonKind === "none";
    btn.textContent = BUTTON_LABEL[buttonKind] || "Press";

    renderTags(tags);
    tagsGroup.hidden = tags.length === 0;

    zeroState.hidden = !(poseNames.length === 0 && moveNames.length === 0 &&
      buttonKind === "none" && tags.length === 0);
  }

  // ── Advanced drawer ───────────────────────────────────────────────
  battery.addEventListener("input", () => handlers.onBattery?.(Number(battery.value)));
  lux.addEventListener("input", () => handlers.onLux?.(Number(lux.value)));

  let tilting = false;
  function setKnob(nx, ny) {
    knob.style.left = `${50 + nx * 40}%`;
    knob.style.top = `${50 + ny * 40}%`;
  }
  setKnob(0, 0);
  function tiltFromEvent(e) {
    const rect = tilt.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const y = ((e.clientY - rect.top) / rect.height) * 2 - 1;
    const nx = Math.max(-1, Math.min(1, x));
    const ny = Math.max(-1, Math.min(1, y));
    setKnob(nx, ny);
    handlers.onTilt?.(nx, ny);
  }
  tilt.addEventListener("pointerdown", (e) => {
    tilting = true;
    tilt.setPointerCapture(e.pointerId);
    tiltFromEvent(e);
  });
  tilt.addEventListener("pointermove", (e) => { if (tilting) tiltFromEvent(e); });
  tilt.addEventListener("pointerup", () => { tilting = false; });
  tilt.addEventListener("pointercancel", () => { tilting = false; });

  function sendFreeTag() {
    const cmd = freeTagInput.value.trim().toLowerCase();
    if (cmd) handlers.onNfc?.(cmd);
  }
  freeTagSend.addEventListener("click", sendFreeTag);
  freeTagInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendFreeTag();
  });

  root.querySelector('[data-act="stop"]').addEventListener("click", () => handlers.onEnow?.("stop"));
  root.querySelector('[data-act="start_game"]').addEventListener("click", () => handlers.onEnow?.("start_game"));

  function resetPose() {
    activePose = "tip_up";
    for (const b of posesRow.querySelectorAll(".pose")) {
      b.classList.toggle("active", b.textContent === POSE_LABELS.tip_up);
    }
  }

  // The raw Hz/on-off detail lives here instead of on the main icon-only
  // indicator chips — not something a kindergarten-teacher audience needs
  // to see by default, but still available for anyone curious enough to
  // open Advanced.
  const advBuzzerStatus = root.querySelector('[data-el="adv-buzzer-status"]');
  const advMotorStatus = root.querySelector('[data-el="adv-motor-status"]');
  function setBuzzerStatus(text) {
    if (advBuzzerStatus) advBuzzerStatus.textContent = text;
  }
  function setMotorStatus(text) {
    if (advMotorStatus) advMotorStatus.textContent = text;
  }

  return {
    setCapabilities, setMuted, setConsoleShown, resetPose,
    setBuzzerStatus, setMotorStatus, root,
  };
}
