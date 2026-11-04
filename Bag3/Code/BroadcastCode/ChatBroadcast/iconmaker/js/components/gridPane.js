/**
 * gridPane.js -- brush color + undo controls under the (persistent,
 * imperatively-painted) 16x16 grid canvas main.js owns directly.
 */
import { swatchStyle } from "../pipeline/ledGamut.js";

export function createGridControls(state, { onOpenBrushPalette, onUndo }) {
  const el = document.createElement("div");
  el.className = "px-3 py-2 flex items-center gap-2 text-xs text-neutral-400";
  el.innerHTML = `
    brush
    <button id="brushColor" title="Pick from the colours this panel can actually show"
            class="w-8 h-6 rounded border border-neutral-600 hover:border-neutral-300"
            style="background:${swatchStyle(state.brushColor)}"></button>
    <span class="text-neutral-500">click/drag to paint · right-click clears a cell · pick "off" to paint dark</span>
    <button id="undoBtn" class="ml-auto text-xs px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200">Undo</button>
  `;
  const brushBtn = el.querySelector("#brushColor");
  brushBtn?.addEventListener("click", () => onOpenBrushPalette(brushBtn));
  el.querySelector("#undoBtn")?.addEventListener("click", onUndo);
  return el;
}
