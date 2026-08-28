/**
 * toolRow.js -- pencil / eraser / revert / brush / undo. Visible in both modes;
 * replaces the old helper sentence and hidden right-click-only revert.
 */
import { swatchStyle } from "../pipeline/ledGamut.js";

const TOOLS = [
  { id: "pencil", icon: "pencil", title: "Pencil" },
  { id: "eraser", icon: "eraser", title: "Eraser" },
  { id: "revert", icon: "undo-2", title: "Revert to imported" },
];

export function createToolRow(state, { onToolChange, onUndo, onOpenBrushPalette }) {
  const el = document.createElement("div");
  el.className = "px-3 py-2 flex items-center gap-2 flex-wrap";

  const toolBtns = TOOLS.map(
    (t) => `
    <button type="button" data-tool="${t.id}" title="${t.title}"
            class="p-2 rounded border ${
              state.activeTool === t.id
                ? "border-emerald-600 bg-emerald-950 text-emerald-200"
                : "border-neutral-700 bg-neutral-800 hover:bg-neutral-700 text-neutral-300"
            }">
      <i data-lucide="${t.icon}" class="w-4 h-4"></i>
    </button>`
  ).join("");

  el.innerHTML = `
    <div class="flex items-center gap-1">${toolBtns}</div>
    <button type="button" id="brushColor" title="Pick from the colours this panel can actually show"
            class="w-8 h-6 rounded border border-neutral-600 hover:border-neutral-300"
            style="background:${swatchStyle(state.brushColor)}"></button>
    <button type="button" id="undoBtn"
            class="ml-auto text-xs px-2 py-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 flex items-center gap-1">
      <i data-lucide="rotate-ccw" class="w-3.5 h-3.5"></i> Undo
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
