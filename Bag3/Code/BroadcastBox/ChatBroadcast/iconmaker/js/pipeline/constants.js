/**
 * constants.js -- shared sizes and thresholds.
 *
 * The size-dependent ones are `let`, not `const`, and are rewritten by
 * applyProfile() when the target board changes. ES module bindings are LIVE,
 * so every `import { W } from "./constants.js"` sees the new value without
 * any plumbing -- which is what keeps profile support from becoming a
 * rewrite of the whole pipeline.
 *
 * The catch, and the one thing to watch when editing this pipeline: a module
 * that computes a derived constant AT LOAD TIME (`const CELLS = W * H`)
 * captures the old value and silently keeps using it. Derive inside the
 * function, or use the live getters below. See profiles.js.
 */

import { getProfile } from "./profiles.js";

// ── geometry: rewritten by applyProfile() ──────────────────────────────
export let W = 16;
export let H = 16;
export let WORK = 512;         // working-canvas resolution
export let BLOCK = WORK / W;   // source px per cell; must stay an integer
export let CELLS = W * H;

export const ALPHA_THRESH = 128;
export const MIN_FRAC = 0.004;
export let MAX_SEGMENTS = 12;

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

// emit.py -- counts, so they scale with the panel (see profiles.js)
export const CH_FLOOR = 20;
export let MAX_LIT_COLORS = 8;
export let MIN_FEATURE_CELLS = 4;

// mapio.py
export const DEFAULT_INTENSITY = 0.30;
export let DEFAULT_MAX_SEGMENTS = 12;

// preview.py
export let PREVIEW_SCALE = 24;
export let DOT_RADIUS = 8;
export const BLOOM_RADIUS = 3;
export const PREVIEW_BG = [10, 10, 12];

/** Firmware clamps intensity here (icon_matrix.py MAX_INTENSITY) -- power limit. */
export const MAX_INTENSITY = 0.5;

/**
 * Adopt a device profile. Call this BEFORE re-running the pipeline; nothing
 * recomputes on its own.
 */
export function applyProfile(profile = getProfile()) {
  W = profile.w;
  H = profile.h;
  WORK = profile.work;
  BLOCK = profile.work / profile.w;
  CELLS = profile.w * profile.h;
  MAX_SEGMENTS = profile.maxSegments;
  DEFAULT_MAX_SEGMENTS = profile.maxSegments;
  MIN_FEATURE_CELLS = profile.minFeatureCells;
  MAX_LIT_COLORS = profile.maxLitColors;
  PREVIEW_SCALE = profile.previewScale;
  DOT_RADIUS = profile.dotRadius;
}

// Adopt whatever profile is active at load, so importers never see a
// half-configured state.
applyProfile();
