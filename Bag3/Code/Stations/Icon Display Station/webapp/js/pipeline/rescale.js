/**
 * rescale.js -- move an icon between panel sizes.
 *
 * The motivating case: a 5x5 wand icon shown on the 16x16 station panel.
 *
 * UPSCALING USES AN INTEGER BLOCK FACTOR, CENTRED -- not a stretch to fill.
 * 16/5 is 3.2, so filling the panel would need some cells 3px and others 4px
 * wide, which visibly distorts a glyph drawn on a 5x5 grid (round things go
 * lumpy, symmetry breaks). Scaling 3x gives a clean 15x15 centred in 16x16
 * with one row/column of margin -- exactly what icon_test.py already does
 * with the 5x5 SHAPE_* glyphs, so this matches existing house convention.
 *
 * DOWNSCALING IS DELIBERATELY NOT DONE HERE. Going 16x16 -> 5x5 throws away
 * ~90% of the cells; averaging produces muddy colours that then have to be
 * re-snapped to the panel palette, and thin features vanish entirely. That
 * wants the real pipeline (re-segment the source at the smaller size), not a
 * pixel resample. downscaleAdvice() explains that rather than pretending.
 */

/**
 * @returns {{factor:number, offsetX:number, offsetY:number, fits:boolean}}
 *   factor 0 means the target is smaller than the source in some axis.
 */
export function fitPlan(fromW, fromH, toW, toH) {
  const factor = Math.floor(Math.min(toW / fromW, toH / fromH));
  if (factor < 1) return { factor: 0, offsetX: 0, offsetY: 0, fits: false };
  const usedW = fromW * factor;
  const usedH = fromH * factor;
  return {
    factor,
    // Centre, biasing the leftover margin to the right/bottom (integer
    // division) -- the same placement icon_test.py uses.
    offsetX: Math.floor((toW - usedW) / 2),
    offsetY: Math.floor((toH - usedH) / 2),
    fits: true,
  };
}

/**
 * Block-scale an icon up to a larger panel.
 * @param {Array<[number,number,number]>} pixels  fromW*fromH, row-major
 * @returns {Array<[number,number,number]>} toW*toH, row-major, padded with off
 */
export function upscaleIcon(pixels, fromW, fromH, toW, toH) {
  const plan = fitPlan(fromW, fromH, toW, toH);
  if (!plan.fits) {
    throw new Error(
      `cannot upscale ${fromW}x${fromH} to ${toW}x${toH}: target is smaller -- see downscaleAdvice()`
    );
  }
  const { factor, offsetX, offsetY } = plan;
  const out = new Array(toW * toH);
  for (let i = 0; i < out.length; i++) out[i] = [0, 0, 0]; // margin stays off

  for (let sy = 0; sy < fromH; sy++) {
    for (let sx = 0; sx < fromW; sx++) {
      const src = pixels[sy * fromW + sx];
      for (let dy = 0; dy < factor; dy++) {
        const ty = offsetY + sy * factor + dy;
        if (ty < 0 || ty >= toH) continue;
        for (let dx = 0; dx < factor; dx++) {
          const tx = offsetX + sx * factor + dx;
          if (tx < 0 || tx >= toW) continue;
          out[ty * toW + tx] = src.slice();
        }
      }
    }
  }
  return out;
}

/** True when `pixels` is the right length for a panel of this size. */
export function matchesSize(pixels, w, h) {
  return Array.isArray(pixels) && pixels.length === w * h;
}

/**
 * Why we don't silently resample downward, phrased for the UI.
 * @returns {string}
 */
export function downscaleAdvice(fromW, fromH, toW, toH) {
  return (
    `A ${fromW}x${fromH} icon has ${fromW * fromH} cells and a ${toW}x${toH} panel has ` +
    `${toW * toH}. Shrinking it would average away most of the detail and the colours ` +
    `would no longer be panel colours. Re-import the original artwork with the ` +
    `${toW}x${toH} profile selected instead -- the segmenter makes much better choices ` +
    `at the target size than a resample can.`
  );
}
