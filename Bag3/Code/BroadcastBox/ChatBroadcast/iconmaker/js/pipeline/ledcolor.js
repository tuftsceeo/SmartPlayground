/**
 * ledcolor.js -- the forward model for
 * what a WS2812 byte actually looks like, vs. an sRGB image byte.
 * See the Python docstring for the root-cause rationale (two decode entry
 * points so an authored LED byte and a source-image pixel never share one
 * gamma-ambiguous OKLab decode).
 *
 * TRUNCATION IS CANONICAL (see webapp/README.md and the top-level plan):
 * predictLedAppearance models `Math.trunc(c * intensity)`, matching
 * emit.js's CH_FLOOR derivation and the new firmware's LUT. This
 * deliberately does NOT match the old main.py's round()-based scale().
 */

// Rec.601-ish linear luma weights.
export const LUMA_W = [0.299, 0.587, 0.114];

export function srgbToLinear(c) {
  // c: 0-255 sRGB byte -> [0,1] linear
  const x = c / 255;
  return x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
}

export function linearToSrgb(c) {
  // c in [0,1] linear -> [0,1] sRGB-encoded
  const v = c <= 0.0031308 ? c * 12.92 : 1.055 * c ** (1 / 2.4) - 0.055;
  return Math.min(1.0, Math.max(0.0, v));
}

function oklabRaw(rl, gl, bl) {
  const l = 0.4122214708 * rl + 0.5363325363 * gl + 0.0514459929 * bl;
  const m = 0.2119034982 * rl + 0.6806995451 * gl + 0.1073969566 * bl;
  const s = 0.0883024619 * rl + 0.2817188376 * gl + 0.6299787005 * bl;
  const l_ = l > 0 ? Math.cbrt(l) : 0.0;
  const m_ = m > 0 ? Math.cbrt(m) : 0.0;
  const s_ = s > 0 ? Math.cbrt(s) : 0.0;
  const L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_;
  const a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_;
  const b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_;
  return [L, a, b];
}

export function oklabFromSrgb(rgb) {
  const [r, g, b] = rgb;
  return oklabRaw(srgbToLinear(r), srgbToLinear(g), srgbToLinear(b));
}

export function oklabFromLinear(rgb) {
  const [r, g, b] = rgb;
  return oklabRaw(r / 255, g / 255, b / 255);
}

function dE(a, b) {
  return Math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2);
}

export function dESrgb(c1, c2) {
  return dE(oklabFromSrgb(c1), oklabFromSrgb(c2));
}

export function dELinear(c1, c2) {
  return dE(oklabFromLinear(c1), oklabFromLinear(c2));
}

export function predictLedAppearance(rgb, intensity) {
  // authored byte -> xINTENSITY -> truncate -> /255 linear -> sRGB-encode
  const out = [];
  for (const c of rgb) {
    const duty = Math.trunc(c * intensity);   // device does this (see icon_matrix.js)
    const linear = duty / 255;
    const srgb = linearToSrgb(linear);
    out.push(Math.round(srgb * 255));
  }
  return out;
}

export function lumaLinear(rgb) {
  const [r, g, b] = rgb;
  return LUMA_W[0] * r + LUMA_W[1] * g + LUMA_W[2] * b;
}

export function purify(rgb) {
  const m = Math.min(...rgb);
  return rgb.map((c) => c - m);
}

export function hueDeg(rgb) {
  const [r, g, b] = rgb.map((c) => c / 255);
  const mx = Math.max(r, g, b);
  const mn = Math.min(r, g, b);
  const d = mx - mn;
  if (d === 0) return 0.0;
  let h;
  if (mx === r) h = (((g - b) / d) % 6 + 6) % 6;
  else if (mx === g) h = (b - r) / d + 2;
  else h = (r - g) / d + 4;
  return h * 60.0;
}

export function isBrown(rgb, hLo = 30.0, hHi = 75.0, chromaMax = 0.45, lightnessMax = 0.55) {
  const [r, g, b] = rgb.map((c) => c / 255);
  const mx = Math.max(r, g, b);
  const mn = Math.min(r, g, b);
  const chroma = mx - mn;
  const lightness = (mx + mn) / 2;
  const h = hueDeg(rgb);
  return h >= hLo && h <= hHi && chroma <= chromaMax && lightness <= lightnessMax;
}
