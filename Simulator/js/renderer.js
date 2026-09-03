/**
 * Wand-face renderer — inlines assets/wand/WAND_FRONT.svg (a hand-authored,
 * layer-named Illustrator export) into the shadow DOM and drives its live
 * elements directly, rather than drawing a separate div grid over/instead
 * of the artwork:
 *
 *   - LED1-2 .. LED25-2 (the "LED_MATRIX-2" duplicate group; LED_MATRIX,
 *     the other copy, is hidden) — fill color per applyFrame(pixels).
 *     Index is direct: pixels[i] (0-indexed) -> path id `LED${i+1}-2`.
 *   - _BUTTON_UP / _BUTTON_DOWN — exactly one visible per setButtonDown().
 *   - _SPEAKER — fill color per setSpeakerColor().
 *
 * Incoming LED bytes are the wand's actual NeoPixel duty cycle — leds.py
 * has already applied brightness.MULTIPLIER (max 0.5, see brightness.py)
 * before emit_led_frame() sends them here. A WS2812's duty cycle is a
 * *linear* light quantity, but an SVG fill color is sRGB-encoded (gamma
 * ~2.2), so using the duty byte directly reads far dimmer than the real
 * LED looks. Converting it through the same linear -> sRGB curve the Icon
 * Display Station pipeline uses (webapp/js/pipeline/ledcolor.js's
 * linearToSrgb, ledDisplay.js's authoredToDisplay) shows the color the LED
 * actually appears to emit.
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

const LED_OFF_FILL = "#070707"; // matches WAND_FRONT.svg's own unlit LED color

export function createRenderer(container, opts = {}) {
  const root = container;
  root.classList.add("wand-art");

  // Gain applied in linear space before sRGB encoding (physically what
  // running the LED harder would do) — defaults to 1 since the gamma
  // correction above already renders duty values at their real perceived
  // brightness, not artificially dim as before.
  let displayGain = opts.displayGain != null ? opts.displayGain : 1;

  const ledEls = new Array(25).fill(null);
  let buttonUpEl = null;
  let buttonDownEl = null;
  let speakerEl = null;
  let ready = false;
  let pendingFrame = null;
  let pendingButtonDown = false;
  let tapPressed = false;

  /** opts.onButtonTap(down) fires from a real click/tap on the drawn
   * button artwork itself (see wireButtonTap below) -- de-duped so a
   * stray extra pointerdown/pointerup pair doesn't double-fire. */
  function setTapPressed(down) {
    if (tapPressed === down) return;
    tapPressed = down;
    opts.onButtonTap?.(down);
  }

  async function load(svgUrl) {
    let svgText;
    try {
      const res = await fetch(svgUrl);
      if (!res.ok) throw new Error(`fetch ${svgUrl}: ${res.status}`);
      svgText = await res.text();
    } catch (err) {
      console.error("wand-sim: failed to load wand artwork", err);
      return;
    }
    root.innerHTML = svgText;
    const svg = root.querySelector("svg");
    if (!svg) {
      console.error("wand-sim: WAND_FRONT.svg has no <svg> root");
      return;
    }
    svg.removeAttribute("width");
    svg.removeAttribute("height");
    svg.style.width = "100%";
    svg.style.height = "auto";
    svg.style.display = "block";

    // The SVG's gradient <image> overlays reference their PNGs by a plain
    // relative path (e.g. "gradients/CaseSide.png") — correct when reading
    // the file directly, but innerHTML-inlining this text resolves any
    // relative URL against the *host page's* location, not the SVG's own.
    // Resolve each one against svgUrl explicitly instead.
    svg.querySelectorAll("image").forEach((img) => {
      const href = img.getAttribute("xlink:href") || img.getAttribute("href");
      if (!href || /^([a-z]+:|\/\/)/i.test(href)) return; // already absolute/data:
      const resolved = new URL(href, svgUrl).href;
      img.setAttribute("xlink:href", resolved);
      img.setAttribute("href", resolved);
    });

    // LED_MATRIX and LED_MATRIX-2 are duplicate copies of the same 25
    // paths (see WAND_FRONT.svg) — only one is driven; the other is hidden
    // outright rather than left stacked underneath.
    const deadMatrix = svg.querySelector("#LED_MATRIX");
    if (deadMatrix) deadMatrix.style.display = "none";
    for (let i = 0; i < 25; i++) {
      ledEls[i] = svg.querySelector(`#LED${i + 1}-2`);
      // The SVG ships with these baked-in lit (LED_MATRIX-2's own default
      // fill); force them off until the first real frame arrives instead
      // of flashing that color for the beat before a game's first write.
      if (ledEls[i]) ledEls[i].style.fill = LED_OFF_FILL;
    }

    buttonUpEl = svg.querySelector("#_BUTTON_UP");
    buttonDownEl = svg.querySelector("#_BUTTON_DOWN");
    speakerEl = svg.querySelector("#_SPEAKER");
    setSpeakerColor(null);

    // The button is drawn right there on the wand face -- clicking it is
    // the obvious, tempting thing to do, so it should actually work like
    // the real physical button rather than only the separate "Press"
    // control. _BUTTON_UP/_BUTTON_DOWN swap display per setButtonDown()
    // mid-press, so pointerdown goes on whichever is currently visible,
    // but release is listened for window-wide rather than via pointer
    // capture on that same (possibly now-hidden) element.
    for (const el of [buttonUpEl, buttonDownEl]) {
      if (!el) continue;
      el.style.cursor = "pointer";
      el.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        setTapPressed(true);
      });
    }
    window.addEventListener("pointerup", () => setTapPressed(false));
    window.addEventListener("pointercancel", () => setTapPressed(false));

    ready = true;
    setButtonDown(pendingButtonDown);
    if (pendingFrame) {
      applyFrame(pendingFrame);
      pendingFrame = null;
    }
  }

  function applyFrame(pixels) {
    if (!ready) {
      pendingFrame = pixels;
      return;
    }
    const list = pixels || [];
    for (let i = 0; i < 25; i++) {
      const el = ledEls[i];
      if (!el) continue;
      const p = list[i] || [0, 0, 0];
      const lit = (p[0] || 0) + (p[1] || 0) + (p[2] || 0) > 0;
      el.style.fill = lit ? dutyRgbToCss(p, displayGain) : LED_OFF_FILL;
    }
  }

  function setDisplayGain(g) {
    displayGain = Number(g) || 1;
  }

  /** Exactly one of _BUTTON_UP / _BUTTON_DOWN is visible at a time —
   * never both, matching the real button's physical state. */
  function setButtonDown(down) {
    pendingButtonDown = !!down;
    if (!ready) return;
    if (buttonUpEl) buttonUpEl.style.display = down ? "none" : "";
    if (buttonDownEl) buttonDownEl.style.display = down ? "" : "none";
  }

  /** cssColor: a CSS color string while the buzzer plays, or null/falsy to
   * return to the idle (unlit) look. */
  function setSpeakerColor(cssColor) {
    if (!speakerEl) return;
    speakerEl.style.fill = cssColor || "#2d2d2d"; // matches Speaker_Background's own inner ring
  }

  load(opts.svgUrl);

  return { applyFrame, setDisplayGain, setButtonDown, setSpeakerColor };
}
