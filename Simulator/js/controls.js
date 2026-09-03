/**
 * Simulator control panel — filtered by the loaded game's capabilities
 * (py/runtime.py:get_capabilities()) so only inputs the game actually
 * reads are shown. Fixed group order regardless of what's present:
 * poses -> moves -> button -> tags. Everything else (battery, ambient
 * lux, raw tilt pad, freeform tag entry, ESPNow) lives in a collapsed
 * "Advanced" drawer.
 */

const POSE_LABELS = {
  tip_up: "Tip up",
  tip_down: "Tip down",
  left_up: "Left side up",
  right_up: "Right side up",
  face_up: "LEDs up",
  face_down: "LEDs down",
};
const POSE_ORDER = ["tip_up", "tip_down", "left_up", "right_up", "face_up", "face_down"];

const MOVE_LABELS = { jump: "Jump", shake: "Shake", flip: "Flip" };
const MOVE_ORDER = ["jump", "shake", "flip"];

const BUTTON_LABEL = { tap: "Tap the button", hold: "Hold the button" };

// Plunger geometry (pinball-launcher style shake control — see
// createPlunger below).
const PLUNGER_TRACK_H = 110;
const PLUNGER_HANDLE = 26;
const PLUNGER_RANGE = PLUNGER_TRACK_H - PLUNGER_HANDLE;

function plungerLabel(intensity) {
  if (intensity < 0.05) return "Pull & let go";
  if (intensity < 0.35) return "Gentle";
  if (intensity < 0.7) return "Medium";
  return "BIG shake!";
}

/**
 * Non-latching, magnitude-by-release control: drag the handle down (like
 * pulling a pinball plunger), release, and the pulled-back distance at the
 * moment of release becomes the gesture's intensity (0..1) — passed to
 * `onRelease`. The handle then springs back to rest on its own; it never
 * reflects a "current" value the way a slider does, since the underlying
 * gesture is a one-shot burst, not a held state.
 */
function createPlunger(onRelease) {
  const wrap = document.createElement("div");
  wrap.className = "plunger";
  wrap.innerHTML = `
    <div class="plunger-track" style="height:${PLUNGER_TRACK_H}px" data-act="plunger-track">
      <div class="plunger-fill"></div>
      <div class="plunger-handle"></div>
    </div>
    <div class="plunger-label">Pull &amp; let go</div>
  `;
  const track = wrap.querySelector(".plunger-track");
  const fill = wrap.querySelector(".plunger-fill");
  const handle = wrap.querySelector(".plunger-handle");
  const label = wrap.querySelector(".plunger-label");

  function setPull(px, animate) {
    handle.style.transition = animate ? "top 180ms cubic-bezier(.2,1.4,.4,1)" : "none";
    handle.style.top = px + "px";
    fill.style.transition = animate ? "height 180ms cubic-bezier(.2,1.4,.4,1)" : "none";
    fill.style.height = px + PLUNGER_HANDLE / 2 + "px";
  }
  setPull(0, false);

  let dragging = false;
  let lastIntensity = 0;

  function pullFromEvent(e) {
    const rect = track.getBoundingClientRect();
    const y = Math.max(0, Math.min(PLUNGER_RANGE, e.clientY - rect.top - PLUNGER_HANDLE / 2));
    setPull(y, false);
    const intensity = PLUNGER_RANGE > 0 ? y / PLUNGER_RANGE : 0;
    label.textContent = plungerLabel(intensity);
    return intensity;
  }

  track.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    track.setPointerCapture(e.pointerId);
    dragging = true;
    lastIntensity = pullFromEvent(e);
  });
  track.addEventListener("pointermove", (e) => {
    if (dragging) lastIntensity = pullFromEvent(e);
  });
  const release = (e) => {
    if (!dragging) return;
    dragging = false;
    if (e.pointerId != null && track.hasPointerCapture?.(e.pointerId)) {
      track.releasePointerCapture(e.pointerId);
    }
    // A stray tap with no real pull shouldn't register as a shake.
    if (lastIntensity > 0.02) onRelease?.(lastIntensity);
    setPull(0, true);
    label.textContent = "Pull & let go";
    lastIntensity = 0;
  };
  track.addEventListener("pointerup", release);
  track.addEventListener("pointercancel", release);

  return wrap;
}

export function createControls(container, handlers = {}) {
  const root = container;
  root.classList.add("wand-controls");
  root.innerHTML = `
    <div class="ctrl-toolbar">
      <button type="button" data-act="mute" class="ctrl-btn" aria-pressed="false">🔊 Mute</button>
      <button type="button" data-act="toggle-console" class="ctrl-btn" aria-pressed="false">Show console</button>
    </div>
    <div class="hint" data-el="hint"></div>
    <div class="uses-row" data-el="uses"></div>

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
      <div class="group-row nfc-tags" data-el="nfc-tags"></div>
    </div>

    <div class="zero-state" data-el="zero-state" hidden>This game has no player controls — just watch it play.</div>

    <details class="advanced">
      <summary>Advanced</summary>
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

  // ── Persistent toolbar: mute + console toggle ──────────────────────
  const muteBtn = root.querySelector('[data-act="mute"]');
  let muted = false;
  function applyMuteVisual() {
    muteBtn.classList.toggle("down", muted);
    muteBtn.setAttribute("aria-pressed", String(muted));
    muteBtn.textContent = muted ? "🔇 Muted" : "🔊 Mute";
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
  function renderPoses(names) {
    posesRow.innerHTML = "";
    for (const name of names) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "ctrl-btn pose";
      b.textContent = POSE_LABELS[name] || name;
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
      b.textContent = MOVE_LABELS[name] || name;
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

  return { setCapabilities, setMuted, setConsoleShown, resetPose, root };
}
