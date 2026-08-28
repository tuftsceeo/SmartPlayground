/**
 * emit.js -- floor enforcement, the device-contract ICON text writer,
 * ICON text, and the lint pass. iconText() must match write_icon()
 * character for character (see plan §Byte-exact emit) so a downloaded
 * icon diffs clean against the Python CLI's output.
 */

import { W, H, CH_FLOOR, MAX_LIT_COLORS, MIN_FEATURE_CELLS } from "./constants.js";
import { ledDeltaE, JND } from "./ledGamut.js";

/** Any nonzero channel below `floor` is raised to `floor`. Zero stays zero. */
export function enforceFloor(pixels, floor = CH_FLOOR) {
  return pixels.map(([r, g, b]) => [r, g, b].map((c) => (c === 0 ? 0 : Math.max(floor, c))));
}

/**
 * Byte-exact match for iconlib/emit.py:write_icon's text output (minus the
 * header comment, which the web app writes differently -- see webapp
 * README's parity notes).
 * @param {Array<[number,number,number]>} pixels  flat 256, row-major
 * @param {string} [nameComment]
 */
export function iconText(pixels, nameComment) {
  const lines = [];
  if (nameComment) lines.push(`# ${nameComment}`);
  lines.push("ICON = (");
  for (let row = 0; row < H; row++) {
    const rowPixels = pixels.slice(row * W, (row + 1) * W);
    const tuples = rowPixels.map(([r, g, b]) => `(${r}, ${g}, ${b})`);
    lines.push(`    ${tuples.join(", ")},`);
  }
  lines.push(")");
  return lines.join("\n") + "\n";
}

function pixEq(a, b) {
  return a[0] === b[0] && a[1] === b[1] && a[2] === b[2];
}
const isBlack = (p) => p[0] === 0 && p[1] === 0 && p[2] === 0;

/**
 * @returns {string[]} human-readable warnings, empty = clean.
 */
export function lint(pixels, fills, decisions, cellsWonArr, intensity) {
  const problems = [];

  const litKeys = new Set();
  for (const p of pixels) if (!isBlack(p)) litKeys.add(p.join(","));
  if (litKeys.size > MAX_LIT_COLORS) {
    problems.push(`${litKeys.size} distinct lit colors on the grid (max recommended ${MAX_LIT_COLORS})`);
  }

  for (let i = 0; i < decisions.length; i++) {
    const d = decisions[i];
    if (d.role !== "color") continue;
    const won = i < cellsWonArr.length ? cellsWonArr[i] : 0;
    const rgbStr = `(${fills[i].rgb.join(", ")})`;
    if (won === 0) {
      problems.push(`segment ${i} ${rgbStr} is colored but won zero cells`);
    } else if (won < MIN_FEATURE_CELLS) {
      problems.push(`segment ${i} ${rgbStr} only won ${won} cell(s) (min feature size ${MIN_FEATURE_CELLS})`);
    }
  }

  // Two segments authored to colours the panel cannot distinguish: the user
  // sees two colours in the editor and one colour on the hardware.
  for (let i = 0; i < decisions.length; i++) {
    for (let j = i + 1; j < decisions.length; j++) {
      const a = decisions[i];
      const b = decisions[j];
      if (a.role !== "color" || b.role !== "color" || !a.color || !b.color) continue;
      if ((cellsWonArr[i] ?? 0) === 0 || (cellsWonArr[j] ?? 0) === 0) continue;
      const dE = ledDeltaE(a.color, b.color, intensity);
      if (dE < JND) {
        problems.push(
          `segments ${i} and ${j} are different colours in the editor but render ` +
            `the same on the panel (dE ${dE.toFixed(3)}, need ${JND})`
        );
      }
    }
  }

  for (const [r, g, b] of pixels) {
    for (const c of [r, g, b]) {
      if (c > 0 && Math.trunc(c * intensity) === 0) {
        problems.push(`channel value ${c} truncates to 0 on-device at intensity=${intensity.toFixed(2)}`);
        break;
      }
    }
  }

  for (let row = 0; row < H; row++) {
    for (let col = 0; col < W; col++) {
      const idx = row * W + col;
      const c1 = pixels[idx];
      for (const [dr, dc] of [
        [0, 1],
        [1, 0],
      ]) {
        const r2 = row + dr;
        const c2 = col + dc;
        if (r2 >= H || c2 >= W) continue;
        const c2v = pixels[r2 * W + c2];
        if (isBlack(c1) || isBlack(c2v) || pixEq(c1, c2v)) continue;
        // Separation is measured on the PANEL, not on authored bytes. The
        // old max-channel-delta test compared duty values, which does not
        // answer "will a viewer tell these apart?" -- the device's per-channel
        // weighting and its intensity truncation both intervene. It missed
        // real collisions: a pale pink and a pale orange sitting 50 apart in
        // authored bytes are dE 0.035 on the panel, i.e. the same colour.
        const dE = ledDeltaE(c1, c2v, intensity);
        if (dE < JND) {
          problems.push(
            `adjacent cells (${row},${col}) (${c1.join(", ")}) and (${r2},${c2}) (${c2v.join(", ")}) ` +
              `look the same on the panel (dE ${dE.toFixed(3)}, need ${JND})`
          );
        }
      }
    }
  }

  const seen = new Set();
  const deduped = [];
  for (const p of problems) {
    if (!seen.has(p)) {
      seen.add(p);
      deduped.push(p);
    }
  }
  return deduped;
}
