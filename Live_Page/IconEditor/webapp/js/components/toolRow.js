/**
 * toolRow.js -- vertical pencil / eraser / revert stack matching the
 * prototype. Simple mode renders the pre-rotated landscape art-supply SVGs
 * as bookmark-style tabs bleeding off the sidebar; advanced mode renders
 * the same art as a small, fully-contained icon inside its usual bordered
 * button. Undo lives in the top bar now.
 */
import { swatchStyle } from "../pipeline/ledGamut.js";
import { ROTATED_COLOR_PENCIL_SVG, ROTATED_PENCIL_ERASER_SVG, landscapeArtHtml, compactArtHtml } from "../utils/toolArt.js";

const TOOLS = [
  { id: "revert", title: "Reset pixel to auto colour", activeClass: "is-active-revert" },
  { id: "eraser", title: "Erase (set to off)", activeClass: "is-active-eraser" },
  { id: "pencil", title: "Draw", activeClass: "is-active-pencil" },
];

function artContentFor(id, brushCss, compact) {
  const render = compact ? compactArtHtml : landscapeArtHtml;
  if (id === "revert") return render(ROTATED_PENCIL_ERASER_SVG, null);
  if (id === "eraser") return render(ROTATED_COLOR_PENCIL_SVG, "#2b2b2b");
  return render(ROTATED_COLOR_PENCIL_SVG, brushCss);
}

export function createToolRow(state, { onToolChange, onOpenBrushPalette }) {
  const el = document.createElement("div");
  el.className = "flex flex-col gap-2.5 w-full";
  const simple = state.uiMode === "simple";
  const brushCss = swatchStyle(state.brushColor);

  const toolBtns = TOOLS.map((t) => {
    const active = state.activeTool === t.id ? t.activeClass : "";
    const content = artContentFor(t.id, brushCss, !simple);
    return `
      <button type="button" data-tool="${t.id}" title="${t.title}" class="tool-btn ${simple ? "tool-btn-art" : ""} ${active}">
        ${content}
      </button>`;
  }).join("");

  el.innerHTML = `
    ${toolBtns}
    <button type="button" id="brushColor" title="Brush colour"
            class="tool-btn h-10"
            style="background:${swatchStyle(state.brushColor)};border-color:var(--ink)"></button>
  `;

  el.querySelectorAll("[data-tool]").forEach((btn) => {
    btn.addEventListener("click", () => onToolChange(btn.dataset.tool));
  });
  const brushBtn = el.querySelector("#brushColor");
  brushBtn?.addEventListener("click", () => onOpenBrushPalette(brushBtn));

  return el;
}
