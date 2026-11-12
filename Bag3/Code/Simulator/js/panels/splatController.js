/**
 * Splat controller card for the all-wands dialog: a MOCK-UP of the
 * dedicated Splat companion wand (design intent recorded in
 * known_issues/2026-11-11-simple-mode-large-changes.md, item 3).
 *
 * A companion wand plays no game of its own. It reads Splat NFC tags,
 * pairs with up to four Splats, and runs the Splat side of the game. The
 * card is a full wand-card size: a 5x5 display for the companion's state,
 * a button (reset, or whatever the game assigns), an NFC reader, and four
 * quarter-size Splat cards in a 2x2 grid as pairing slots. Clicking an
 * empty slot "pairs" a Splat into it; the display lights the matching
 * corner. Clicking a paired Splat presses it
 * (a short pulse); its x unpairs it. The button flashes the display.
 *
 * Nothing here runs Python, joins the radio bus or reaches a game: it is
 * layout and interaction only, until the firmware companion mode exists.
 *
 *   createSplatController({ onRemove })   .card
 */

import { icon } from "../icons.js";
import { CASE, BLOB } from "./splats.js";
import { addMinimize } from "./minimize.js";

export const SLOTS = 4;

/** Corner LEDs of the 5x5 display, one per slot: top-left, top-right,
 * bottom-left, bottom-right, in the slots' own 2x2 order. */
const CORNER = [[0, 1, 5, 6], [3, 4, 8, 9], [15, 16, 20, 21], [18, 19, 23, 24]];

export const SPLAT_CONTROLLER_STYLE = `
/* Full wand-card size: as wide as its grid column. */
.wand-card.splat-controller { min-width: 0; }
.splat-controller .sc-body { display: flex; flex-direction: column; gap: 12px; }
.splat-controller .sc-top { display: flex; align-items: center; justify-content: center; gap: 22px; padding: 8px 0; }
.splat-controller .sc-screen { display: grid; grid-template-columns: repeat(5, 16px); grid-auto-rows: 16px; gap: 3px;
  padding: 8px; border-radius: 12px; background: #14121a; }
.splat-controller .sc-screen i { border-radius: 3px; background: #2a2a30; }
.splat-controller .sc-screen i.on { background: #4491e8; }
.splat-controller .sc-screen.flash i { background: #fff; }
.splat-controller .sc-btn { width: 48px; height: 48px; border-radius: 50%; border: 0; cursor: pointer;
  background: radial-gradient(circle at 40% 35%, #55525e, #232228); box-shadow: 0 4px 0 #15141a; }
.splat-controller .sc-btn:active { transform: translateY(3px); box-shadow: 0 1px 0 #15141a; }
.splat-controller .sc-nfc { display: inline-flex; color: #8b859a; }
.splat-controller .sc-nfc.reading { color: #2f76c8; animation: sc-read .6s ease; }
@keyframes sc-read { 50% { transform: scale(1.25); } }
/* Four quarter-size Splat cards, 2x2. */
.splat-controller .sc-slots { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.splat-controller .sc-slot { position: relative; display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 10px; border-radius: 16px; cursor: pointer; border: 2px dashed #c9c4dc; background: #fff;
  color: #8b859a; font: 800 12px 'Nunito', system-ui, sans-serif; }
.splat-controller .sc-slot:hover { border-color: #2f76c8; color: #2f76c8; }
.splat-controller .sc-slot.paired { border: 2px solid #e8f1fc; color: #2f76c8; }
.splat-controller .sc-art { width: 100%; aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
  font: 800 28px 'Nunito', system-ui, sans-serif; }
.splat-controller .sc-art svg { width: 82%; height: 82%; display: block; overflow: visible; }
.splat-controller .sc-art .case { fill: #4491e8; }
.splat-controller .sc-art .blob { fill: #d4d7de; }
.splat-controller .sc-slot.pressed .sc-art { animation: splat-chirp .3s ease; }
.splat-controller .sc-unpair { position: absolute; top: 6px; right: 6px; width: 22px; height: 22px; border-radius: 50%;
  border: 1.5px solid #e8e6f0; background: #fff; color: #5b5468; display: none; align-items: center; justify-content: center;
  padding: 0; cursor: pointer; }
.splat-controller .sc-slot.paired:hover .sc-unpair { display: inline-flex; }
.splat-controller .sc-mock { font: 700 11px 'Nunito', system-ui, sans-serif; color: #8b859a; text-align: center; }
.wand-card.min.splat-controller .sc-body { display: none; }
`;

const SPLAT_SVG = `<svg viewBox="-6 -6 268 267" aria-hidden="true">
  <path class="case" fill-rule="evenodd" d="${CASE}"/><path class="blob" d="${BLOB}"/></svg>`;

/** One mock Splat controller card. `onRemove(card)` runs when its x is pressed. */
export function createSplatController({ onRemove }) {
  const paired = new Array(SLOTS).fill(false);
  const card = document.createElement("div");
  card.className = "wand-card splat-controller";
  card.innerHTML = `<div class="chips"><span class="chip device-name splat-name">Splat controller</span></div>
    <div class="sc-body">
      <div class="sc-top">
        <div class="sc-screen" role="img" aria-label="Controller display">${"<i></i>".repeat(25)}</div>
        <button type="button" class="sc-btn" title="Controller button (reset, or as the game assigns)" aria-label="Controller button"></button>
        <span class="sc-nfc" title="NFC reader: reads a Splat's tag to pair it">${icon("nfcCard", 32)}</span>
      </div>
      <div class="sc-slots"></div>
      <div class="sc-mock">Mock-up: not connected to a game</div>
    </div>`;
  const chips = card.querySelector(".chips");
  const rm = document.createElement("button");
  rm.type = "button";
  rm.className = "wbtn small sq";
  rm.setAttribute("aria-label", "Take this Splat controller away");
  rm.innerHTML = icon("close", 15);
  rm.addEventListener("click", () => onRemove(card));
  chips.appendChild(rm);
  addMinimize(card, chips, "Splat controller");

  const screen = card.querySelector(".sc-screen");
  const cells = [...screen.children];
  const nfc = card.querySelector(".sc-nfc");
  const slotsEl = card.querySelector(".sc-slots");

  function paint() {
    const on = new Set(paired.flatMap((p, i) => (p ? CORNER[i] : [])));
    cells.forEach((c, i) => c.classList.toggle("on", on.has(i)));
    slotsEl.textContent = "";
    paired.forEach((p, i) => {
      const slot = document.createElement("div");
      slot.className = `sc-slot${p ? " paired" : ""}`;
      slot.setAttribute("role", "button");
      slot.tabIndex = 0;
      slot.setAttribute("aria-label", p ? `Splat ${i + 1}: press` : `Slot ${i + 1}: pair a Splat`);
      slot.title = p ? `Splat ${i + 1}` : "Pair a Splat";
      slot.innerHTML = `<div class="sc-art">${p ? SPLAT_SVG : "+"}</div><span>${p ? `Splat ${i + 1}` : "Pair a Splat"}</span>`;
      if (p) {
        const x = document.createElement("button");
        x.type = "button";
        x.className = "sc-unpair";
        x.setAttribute("aria-label", `Unpair Splat ${i + 1}`);
        x.innerHTML = icon("close", 12);
        x.addEventListener("click", (e) => {
          e.stopPropagation();
          paired[i] = false;
          paint();
        });
        slot.appendChild(x);
      }
      const act = () => {
        if (!paired[i]) {
          // Pairing: the reader reads the Splat's tag.
          paired[i] = true;
          nfc.classList.remove("reading");
          void nfc.offsetWidth;
          nfc.classList.add("reading");
          paint();
          return;
        }
        slot.classList.remove("pressed");
        void slot.offsetWidth;
        slot.classList.add("pressed");
      };
      slot.addEventListener("click", act);
      slot.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); act(); }
      });
      slotsEl.appendChild(slot);
    });
  }

  card.querySelector(".sc-btn").addEventListener("click", () => {
    screen.classList.add("flash");
    setTimeout(() => screen.classList.remove("flash"), 200);
  });

  paint();
  return { card };
}
