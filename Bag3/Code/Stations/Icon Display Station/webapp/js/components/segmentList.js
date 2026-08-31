/**
 * segmentList.js -- adjust-drawer segment rows matching the prototype.
 */
import { MIN_FEATURE_CELLS } from "../pipeline/constants.js";
import { rgbToHex } from "../utils/colorUtils.js";
import { swatchStyle } from "../pipeline/ledGamut.js";

export function createSegmentList(state, callbacks) {
  const el = document.createElement("div");
  el.className = "flex flex-col gap-2 max-w-[360px]";

  if (!state.fills.length) {
    el.innerHTML = `<div class="text-sm font-semibold text-[var(--muted2)]">No icon loaded.</div>`;
    return el;
  }

  const detailRow = document.createElement("div");
  detailRow.className = "flex flex-col gap-1.5";
  detailRow.innerHTML = `
    <span class="font-bold text-[12.5px] text-[#823f82]">Detail · ${state.maxSegments} segments</span>
    <div class="flex items-center gap-2 font-semibold text-[11.5px] text-[var(--muted2)]">
      <span>fewer</span>
      <input type="range" id="drawerSegSlider" min="1" max="${state.maxSegments > 12 ? state.maxSegments : 12}"
             step="1" value="${state.maxSegments}" class="flex-1" />
      <span>more</span>
    </div>
  `;
  el.appendChild(detailRow);

  state.fills.forEach((fill, i) => {
    const d = state.decisions[i];
    const won = state.cellsWon[i] ?? 0;
    const wonBad = d.role === "color" && won < MIN_FEATURE_CELLS;
    const on = d.role !== "off";
    const srcHex = rgbToHex(fill.rgb);
    const colorStyle = swatchStyle(d.color);

    const row = document.createElement("div");
    row.className = "flex flex-col gap-1.5 border-2 border-[var(--border)] rounded-[11px] px-2.5 py-2";
    row.dataset.segIdx = i;

    row.innerHTML = `
      <div class="flex items-center gap-2.5">
        <button type="button" data-color title="Pick colour"
                class="swatch-crayon w-[18px] h-[38px] ${d.role === "color" ? "" : "opacity-35"}"
                style="background:${d.role === "color" ? colorStyle : srcHex}"></button>
        <span class="font-bold text-[13px] flex-1 truncate">seg ${i}</span>
        <select data-role class="select-themed text-[10.5px] py-1 px-1.5">
          <option value="color" ${d.role === "color" ? "selected" : ""}>color</option>
          <option value="off" ${d.role === "off" ? "selected" : ""}>off</option>
          <option value="merge" ${d.role === "merge" ? "selected" : ""}>merge</option>
        </select>
        <div data-toggle class="toggle-switch ${on ? "is-on" : ""}" title="${on ? "Turn off" : "Turn on"}"></div>
      </div>
      <div class="flex items-center gap-2.5 pl-7 flex-wrap">
        <span class="font-semibold text-[10px] text-[var(--muted2)] font-mono">rgb(${fill.rgb.join(",")})</span>
        <span class="font-semibold text-[10px] text-[var(--muted2)]">${(fill.frac * 100).toFixed(1)}% · won ${won}${wonBad ? " ⚠" : ""}</span>
        ${
          d.role === "merge"
            ? `<select data-merge class="select-themed text-[10px] py-0.5 px-1">
                ${state.fills
                  .map((f, j) => (j === i ? "" : `<option value="${j}" ${d.merge_into === j ? "selected" : ""}>seg ${j}</option>`))
                  .join("")}
              </select>`
            : ""
        }
        ${
          d.role !== "off"
            ? `<div class="flex items-center gap-1.5 flex-1 min-w-[130px]">
                <span class="font-semibold text-[10px] text-[var(--muted)]">priority</span>
                <input type="range" data-priority min="0.1" max="3.0" step="0.1" value="${d.priority}" class="flex-1" />
                <span data-priorityVal class="font-bold text-[10px] text-[#823f82] w-[26px] text-right">${d.priority.toFixed(1)}</span>
              </div>`
            : ""
        }
      </div>
    `;

    row.querySelector("[data-role]")?.addEventListener("change", (e) => callbacks.onRoleChange(i, e.target.value));
    row.querySelector("[data-toggle]")?.addEventListener("click", () =>
      callbacks.onRoleChange(i, on ? "off" : "color")
    );
    row.querySelector("[data-merge]")?.addEventListener("change", (e) =>
      callbacks.onMergeChange(i, Number(e.target.value))
    );
    const colorBtn = row.querySelector("[data-color]");
    colorBtn?.addEventListener("click", () => callbacks.onOpenPalette(i, colorBtn));
    const prioInput = row.querySelector("[data-priority]");
    const prioVal = row.querySelector("[data-priorityVal]");
    prioInput?.addEventListener("input", (e) => {
      const v = Number(e.target.value);
      if (prioVal) prioVal.textContent = v.toFixed(1);
      callbacks.onPriorityInput(i, v);
    });
    prioInput?.addEventListener("change", (e) => callbacks.onPriorityCommit(i, Number(e.target.value)));

    el.appendChild(row);
  });

  return el;
}
