/**
 * constants.js -- the panel geometry and preview scale the icon preview
 * needs, lifted from the icon station's webapp
 * (Stations/Icon Display Station/webapp/js/pipeline/constants.js).
 *
 * Kept as its own module so preview.js is a verbatim copy of the station's,
 * and so the numbers that must match the device -- the 16x16 geometry and
 * the 0.50 intensity ceiling icon_matrix.py enforces -- sit in one place.
 */

/** Panel geometry, matching icon_matrix.py. */
export const W = 16;
export const H = 16;

/** What the station boots at, and the ceiling it clamps to (power limit). */
export const DEFAULT_INTENSITY = 0.30;
export const MAX_INTENSITY = 0.5;

/** Preview render scale: one 16x16 icon becomes a 384px canvas. */
export const PREVIEW_SCALE = 24;
export const DOT_RADIUS = 8;
export const BLOOM_RADIUS = 3;
export const PREVIEW_BG = [10, 10, 12];
