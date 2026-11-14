/**
 * Minimize toggle for the all-wands dialog's cards (wands and icon displays).
 *
 * A minimized card keeps its illustration, a name and the expand button.
 * Wand cards also set `minimized` on their <wand-sim>, which hides its
 * controls. State lives on the card, so a redraw keeps it.
 */

import { icon } from "../icons.js";

/** Set a card minimized or expanded and sync its button and <wand-sim>. */
export function setMinimized(card, on) {
  card.classList.toggle("min", on);
  card.querySelector("wand-sim")?.toggleAttribute("minimized", on);
  const btn = card.querySelector(".min-btn");
  if (btn) {
    btn.innerHTML = icon(on ? "plus" : "minus", 15);
    btn.setAttribute("aria-label", on ? "Expand" : "Minimize");
    btn.setAttribute("aria-expanded", String(!on));
  }
}

/**
 * Add the name label and toggle button to a card's `.chips` row, ahead of
 * any other button. The card's current state is applied.
 */
export function addMinimize(card, chips, name) {
  chips.querySelector(".min-name")?.remove();
  chips.querySelector(".min-btn")?.remove();
  const label = document.createElement("span");
  label.className = "min-name";
  label.textContent = name;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "wbtn small sq min-btn";
  btn.addEventListener("click", () => setMinimized(card, !card.classList.contains("min")));
  const firstBtn = chips.querySelector("button");
  chips.insertBefore(label, firstBtn);
  chips.insertBefore(btn, firstBtn);
  setMinimized(card, card.classList.contains("min"));
}
