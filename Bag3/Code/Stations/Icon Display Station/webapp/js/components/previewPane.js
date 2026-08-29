/**
 * previewPane.js -- just the brightness slider under the (persistent,
 * imperatively-painted) preview canvas that main.js owns directly.
 */
export function createBrightnessControls(state, { onIntensityInput, onIntensityCommit }) {
  const el = document.createElement("div");
  el.className = "px-3 py-2 flex items-center gap-2 text-xs text-neutral-400";
  const simple = state.uiMode === "simple";
  el.innerHTML = `
    brightness
    <input type="range" min="0.02" max="0.50" step="0.01" value="${state.intensity}" id="intensitySlider" class="flex-1" ${state.mode ? "" : "disabled"} />
    ${simple ? "" : `<span id="intensityVal" class="w-10 text-neutral-200">${Math.round(state.intensity * 100)}%</span>`}
  `;
  const slider = el.querySelector("#intensitySlider");
  const val = el.querySelector("#intensityVal");
  slider?.addEventListener("input", (e) => {
    const v = Number(e.target.value);
    if (val) val.textContent = `${Math.round(v * 100)}%`;
    onIntensityInput(v);
  });
  slider?.addEventListener("change", (e) => onIntensityCommit(Number(e.target.value)));
  return el;
}
