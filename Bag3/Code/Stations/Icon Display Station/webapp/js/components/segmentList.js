/**
 * segmentList.js -- per-segment rows: role/color/priority/merge, palette
 * swatches, cells-won badge. Priority/color dragging use fast "Input"
 * callbacks (imperative repaint, no store rebuild) with a "Commit"
 * callback on release that updates the store -- see plan §fast paths.
 */

import { MIN_FEATURE_CELLS } from "../pipeline/constants.js";
import { rgbToHex } from "../utils/colorUtils.js";
import { swatchStyle } from "../pipeline/ledGamut.js";

export function createSegmentList(state, callbacks) {
  const el = document.createElement("div");
  el.className = "flex flex-col divide-y divide-neutral-800";

  if (!state.fills.length) {
    el.innerHTML = `<div class="p-4 text-sm text-neutral-500">No icon loaded.</div>`;
    return el;
  }

  state.fills.forEach((fill, i) => {
    const d = state.decisions[i];
    const won = state.cellsWon[i] ?? 0;
    const wonBad = d.role === "color" && won < MIN_FEATURE_CELLS;

    const row = document.createElement("div");
    row.className = "p-3 flex flex-col gap-2";
    row.dataset.segIdx = i;

    // fill.rgb is a SOURCE pixel (already sRGB) -> show raw.
    // d.color is AUTHORED linear duty -> show how the PANEL renders it, via
    // the device model. Mixing these two up is the gamma/gamut trap that made
    // every authored colour look muted next to the real matrix.
    const srcHex = rgbToHex(fill.rgb);
    const colorStyle = swatchStyle(d.color);

    row.innerHTML = `
      <div class="flex items-center gap-2 text-xs text-neutral-400">
        <span class="w-4 h-4 rounded border border-neutral-700" style="background:${srcHex}"></span>
        <span>seg ${i} · src rgb(${fill.rgb.join(",")}) · ${(fill.frac * 100).toFixed(1)}%</span>
        <span class="ml-auto ${wonBad ? "text-red-400 font-semibold" : "text-neutral-500"}">cells won: ${won}</span>
      </div>

      <div class="flex items-center gap-2">
        <select data-role class="text-xs bg-neutral-800 text-neutral-200 rounded px-2 py-1 border border-neutral-700">
          <option value="color" ${d.role === "color" ? "selected" : ""}>color</option>
          <option value="off" ${d.role === "off" ? "selected" : ""}>off</option>
          <option value="merge" ${d.role === "merge" ? "selected" : ""}>merge</option>
        </select>

        ${
          d.role === "color"
            ? `<button data-color title="Pick from the colours this panel can actually show"
                       class="w-8 h-6 rounded border border-neutral-600 hover:border-neutral-300"
                       style="background:${colorStyle}"></button>`
            : ""
        }
        ${
          d.role === "merge"
            ? `<select data-merge class="text-xs bg-neutral-800 text-neutral-200 rounded px-2 py-1 border border-neutral-700">
                ${state.fills
                  .map((f, j) => (j === i ? "" : `<option value="${j}" ${d.merge_into === j ? "selected" : ""}>seg ${j}</option>`))
                  .join("")}
              </select>`
            : ""
        }

        <button data-off class="text-xs px-2 py-1 rounded bg-neutral-800 hover:bg-red-900 text-neutral-300 ml-auto">Off</button>
      </div>

      ${
        d.role !== "off"
          ? `<label class="flex items-center gap-2 text-xs text-neutral-400">
              priority
              <input type="range" data-priority min="0.1" max="3.0" step="0.1" value="${d.priority}" class="flex-1" />
              <span data-priorityVal class="w-8 text-neutral-200">${d.priority.toFixed(1)}</span>
            </label>`
          : ""
      }

    `;

    row.querySelector("[data-role]")?.addEventListener("change", (e) => callbacks.onRoleChange(i, e.target.value));
    row.querySelector("[data-off]")?.addEventListener("click", () => callbacks.onRoleChange(i, "off"));
    row.querySelector("[data-merge]")?.addEventListener("change", (e) => callbacks.onMergeChange(i, Number(e.target.value)));

    const colorBtn = row.querySelector("[data-color]");
    colorBtn?.addEventListener("click", () => callbacks.onOpenPalette(i, colorBtn));

    const prioInput = row.querySelector("[data-priority]");
    const prioVal = row.querySelector("[data-priorityVal]");
    prioInput?.addEventListener("input", (e) => {
      const v = Number(e.target.value);
      if (prioVal) prioVal.textContent = v.toFixed(1);
      callbacks.onPriorityInput(i, v);
    });
    prioInput?.addEventListener("change", (e) => callbacks.onPriorityCommit(i, Number(e.target.value)));


    el.appendChild(row);
  });

  return el;
}

