/** problemsPanel.js -- lint output, from emit.js's lint(). */
export function createProblemsPanel(state) {
  const el = document.createElement("div");
  el.className = "p-3 text-xs";
  if (state.uiMode === "simple") {
    el.innerHTML = "";
    return el;
  }
  if (!state.mode) {
    el.innerHTML = "";
    return el;
  }
  if (!state.problems.length) {
    el.innerHTML = `<div class="text-emerald-400">Problems: none</div>`;
    return el;
  }
  el.innerHTML = `
    <div class="text-amber-400 font-semibold mb-1">Problems (${state.problems.length})</div>
    <ul class="list-disc list-inside space-y-0.5 text-neutral-400">
      ${state.problems.map((p) => `<li>${escapeHtml(p)}</li>`).join("")}
    </ul>
  `;
  return el;
}

function escapeHtml(s) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}
