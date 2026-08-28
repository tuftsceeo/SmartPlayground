/** colorUtils.js -- small hex/rgb helpers shared by the editor components. */

export function rgbToHex([r, g, b]) {
  const h = (n) => n.toString(16).padStart(2, "0");
  return `#${h(r)}${h(g)}${h(b)}`;
}

export function hexToRgb(hex) {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff];
}

// 12-color qualitative palette for the segmented debug view -- deliberately
// distinct from PALETTE (segment identity, not authored color).
export const DEBUG_SWATCHES = [
  "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4",
  "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080", "#e6beff",
];
