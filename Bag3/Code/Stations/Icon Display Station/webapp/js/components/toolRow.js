/**
 * toolRow.js -- vertical pencil / eraser / revert / undo matching the prototype.
 */
import { swatchStyle } from "../pipeline/ledGamut.js";

const TOOLS = [
  { id: "pencil", icon: "pencil", title: "Draw", activeClass: "is-active-pencil" },
  { id: "eraser", icon: "eraser", title: "Erase (set to off)", activeClass: "is-active-eraser" },
  { id: "revert", icon: "rotate-ccw", title: "Reset pixel to auto colour", activeClass: "is-active-revert" },
];

export function createToolRow(state, { onToolChange, onUndo, onOpenBrushPalette }) {
  const el = document.createElement("div");
  el.className = "flex flex-col gap-2.5 w-full";

  const toolBtns = TOOLS.map((t) => {
    const active = state.activeTool === t.id ? t.activeClass : "";
    return `
      <button type="button" data-tool="${t.id}" title="${t.title}" class="tool-btn ${active}">
        <i data-lucide="${t.icon}" class="w-[19px] h-[19px]"></i>
      </button>`;
  }).join("");

  el.innerHTML = `
    ${toolBtns}
    <button type="button" id="brushColor" title="Brush colour"
            class="tool-btn h-10"
            style="background:${swatchStyle(state.brushColor)};border-color:var(--ink)"></button>
    <button type="button" id="undoBtn" title="Undo" class="tool-btn">
      <i data-lucide="undo-2" class="w-[19px] h-[19px]"></i>
    </button>
  `;

  el.querySelectorAll("[data-tool]").forEach((btn) => {
    btn.addEventListener("click", () => onToolChange(btn.dataset.tool));
  });
  const brushBtn = el.querySelector("#brushColor");
  brushBtn?.addEventListener("click", () => onOpenBrushPalette(brushBtn));
  el.querySelector("#undoBtn")?.addEventListener("click", onUndo);

  return el;
}
