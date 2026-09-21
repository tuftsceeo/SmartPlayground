/**
 * segment.js -- port of iconlib/segment.py: label map, per-segment coverage,
 * ring-contact/encloser detection, and auto-propose. Restructured from
 * Python's per-segment full-res passes into single full-res passes (see
 * plan §Pipeline port) -- numerically equivalent, not an approximation.
 *
 */

import { W, H, WORK, BLOCK, ALPHA_THRESH } from "./constants.js";
import { oklabFromSrgb, hueDeg, isBrown, purify } from "./ledcolor.js";
import { PALETTE, PALETTE_DIRECTIONS } from "./palette.js";
import {
  THIN_FRAC,
  ENCLOSE_OFF,
  BG_CONTACT_MAX,
  BROWN_AMBER,
  MAX_CH_BODY,
  CH_FLOOR_HINT,
  MIN_RATIO,
} from "./constants.js";

// Derived INSIDE the functions, not captured here: W/H/BLOCK are live
// bindings that change with the device profile, and a module-level `const`
// would freeze the 16x16 values (see constants.js).
const cells = () => W * H;
const blockArea = () => BLOCK * BLOCK;

function nearestFillIdx(rgb, fillRgbs) {
  let bestI = 0;
  let bestD = null;
  for (let i = 0; i < fillRgbs.length; i++) {
    const f = fillRgbs[i];
    const dr = rgb[0] - f[0];
    const dg = rgb[1] - f[1];
    const db = rgb[2] - f[2];
    const d = dr * dr + dg * dg + db * db;
    if (bestD === null || d < bestD) {
      bestD = d;
      bestI = i;
    }
  }
  return bestI;
}

/**
 * Assign every working-canvas pixel to a segment id (index into `fills`) or
 * -1 for background/transparent (Python's None). Anti-aliased edge pixels
 * are literal blends of two fills, so nearest-fill-by-RGB is the correct
 * assignment, not a heuristic.
 * @returns {Int16Array} length WORK*WORK, row-major
 */
export function labelMap(imageData, fills, alphaThresh = ALPHA_THRESH) {
  const { data } = imageData;
  const fillRgbs = fills.map((f) => f.rgb);
  const labels = new Int16Array(WORK * WORK);
  const cache = new Map(); // packed rgb -> idx

  for (let i = 0, n = WORK * WORK; i < n; i++) {
    const o = i * 4;
    const a = data[o + 3];
    if (a < alphaThresh) {
      labels[i] = -1;
      continue;
    }
    const r = data[o];
    const g = data[o + 1];
    const b = data[o + 2];
    const key = (r << 16) | (g << 8) | b;
    let idx = cache.get(key);
    if (idx === undefined) {
      idx = nearestFillIdx([r, g, b], fillRgbs);
      cache.set(key, idx);
    }
    labels[i] = idx;
  }
  return labels;
}

/**
 * One full-res pass computing everything that's priority/decision-
 * independent: per-segment per-cell coverage counts, opaque coverage
 * counts, and the ring-contact matrix (for encloser detection). This is
 * tier T2 in the plan's recompute tiers -- cached until the source image,
 * mask, or segmentation knobs change.
 */
export function computeSegmentStats(labels, nSegs) {
  const CELLS = cells(); // bind once -- live binding, see constants.js
  const covCounts = new Int32Array(nSegs * CELLS);
  const opaqueCounts = new Int32Array(CELLS);
  const ringMatch = new Int32Array(nSegs * nSegs);
  const ringTotal = new Int32Array(nSegs);
  const bgMatch = new Int32Array(nSegs);

  for (let y = 0; y < WORK; y++) {
    const cellRow = (y / BLOCK) | 0;
    const rowBase = y * WORK;
    for (let x = 0; x < WORK; x++) {
      const idx = rowBase + x;
      const lbl = labels[idx];
      if (lbl === -1) continue;
      const cellCol = (x / BLOCK) | 0;
      const cell = cellRow * W + cellCol;
      covCounts[lbl * CELLS + cell]++;
      opaqueCounts[cell]++;

      const up = y > 0 ? labels[idx - WORK] : -1;
      const down = y < WORK - 1 ? labels[idx + WORK] : -1;
      const left = x > 0 ? labels[idx - 1] : -1;
      const right = x < WORK - 1 ? labels[idx + 1] : -1;

      // Distinct non-self neighbor labels (off-canvas and background both
      // use -1, matching Python's "off-canvas counts as background").
      let distinct = null;
      if (up !== lbl) (distinct ||= new Set()).add(up);
      if (down !== lbl) (distinct ||= new Set()).add(down);
      if (left !== lbl) (distinct ||= new Set()).add(left);
      if (right !== lbl) (distinct ||= new Set()).add(right);
      if (distinct) {
        ringTotal[lbl]++;
        for (const v of distinct) {
          if (v === -1) bgMatch[lbl]++;
          else ringMatch[lbl * nSegs + v]++;
        }
      }
    }
  }
  return { covCounts, opaqueCounts, ringMatch, ringTotal, bgMatch };
}

/**
 * Exact fractional coverage of a cell by a segment.
 *
 * This used to round-trip through 8 bits to replicate an artefact of
 * Pillow's BOX resize (coverage came back as round(255*k/1024)/255, which
 * straddles the CELL_ON threshold: 359/1024 is 0.3506 exactly but 0.34902
 * once quantized -- on opposite sides of 0.35). That existed only for
 * byte-parity with the old CLI. The exact mean is simply correct.
 */
function coverageFraction(k) {
  return k / blockArea();
}

/** Per-segment per-cell coverage grids, flat Float64Array per segment. */
export function buildCoverageBySeg(covCounts, nSegs) {
  const CELLS = cells();
  const out = [];
  for (let s = 0; s < nSegs; s++) {
    const grid = new Float64Array(CELLS);
    const base = s * CELLS;
    for (let c = 0; c < CELLS; c++) grid[c] = coverageFraction(covCounts[base + c]);
    out.push(grid);
  }
  return out;
}

export function buildOpaqueCoverage(opaqueCounts) {
  const CELLS = cells();
  const grid = new Float64Array(CELLS);
  for (let c = 0; c < CELLS; c++) grid[c] = coverageFraction(opaqueCounts[c]);
  return grid;
}

/** Fraction of segment i's boundary ring touching background. */
export function bgFrac(i, ringTotal, bgMatch) {
  return ringTotal[i] ? bgMatch[i] / ringTotal[i] : 0.0;
}

/** (bestOtherId, contactFrac) -- whichever other segment most surrounds i. */
export function encloserOf(i, nSegs, ringMatch, ringTotal) {
  let bestId = null;
  let bestFrac = 0.0;
  const total = ringTotal[i];
  if (!total) return [null, 0.0];
  for (let other = 0; other < nSegs; other++) {
    if (other === i) continue;
    const frac = ringMatch[i * nSegs + other] / total;
    if (frac > bestFrac) {
      bestFrac = frac;
      bestId = other;
    }
  }
  return [bestId, bestFrac];
}

// ══════════════════════════════════════════════
// AUTO-PROPOSE -- the editor's starting point, always human-overridable
// ══════════════════════════════════════════════

const HUE_ANCHORS = Object.entries(PALETTE)
  .filter(([name]) => name !== "WHITE")
  .map(([name, rgb]) => [hueDeg(rgb), name, PALETTE_DIRECTIONS[name]])
  .sort((a, b) => a[0] - b[0]);

function nearestPaletteDirection(rgb) {
  const pure = purify(rgb);
  const norm = Math.sqrt(pure.reduce((s, c) => s + c * c, 0));
  if (norm < 12) return ["WHITE", PALETTE_DIRECTIONS.WHITE];

  const h = hueDeg(rgb);
  const n = HUE_ANCHORS.length;
  for (let i = 0; i < n; i++) {
    const [h1, name1, d1] = HUE_ANCHORS[i];
    const [h2, name2, d2] = HUE_ANCHORS[(i + 1) % n];
    let span = (((h2 - h1) % 360) + 360) % 360;
    if (span === 0) span = 360;
    const pos = (((h - h1) % 360) + 360) % 360;
    if (pos > span) continue;
    const t = pos / span;
    let interp = d1.map((a, k) => a + (d2[k] - a) * t);
    interp = interp.map((c) => (c >= MIN_RATIO ? c : 0.0));
    const m = Math.max(...interp) || 1;
    const unit = interp.map((c) => c / m);
    let label = t < 0.5 ? name1 : name2;
    if (t > 0.15 && t < 0.85) label = `${name1}~${name2}`;
    return [label, unit];
  }
  return [HUE_ANCHORS[0][1], HUE_ANCHORS[0][2]];
}

/**
 * @returns {Array<{role:'color'|'off', color:number[]|null, priority:number, palette_hint:string|null}>}
 * parallel to `fills`.
 */
export function autoPropose(fills, nSegs, ringMatch, ringTotal, bgMatchArr) {
  const lightness = fills.map((f) => oklabFromSrgb(f.rgb)[0]);
  const proposals = new Array(fills.length);

  for (let i = 0; i < fills.length; i++) {
    const { rgb, frac } = fills[i];

    if (isBrown(rgb)) {
      proposals[i] = {
        role: "color",
        color: BROWN_AMBER.slice(),
        priority: frac < THIN_FRAC ? 2.5 : 1.0,
        palette_hint: "AMBER (brown approximation)",
      };
      continue;
    }

    const [encloser, encFrac] = encloserOf(i, nSegs, ringMatch, ringTotal);
    const bgf = bgFrac(i, ringTotal, bgMatchArr);
    if (
      encloser !== null &&
      encFrac >= ENCLOSE_OFF &&
      bgf <= BG_CONTACT_MAX &&
      lightness[i] < lightness[encloser]
    ) {
      proposals[i] = { role: "off", color: null, priority: 0.0, palette_hint: null };
      continue;
    }

    const [name, unit] = nearestPaletteDirection(rgb);
    const amplitude = Math.max(CH_FLOOR_HINT, Math.min(MAX_CH_BODY, Math.round(MAX_CH_BODY * lightness[i])));
    const color = unit.map((c) => Math.min(255, Math.round(c * amplitude)));

    let priority;
    if (frac < THIN_FRAC) priority = 2.5;
    else if (encloser !== null && lightness[i] > lightness[encloser] && frac < 0.1) priority = 0.6;
    else priority = 1.0;

    proposals[i] = { role: "color", color, priority, palette_hint: name };
  }

  return proposals;
}
