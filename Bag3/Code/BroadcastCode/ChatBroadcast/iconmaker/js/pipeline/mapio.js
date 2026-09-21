/**
 * mapio.js -- load/save maps/<name>.json, tying segmentation + auto-propose
 * + the saved map into one `decisions` list, keyed by exact source RGB so
 * decisions survive a re-run.
 */

import { DEFAULT_INTENSITY } from "./constants.js";

export function rgbKey(rgb) {
  return rgb.join(",");
}

function decisionFromSaved(saved) {
  const d = { role: saved.role, priority: saved.priority ?? 1.0 };
  if (saved.role === "merge") {
    d.merge_into = saved.merge_into;
    d.color = null;
  } else if (saved.role === "color") {
    d.color = saved.color.slice();
  } else {
    d.color = null;
  }
  return d;
}

/**
 * Merge freshly-computed `fills` with an existing map's saved decisions
 * (matched by exact source RGB key) or the auto-proposal fallback.
 * Segment indices ("merge_into" targets) are always indices into THIS
 * call's `fills` -- saved merge targets are re-resolved by rgb key.
 *
 * @param {Array} fills
 * @param {Array} proposed  from segment.autoPropose, parallel to fills
 * @param {object|null} existingMap
 * @returns {{decisions: Array, overlay: object, intensity: number}}
 */
export function buildDecisions(fills, proposed, existingMap) {
  const savedByKey = {};
  if (existingMap) {
    for (const [key, saved] of Object.entries(existingMap.decisions || {})) savedByKey[key] = saved;
  }
  const keyToIdx = {};
  fills.forEach((f, i) => (keyToIdx[rgbKey(f.rgb)] = i));

  const decisions = fills.map((f, i) => {
    const key = rgbKey(f.rgb);
    const saved = savedByKey[key];
    if (saved !== undefined) {
      const d = decisionFromSaved(saved);
      if (d.role === "merge") {
        const targetKey = saved.merge_into_key;
        d.merge_into = targetKey in keyToIdx ? keyToIdx[targetKey] : i;
      }
      return d;
    }
    const p = proposed[i];
    return { role: p.role, color: p.color, priority: p.priority };
  });

  const overlay = existingMap ? { ...(existingMap.overlay || {}) } : {};
  const intensity =
    existingMap && existingMap.intensity !== undefined ? existingMap.intensity : DEFAULT_INTENSITY;

  return { decisions, overlay, intensity };
}

function round5(f) {
  return Math.round(f * 1e5) / 1e5;
}

/** @returns {object} the maps/<name>.json shape. */
export function toMapObj(sourcePath, fills, decisions, overlay, intensity, maxSegments) {
  const decisionsByKey = {};
  fills.forEach((f, i) => {
    const d = decisions[i];
    const entry = { role: d.role, priority: d.priority ?? 1.0 };
    if (d.role === "merge") {
      entry.merge_into_key = rgbKey(fills[d.merge_into].rgb);
      entry.merge_into = d.merge_into;
    } else if (d.role === "color") {
      entry.color = d.color.slice();
    }
    decisionsByKey[rgbKey(f.rgb)] = entry;
  });

  return {
    source: sourcePath,
    max_segments: maxSegments,
    intensity,
    fills: fills.map((f) => ({ rgb: f.rgb.slice(), count: f.count, frac: round5(f.frac) })),
    decisions: decisionsByKey,
    overlay,
  };
}

/** Serialize a map object as pretty JSON. */
export function serializeMap(mapObj) {
  return JSON.stringify(mapObj, null, 2) + "\n";
}
