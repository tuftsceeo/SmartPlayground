/**
 * raster.js -- winner-take-all rasterisation, taking a precomputed
 * coverageBySeg (see segment.js's computeSegmentStats/buildCoverageBySeg,
 * tier T2) rather than recomputing coverage per call -- coverage is
 * priority/decision-independent, so this whole module is the ~1ms tier T4
 * that can run synchronously on every interactive edit.
 */

import { W, H, CELL_ON, DEFAULT_PRIORITY } from "./constants.js";

const CELLS = W * H;

/**
 * @param {Array<Float64Array>} coverageBySeg  from segment.buildCoverageBySeg
 * @param {Array<{role, color, priority, merge_into}>} decisions  parallel to fills
 * @returns {Array<Float64Array|null>} scoreBySeg, null for role === 'off'
 */
export function scoreGrid(coverageBySeg, decisions) {
  const n = decisions.length;
  const scoreBySeg = new Array(n);
  for (let i = 0; i < n; i++) {
    const d = decisions[i];
    if (d.role === "off") {
      scoreBySeg[i] = null;
      continue;
    }
    const target = d.role === "merge" ? d.merge_into : i;
    const priority = decisions[target].priority ?? DEFAULT_PRIORITY;
    const cov = coverageBySeg[i];
    const score = new Float64Array(CELLS);
    for (let c = 0; c < CELLS; c++) score[c] = cov[c] * priority;
    scoreBySeg[i] = score;
  }
  return scoreBySeg;
}

export function effectiveColor(decisions, segId) {
  const d = decisions[segId];
  if (d.role === "merge") return decisions[d.merge_into].color;
  return d.color;
}

/** Shared winner-take-all pass (no connect pass) -- used by both rasterize() and cellsWon(). */
function winnerTakeAll(coverageBySeg, scoreBySeg) {
  const n = scoreBySeg.length;
  const winner = new Int16Array(CELLS).fill(-1);
  for (let c = 0; c < CELLS; c++) {
    let bestSeg = -1;
    let bestScore = 0.0;
    for (let i = 0; i < n; i++) {
      const score = scoreBySeg[i];
      if (score === null) continue;
      if (coverageBySeg[i][c] < CELL_ON) continue;
      const s = score[c];
      if (s > bestScore) {
        bestScore = s;
        bestSeg = i;
      }
    }
    winner[c] = bestSeg;
  }
  return winner;
}

/**
 * Connect pass: breaks single-cell-wide diagonal features out of dashed
 * lines by filling an orthogonal neighbour (see raster.py docstring).
 * Mutates `winner` in place.
 */
function connectPass(winner, coverageBySeg) {
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const seg = winner[y * W + x];
      if (seg === -1) continue;
      for (const [dy, dx] of [
        [-1, -1],
        [-1, 1],
        [1, -1],
        [1, 1],
      ]) {
        const ny = y + dy;
        const nx = x + dx;
        if (ny < 0 || ny >= H || nx < 0 || nx >= W) continue;
        if (winner[ny * W + nx] !== seg) continue;
        const oy = ny;
        const ox = x; // vertical neighbor (same col, target row)
        const py = y;
        const px = nx; // horizontal neighbor (same row, target col)
        const orthHasSeg =
          (oy >= 0 && oy < H && winner[oy * W + ox] === seg) ||
          (py >= 0 && py < H && px >= 0 && px < W && winner[py * W + px] === seg);
        if (orthHasSeg) continue;
        const covO = oy >= 0 && oy < H ? coverageBySeg[seg][oy * W + ox] : -1;
        const covP = py >= 0 && py < H && px >= 0 && px < W ? coverageBySeg[seg][py * W + px] : -1;
        if (covO >= covP && covO >= 0) winner[oy * W + ox] = seg;
        else if (covP >= 0) winner[py * W + px] = seg;
      }
    }
  }
  return winner;
}

/**
 * Winner-take-all + connect pass.
 * @returns {{winner: Int16Array, pixels: Array<[number,number,number]>}}
 */
export function rasterize(coverageBySeg, decisions) {
  const scoreBySeg = scoreGrid(coverageBySeg, decisions);
  const winner = connectPass(winnerTakeAll(coverageBySeg, scoreBySeg), coverageBySeg);

  const pixels = new Array(CELLS);
  for (let c = 0; c < CELLS; c++) {
    const seg = winner[c];
    pixels[c] = seg === -1 ? [0, 0, 0] : effectiveColor(decisions, seg) || [0, 0, 0];
  }
  return { winner, pixels };
}

/** overlay: Map or plain object of {flatIndex: [r,g,b]} -- applied last, always wins. */
export function applyOverlay(pixels, overlay) {
  const out = pixels.map((p) => p.slice());
  const entries = overlay instanceof Map ? overlay.entries() : Object.entries(overlay || {});
  for (const [k, rgb] of entries) {
    const idx = Number(k);
    if (idx >= 0 && idx < out.length) out[idx] = rgb.slice();
  }
  return out;
}

/**
 * Cells each segment wins, INCLUDING the connect pass.
 *
 * The Python original omitted the connect pass despite its docstring
 * claiming otherwise, so it undercounted exactly the thin diagonal features
 * that `priority` exists to rescue -- a segment could be reported as winning
 * too few cells (and get flagged by lint) while actually rendering fine.
 * That was ported deliberately for parity with the old CLI; with parity
 * dropped there is no reason to keep the bug.
 */
export function cellsWon(coverageBySeg, decisions) {
  const scoreBySeg = scoreGrid(coverageBySeg, decisions);
  const winner = connectPass(winnerTakeAll(coverageBySeg, scoreBySeg), coverageBySeg);
  const counts = new Array(decisions.length).fill(0);
  for (let c = 0; c < CELLS; c++) {
    const seg = winner[c];
    if (seg !== -1) counts[seg]++;
  }
  return counts;
}
