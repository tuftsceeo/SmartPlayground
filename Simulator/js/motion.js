/**
 * Motion model — tilt pad, hold-to-shake, jump/freefall pulse.
 * Single source of (x, y, z) in g for the fake LIS2DW12.
 *
 * Orientation convention (wand tip up, LED face toward user):
 *   tip up        → y = +1
 *   LED face up   → z = -1
 *   tip left      → x = +1
 */

const JUMP_MAG = 0.05;
const JUMP_MS = 150;

let tiltX = 0; // -1..1 left/right
let tiltY = 0; // -1..1 tip down/up (0 = tip up)
let shaking = false;
let shakeIntensity = 0.5; // 0..1
let jumpUntil = 0;
let shakePhase = 0;

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

/** Gravity vector from tilt pad position. */
function gravityFromTilt() {
  // tiltX: negative = tip right → x negative; positive = tip left → x = +1
  // tiltY: 0 = tip up (y=+1); +1 = tip toward user / LED face up-ish (z toward -1)
  const tx = clamp(tiltX, -1, 1);
  const ty = clamp(tiltY, -1, 1);
  let x = tx;
  let y = 1 - Math.abs(ty) * 0.85;
  let z = -ty;
  // Normalize to ~1g
  const mag = Math.hypot(x, y, z) || 1;
  return { x: x / mag, y: y / mag, z: z / mag };
}

export function setTilt(x, y) {
  tiltX = clamp(Number(x) || 0, -1, 1);
  tiltY = clamp(Number(y) || 0, -1, 1);
}

export function startShake(intensity = 0.5) {
  shaking = true;
  shakeIntensity = clamp(intensity, 0, 1);
}

export function stopShake() {
  shaking = false;
}

export function setShakeIntensity(intensity) {
  shakeIntensity = clamp(intensity, 0, 1);
}

export function triggerJump(now = performance.now()) {
  jumpUntil = now + JUMP_MS;
}

export function tick(now = performance.now()) {
  if (now < jumpUntil) {
    return { x: 0, y: 0, z: JUMP_MAG };
  }
  const g = gravityFromTilt();
  if (!shaking || shakeIntensity <= 0) {
    return g;
  }
  shakePhase += 0.35 + shakeIntensity * 0.8;
  const amp = 0.4 + shakeIntensity * 2.5;
  return {
    x: g.x + Math.sin(shakePhase) * amp,
    y: g.y + Math.cos(shakePhase * 1.3) * amp * 0.7,
    z: g.z + Math.sin(shakePhase * 0.9) * amp * 0.5,
  };
}

export function getAccel(now = performance.now()) {
  return tick(now);
}
