/**
 * quantize.js -- median-cut colour quantizer for the non-flat fallback path.
 *
 * WHY THIS EXISTS: histogram.js's exact-fill path only works when an image
 * genuinely has a handful of flat colours. Any resampled/antialiased or
 * photographic source has thousands, and the previous fallback simply took
 * the top-N most FREQUENT exact colours. On resampled vector art that is
 * pathological: the ten most common colours are all one-unit variants of
 * the same two or three fills (observed: (172,0,176) and (171,0,175);
 * (99,0,157), (98,0,157), (98,0,156)), so the segment budget is spent on
 * duplicates, genuinely distinct small features (a red beak, a cyan wing)
 * never get a slot at all, and per-pixel nearest-fill flip-flops between
 * the twins -- which is the speckle in the segmented debug view.
 *
 * Median cut fixes both halves of that:
 *   - Binning to 5 bits/channel puts near-identical colours in the SAME bin
 *     (8 units wide), so twins collapse before any splitting happens.
 *   - Splitting the colour SPACE by population, rather than ranking by
 *     frequency, reserves boxes for distinct regions even when they're small.
 *
 * Chosen over an octree (which the Python side uses via Pillow's FASTOCTREE)
 * because octree merge order is insertion-sensitive and covers a photo's
 * dominant hues worse at the 8-12 colour budget we actually run at.
 */

import { oklabFromSrgb } from "./ledcolor.js";

const BITS = 5;
const LEVELS = 1 << BITS; // 32
const NBINS = LEVELS * LEVELS * LEVELS; // 32768
const SHIFT = 8 - BITS; // 3

/** Merge representatives closer than this in OKLab -- a safety net on top of
 *  the 5-bit binning, for twins that straddle a bin boundary. Roughly a
 *  just-noticeable difference; large enough to catch AA variants, small
 *  enough to keep genuinely different hues apart. */
const MERGE_DE = 0.02;

function binIndex(r, g, b) {
  return ((r >> SHIFT) << (2 * BITS)) | ((g >> SHIFT) << BITS) | (b >> SHIFT);
}

/**
 * @param {Map<number,number>} counts  packed 0xRRGGBB -> pixel count
 * @param {number} nOpaque             total counted pixels (for frac)
 * @param {number} maxSegments
 * @returns {Array<{rgb:[number,number,number], count:number, frac:number}>}
 */
export function quantizeFills(counts, nOpaque, maxSegments) {
  // ── bin the exact-colour histogram to 5:5:5, keeping full-precision sums
  //    so representatives are true means rather than bucket centres ────────
  const binCount = new Uint32Array(NBINS);
  const sumR = new Float64Array(NBINS);
  const sumG = new Float64Array(NBINS);
  const sumB = new Float64Array(NBINS);

  for (const [key, cnt] of counts) {
    const r = (key >> 16) & 0xff;
    const g = (key >> 8) & 0xff;
    const b = key & 0xff;
    const bi = binIndex(r, g, b);
    binCount[bi] += cnt;
    sumR[bi] += r * cnt;
    sumG[bi] += g * cnt;
    sumB[bi] += b * cnt;
  }

  // Occupied bins only -- the array median cut partitions in place.
  const occupied = [];
  for (let i = 0; i < NBINS; i++) if (binCount[i]) occupied.push(i);

  if (occupied.length === 0) return [];

  const axisOf = (bi) => [(bi >> (2 * BITS)) & (LEVELS - 1), (bi >> BITS) & (LEVELS - 1), bi & (LEVELS - 1)];

  function makeBox(start, end) {
    let count = 0;
    const lo = [LEVELS, LEVELS, LEVELS];
    const hi = [-1, -1, -1];
    for (let i = start; i <= end; i++) {
      const bi = occupied[i];
      count += binCount[bi];
      const a = axisOf(bi);
      for (let k = 0; k < 3; k++) {
        if (a[k] < lo[k]) lo[k] = a[k];
        if (a[k] > hi[k]) hi[k] = a[k];
      }
    }
    return { start, end, count, lo, hi };
  }

  let boxes = [makeBox(0, occupied.length - 1)];

  while (boxes.length < maxSegments) {
    // Pick the box to split by count WEIGHTED BY COLOUR SPREAD, not by count
    // alone. Textbook median cut splits the most populous box, which is wrong
    // here: the dominant region of a flat illustration is huge but
    // perceptually TIGHT (its spread is just resampling/JPEG noise), so pure
    // population keeps subdividing one colour and starves small distinct
    // features. Measured on a synthetic bird: count-only produced 10 boxes
    // that the ΔE merge collapsed back to 6, and the red beak never got a
    // slot; span-weighted selection keeps the budget on genuinely different
    // colours instead.
    let target = -1;
    let best = 0;
    for (let i = 0; i < boxes.length; i++) {
      const bx = boxes[i];
      if (bx.end <= bx.start) continue; // single bin -- indivisible
      const span = Math.max(bx.hi[0] - bx.lo[0], bx.hi[1] - bx.lo[1], bx.hi[2] - bx.lo[2]);
      if (span < 1) continue; // already tighter than one bin: nothing to gain
      const score = bx.count * span;
      if (score > best) {
        best = score;
        target = i;
      }
    }
    if (target < 0) break; // every box is perceptually tight -- stop early

    const bx = boxes[target];
    // Longest axis in 5-bit units.
    const spans = [bx.hi[0] - bx.lo[0], bx.hi[1] - bx.lo[1], bx.hi[2] - bx.lo[2]];
    let axis = 0;
    if (spans[1] > spans[axis]) axis = 1;
    if (spans[2] > spans[axis]) axis = 2;
    if (spans[axis] === 0) {
      // All bins identical on every axis (can happen with ties) -- treat as
      // indivisible so the loop can't spin.
      bx.end = bx.start;
      continue;
    }

    // Sort this box's slice along the chosen axis, then cut at the
    // population median (median CUT, not mid-point: budget follows pixels).
    const slice = occupied.slice(bx.start, bx.end + 1);
    slice.sort((p, q) => axisOf(p)[axis] - axisOf(q)[axis]);
    for (let i = 0; i < slice.length; i++) occupied[bx.start + i] = slice[i];

    const half = bx.count / 2;
    let acc = 0;
    let cut = bx.start;
    for (let i = bx.start; i < bx.end; i++) {
      acc += binCount[occupied[i]];
      cut = i;
      if (acc >= half) break;
    }

    boxes[target] = makeBox(bx.start, cut);
    boxes.push(makeBox(cut + 1, bx.end));
  }

  // ── representatives: true mean of the actual 8-bit values in each box ──
  let reps = boxes
    .map((bx) => {
      let c = 0;
      let r = 0;
      let g = 0;
      let b = 0;
      for (let i = bx.start; i <= bx.end; i++) {
        const bi = occupied[i];
        c += binCount[bi];
        r += sumR[bi];
        g += sumG[bi];
        b += sumB[bi];
      }
      if (!c) return null;
      return {
        rgb: [Math.round(r / c), Math.round(g / c), Math.round(b / c)],
        count: c,
      };
    })
    .filter(Boolean);

  reps = mergeNearDuplicates(reps);

  const total = nOpaque || reps.reduce((s, f) => s + f.count, 0) || 1;
  const fills = reps.map((f) => ({ rgb: f.rgb, count: f.count, frac: f.count / total }));

  // Same ordering contract as the exact path: most pixels first, ties broken
  // by packed key so the result is deterministic (segment indices are
  // persisted in maps/*.json as merge_into).
  fills.sort(
    (a, b) =>
      b.count - a.count ||
      ((a.rgb[0] << 16) | (a.rgb[1] << 8) | a.rgb[2]) - ((b.rgb[0] << 16) | (b.rgb[1] << 8) | b.rgb[2])
  );
  return fills;
}

/** Collapse representatives within MERGE_DE of each other (pixel-weighted mean). */
function mergeNearDuplicates(reps, threshold = MERGE_DE) {
  const out = [];
  for (const r of reps) {
    const lab = oklabFromSrgb(r.rgb);
    let merged = false;
    for (const o of out) {
      const ol = o._lab;
      const d = Math.hypot(lab[0] - ol[0], lab[1] - ol[1], lab[2] - ol[2]);
      if (d < threshold) {
        // Pixel-weighted mean so the survivor sits where the pixels are.
        const tc = o.count + r.count;
        o.rgb = [
          Math.round((o.rgb[0] * o.count + r.rgb[0] * r.count) / tc),
          Math.round((o.rgb[1] * o.count + r.rgb[1] * r.count) / tc),
          Math.round((o.rgb[2] * o.count + r.rgb[2] * r.count) / tc),
        ];
        o.count = tc;
        o._lab = oklabFromSrgb(o.rgb);
        merged = true;
        break;
      }
    }
    if (!merged) out.push({ rgb: r.rgb.slice(), count: r.count, _lab: lab });
  }
  for (const o of out) delete o._lab;
  return out;
}
