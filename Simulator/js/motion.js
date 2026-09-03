/**
 * Motion model — sticky orientation poses + one-shot/held gestures that
 * settle back to the currently-held pose.
 *
 * Orientation convention: ChatApp/knowledge/knowledge.py §9 ("confirmed
 * from calibration") documents wand held upright (tip up) -> y=+1, left
 * side up -> x=+1, LED face up -> z=-1 -- but the actual on-hand hardware
 * has its x/y axes swapped from that (up-down and left-right are
 * flipped), so x and y are swapped here from that documented mapping.
 * z (LED face up/down) is unaffected.
 *
 *   tip up (rest)     (+1, 0, 0)
 *   tip down          (-1, 0, 0)
 *   left side up      (0, +1, 0)
 *   right side up     (0, -1, 0)
 *   LED face up       (0, 0, -1)
 *   LED face down     (0, 0, +1)
 *
 * A pose LATCHES: it's the gravity vector reported at rest until changed.
 * A gesture (jump/shake/flip/wiggle) plays a short synthetic motion on top
 * of the latched pose and, except flip, settles back to it when done.
 *
 * We intentionally don't model hardware fidelity (noise, debounce, sensor
 * bandwidth) — we own both ends of this pipe, so a gesture only needs to
 * cross the same numeric thresholds the game code tests.
 */

export const POSES = {
  tip_up:    { x: 1, y: 0, z: 0 },
  tip_down:  { x: -1, y: 0, z: 0 },
  left_up:   { x: 0, y: 1, z: 0 },
  right_up:  { x: 0, y: -1, z: 0 },
  face_up:   { x: 0, y: 0, z: -1 },
  face_down: { x: 0, y: 0, z: 1 },
};

const OPPOSITE = {
  tip_up: "tip_down", tip_down: "tip_up",
  left_up: "right_up", right_up: "left_up",
  face_up: "face_down", face_down: "face_up",
};

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

function normalize(v) {
  const mag = Math.hypot(v.x, v.y, v.z) || 1;
  return { x: v.x / mag, y: v.y / mag, z: v.z / mag };
}

function lerp(a, b, t) {
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, z: a.z + (b.z - a.z) * t };
}

// ── Latched state ──────────────────────────────────────────────────
let base = { ...POSES.tip_up };
let program = null; // { start, duration, sample(tMs, base) -> vec, endPose? } or null

export function setPose(name) {
  const v = POSES[name];
  if (v) base = { ...v };
}

export function getPose() {
  for (const [name, v] of Object.entries(POSES)) {
    if (Math.abs(v.x - base.x) < 1e-6 && Math.abs(v.y - base.y) < 1e-6 && Math.abs(v.z - base.z) < 1e-6) {
      return name;
    }
  }
  return null; // free-form (tilt pad)
}

/** Free-form tilt pad: sets the latched base directly from a 2D pad
 * position rather than a named pose. nx (left-right drag) and the
 * upright-residual magnitude are swapped onto y/x respectively, same
 * x/y swap as POSES above -- the pad's own left-right/up-down feel is
 * unchanged, only which accelerometer axis reports it. */
export function setTilt(nx, ny) {
  const tx = clamp(Number(nx) || 0, -1, 1);
  const ty = clamp(Number(ny) || 0, -1, 1);
  const x = 1 - Math.abs(ty) * 0.85;
  const y = tx;
  const z = -ty;
  base = normalize({ x, y, z });
}

function now() {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}

// ── Gesture programs ────────────────────────────────────────────────
// Raised-cosine envelope: 0 at t=0 and t=1, peaks at 1 in the middle.
function raisedCosine(t) {
  return (1 - Math.cos(2 * Math.PI * clamp(t, 0, 1))) / 2;
}

function jumpProgram() {
  const RAMP = 60, FLAT = 150, LAND = 120;
  const duration = RAMP + FLAT + LAND;
  return {
    duration,
    sample(t, b) {
      let mag;
      if (t < RAMP) {
        mag = 1 - raisedCosine(t / RAMP) * 0.95; // 1.0 -> 0.05
      } else if (t < RAMP + FLAT) {
        mag = 0.05;
      } else {
        const u = (t - RAMP - FLAT) / LAND;
        mag = 0.05 + raisedCosine(clamp(u, 0, 1)) * 1.65; // overshoot to ~1.7g, settle to 1
      }
      const dir = normalize(b);
      return { x: dir.x * mag, y: dir.y * mag, z: dir.z * mag };
    },
  };
}

// intensity 0..1 -> peak gravity-subtracted excess, calibrated so
// intensity reads as "how many LEDs light up" rather than raw g-force.
// shake.py fills level = floor(excess**3 * 1.5) (cubic in excess), so a
// linear intensity->excess mapping is all-or-nothing: most of the 0..1
// range does nothing and the last stretch instantly floods the grid.
// Using a cube-root response here cancels that cube, making level rise
// ~linearly with intensity instead. 2.6g excess is shake.py's full-grid
// point (excess**3 * 1.5 >= 25) and lands shake_rainbow.py at its top
// color too (needs ~2.58g); intensity 0 means "not shaking" (0g excess).
function shakeExcess(intensity) {
  return 2.6 * Math.cbrt(clamp(intensity, 0, 1));
}

function shakeProgram(intensity, durationMs) {
  const peak = shakeExcess(intensity);
  const freq = 7; // Hz
  return {
    duration: durationMs,
    sample(t, b) {
      const tSec = t / 1000;
      const env = raisedCosine(clamp(t / (durationMs * 0.4), 0, 1)); // ramp up, then held by loop below
      const osc = Math.abs(Math.sin(2 * Math.PI * freq * tSec));
      const mag = 1 + peak * (t < durationMs * 0.4 ? env : 1) * osc;
      const wobble = Math.sin(tSec * 3) * 0.35; // slow precession so direction isn't static
      const dir0 = normalize(b);
      const dir = normalize({
        x: dir0.x + wobble * (dir0.y - dir0.z),
        y: dir0.y + wobble * (dir0.z - dir0.x),
        z: dir0.z + wobble * (dir0.x - dir0.y),
      });
      return { x: dir.x * mag, y: dir.y * mag, z: dir.z * mag };
    },
  };
}

function flipProgram(durationMs) {
  const startPose = getPose() || "tip_up";
  const endName = OPPOSITE[startPose] || "tip_down";
  const from = normalize(base);
  const to = normalize(POSES[endName]);
  return {
    duration: durationMs,
    endPose: endName,
    sample(t) {
      const u = raisedCosine(clamp(t / durationMs, 0, 1));
      return lerp(from, to, u);
    },
  };
}

function wiggleProgram(durationMs) {
  const peak = 0.35;
  const freq = 5;
  return {
    duration: durationMs,
    sample(t, b) {
      const tSec = t / 1000;
      const env = raisedCosine(clamp(t / durationMs, 0, 1));
      const osc = Math.sin(2 * Math.PI * freq * tSec);
      const dir = normalize(b);
      const mag = 1 + peak * env * Math.abs(osc);
      return { x: dir.x * mag, y: dir.y * mag, z: dir.z * mag };
    },
  };
}

/**
 * Fire a one-shot (or, for shake, optionally held) gesture on top of the
 * currently latched pose. Returns the duration in ms (0 if unknown kind).
 */
export function fireMove(kind, opts = {}) {
  let prog;
  if (kind === "jump") {
    prog = jumpProgram();
  } else if (kind === "shake") {
    prog = shakeProgram(opts.intensity != null ? opts.intensity : 1, opts.durationMs || 900);
  } else if (kind === "flip") {
    prog = flipProgram(opts.durationMs || 500);
  } else if (kind === "wiggle") {
    prog = wiggleProgram(opts.durationMs || 800);
  } else {
    return 0;
  }
  program = { ...prog, start: now() };
  return prog.duration;
}

export function cancelMove() {
  program = null;
}

export function isMoving() {
  return program !== null;
}

/** Sample the current acceleration vector (in g) at time `t` (ms, default now). */
export function tick(t = now()) {
  if (program) {
    const elapsed = t - program.start;
    if (elapsed >= program.duration) {
      if (program.endPose) base = { ...POSES[program.endPose] };
      program = null;
      return { ...base };
    }
    return program.sample(elapsed, base);
  }
  return { ...base };
}

export function getAccel(t) {
  return tick(t);
}
