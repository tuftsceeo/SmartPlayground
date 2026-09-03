/**
 * Web Audio oscillator driven by PWM freq/duty, plus visual indicators
 * for buzzer and vibration motor.
 */

export function createAudio(opts = {}) {
  let ctx = null;
  let osc = null;
  let gain = null;
  let currentFreq = 0;
  let currentDuty = 0;
  let motorOn = false;
  let muted = false;

  const buzzEl = opts.buzzerEl || null;
  const motorEl = opts.motorEl || null;

  function ensureCtx() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
    }
    if (ctx.state === "suspended") ctx.resume().catch(() => {});
    return ctx;
  }

  function updateIndicators() {
    if (buzzEl) {
      const on = currentFreq > 0 && currentDuty > 0;
      buzzEl.classList.toggle("active", on);
      buzzEl.textContent = on ? `${currentFreq} Hz` : "buzzer";
    }
    if (motorEl) {
      motorEl.classList.toggle("active", motorOn);
    }
  }

  function setPwm(freq, duty) {
    currentFreq = Number(freq) || 0;
    currentDuty = Number(duty) || 0;
    const audio = ensureCtx();
    const on = currentFreq > 20 && currentDuty > 0;

    if (!on) {
      if (osc) {
        try { osc.stop(); } catch (_) { /* */ }
        try { osc.disconnect(); } catch (_) { /* */ }
        osc = null;
        gain = null;
      }
      updateIndicators();
      return;
    }

    if (!audio) {
      updateIndicators();
      return;
    }

    if (!osc) {
      osc = audio.createOscillator();
      gain = audio.createGain();
      osc.type = "square";
      osc.connect(gain);
      gain.connect(audio.destination);
      osc.start();
    }
    osc.frequency.setValueAtTime(currentFreq, audio.currentTime);
    // duty_u16 0..65535 → gain 0..0.12
    const level = muted ? 0 : Math.min(0.12, (currentDuty / 65535) * 0.12);
    gain.gain.setValueAtTime(level, audio.currentTime);
    updateIndicators();
  }

  function setMotor(on) {
    motorOn = !!on;
    updateIndicators();
  }

  function setMuted(v) {
    muted = !!v;
    if (gain && ctx) {
      const level = muted ? 0 : Math.min(0.12, (currentDuty / 65535) * 0.12);
      gain.gain.setValueAtTime(level, ctx.currentTime);
    }
  }

  function isMuted() {
    return muted;
  }

  /**
   * Chrome's autoplay policy only honors AudioContext.resume() when it's
   * called synchronously from within a real user-gesture handler (click /
   * pointerdown / keydown). setPwm()/setMotor() are driven by the Python
   * game loop through Pyodide's async bridge — several ticks removed from
   * whatever click triggered them — so resume() called from there silently
   * fails and keeps failing on every later PWM write. Call this directly
   * from a pointerdown/click listener (wand-sim.js does, on the whole
   * panel) so the very first real tap unlocks it for everything after.
   */
  function unlock() {
    ensureCtx();
  }

  function dispose() {
    setPwm(0, 0);
    if (ctx) {
      try { ctx.close(); } catch (_) { /* */ }
      ctx = null;
    }
  }

  return { setPwm, setMotor, setMuted, isMuted, unlock, dispose };
}
