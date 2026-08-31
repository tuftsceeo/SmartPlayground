/**
 * documentSwatches.js -- crayon-shaped colours used in the current icon.
 */
import { ledDeltaE, JND, OFF_DUTY, isOff, swatchStyle } from "../pipeline/ledGamut.js";
import { doc } from "../state/doc.js";

function collectDocumentColors(decisions, overlay, intensity) {
  const out = [];

  function alreadySeen(duty) {
    return out.some((e) => !e.off && !isOff(e.duty) && ledDeltaE(e.duty, duty, intensity) < JND);
  }

  for (const d of decisions) {
    if (d.role !== "color" || !d.color || isOff(d.color)) continue;
    if (!alreadySeen(d.color)) out.push({ duty: d.color.slice(), off: false });
  }

  for (const duty of overlay.values()) {
    if (isOff(duty)) continue;
    if (!alreadySeen(duty)) out.push({ duty: duty.slice(), off: false });
  }

  let hasOff = false;
  for (const duty of overlay.values()) {
    if (isOff(duty)) {
      hasOff = true;
      break;
    }
  }
  if (hasOff) out.push({ duty: OFF_DUTY.slice(), off: true });

  return out;
}

export function createDocumentSwatches(state, { onPick, onAddColor }) {
  const el = document.createElement("div");
  el.className = "panel flex flex-col gap-2.5";

  if (!state.mode) {
    el.innerHTML = `
      <span class="panel-label">Palette</span>
      <span class="text-[11px] font-semibold text-[var(--muted2)]">Load an icon to see its colours</span>
    `;
    return el;
  }

  const colors = collectDocumentColors(state.decisions, doc.overlay, state.intensity);
  const brush = state.brushColor;

  el.innerHTML = `
    <span class="panel-label">Palette</span>
    <div class="flex flex-wrap gap-2 justify-center">
      ${colors
        .map((c, i) => {
          const selected =
            !c.off &&
            brush &&
            brush[0] === c.duty[0] &&
            brush[1] === c.duty[1] &&
            brush[2] === c.duty[2];
          return `
          <button type="button" data-swatch="${i}" title="${c.off ? "off" : "Use this colour"}"
                  class="swatch-crayon ${selected ? "is-selected" : ""}"
                  style="background:${swatchStyle(c.duty)}"></button>`;
        })
        .join("")}
      <button type="button" id="addColorBtn" class="swatch-crayon-add" title="Add a colour">
        <i data-lucide="plus" class="w-3.5 h-3.5"></i>
      </button>
    </div>
  `;

  el.querySelectorAll("[data-swatch]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const entry = colors[Number(btn.dataset.swatch)];
      onPick(entry.duty.slice());
    });
  });
  const addBtn = el.querySelector("#addColorBtn");
  addBtn?.addEventListener("click", () => onAddColor?.(addBtn));

  return el;
}
