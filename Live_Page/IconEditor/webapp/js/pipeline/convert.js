/**
 * convert.js -- orchestration glue tying the pipeline stages together,
 * mirroring iconlib/mapio.py:build() + image_to_icon.py:convert_one().
 * This is where the app.js/main.js recompute tiers (T0-T5, see plan) will
 * hook in.
 */

import { decodeToWorking, decodeUrlToWorking } from "./decode.js";
import { histogramFills } from "./histogram.js";
import {
  labelMap,
  computeSegmentStats,
  buildCoverageBySeg,
  buildOpaqueCoverage,
  autoPropose,
} from "./segment.js";
import { buildDecisions, toMapObj } from "./mapio.js";
import { rasterize, applyOverlay, cellsWon } from "./raster.js";
import { enforceFloor, iconText, lint } from "./emit.js";
import { DEFAULT_MAX_SEGMENTS } from "./constants.js";

/**
 * Full pipeline: source image (+ optional existing map) -> everything
 * needed to render/export/lint one icon.
 *
 * @param {ImageData} imageData  from decode.js, WORKxWORK
 * @param {object|null} existingMap  a loaded maps/<name>.json, or null
 * @param {{maxSegments?: number}} opts
 */
export function buildIcon(imageData, existingMap, opts = {}) {
  const maxSegments = opts.maxSegments ?? existingMap?.max_segments ?? DEFAULT_MAX_SEGMENTS;

  const { fills, mode } = histogramFills(imageData, { maxSegments });
  const nSegs = fills.length;
  const labels = labelMap(imageData, fills);
  const stats = computeSegmentStats(labels, nSegs);
  const coverageBySeg = buildCoverageBySeg(stats.covCounts, nSegs);
  const opaqueCoverage = buildOpaqueCoverage(stats.opaqueCounts);

  const proposed = autoPropose(fills, nSegs, stats.ringMatch, stats.ringTotal, stats.bgMatch);
  const { decisions, overlay, intensity } = buildDecisions(fills, proposed, existingMap);

  const { winner, pixels: rasterPixels } = rasterize(coverageBySeg, decisions);
  const overlaid = applyOverlay(rasterPixels, overlay);
  const pixels = enforceFloor(overlaid);

  const won = cellsWon(coverageBySeg, decisions);
  const problems = lint(pixels, fills, decisions, won, intensity);

  return {
    mode,
    fills,
    labels,
    coverageBySeg,
    opaqueCoverage,
    decisions,
    overlay,
    intensity,
    winner,
    pixels,
    cellsWon: won,
    problems,
  };
}

/** Convenience: fetch a source PNG + its map (if present) and run the pipeline. */
export async function buildIconFromUrls(pngUrl, mapUrl) {
  const { imageData } = await decodeToWorking(await (await fetch(pngUrl)).blob());
  let existingMap = null;
  try {
    const res = await fetch(mapUrl);
    if (res.ok) existingMap = await res.json();
  } catch {
    /* no existing map -- fine */
  }
  const result = buildIcon(imageData, existingMap, { maxSegments: existingMap?.max_segments });
  return { result, existingMap };
}

export { decodeUrlToWorking };
export { iconText, toMapObj };
