/**
 * One virtual clock shared by every simulated device and peer.
 *
 * Each wand's py/shims/time_patch.py reads nowMs() through
 * set_clock_source(), and bus.js schedules deliveries on it, so timeouts
 * such as WAND_LOST_MS and heartbeat intervals are measured against the
 * same time base on every device.
 *
 * Two modes:
 * - running (default): virtual time = real elapsed time * scale.
 * - manual: time moves only through advance(); used by headless tests.
 */

export function createClock(opts = {}) {
  const realNow = opts.realNow || (() => performance.now());
  let manual = !!opts.manual;
  let scale = opts.scale ?? 1;
  let paused = false;
  // Virtual ms at the last rebase, and the real ms it was taken at.
  let baseVirtual = 0;
  let baseReal = realNow();

  if (!(scale > 0)) throw new RangeError(`clock scale must be > 0, got ${scale}`);

  function nowMs() {
    if (manual || paused) return baseVirtual;
    return baseVirtual + (realNow() - baseReal) * scale;
  }

  function rebase() {
    baseVirtual = nowMs();
    baseReal = realNow();
  }

  return {
    nowMs,
    getScale: () => scale,
    setScale(k) {
      if (!(k > 0)) throw new RangeError(`clock scale must be > 0, got ${k}`);
      rebase();
      scale = k;
    },
    isManual: () => manual,
    setManual(on) {
      rebase();
      manual = !!on;
    },
    pause() {
      rebase();
      paused = true;
    },
    resume() {
      baseReal = realNow();
      paused = false;
    },
    isPaused: () => paused,
    /** Move virtual time forward. Allowed in any mode. */
    advance(ms) {
      if (!(ms >= 0)) throw new RangeError(`advance needs ms >= 0, got ${ms}`);
      rebase();
      baseVirtual += ms;
    },
    /** Real ms that correspond to `virtualMs` at the current scale. */
    toRealMs(virtualMs) {
      return virtualMs / scale;
    },
  };
}

/** The page-wide clock. Pages that need isolation call createClock(). */
export const sharedClock = createClock();
