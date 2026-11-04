/**
 * sourcePane.js -- crop link + hidden file/drop under the source canvas slot.
 */

export function createImportControls(state, { onFilePicked, onOpenCrop, onLoadFixture }) {
  const el = document.createElement("div");
  el.className = "flex flex-col gap-1.5 items-center w-full";
  const simple = state.uiMode === "simple";
  const s = state.sourceInfo;

  el.innerHTML = `
    ${
      s
        ? `<button type="button" id="cropBtn" class="font-bold text-[10px] text-[var(--teal)] cursor-pointer bg-transparent border-none p-0">crop &amp; scale…</button>`
        : `<span class="font-bold text-[10px] text-[var(--muted2)]">drop a photo</span>`
    }
    <input type="file" id="fileInput" accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml" class="hidden" />
    <div id="dropZone" class="w-full text-[10px] font-semibold text-[var(--muted2)] border border-dashed border-[var(--border-soft)] rounded-lg px-1 py-1 text-center cursor-pointer">
      import
    </div>
    ${
      simple
        ? `<select id="fixtureSelect" class="select-themed text-[10px] w-full py-1 px-1">
             <option value="">sample…</option>
             ${["apple", "cherries", "grapes", "lemon", "orange", "watermelon"]
               .map((n) => `<option value="${n}" ${n === state.iconName ? "selected" : ""}>${n}</option>`)
               .join("")}
           </select>`
        : ""
    }
  `;

  el.querySelector("#fileInput")?.addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    if (file) onFilePicked(file);
  });
  el.querySelector("#cropBtn")?.addEventListener("click", onOpenCrop);
  el.querySelector("#fixtureSelect")?.addEventListener("change", (e) => {
    if (e.target.value) onLoadFixture?.(e.target.value);
  });
  el.querySelector("#dropZone")?.addEventListener("click", () => el.querySelector("#fileInput")?.click());

  const zone = el.querySelector("#dropZone");
  const hi = () => zone?.classList.add("border-[var(--teal)]", "text-[var(--teal)]");
  const lo = () => zone?.classList.remove("border-[var(--teal)]", "text-[var(--teal)]");
  ["dragenter", "dragover"].forEach((ev) =>
    zone?.addEventListener(ev, (e) => {
      e.preventDefault();
      hi();
    })
  );
  ["dragleave", "dragend"].forEach((ev) => zone?.addEventListener(ev, lo));
  zone?.addEventListener("drop", (e) => {
    e.preventDefault();
    lo();
    const file = e.dataTransfer?.files?.[0];
    if (file) onFilePicked(file);
  });

  return el;
}
