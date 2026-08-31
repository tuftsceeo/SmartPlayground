/**
 * topBar.js -- prototype header: name, file toolbar, mode badge, profile,
 * adjust/gear/download. Device plug lives in #deviceMount beside this mount.
 */
import { listProfiles } from "../pipeline/profiles.js";

export function createTopBar(
  state,
  {
    onMaxSegmentsChange,
    onSaveMap,
    onExportIcon,
    onDownloadPreview,
    onLoadFixture,
    onProfileChange,
    onUiModeChange,
    onNew,
    onOpen,
    onRename,
    onToggleAdjust,
    cropOpen,
  }
) {
  const el = document.createElement("div");
  el.className = "flex items-center justify-between gap-3 px-6 py-4";

  const modeLabel = state.mode ? `${state.mode} · ${state.fills.length} segments` : "no icon loaded";
  const adjustOn = !!state.showAdjust;

  el.innerHTML = `
    <div class="flex items-center gap-4 min-w-0">
      <div class="flex items-center gap-2 font-bold text-[17px] min-w-0">
        <i data-lucide="pencil-line" class="w-4 h-4 text-[var(--muted)] flex-none"></i>
        <input type="text" id="iconNameInput" value="${state.iconName || ""}" placeholder="icon name"
               class="input-themed min-w-0 max-w-[10rem] py-1 px-2 text-[15px]" />
      </div>
      <span class="pill-badge flex-none">${modeLabel}</span>
      <div class="flex items-center gap-1 pl-3 border-l-2 border-[var(--border)]">
        <button type="button" id="btnNew" class="icon-btn" title="New"><i data-lucide="file-plus" class="w-[15px] h-[15px]"></i></button>
        <button type="button" id="btnOpen" class="icon-btn" title="Open"><i data-lucide="folder-open" class="w-[15px] h-[15px]"></i></button>
        <button type="button" id="btnSave" class="icon-btn" title="Save map" ${state.mode ? "" : "disabled"}><i data-lucide="save" class="w-[15px] h-[15px]"></i></button>
        <button type="button" id="btnRename" class="icon-btn" title="Rename"><i data-lucide="pencil-line" class="w-[14px] h-[14px]"></i></button>
        <input type="file" id="fileOpenHidden" accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml" class="hidden" />
      </div>
    </div>

    <div class="flex items-center gap-2.5 flex-none">
      <select id="profileSelect" title="Target hardware" class="select-themed">
        ${listProfiles()
          .map((p) => `<option value="${p.id}" ${p.id === state.profileId ? "selected" : ""}>${p.label}</option>`)
          .join("")}
      </select>
      <select id="fixtureSelect" class="select-themed">
        <option value="">Load fixture…</option>
        ${["apple", "cherries", "grapes", "lemon", "orange", "watermelon"]
          .map((n) => `<option value="${n}" ${n === state.iconName ? "selected" : ""}>${n}</option>`)
          .join("")}
      </select>
      <button type="button" id="btnAdjust" title="Pixelation &amp; segment colours"
              class="icon-btn-square"
              style="background:${adjustOn ? "#fdeaa8" : "#fff9e8"};border-color:var(--gold);color:var(--hw-ink)">
        <i data-lucide="sliders-horizontal" class="w-[18px] h-[18px]"></i>
      </button>
      <button type="button" id="modeGear" title="${cropOpen ? "Finish cropping first" : "Switch to simple mode"}"
              class="icon-btn-square disabled:opacity-40"
              style="background:var(--teal);color:#fff"
              ${cropOpen ? "disabled" : ""}>
        <i data-lucide="settings" class="w-[18px] h-[18px]"></i>
      </button>
      <button type="button" id="btnExportIcon" title="Download icon"
              class="icon-btn-square disabled:opacity-40"
              style="background:var(--red-soft);border-color:var(--red);color:#8a3a30"
              ${state.mode ? "" : "disabled"}>
        <i data-lucide="download" class="w-[17px] h-[17px]"></i>
      </button>
      <button type="button" id="btnDownloadPreview" class="hidden" aria-hidden="true"></button>
      <button type="button" id="btnSaveMap" class="hidden" aria-hidden="true"></button>
      <input type="range" id="segSlider" class="hidden" min="1" max="${state.maxSegments > 12 ? state.maxSegments : 12}"
             value="${state.maxSegments}" ${state.mode ? "" : "disabled"} />
    </div>
  `;

  el.querySelector("#profileSelect")?.addEventListener("change", (e) => onProfileChange(e.target.value));
  el.querySelector("#fixtureSelect")?.addEventListener("change", (e) => {
    if (e.target.value) onLoadFixture(e.target.value);
  });
  el.querySelector("#btnAdjust")?.addEventListener("click", () => onToggleAdjust?.());
  el.querySelector("#modeGear")?.addEventListener("click", () => onUiModeChange?.("simple"));
  el.querySelector("#btnExportIcon")?.addEventListener("click", onExportIcon);
  el.querySelector("#btnDownloadPreview")?.addEventListener("click", onDownloadPreview);
  el.querySelector("#btnSaveMap")?.addEventListener("click", onSaveMap);
  el.querySelector("#btnSave")?.addEventListener("click", onSaveMap);
  el.querySelector("#btnNew")?.addEventListener("click", () => onNew?.());
  el.querySelector("#btnOpen")?.addEventListener("click", () => {
    el.querySelector("#fileOpenHidden")?.click();
  });
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
      // rename via onRename is focus-only; name change goes through optional path if provided later
    }
  });
  el.querySelector("#segSlider")?.addEventListener("change", (e) => onMaxSegmentsChange(Number(e.target.value)));

  return el;
}
