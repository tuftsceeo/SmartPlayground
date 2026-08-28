/**
 * palettePicker.js -- pick a colour from what the PANEL can actually show.
 *
 * Replaces hunting in an sRGB picker where ~76% of the space reads as the
 * same white and the useful saturated colours are crammed into a ~3% sliver
 * of near-black values (see ledGamut.js's header for the measurements).
 * Here every swatch is a colour the panel renders distinguishably from every
 * other swatch, laid out hue across / brightness down.
 *
 * A single shared popover rather than a grid inlined in each segment row:
 * the palette is ~77 swatches, and repeating that per segment would be
 * hundreds of DOM nodes rebuilt on every state change.
 *
 * The raw sRGB picker is still available at the bottom, but anything chosen
 * through it is SNAPPED to the nearest panel-distinguishable colour, and the
 * dialog says what it became -- otherwise you can pick two colours that look
 * different on screen and identical on the hardware.
 */

import { buildPalette, snapToPalette, ledDeltaE, swatchStyle, isOff, JND } from "../pipeline/ledGamut.js";
import { authoredToDisplayHex, displayHexToAuthored } from "../pipeline/ledDisplay.js";

export class PalettePicker {
  constructor() {
    this.el = null;
    this.onPick = null;
    this._palette = null;
    this._paletteIntensity = null;
    this._keyHandler = null;
  }

  /** Palette depends on brightness, so cache per intensity. */
  paletteFor(intensity) {
    if (!this._palette || this._paletteIntensity !== intensity) {
      this._palette = buildPalette(intensity);
      this._paletteIntensity = intensity;
    }
    return this._palette;
  }

  /**
   * @param {HTMLElement} anchor   element to position near
   * @param {number[]} currentDuty authored linear duty currently selected
   * @param {number} intensity     current brightness (palette depends on it)
   * @param {(duty:number[])=>void} onPick
   */
  open(anchor, currentDuty, intensity, onPick) {
    this.close();
    this.onPick = onPick;
    const palette = this.paletteFor(intensity);

    const el = document.createElement("div");
    el.className = "fixed inset-0 z-50";
    el.innerHTML = `
      <div data-scrim class="absolute inset-0"></div>
      <div data-panel class="absolute bg-neutral-900 border border-neutral-700 rounded-lg shadow-2xl p-3 flex flex-col gap-2"
           style="max-width:min(92vw,720px)">
        <div class="flex items-center gap-2 text-xs">
          <span class="text-neutral-300 font-semibold">Panel colours</span>
          <span class="text-neutral-500">${palette.count} distinguishable at ${Math.round(intensity * 100)}% brightness</span>
          <button data-close class="ml-auto text-neutral-500 hover:text-neutral-200 text-base leading-none">&times;</button>
        </div>

        <div data-grid class="flex gap-1 overflow-x-auto pb-1"></div>

        <div class="text-[11px] text-neutral-600 leading-snug">
          Leftmost column is off and the neutrals. Every swatch is a colour this
          panel shows differently from the others.
          Fewer appear at low brightness because fewer actually exist there.
        </div>

        <div class="flex items-center gap-2 border-t border-neutral-800 pt-2 text-xs">
          <span class="text-neutral-500">custom</span>
          <input type="color" data-raw class="w-8 h-6 rounded border border-neutral-700 bg-neutral-800" />
          <span data-snapnote class="text-neutral-500 flex-1"></span>
          <button data-usesnap class="px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200">Use</button>
        </div>
      </div>
    `;
    document.body.appendChild(el);
    this.el = el;

    const grid = el.querySelector("[data-grid]");
    for (const col of palette.columns) {
      const colEl = document.createElement("div");
      colEl.className = "flex flex-col gap-1";
      colEl.title = `${col.name}${col.variant === "pastel" ? " (pastel)" : ""}`;
      for (const entry of col.entries) {
        const b = document.createElement("button");
        const isCurrent = entry.off
          ? isOff(currentDuty)
          : currentDuty && !isOff(currentDuty) && ledDeltaE(entry.duty, currentDuty, intensity) < JND / 2;
        b.className =
          "w-6 h-6 rounded border transition-transform hover:scale-110 " +
          (isCurrent ? "border-white ring-1 ring-white" : "border-neutral-700");
        b.style.background = swatchStyle(entry.duty);
        b.title = entry.off
          ? "off -- cell stays dark"
          : `${col.name}${col.variant === "pastel" ? " pastel" : ""} · duty ${entry.duty.join(",")}`;
        b.addEventListener("click", () => {
          this.onPick?.(entry.duty.slice());
          this.close();
        });
        colEl.appendChild(b);
      }
      grid.appendChild(colEl);
    }

    // ── custom colour: snap and say so ────────────────────────────────
    const raw = el.querySelector("[data-raw]");
    const note = el.querySelector("[data-snapnote]");
    const useBtn = el.querySelector("[data-usesnap]");
    let snapped = null;

    raw.value = currentDuty ? authoredToDisplayHex(currentDuty) : "#000000";
    const updateSnap = () => {
      const wanted = displayHexToAuthored(raw.value);
      snapped = snapToPalette(wanted, palette);
      if (!snapped) {
        note.textContent = "";
        return;
      }
      if (snapped.deltaE < JND / 2) {
        note.innerHTML = `<span class="text-emerald-400">already a panel colour</span>`;
      } else {
        note.innerHTML = snapped.off
          ? `snaps to <span class="text-neutral-300">off</span> <span class="text-neutral-600">(too dark to light a cell)</span>`
          : `snaps to <span style="color:${snapped.hex}">${snapped.name}` +
            `${snapped.variant === "pastel" ? " pastel" : ""}</span> ` +
          `<span class="text-neutral-600">(the panel can't show the difference)</span>`;
      }
    };
    raw.addEventListener("input", updateSnap);
    updateSnap();
    useBtn.addEventListener("click", () => {
      if (snapped) {
        this.onPick?.(snapped.duty.slice());
        this.close();
      }
    });

    // ── placement + dismissal ─────────────────────────────────────────
    const panel = el.querySelector("[data-panel]");
    const r = anchor.getBoundingClientRect();
    panel.style.visibility = "hidden";
    requestAnimationFrame(() => {
      const pr = panel.getBoundingClientRect();
      const left = Math.max(8, Math.min(window.innerWidth - pr.width - 8, r.left));
      const below = r.bottom + 6;
      const top = below + pr.height > window.innerHeight - 8 ? Math.max(8, r.top - pr.height - 6) : below;
      panel.style.left = `${left}px`;
      panel.style.top = `${top}px`;
      panel.style.visibility = "visible";
    });

    el.querySelector("[data-scrim]").addEventListener("mousedown", () => this.close());
    el.querySelector("[data-close]").addEventListener("click", () => this.close());
    this._keyHandler = (e) => {
      if (e.key === "Escape") this.close();
    };
    window.addEventListener("keydown", this._keyHandler);
  }

  close() {
    if (this._keyHandler) window.removeEventListener("keydown", this._keyHandler);
    this._keyHandler = null;
    this.el?.remove();
    this.el = null;
    this.onPick = null;
  }

  /** Brightness changed -- the set of distinguishable colours changed with it. */
  invalidate() {
    this._palette = null;
    this._paletteIntensity = null;
  }
}
