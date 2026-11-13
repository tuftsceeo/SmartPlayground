/**
 * Splat host card parts for the all-wands dialog ("+ Add a Splat host").
 *
 * A Splat host is a real <wand-sim> in the Splat host role
 * (Wand Module/lib/splat_host.py; py/runtime.py set_role("splat_host")),
 * on the room's bus like the other wands. It plays no game of its own: it
 * holds up to SLOTS Splats and runs the Splat side of a Splat host game
 * (SPLAT_HOST = True), leading that game's lobby. Its 5x5 shows the
 * player count in the lobby. A game that is not a Splat host game does
 * not run on it.
 *
 * This module draws the four pairing slots under the host's wand: an empty
 * slot "pairs" a Splat when clicked (standing in for tapping the Splat's
 * card); a paired slot holds that Splat's toy, and its x unpairs it. The
 * wand restarts on each change, as a wand resets after a pairing.
 *
 *   createHostSlots({ onPair, onUnpair })   .el, .render(toys)
 */

import { icon } from "../icons.js";

export const SLOTS = 4;

export const SPLAT_CONTROLLER_STYLE = `
.wand-card.splat-controller .chip.splat-name { background: #e8f1fc; color: #2f76c8; }
.splat-controller .sc-slots { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.splat-controller .sc-slot { position: relative; display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 10px; border-radius: 16px; border: 2px dashed #c9c4dc; background: #fff;
  color: #8b859a; font: 800 12px 'Nunito', system-ui, sans-serif; min-height: 90px; justify-content: center; }
.splat-controller .sc-slot.empty { cursor: pointer; }
.splat-controller .sc-slot.empty:hover { border-color: #2f76c8; color: #2f76c8; }
.splat-controller .sc-slot.paired { border: 2px solid #e8f1fc; color: #2f76c8; }
.splat-controller .sc-slot .sc-plus { font: 800 28px 'Nunito', system-ui, sans-serif; }
.splat-controller .sc-slot > :not(.sc-unpair):not(span) { width: 100%; }
.splat-controller .sc-unpair { position: absolute; top: 6px; right: 6px; width: 22px; height: 22px; border-radius: 50%;
  border: 1.5px solid #e8e6f0; background: #fff; color: #5b5468; display: inline-flex; align-items: center;
  justify-content: center; padding: 0; cursor: pointer; z-index: 1; }
.splat-controller .sc-note { font: 700 11px 'Nunito', system-ui, sans-serif; color: #8b859a; text-align: center; }
.wand-card.min.splat-controller .sc-slots, .wand-card.min.splat-controller .sc-note { display: none; }
`;

/** The host's four Splat slots. `render(toys)` puts toy i (a createSplatToy) in slot i. */
export function createHostSlots({ onPair, onUnpair }) {
  const el = document.createElement("div");
  el.className = "sc-slots";

  function render(toys) {
    el.textContent = "";
    for (let i = 0; i < SLOTS; i++) {
      const slot = document.createElement("div");
      const toy = toys[i];
      if (toy) {
        slot.className = "sc-slot paired";
        slot.appendChild(toy.el);
        const label = document.createElement("span");
        label.textContent = `Splat ${i + 1}`;
        slot.appendChild(label);
        const x = document.createElement("button");
        x.type = "button";
        x.className = "sc-unpair";
        x.setAttribute("aria-label", `Unpair Splat ${i + 1}`);
        x.innerHTML = icon("close", 12);
        x.addEventListener("click", (e) => {
          e.stopPropagation();
          onUnpair(i);
        });
        slot.appendChild(x);
      } else {
        // Only the next free slot pairs: Splats keep tap order.
        const next = i === toys.length;
        slot.className = `sc-slot${next ? " empty" : ""}`;
        slot.innerHTML = `<span class="sc-plus">+</span><span>${next ? "Pair a Splat" : "Empty"}</span>`;
        if (next) {
          slot.setAttribute("role", "button");
          slot.tabIndex = 0;
          slot.setAttribute("aria-label", `Slot ${i + 1}: pair a Splat`);
          slot.addEventListener("click", () => onPair());
          slot.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPair(); }
          });
        }
      }
      el.appendChild(slot);
    }
  }

  render([]);
  return { el, render };
}
