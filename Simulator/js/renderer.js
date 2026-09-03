/**
 * 5x5 LED grid renderer.
 * applyFrame(pixels) where pixels is an array of [r,g,b] (0-255).
 *
 * Incoming bytes are the wand's actual NeoPixel duty cycle — leds.py has
 * already applied brightness.MULTIPLIER (max 0.5, see brightness.py) before
 * emit_led_frame() sends them here. A WS2812's duty cycle is a *linear*
 * light quantity, but a CSS/canvas RGB byte is interpreted as sRGB-encoded
 * (gamma ~2.2), so displaying the duty byte directly reads far dimmer than
 * the real LED looks — that's what the old flat displayGain multiply was
 * (imprecisely) compensating for. Converting it through the same
 * linear -> sRGB curve the Icon Display Station pipeline uses
 * (webapp/js/pipeline/ledcolor.js's linearToSrgb, ledDisplay.js's
 * authoredToDisplay) shows the color the LED actually appears to emit.
 */

function linearToSrgb(c) {
  // c in [0,1] linear -> [0,1] sRGB-encoded (IEC 61966-2-1).
  const v = c <= 0.0031308 ? c * 12.92 : 1.055 * c ** (1 / 2.4) - 0.055;
  return Math.min(1, Math.max(0, v));
}

function dutyToDisplayByte(duty, gain) {
  const linear = Math.min(1, Math.max(0, (duty * gain) / 255));
  return Math.round(linearToSrgb(linear) * 255);
}

export function createRenderer(container, opts = {}) {
  const root = container;
  root.classList.add("wand-led-grid");
  root.style.setProperty("--wand-led-size", opts.size || "var(--wand-led-size, 18px)");
  root.style.setProperty("--wand-grid-gap", opts.gap || "var(--wand-grid-gap, 6px)");
  root.style.setProperty("--wand-led-radius", opts.radius || "var(--wand-led-radius, 4px)");

  root.innerHTML = "";
  const cells = [];
  for (let i = 0; i < 25; i++) {
    const cell = document.createElement("div");
    cell.className = "wand-led-cell";
    cell.dataset.index = String(i);
    root.appendChild(cell);
    cells.push(cell);
  }

  // Gain applied in linear space before sRGB encoding (physically what
  // running the LED harder would do) — defaults to 1 since the gamma
  // correction above already renders duty values at their real perceived
  // brightness, not artificially dim as before.
  let displayGain = opts.displayGain != null ? opts.displayGain : 1;

  function applyFrame(pixels) {
    const list = pixels || [];
    for (let i = 0; i < 25; i++) {
      const p = list[i] || [0, 0, 0];
      const r = dutyToDisplayByte(p[0] || 0, displayGain);
      const g = dutyToDisplayByte(p[1] || 0, displayGain);
      const b = dutyToDisplayByte(p[2] || 0, displayGain);
      const lit = (p[0] || 0) + (p[1] || 0) + (p[2] || 0) > 0;
      cells[i].style.background = lit ? `rgb(${r},${g},${b})` : "var(--wand-led-off, #1a1a1a)";
      cells[i].style.boxShadow = lit
        ? `0 0 var(--wand-led-glow, 8px) rgba(${r},${g},${b},0.55)`
        : "none";
    }
  }

  function setDisplayGain(g) {
    displayGain = Number(g) || 1;
  }

  return { applyFrame, setDisplayGain, cells };
}
