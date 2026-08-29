/**
 * histogram.js -- exact-fill histogram, with quantize.js as the fallback
 * for images that aren't flat enough for it.
 *
 * The fill ordering must be DETERMINISTIC: segment indices are written into
 * maps/<name>.json as `merge_into`, so an unstable sort would silently
 * re-point saved merge targets on reload. Hence the explicit tie-break.
 */

import { ALPHA_THRESH, MIN_FRAC, MAX_SEGMENTS } from "./constants.js";
import { quantizeFills } from "./quantize.js";

function packRgb(r, g, b) {
  return (r << 16) | (g << 8) | b;
}

/**
 * @param {ImageData} imageData
 * @returns {{fills: Array<{rgb:[number,number,number], count:number, frac:number}>, mode: 'exact'|'quantize'}}
 */
export function histogramFills(
  imageData,
  { alphaThresh = ALPHA_THRESH, minFrac = MIN_FRAC, maxSegments = MAX_SEGMENTS } = {}
) {
  const { data, width, height } = imageData;
  const counts = new Map(); // packedRGB -> count
  let nOpaque = 0;

  for (let i = 0, n = width * height; i < n; i++) {
    const o = i * 4;
    const a = data[o + 3];
    if (a < alphaThresh) continue;
    const key = packRgb(data[o], data[o + 1], data[o + 2]);
    counts.set(key, (counts.get(key) || 0) + 1);
    nOpaque++;
  }

  if (nOpaque === 0) return { fills: [], mode: "exact" };

  const fills = [];
  for (const [key, cnt] of counts) {
    const rgb = [(key >> 16) & 0xff, (key >> 8) & 0xff, key & 0xff];
    fills.push({ rgb, count: cnt, frac: cnt / nOpaque, _key: key });
  }
  // Most pixels first; ties broken by packed RGB so the order is stable.
  fills.sort((a, b) => b.count - a.count || a._key - b._key);
  for (const f of fills) delete f._key;

  const big = fills.filter((f) => f.frac >= minFrac);
  const covered = big.reduce((s, f) => s + f.frac, 0);

  if (big.length <= maxSegments && covered >= 0.9) {
    return { fills: big.slice(0, maxSegments), mode: "exact" };
  }

  // Not flat enough for the exact path -- quantize. Note this must NOT be a
  // "take the top-N most frequent exact colours" truncation, which is what
  // this used to do: on resampled vector art the top N are all one-unit
  // variants of the same few fills, so distinct small features get no slot
  // and nearest-fill flip-flops between the twins. See quantize.js.
  return { fills: quantizeFills(counts, nOpaque, maxSegments), mode: "quantize" };
}
