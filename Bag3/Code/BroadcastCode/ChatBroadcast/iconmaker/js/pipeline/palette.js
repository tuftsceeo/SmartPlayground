/**
 * palette.js -- the named LED colours. Values are LINEAR PWM DUTY, not sRGB
 * -- see ledcolor.js's boundary note before rendering them anywhere.
 */

export const PALETTE = {
  RED: [130, 0, 0], ROSE: [120, 10, 20],
  ORANGE: [120, 40, 0], AMBER: [120, 80, 0], YELLOW: [110, 120, 0],
  LIME: [50, 210, 0], GREEN: [0, 230, 0],
  TEAL: [0, 180, 100], CYAN: [0, 180, 240], BLUE: [0, 20, 255],
  INDIGO: [30, 0, 255], PURPLE: [50, 0, 250], MAGENTA: [120, 0, 160],
  WHITE: [140, 150, 150], PINK: [200, 80, 120], PEACH: [180, 120, 30],
  MINT: [30, 190, 50], SKY: [60, 150, 250],
};

// Unit directions (max component normalized to 1.0) -- HUE-ONLY matching.
// Never compare raw PALETTE magnitudes to a source pixel.
export const PALETTE_DIRECTIONS = {};
for (const [name, rgb] of Object.entries(PALETTE)) {
  const m = Math.max(...rgb);
  PALETTE_DIRECTIONS[name] = rgb.map((c) => (m ? c / m : 0));
}
