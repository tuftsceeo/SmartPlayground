/**
 * simpleSegmentList.js -- eye + crayon swatch; zero-cell rows auto-hide.
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
  el.className = "flex flex-col gap-2 max-w-[360px]";

  if (!state.fills.length) {
    el.innerHTML = `<div class="text-sm font-semibold text-[var(--muted2)]">No icon loaded.</div>`;
    return el;
  }

  state.fills.forEach((fill, i) => {
    if (isRowHidden(state, i)) return;

    const d = state.decisions[i];
    const visible = d.role !== "off";
    const colorStyle = swatchStyle(d.color);

    const row = document.createElement("div");
    row.className = "flex items-center gap-2.5 border-2 border-[var(--border)] rounded-[11px] px-2.5 py-2";
    row.dataset.segIdx = i;

    row.innerHTML = `
      <button type="button" data-color title="Pick colour"
              class="swatch-crayon w-[18px] h-[38px] ${visible ? "" : "opacity-35"}"
              style="background:${colorStyle}"></button>
      <span class="font-bold text-[13px] flex-1">seg ${i}</span>
      <button type="button" data-eye title="${visible ? "Hide this colour" : "Show this colour"}"
              class="icon-btn">
        <i data-lucide="${visible ? "eye" : "eye-off"}" class="w-4 h-4"></i>
      </button>
      <div data-toggle class="toggle-switch ${visible ? "is-on" : ""}"></div>
    `;

    row.querySelector("[data-eye]")?.addEventListener("click", () => {
      callbacks.onRoleChange(i, visible ? "off" : "color");
    });
    row.querySelector("[data-toggle]")?.addEventListener("click", () => {
      callbacks.onRoleChange(i, visible ? "off" : "color");
    });
    const colorBtn = row.querySelector("[data-color]");
    colorBtn?.addEventListener("click", () => callbacks.onOpenPalette(i, colorBtn));

    el.appendChild(row);
  });

  return el;
}
