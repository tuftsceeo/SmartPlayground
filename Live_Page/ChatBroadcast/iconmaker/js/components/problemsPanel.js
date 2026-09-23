/** problemsPanel.js -- lint output card for the adjust drawer. */
export function createProblemsPanel(state) {
  const el = document.createElement("div");
  if (state.uiMode === "simple" || !state.mode) {
    el.innerHTML = "";
    return el;
  }

  el.className = "flex flex-col gap-1.5 border-2 border-[var(--border)] rounded-[11px] px-3 py-2.5 bg-[#fffef9]";
  if (!state.problems.length) {
    el.innerHTML = `
      <span class="panel-label">Problems</span>
      <span class="text-[11.5px] font-semibold text-[#c9c0aa]">no problems detected</span>
    `;
    return el;
  }
  el.innerHTML = `
    <span class="panel-label">Problems</span>
    ${state.problems
      .map(
        (p) => `
      <div class="flex gap-2 items-start text-[11.5px] font-semibold text-[var(--gold)]">
        <span>⚠</span><span>${escapeHtml(p)}</span>
      </div>`
      )
      .join("")}
  `;
  return el;
}

function escapeHtml(s) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}
