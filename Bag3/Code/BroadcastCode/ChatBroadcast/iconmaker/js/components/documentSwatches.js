/**
 * documentSwatches.js -- the "Palette": colours from the current
 * segmentation, plus any manually added via the brush dropper / "+" button.
 * In simple mode each swatch is drawn as an actual Crayon.svg with its
 * MainColor group recoloured; overlap is intentional -- a box of crayons.
 */
import { ledDeltaE, JND, OFF_DUTY, isOff, swatchStyle } from "../pipeline/ledGamut.js";
import { doc } from "../state/doc.js";
import { crayonSwatchHtml } from "../utils/toolArt.js";

function collectDocumentColors(decisions, overlay, intensity, customColors) {
  const out = [];

  function alreadySeen(duty) {
    return out.some((e) => !e.off && !isOff(e.duty) && ledDeltaE(e.duty, duty, intensity) < JND);
  }

  for (const duty of customColors || []) {
    if (isOff(duty)) continue;
    if (!alreadySeen(duty)) out.push({ duty: duty.slice(), off: false });
  }

  const segmentColors = decisions.filter((d) => d.role === "color" && d.color && !isOff(d.color));
  if (segmentColors.length) {
    for (const d of segmentColors) {
      if (!alreadySeen(d.color)) out.push({ duty: d.color.slice(), off: false });
    }
  } else if (doc.pixels) {
    // An icon opened from the library arrives as finished pixels with no
    // segmentation behind them, so there are no decisions to read. Its
    // palette is simply the colours it is drawn with -- exactly those, not a
    // leftover set from whatever was segmented before it.
    for (const px of doc.pixels) {
      if (isOff(px)) continue;
      if (!alreadySeen(px)) out.push({ duty: px.slice(), off: false });
    }
  }

  for (const duty of overlay.values()) {
    if (isOff(duty)) continue;
    if (!alreadySeen(duty)) out.push({ duty: duty.slice(), off: false });
  }

  // "Off" is a real colour to paint with -- the unlit pixel. It counts
  // whether it came from a brush stroke or from the icon as drawn.
  let hasOff = false;
  for (const duty of overlay.values()) {
    if (isOff(duty)) {
      hasOff = true;
      break;
    }
  }
  if (!hasOff && !segmentColors.length && doc.pixels) {
    hasOff = doc.pixels.some((px) => isOff(px));
  }
  if (hasOff) out.push({ duty: OFF_DUTY.slice(), off: true });

  return out;
}

export function createDocumentSwatches(state, { onPick, onAddColor }) {
  const el = document.createElement("div");
  el.className = "panel flex flex-col gap-2.5";
  const simple = state.uiMode === "simple";

  if (!state.mode) {
    el.innerHTML = `
      <span class="panel-label">Palette</span>
      <span class="text-[11px] font-semibold text-[var(--muted2)]">Load an icon to see its colours</span>
    `;
    return el;
  }

  const colors = collectDocumentColors(state.decisions, doc.overlay, state.intensity, state.customPaletteColors);
  const brush = state.brushColor;

  el.innerHTML = `
    <span class="panel-label">Palette</span>
    <div class="flex flex-wrap ${simple ? "swatch-crayon-box" : "gap-2 justify-center"}">
      ${colors
        .map((c, i) => {
          const selected =
            !c.off &&
            brush &&
            brush[0] === c.duty[0] &&
            brush[1] === c.duty[1] &&
            brush[2] === c.duty[2];
          const artInner = simple && !c.off ? crayonSwatchHtml(swatchStyle(c.duty)) : "";
          const bg = simple && !c.off ? "" : `background:${swatchStyle(c.duty)}`;
          return `
          <button type="button" data-swatch="${i}" title="${c.off ? "off" : "Use this colour"}"
                  class="swatch-crayon ${simple ? "swatch-crayon-art" : ""} ${selected ? "is-selected" : ""}"
                  style="${bg}">${artInner}</button>`;
        })
        .join("")}
      <button type="button" id="addColorBtn" class="swatch-crayon-add ${simple ? "swatch-crayon-art" : ""}" title="Add a colour">
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
