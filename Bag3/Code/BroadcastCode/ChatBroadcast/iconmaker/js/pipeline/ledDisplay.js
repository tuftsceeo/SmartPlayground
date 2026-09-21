/**
 * ledDisplay.js -- the screen/device colour boundary.
 *
 * ledcolor.js models the physics (what a duty byte does to an LED); this
 * module is the UI boundary -- authored duty -> something a browser can
 * paint, and a colour picked in a browser -> authored duty. Kept separate
 * so the physics stays free of DOM/CSS concerns.
 *
 * INVARIANT for the whole app: authored/stored values (PALETTE, maps/*.json
 * `color`, icons/*.py bytes, doc.pixels) are LINEAR PWM DUTY. Everything
 * shown on screen or entered through an <input type="color"> is sRGB.
 * Convert at the boundary, never in the middle.
 *
 * Getting this wrong is the bug these helpers exist to prevent: painting a
 * linear duty byte straight into a CSS colour renders it far too dark,
 * because sRGB encoding of a linear value raises it substantially (linear
 * 0.1 displays as sRGB ~0.35). PALETTE.RED is [130,0,0] -- shown raw that's
 * #820000, a dark maroon, while the LED it describes is a vivid red. That
 * mismatch is why the palette swatches, the 16x16 grid and the colour
 * pickers all looked muted next to the real matrix, and why the grid
 * disagreed with the bloom preview directly above it (preview.js was the
 * only place running the forward model).
 *
 * Deliberately intensity-INDEPENDENT: these are authoring surfaces and must
 * stay legible at 5% brightness. The live-intensity appearance is the job of
 * preview.js's bloom canvas, which uses predictLedAppearance().
 */

import { srgbToLinear, linearToSrgb } from "./ledcolor.js";

/** Authored linear duty byte tuple -> sRGB byte tuple for display. */
export function authoredToDisplay(rgb) {
  return rgb.map((c) => Math.round(linearToSrgb(Math.max(0, Math.min(255, c)) / 255) * 255));
}

/** sRGB byte tuple (from a colour picker) -> authored linear duty bytes. */
export function displayToAuthored(rgb) {
  return rgb.map((c) => Math.round(srgbToLinear(Math.max(0, Math.min(255, c))) * 255));
}

const hex2 = (n) => n.toString(16).padStart(2, "0");

/** Authored linear duty -> "#rrggbb" for CSS. */
export function authoredToDisplayHex(rgb) {
  const [r, g, b] = authoredToDisplay(rgb);
  return `#${hex2(r)}${hex2(g)}${hex2(b)}`;
}

/** "#rrggbb" from a picker -> authored linear duty bytes. */
export function displayHexToAuthored(hex) {
  const n = parseInt(String(hex).replace("#", ""), 16);
  return displayToAuthored([(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff]);
}
