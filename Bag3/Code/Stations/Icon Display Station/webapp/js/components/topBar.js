/**
 * topBar.js -- icon name, mode badge, segments slider, export buttons,
 * status text. create<Name>() factory returning a detached element, per
 * Live_Page/WebApp2's component convention.
 */

const MODE_COLORS = {
  exact: "bg-emerald-900 text-emerald-300",
  quantize: "bg-amber-900 text-amber-300",
};

import { listProfiles } from "../pipeline/profiles.js";

export function createTopBar(state, { onMaxSegmentsChange, onSaveMap, onExportIcon, onDownloadPreview, onLoadFixture, onProfileChange }) {
  const el = document.createElement("div");
  el.className = "flex flex-wrap items-center gap-3 px-4 py-3 bg-neutral-900 border-b border-neutral-800";

  const modeCls = MODE_COLORS[state.mode] || "bg-neutral-800 text-neutral-400";
  const modeLabel = state.mode ? `${state.mode} · ${state.fills.length} segments` : "no icon loaded";

  el.innerHTML = `
    <span class="font-semibold text-neutral-100">${state.iconName || "Icon Maker"}</span>
    <span class="text-xs px-2 py-1 rounded ${modeCls}">${modeLabel}</span>

    <label class="flex items-center gap-2 text-xs text-neutral-400">
      segments
      <input type="range" min="1" max="${state.maxSegments > 12 ? state.maxSegments : 12}" step="1" value="${state.maxSegments}" id="segSlider" class="w-24" ${state.mode ? "" : "disabled"} />
      <span id="segVal" class="w-4 text-neutral-200">${state.maxSegments}</span>
    </label>

    <select id="profileSelect" title="Target hardware -- changes grid size, thresholds and power limits"
            class="text-xs bg-neutral-800 text-neutral-200 rounded px-2 py-1 border border-neutral-700">
      ${listProfiles()
        .map(
          (p) =>
            `<option value="${p.id}" ${p.id === state.profileId ? "selected" : ""}>${p.label}</option>`
        )
        .join("")}
    </select>

    <select id="fixtureSelect" class="text-xs bg-neutral-800 text-neutral-200 rounded px-2 py-1 border border-neutral-700">
      <option value="">Load fixture…</option>
      ${["apple", "cherries", "grapes", "lemon", "orange", "watermelon"]
        .map((n) => `<option value="${n}" ${n === state.iconName ? "selected" : ""}>${n}</option>`)
        .join("")}
    </select>

    <div class="ml-auto flex items-center gap-2">
      <button id="btnSaveMap" class="text-xs px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 disabled:opacity-40" ${state.mode ? "" : "disabled"}>Download map</button>
      <button id="btnExportIcon" class="text-xs px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 disabled:opacity-40" ${state.mode ? "" : "disabled"}>Download icon</button>
      <button id="btnDownloadPreview" class="text-xs px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 disabled:opacity-40" ${state.mode ? "" : "disabled"}>Download preview</button>
      <span class="text-xs text-neutral-500">${state.statusText}</span>
    </div>
  `;

  el.querySelector("#segSlider")?.addEventListener("input", (e) => {
    el.querySelector("#segVal").textContent = e.target.value;
  });
  el.querySelector("#segSlider")?.addEventListener("change", (e) => onMaxSegmentsChange(Number(e.target.value)));
  el.querySelector("#profileSelect")?.addEventListener("change", (e) => onProfileChange(e.target.value));
  el.querySelector("#fixtureSelect")?.addEventListener("change", (e) => {
    if (e.target.value) onLoadFixture(e.target.value);
  });
  el.querySelector("#btnSaveMap")?.addEventListener("click", onSaveMap);
  el.querySelector("#btnExportIcon")?.addEventListener("click", onExportIcon);
  el.querySelector("#btnDownloadPreview")?.addEventListener("click", onDownloadPreview);

  return el;
}
