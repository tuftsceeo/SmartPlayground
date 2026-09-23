/**
 * previewPane.js -- brightness slider under the LED preview canvas.
 */
export function createBrightnessControls(state, { onIntensityInput, onIntensityCommit }) {
  const el = document.createElement("div");
  el.className = "flex items-center gap-1.5 w-full";
  const pct = Math.round(state.intensity * 100);
  el.innerHTML = `
    <i data-lucide="sun" class="w-3 h-3 text-[var(--muted2)] flex-none"></i>
    <input type="range" min="0.02" max="0.50" step="0.01" value="${state.intensity}" id="intensitySlider"
           class="flex-1" ${state.mode ? "" : "disabled"} />
    <span id="intensityVal" class="font-bold text-[11px] text-[var(--muted)] w-[28px] text-right">${pct}%</span>
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
