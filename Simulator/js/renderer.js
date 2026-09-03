/**
 * 5x5 LED grid renderer.
 * applyFrame(pixels) where pixels is an array of [r,g,b] (0-255).
 * displayGain multiplies channels for legibility (separate from OPT3002).
 */

export function createRenderer(container, opts = {}) {
  const root = container;
  root.classList.add("wand-led-grid");
  root.style.setProperty("--wand-led-size", opts.size || "var(--wand-led-size, 18px)");
  root.style.setProperty("--wand-grid-gap", opts.gap || "var(--wand-grid-gap, 6px)");
  root.style.setProperty("--wand-led-radius", opts.radius || "var(--wand-led-radius, 4px)");

  root.innerHTML = "";
  const cells = [];
  for (let i = 0; i < 25; i++) {
    const cell = document.createElement("div");
    cell.className = "wand-led-cell";
    cell.dataset.index = String(i);
    root.appendChild(cell);
    cells.push(cell);
  }

  let displayGain = opts.displayGain != null ? opts.displayGain : 2.5;

  function applyFrame(pixels) {
    const list = pixels || [];
    for (let i = 0; i < 25; i++) {
      const p = list[i] || [0, 0, 0];
      const r = Math.min(255, Math.round((p[0] || 0) * displayGain));
      const g = Math.min(255, Math.round((p[1] || 0) * displayGain));
      const b = Math.min(255, Math.round((p[2] || 0) * displayGain));
      const lit = r + g + b > 0;
      cells[i].style.background = lit ? `rgb(${r},${g},${b})` : "var(--wand-led-off, #1a1a1a)";
      cells[i].style.boxShadow = lit
        ? `0 0 var(--wand-led-glow, 8px) rgba(${r},${g},${b},0.55)`
        : "none";
    }
  }

  function setDisplayGain(g) {
    displayGain = Number(g) || 1;
  }

  return { applyFrame, setDisplayGain, cells };
}
