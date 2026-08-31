/**
 * simpleTopBar.js -- teacher header matching the lavender prototype.
 */
import { listProfiles } from "../../pipeline/profiles.js";

export function createSimpleTopBar(
  state,
  {
    onMaxSegmentsChange,
    onExportIcon,
    onProfileChange,
    onIconNameChange,
    onUiModeChange,
    onNew,
    onOpen,
    onSaveMap,
    onRename,
    onToggleAdjust,
    cropOpen,
  }
) {
  const el = document.createElement("div");
  el.className = "flex items-center justify-between gap-3 px-6 py-4";
  const adjustOn = !!state.showAdjust;

  el.innerHTML = `
    <div class="flex items-center gap-4 min-w-0">
      <div class="flex items-center gap-2 font-bold text-[17px] min-w-0">
        <i data-lucide="pencil-line" class="w-4 h-4 text-[var(--muted)] flex-none"></i>
        <input type="text" id="iconNameInput" value="${state.iconName || ""}" placeholder="icon name"
               class="input-themed min-w-0 max-w-[10rem] py-1 px-2 text-[15px]" />
      </div>
      <div class="flex items-center gap-1 pl-3 border-l-2 border-[var(--border)]">
        <button type="button" id="btnNew" class="icon-btn" title="New"><i data-lucide="file-plus" class="w-[15px] h-[15px]"></i></button>
        <button type="button" id="btnOpen" class="icon-btn" title="Open"><i data-lucide="folder-open" class="w-[15px] h-[15px]"></i></button>
        <button type="button" id="btnSave" class="icon-btn" title="Save" ${state.mode ? "" : "disabled"}><i data-lucide="save" class="w-[15px] h-[15px]"></i></button>
        <button type="button" id="btnRename" class="icon-btn" title="Rename"><i data-lucide="pencil-line" class="w-[14px] h-[14px]"></i></button>
        <input type="file" id="fileOpenHidden" accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml" class="hidden" />
      </div>
      <label class="flex items-center gap-2 text-[11.5px] font-semibold text-[var(--muted2)]">
        fewer
        <input type="range" min="1" max="${state.maxSegments > 12 ? state.maxSegments : 12}" step="1"
               value="${state.maxSegments}" id="segSlider" class="w-24" ${state.mode ? "" : "disabled"} />
        more
      </label>
    </div>

    <div class="flex items-center gap-2.5 flex-none">
      <select id="profileSelect" title="Target hardware" class="select-themed">
        ${listProfiles()
          .map((p) => `<option value="${p.id}" ${p.id === state.profileId ? "selected" : ""}>${p.label}</option>`)
          .join("")}
      </select>
      <button type="button" id="btnAdjust" title="Pixelation &amp; segment colours"
              class="icon-btn-square"
              style="background:${adjustOn ? "#fdeaa8" : "#fff9e8"};border-color:var(--gold);color:var(--hw-ink)">
        <i data-lucide="sliders-horizontal" class="w-[18px] h-[18px]"></i>
      </button>
      <button type="button" id="modeGear" title="${cropOpen ? "Finish cropping first" : "Switch to advanced mode"}"
              class="icon-btn-square disabled:opacity-40"
              style="background:var(--pink-soft);color:var(--muted)"
              ${cropOpen ? "disabled" : ""}>
        <i data-lucide="settings" class="w-[18px] h-[18px]"></i>
      </button>
      <button type="button" id="btnDownload" title="Download"
              class="icon-btn-square disabled:opacity-40"
              style="background:var(--red-soft);border-color:var(--red);color:#8a3a30"
              ${state.mode ? "" : "disabled"}>
        <i data-lucide="download" class="w-[17px] h-[17px]"></i>
      </button>
    </div>
  `;

  el.querySelector("#segSlider")?.addEventListener("change", (e) => onMaxSegmentsChange(Number(e.target.value)));
  el.querySelector("#profileSelect")?.addEventListener("change", (e) => onProfileChange(e.target.value));
  el.querySelector("#btnDownload")?.addEventListener("click", onExportIcon);
  el.querySelector("#btnAdjust")?.addEventListener("click", () => onToggleAdjust?.());
  el.querySelector("#modeGear")?.addEventListener("click", () => onUiModeChange("advanced"));
  el.querySelector("#btnNew")?.addEventListener("click", () => onNew?.());
  el.querySelector("#btnSave")?.addEventListener("click", () => onSaveMap?.());
  el.querySelector("#btnOpen")?.addEventListener("click", () => el.querySelector("#fileOpenHidden")?.click());
  el.querySelector("#fileOpenHidden")?.addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    if (file) onOpen?.(file);
  });
  el.querySelector("#btnRename")?.addEventListener("click", () => {
    const input = el.querySelector("#iconNameInput");
    input?.focus();
    input?.select();
    onRename?.();
  });
  el.querySelector("#iconNameInput")?.addEventListener("change", (e) => {
    const name = e.target.value.trim().replace(/[^a-z0-9_]+/gi, "_").toLowerCase();
    if (name) {
      e.target.value = name;
      onIconNameChange?.(name);
    }
  });

  return el;
}
