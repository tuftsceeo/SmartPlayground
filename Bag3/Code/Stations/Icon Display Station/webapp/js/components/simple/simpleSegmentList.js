/**
 * simpleSegmentList.js -- colour swatch + eye toggle per segment. Zero-cell
 * rows auto-hide unless explicitly turned off. Indices must match decisions.
 */
import { swatchStyle } from "../../pipeline/ledGamut.js";

function isRowHidden(state, i) {
  const d = state.decisions[i];
  const won = state.cellsWon[i] ?? 0;
  if (d.role === "off") return false;
  return won === 0;
}

export function createSimpleSegmentList(state, callbacks) {
  const el = document.createElement("div");
  el.className = "flex flex-col divide-y divide-neutral-800";

  if (!state.fills.length) {
    el.innerHTML = `<div class="p-4 text-sm text-neutral-500">No icon loaded.</div>`;
    return el;
  }

  state.fills.forEach((fill, i) => {
    if (isRowHidden(state, i)) return;

    const d = state.decisions[i];
    const visible = d.role !== "off";
    const colorStyle = swatchStyle(d.color);

    const row = document.createElement("div");
    row.className = "p-2 flex items-center gap-2";
    row.dataset.segIdx = i;

    row.innerHTML = `
      <button type="button" data-eye title="${visible ? "Hide this colour" : "Show this colour"}"
              class="p-1.5 rounded border border-neutral-700 bg-neutral-800 hover:bg-neutral-700 text-neutral-300">
        <i data-lucide="${visible ? "eye" : "eye-off"}" class="w-4 h-4"></i>
      </button>
      <button type="button" data-color title="Pick colour"
              class="w-8 h-6 rounded border border-neutral-600 hover:border-neutral-300"
              style="background:${colorStyle}"></button>
    `;

    row.querySelector("[data-eye]")?.addEventListener("click", () => {
      callbacks.onRoleChange(i, visible ? "off" : "color");
    });
    const colorBtn = row.querySelector("[data-color]");
    colorBtn?.addEventListener("click", () => callbacks.onOpenPalette(i, colorBtn));

    el.appendChild(row);
  });

  return el;
}
