/**
 * frameThrottle.js -- ack-gated single-frame-in-flight coalescer, plus the
 * power gate the plan calls for: the browser can now hold an arbitrary
 * bright frame on the matrix indefinitely, which the Python tool never
 * could, and readme.md measured real failures well under a full-bright
 * 256px frame. See the plan §Power guard / §Brightness control.
 *
 * CURRENT ESTIMATE IS APPROXIMATE, not a calibrated measurement -- it
 * uses a commonly-cited WS2812B figure (~20mA per color channel at full
 * duty) applied to the post-intensity, post-floor duty bytes actually
 * being sent. The default ceiling matches the 5V/3A driver board rating
 * from readme.md; the "12V / power injection" toggle raises it to a
 * looser, still-unverified bound -- see the plan's hardware risk list.
 * Treat both numbers as a guardrail, not a spec.
 */

const MA_PER_CHANNEL_AT_FULL = 20; // commonly-cited WS2812B datasheet figure
const CEILING_5V_MA = 3000; // readme.md: driver board rated 5V/3A
const CEILING_12V_MA = 4000; // readme.md: 12V/2A board + injection headroom -- UNVERIFIED, see docstring
const FLASH_ANYWAY_MS = 2000;

/** Estimated current draw for a post-intensity, post-floor 768-byte frame. */
export function estimateCurrentMa(frame) {
  let sum = 0;
  for (let i = 0; i < frame.length; i++) sum += frame[i];
  return (sum / 255) * MA_PER_CHANNEL_AT_FULL;
}

/** Highest intensity (0..original) that would bring `authoredFrame` under `ceilingMa`. */
export function suggestSafeIntensity(authoredFrame, ceilingMa, currentIntensity) {
  let sum = 0;
  for (let i = 0; i < authoredFrame.length; i++) sum += authoredFrame[i];
  if (sum === 0) return currentIntensity;
  // estimateCurrentMa scales linearly with the post-intensity duty sum,
  // which itself scales ~linearly with intensity (ignoring the CH_FLOOR
  // and per-byte truncation, both small at this resolution).
  const maxSumForCeiling = (ceilingMa * 255) / MA_PER_CHANNEL_AT_FULL;
  const scale = maxSumForCeiling / sum;
  return Math.max(0.02, Math.min(currentIntensity, currentIntensity * scale));
}

export class FrameThrottle {
  constructor(link) {
    this.link = link;
    this.inFlight = false;
    this.latest = null; // most recent {authored, scaled} requested while inFlight
    this.lastSent = null; // last frame actually written to the wire
    this.ceilingMa = CEILING_5V_MA;
    this.twelveVMode = false;
    this._flashTimer = null;
  }

  setTwelveVMode(on) {
    this.twelveVMode = on;
    this.ceilingMa = on ? CEILING_12V_MA : CEILING_5V_MA;
  }

  _sameFrame(a, b) {
    if (!a || !b || a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
    return true;
  }

  /**
   * Request a frame push. `scaled` is the post-intensity, post-floor
   * 768-byte frame actually estimated for the power gate (the device
   * applies intensity itself from `authored`, but the estimate has to
   * reflect what will actually be lit).
   * @returns {{sent:boolean, refused?:boolean, estimatedMa?, suggestion?}}
   */
  request(authored, scaled) {
    const estimatedMa = estimateCurrentMa(scaled);
    if (estimatedMa > this.ceilingMa) {
      return {
        sent: false,
        refused: true,
        estimatedMa,
        ceilingMa: this.ceilingMa,
      };
    }
    this._push(authored);
    return { sent: true, estimatedMa, ceilingMa: this.ceilingMa };
  }

  /** Bypass the gate for FLASH_ANYWAY_MS, then drop back to the last safe frame (or clear). */
  async flashAnyway(authored, safeAuthored) {
    if (this._flashTimer) clearTimeout(this._flashTimer);
    this._push(authored);
    this._flashTimer = setTimeout(() => {
      this._flashTimer = null;
      if (safeAuthored) this._push(safeAuthored);
      else this.link.clear().catch(() => {});
    }, FLASH_ANYWAY_MS);
  }

  cancelFlash() {
    if (this._flashTimer) {
      clearTimeout(this._flashTimer);
      this._flashTimer = null;
    }
  }

  _push(authored) {
    if (this._sameFrame(authored, this.lastSent)) return; // dedupe identical frames
    if (this.inFlight) {
      this.latest = authored;
      return;
    }
    this._send(authored);
  }

  async _send(authored) {
    this.inFlight = true;
    this.lastSent = authored;
    try {
      await this.link.sendFrame(authored, { ack: true });
    } catch (e) {
      console.warn("frameThrottle: sendFrame failed", e);
    } finally {
      this.inFlight = false;
      if (this.latest && !this._sameFrame(this.latest, this.lastSent)) {
        const next = this.latest;
        this.latest = null;
        this._send(next);
      }
    }
  }
}
