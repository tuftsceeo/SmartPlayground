/**
 * Web Audio oscillator driven by PWM freq/duty, plus visual indicators
 * for buzzer and vibration motor.
 */

function gestureIconUrl(file) {
  return new URL(`../assets/wand/WandGestures/${file}`, import.meta.url).href;
}

export function createAudio(opts = {}) {
  let ctx = null;
  let osc = null;
  let gain = null;
  let currentFreq = 0;
  let currentDuty = 0;
  let motorOn = false;
  let muted = false;
  // Chrome's autoplay policy blocks AudioContext.resume() until a real
  // user gesture (see unlock()) -- before that, ensureCtx() would just
  // fail (and log a console warning) on every PWM write the game loop
  // makes. Skip the attempt until unlock() has actually run.
  let unlocked = false;

  const buzzEl = opts.buzzerEl || null;
  const motorEl = opts.motorEl || null;
  const buzzIcon = buzzEl?.querySelector(".ind-icon") || null;
  const motorIcon = motorEl?.querySelector(".ind-icon") || null;
  // The main indicator chips are icon-only (a kindergarten-teacher
  // audience doesn't need a raw Hz readout) — these report the detail
  // for whoever wires it into the Advanced drawer instead.
  const onBuzzerChange = opts.onBuzzerChange || null;
  const onMotorChange = opts.onMotorChange || null;

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
      // sound.svg's artwork is padded into a larger viewBox than
      // no_sound.svg's, so at a fixed icon size the "on" icon renders
      // visibly smaller than the "off" one. The size-matched re-export
      // this used to point at (sound2.svg) was never added to
      // assets/wand/WandGestures/ and 404'd on every buzzer change, which
      // left the indicator blank -- a slightly small icon beats none.
      if (buzzIcon) buzzIcon.src = gestureIconUrl(on ? "sound.svg" : "no_sound.svg");
      onBuzzerChange?.(on, currentFreq);
    }
    if (motorEl) {
      motorEl.classList.toggle("active", motorOn);
      // vibrate.svg for the same reason as sound.svg above -- the
      // re-exported vibration.svg it named isn't in the assets folder.
      if (motorIcon) motorIcon.src = gestureIconUrl(motorOn ? "vibrate.svg" : "no_vibrate.svg");
      onMotorChange?.(motorOn);
    }
  }

  function setPwm(freq, duty) {
    currentFreq = Number(freq) || 0;
    currentDuty = Number(duty) || 0;
    const audio = unlocked ? ensureCtx() : null;
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
    unlocked = true;
    ensureCtx();
  }

  function dispose() {
    setPwm(0, 0);
    if (ctx) {
      try { ctx.close(); } catch (_) { /* */ }
      ctx = null;
    }
  }

  updateIndicators(); // set the initial no_sound/no_vibrate icons, not just a blank <img>

  return { setPwm, setMotor, setMuted, isMuted, unlock, dispose };
}
