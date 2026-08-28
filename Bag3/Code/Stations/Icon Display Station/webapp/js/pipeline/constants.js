/**
 * constants.js -- shared sizes/thresholds, ported 1:1 from the Python
 * modules named in each comment. Keep these in sync by hand; there's no
 * shared source of truth across the Python/JS boundary (same tradeoff as
 * iconlib/palette.py's comment re: leds.py).
 */

// segment.py
export const W = 16;
export const H = 16;
export const WORK = 512;          // fixed working-canvas resolution
export const BLOCK = WORK / W;    // 32 -- must stay an integer, or cell coverage stops being an exact block mean
export const ALPHA_THRESH = 128;
export const MIN_FRAC = 0.004;
export const MAX_SEGMENTS = 12;

// segment.py auto_propose
export const THIN_FRAC = 0.03;
export const ENCLOSE_OFF = 0.85;
export const BG_CONTACT_MAX = 0.15;
export const BROWN_AMBER = [60, 40, 0];
export const MAX_CH_BODY = 220;
export const CH_FLOOR_HINT = 20;
export const MIN_RATIO = 0.06;

// raster.py
export const CELL_ON = 0.35;
export const DEFAULT_PRIORITY = 1.0;

// emit.py
export const CH_FLOOR = 20;
export const MAX_LIT_COLORS = 8;
export const MIN_FEATURE_CELLS = 4;
export const SEPARATION_MIN = 25;

// mapio.py
export const DEFAULT_INTENSITY = 0.30;
export const DEFAULT_MAX_SEGMENTS = 12;

// preview.py
export const PREVIEW_SCALE = 24;
export const DOT_RADIUS = 8;
export const BLOOM_RADIUS = 3;
export const PREVIEW_BG = [10, 10, 12];

/** Firmware clamps intensity here (icon_matrix.py MAX_INTENSITY) -- power limit. */
export const MAX_INTENSITY = 0.5;
