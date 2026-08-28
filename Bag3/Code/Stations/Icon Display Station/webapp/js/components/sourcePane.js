/**
 * sourcePane.js -- import controls above the (persistent, imperatively-
 * painted) source/segmented canvases main.js owns directly.
 */

export function createImportControls(state, { onFilePicked, onOpenCrop }) {
  const el = document.createElement("div");
  el.className = "px-3 py-2 border-b border-neutral-800 flex flex-col gap-2";

  const s = state.sourceInfo; // {width, height, name} or null
  const fitLabel = state.transformLabel || "";

  el.innerHTML = `
    <input type="file" id="fileInput" accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml"
           class="text-xs text-neutral-400" />
    <div id="dropZone" class="text-[11px] text-neutral-600 border border-dashed border-neutral-800 rounded px-2 py-1.5 text-center">
      …or drop an image here (PNG, JPEG, WebP, SVG)
    </div>
    ${
      s
        ? `<div class="flex items-center gap-2">
             <span class="text-[11px] text-neutral-500 truncate flex-1">${s.width}×${s.height}px${fitLabel ? ` · ${fitLabel}` : ""}</span>
             <button id="cropBtn" class="text-xs px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200">Crop &amp; scale…</button>
           </div>`
        : ""
    }
  `;

  el.querySelector("#fileInput")?.addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    if (file) onFilePicked(file);
  });
  el.querySelector("#cropBtn")?.addEventListener("click", onOpenCrop);

  // Drag-and-drop straight onto the panel.
  const zone = el.querySelector("#dropZone");
  const hi = () => zone.classList.add("border-emerald-600", "text-emerald-400");
  const lo = () => zone.classList.remove("border-emerald-600", "text-emerald-400");
  ["dragenter", "dragover"].forEach((ev) =>
    zone.addEventListener(ev, (e) => {
      e.preventDefault();
      hi();
    })
  );
  ["dragleave", "dragend"].forEach((ev) => zone.addEventListener(ev, lo));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    lo();
    const file = e.dataTransfer?.files?.[0];
    if (file) onFilePicked(file);
  });

  return el;
}
