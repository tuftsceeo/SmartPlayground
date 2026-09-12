/**
 * ledGamut.js -- what colours this panel can ACTUALLY show, and how to
 * present them for authoring.
 *
 * WHY THIS EXISTS. Authoring in sRGB is a bad fit for a WS2812 matrix:
 *
 *   - At the working brightness the device has far fewer levels than the
 *     picker implies. At intensity 0.30, authored 0-255 collapses to 77
 *     distinct PWM levels per channel -- authored 100 and 103 are literally
 *     the same on the panel.
 *   - Measured over a uniform sample of the RGB cube, ~76% of the picker's
 *     volume is bright colours that all read as indistinguishable white,
 *     and the saturated colours worth having live in a ~3% sliver of dim
 *     values (which the picker draws as almost black -- a usable dark teal
 *     is authored around rgb(0,36,46), impossible to pick by eye).
 *   - Counting perceptually distinct results: ~330 colours at intensity
 *     0.30 (OKLab dE >= 0.05), ~65 at 0.05. Not 16.7 million. The sRGB
 *     picker offers roughly 50,000 choices per real outcome.
 *
 * So this module builds the palette from the DEVICE side: enumerate what is
 * distinguishable on the panel, organise it as hue x level, and hand that to
 * the UI. Picking becomes choosing among things that actually differ.
 *
 * DEVICE MODEL. From the WS2812B datasheet: luminous intensity at 16mA
 * (R 300-500, G 800-1500, B 200-300 mcd) and dominant wavelength (R 620-630,
 * G 515-525, B 465-475 nm). Midpoints are used. Because mcd is photometric
 * it is already eye-weighted, and dominant wavelength pins each primary on
 * the CIE 1931 spectral locus -- together that's a duty -> XYZ matrix.
 *
 * Consequences worth knowing, all falling out of that matrix:
 *   - Blue carries ~0.139 of white luminance here vs ~0.072 in sRGB, i.e.
 *     about twice the weight. Dim blues look far brighter than sRGB suggests.
 *   - Equal duty is NOT white: (255,255,255) lands at xy(0.224,0.256), a
 *     blue-cyan. Neutral D65 needs roughly duty (255,171,93).
 *   - All three primaries are outside sRGB, so screen output clips to the
 *     gamut boundary. That is the honest best a monitor can do.
 *
 * CAVEAT: the datasheet quotes min-max with no typical, parts are binned,
 * and this treats the primaries as monochromatic when they're ~20-30nm wide
 * (which slightly overstates saturation). This is a nominal model for
 * relative correctness, not a calibration.
 */

import { MAX_INTENSITY, CH_FLOOR } from "./constants.js";

// xy chromaticity on the CIE 1931 spectral locus at each dominant
// wavelength, and luminous intensity in mcd at 16mA.
const PRIMARIES = [
  { x: 0.7006, y: 0.2993, Iv: 400.0 }, // R, 625nm
  { x: 0.0743, y: 0.8338, Iv: 1150.0 }, // G, 520nm
  { x: 0.1241, y: 0.0578, Iv: 250.0 }, // B, 470nm
];

// Each primary's XYZ contribution at full duty.
const PRIM_XYZ = PRIMARIES.map(({ x, y, Iv }) => [(x / y) * Iv, Iv, ((1 - x - y) / y) * Iv]);
const Y_WHITE = PRIM_XYZ.reduce((s, p) => s + p[1], 0);

/**
 * Authored duty -> normalised XYZ of the light the panel emits.
 * `intensity` applies the device's own truncating scale (see icon_matrix.py).
 */
export function authoredToXYZ(duty, intensity = 1) {
  const d = duty.map((c) => (intensity === 1 ? c : Math.trunc(c * intensity)) / 255);
  return [0, 1, 2].map(
    (i) => (d[0] * PRIM_XYZ[0][i] + d[1] * PRIM_XYZ[1][i] + d[2] * PRIM_XYZ[2][i]) / Y_WHITE
  );
}

function encodeSrgb(c) {
  const v = Math.max(0, Math.min(1, c));
  return v <= 0.0031308 ? 12.92 * v : 1.055 * Math.pow(v, 1 / 2.4) - 0.055;
}

/** XYZ -> sRGB bytes, clipping out-of-gamut to the boundary. */
export function xyzToSrgb(X, Y, Z) {
  const lin = [
    3.2406 * X - 1.5372 * Y - 0.4986 * Z,
    -0.9689 * X + 1.8758 * Y + 0.0415 * Z,
    0.0557 * X - 0.204 * Y + 1.057 * Z,
  ];
  return lin.map((c) => Math.round(encodeSrgb(c) * 255));
}

/**
 * How a swatch of this authored colour should be painted on screen.
 *
 * Intensity-INDEPENDENT on purpose: these are authoring surfaces and have to
 * stay legible when the panel is running at 5%. The live-brightness
 * appearance is the preview canvas's job, not the palette's.
 */
export function ledSwatchHex(duty) {
  const [r, g, b] = xyzToSrgb(...authoredToXYZ(duty, 1));
  const h = (n) => n.toString(16).padStart(2, "0");
  return `#${h(r)}${h(g)}${h(b)}`;
}

/** OKLab of the panel's emitted light, for perceptual distance ON THE LED. */
export function authoredToLedOklab(duty, intensity = 1) {
  const [X, Y, Z] = authoredToXYZ(duty, intensity);
  let l = 0.8189 * X + 0.3619 * Y - 0.1288 * Z;
  let m = 0.0329 * X + 0.9293 * Y + 0.0361 * Z;
  let s = 0.0482 * X + 0.2642 * Y + 0.6339 * Z;
  l = l > 0 ? Math.cbrt(l) : 0;
  m = m > 0 ? Math.cbrt(m) : 0;
  s = s > 0 ? Math.cbrt(s) : 0;
  return [
    0.2105 * l + 0.7936 * m - 0.0041 * s,
    1.978 * l - 2.4286 * m + 0.4506 * s,
    0.0259 * l + 0.7828 * m - 0.8087 * s,
  ];
}

/**
 * Perceptual distance between two authored colours AS THE PANEL SHOWS THEM.
 * This is the right metric for "will a viewer tell these apart?" -- comparing
 * authored bytes directly does not answer that question, because the device's
 * per-channel weighting and the intensity truncation both intervene.
 */
export function ledDeltaE(a, b, intensity = 1) {
  const p = authoredToLedOklab(a, intensity);
  const q = authoredToLedOklab(b, intensity);
  return Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]);
}

/** Below this, two colours read as the same cell on the panel. */
export const JND = 0.05;

/** A dark cell is OFF, not "very dim": CH_FLOOR raises any nonzero channel,
 *  so there is nothing between black and the dimmest lit colour. Worth being
 *  explicit about in the palette rather than leaving it to a right-click. */
export const OFF_DUTY = [0, 0, 0];

export function isOff(duty) {
  return !duty || (duty[0] === 0 && duty[1] === 0 && duty[2] === 0);
}

/**
 * CSS background for a swatch. Off gets a slash rather than a plain black
 * fill, which on a dark UI is indistinguishable from an empty slot.
 */
export function swatchStyle(duty) {
  if (isOff(duty)) return "linear-gradient(135deg,#0a0a0a 44%,#7a7a7a 44%,#7a7a7a 56%,#0a0a0a 56%)";
  return ledSwatchHex(duty);
}

// Hue directions in duty space, chosen to land on reasonably even steps of
// LED-appearance hue. Each is a unit-ish direction; magnitude comes from the
// level, and `desat` mixes toward the panel's white for pastel columns.
const HUE_DIRECTIONS = [
  // Neutrals lead so the leftmost column is always the same place to find
  // "off" and "white" -- the two you reach for most and shouldn't have to
  // hunt for. OFF is injected at the head of this column by buildPalette().
  ["white", [1, 0.67, 0.36]], // the duty mix that is actually neutral, see header
  ["red", [1, 0, 0]],
  ["orange", [1, 0.28, 0]],
  ["amber", [1, 0.55, 0]],
  ["yellow", [1, 1, 0]],
  ["lime", [0.45, 1, 0]],
  ["green", [0, 1, 0]],
  ["mint", [0, 1, 0.3]],
  ["teal", [0, 1, 0.75]],
  ["cyan", [0, 0.7, 1]],
  ["sky", [0, 0.35, 1]],
  ["blue", [0, 0.08, 1]],
  ["indigo", [0.3, 0, 1]],
  ["violet", [0.6, 0, 1]],
  ["magenta", [1, 0, 1]],
  ["pink", [1, 0.12, 0.5]],
];

/**
 * Build the authoring palette for a given brightness.
 *
 * Returns rows of levels x columns of hues, with every entry guaranteed
 * distinguishable from its neighbours on the panel at this intensity. The
 * palette legitimately SHRINKS as brightness drops -- that is a true fact
 * about the hardware and worth showing rather than hiding.
 */
export function buildPalette(intensity, { levels = 4, pastel = true, jnd = JND, includeOff = true } = {}) {
  const inten = Math.min(intensity || 0.3, MAX_INTENSITY);
  const columns = [];
  const kept = []; // every entry accepted so far, for GLOBAL separation

  const floorDuty = (d) => d.map((c) => (c === 0 ? 0 : Math.max(CH_FLOOR, Math.min(255, c))));

  for (const [name, dir] of HUE_DIRECTIONS) {
    const variants = pastel && name !== "white" ? ["pure", "pastel"] : ["pure"];
    for (const variant of variants) {
      // Candidate ladder from full magnitude down to the floor.
      const candidates = [];
      for (let mag = 255; mag >= CH_FLOOR; mag -= 1) {
        let duty = dir.map((c) => Math.round(c * mag));
        if (variant === "pastel") {
          // Mix toward the NEUTRAL duty mix, not toward equal-RGB: equal duty
          // is blue-cyan on this panel (see header).
          const w = [1, 0.67, 0.36].map((c) => c * mag * 0.55);
          duty = duty.map((c, i) => Math.round(Math.min(255, c * 0.6 + w[i])));
        }
        duty = floorDuty(duty);
        if (Math.max(...duty) === 0) continue;
        candidates.push({ duty, L: authoredToLedOklab(duty, inten)[0] });
      }
      if (!candidates.length) continue;

      // Spread levels evenly across the achievable LIGHTNESS range rather
      // than taking the first few distinguishable steps -- otherwise every
      // level clusters at the bright end and the dim, saturated colours
      // (the ones that are hard to pick in an sRGB picker, and the whole
      // reason for this palette) never appear at all.
      const Ls = candidates.map((c) => c.L);
      const Lmax = Math.max(...Ls);
      const Lmin = Math.min(...Ls);
      const entries = [];
      for (let i = 0; i < levels; i++) {
        const target = levels === 1 ? Lmax : Lmax - ((Lmax - Lmin) * i) / (levels - 1);
        let pick = candidates[0];
        let bestGap = Infinity;
        for (const c of candidates) {
          const gap = Math.abs(c.L - target);
          if (gap < bestGap) {
            bestGap = gap;
            pick = c;
          }
        }
        // Global separation: never offer two swatches the panel renders alike.
        if (kept.some((k) => ledDeltaE(pick.duty, k, inten) < jnd)) continue;
        entries.push({ name, variant, duty: pick.duty, hex: ledSwatchHex(pick.duty) });
        kept.push(pick.duty);
      }
      if (entries.length) columns.push({ name, variant, entries });
    }
  }

  if (includeOff && columns.length) {
    columns[0].entries.unshift({ name: "off", variant: "pure", duty: OFF_DUTY.slice(), hex: "#000000", off: true });
  }
  return { intensity: inten, levels, columns, count: kept.length + (includeOff ? 1 : 0) };
}

/** Flatten a palette to a plain list of authored colours. */
export function paletteColors(palette) {
  return palette.columns.flatMap((c) => c.entries.map((e) => e.duty));
}

/**
 * Nearest palette colour to an arbitrary authored value, measured on the
 * panel. Used to snap raw colour-picker choices onto something that will
 * actually be distinguishable.
 */
export function snapToPalette(duty, palette) {
  let best = null;
  let bestD = Infinity;
  // Only consider OFF when the request is essentially black already; snapping
  // a dim-but-intended colour to "off" would be a destructive surprise.
  const allowOff = Math.max(...duty) < CH_FLOOR;
  for (const col of palette.columns) {
    for (const e of col.entries) {
      if (e.off && !allowOff) continue;
      const d = ledDeltaE(duty, e.duty, palette.intensity);
      if (d < bestD) {
        bestD = d;
        best = e;
      }
    }
  }
  return best ? { ...best, deltaE: bestD } : null;
}
