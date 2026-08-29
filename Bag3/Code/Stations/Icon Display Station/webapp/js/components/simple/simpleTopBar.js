/**
 * simpleTopBar.js -- icon name, detail slider, profile, download, mode gear.
 */
import { listProfiles } from "../../pipeline/profiles.js";

export function createSimpleTopBar(state, { onMaxSegmentsChange, onExportIcon, onProfileChange, onIconNameChange, onUiModeChange, cropOpen }) {
  const el = document.createElement("div");
  el.className = "flex flex-wrap items-center gap-3 px-4 py-3 bg-neutral-900 border-b border-neutral-800";

  el.innerHTML = `
    <input type="text" id="iconNameInput" value="${state.iconName || ""}" placeholder="Icon name"
           class="font-semibold text-neutral-100 bg-transparent border-b border-neutral-700 focus:border-emerald-600 outline-none min-w-[8rem] max-w-[14rem]" />

    <label class="flex items-center gap-2 text-xs text-neutral-400">
      Detail: fewer
      <input type="range" min="1" max="${state.maxSegments > 12 ? state.maxSegments : 12}" step="1"
             value="${state.maxSegments}" id="segSlider" class="w-24" ${state.mode ? "" : "disabled"} />
      more
    </label>

    <select id="profileSelect" title="Target hardware"
            class="text-xs bg-neutral-800 text-neutral-200 rounded px-2 py-1 border border-neutral-700">
      ${listProfiles()
        .map((p) => `<option value="${p.id}" ${p.id === state.profileId ? "selected" : ""}>${p.label}</option>`)
        .join("")}
    </select>

    <div class="ml-auto flex items-center gap-2">
      <button id="btnDownload" class="text-xs px-3 py-1.5 rounded bg-emerald-900 hover:bg-emerald-800 text-emerald-100 disabled:opacity-40 flex items-center gap-1"
              ${state.mode ? "" : "disabled"}>
        <i data-lucide="download" class="w-3.5 h-3.5"></i> Download
      </button>
      <button id="modeGear" title="${cropOpen ? "Finish cropping first" : "Switch to advanced mode"}"
              class="p-2 rounded border border-neutral-700 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 disabled:opacity-40"
              ${cropOpen ? "disabled" : ""}>
        <i data-lucide="settings" class="w-4 h-4"></i>
      </button>
    </div>
  `;

  el.querySelector("#segSlider")?.addEventListener("change", (e) => onMaxSegmentsChange(Number(e.target.value)));
  el.querySelector("#profileSelect")?.addEventListener("change", (e) => onProfileChange(e.target.value));
  el.querySelector("#btnDownload")?.addEventListener("click", onExportIcon);
  el.querySelector("#modeGear")?.addEventListener("click", () => onUiModeChange("advanced"));
  el.querySelector("#iconNameInput")?.addEventListener("change", (e) => {
    const name = e.target.value.trim().replace(/[^a-z0-9_]+/gi, "_").toLowerCase();
    if (name) {
      e.target.value = name;
      onIconNameChange?.(name);
    }
  });

  return el;
}
