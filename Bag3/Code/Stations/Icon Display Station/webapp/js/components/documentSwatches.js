/**
 * documentSwatches.js -- colours actually used in the current icon, clickable
 * to set the brush. Mounted in both simple and advanced modes.
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

export function createDocumentSwatches(state, { onPick }) {
  const el = document.createElement("div");
  el.className = "px-3 py-1.5 flex items-center gap-2 flex-wrap";

  if (!state.mode) {
    el.innerHTML = `<span class="text-[11px] text-neutral-600">Load an icon to see its colours</span>`;
    return el;
  }

  const colors = collectDocumentColors(state.decisions, doc.overlay, state.intensity);
  if (!colors.length) {
    el.innerHTML = `<span class="text-[11px] text-neutral-600">No colours yet</span>`;
    return el;
  }

  el.innerHTML = `
    <span class="text-[11px] text-neutral-500 shrink-0">colours in this icon</span>
    <div class="flex flex-wrap gap-1">
      ${colors
        .map(
          (c, i) => `
        <button type="button" data-swatch="${i}" title="${c.off ? "off" : "Use this colour"}"
                class="w-6 h-6 rounded border border-neutral-600 hover:border-neutral-300"
                style="background:${swatchStyle(c.duty)}"></button>`
        )
        .join("")}
    </div>
  `;

  el.querySelectorAll("[data-swatch]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const entry = colors[Number(btn.dataset.swatch)];
      onPick(entry.duty.slice());
    });
  });

  return el;
}
