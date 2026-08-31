/**
 * palettePicker.js -- panel-gamut popover with crayon chrome + RGB fine-tune.
 */
import { buildPalette, snapToPalette, ledDeltaE, swatchStyle, isOff, JND } from "../pipeline/ledGamut.js";
import { authoredToDisplayHex, displayHexToAuthored } from "../pipeline/ledDisplay.js";
import { state } from "../state/store.js";

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rgbToHex(r, g, b) {
  return "#" + [r, g, b].map((v) => Math.max(0, Math.min(255, v | 0)).toString(16).padStart(2, "0")).join("");
}

export class PalettePicker {
  constructor() {
    this.el = null;
    this.onPick = null;
    this._palette = null;
    this._paletteIntensity = null;
    this._keyHandler = null;
  }

  paletteFor(intensity) {
    if (!this._palette || this._paletteIntensity !== intensity) {
      this._palette = buildPalette(intensity);
      this._paletteIntensity = intensity;
    }
    return this._palette;
  }

  open(anchor, currentDuty, intensity, onPick) {
    this.close();
    this.onPick = onPick;
    const palette = this.paletteFor(intensity);
    const simple = state.uiMode === "simple";
    const startHex = currentDuty ? authoredToDisplayHex(currentDuty) : "#000000";
    let [rr, gg, bb] = hexToRgb(startHex);

    const el = document.createElement("div");
    el.className = "fixed inset-0 z-50";
    el.innerHTML = `
      <div data-scrim class="absolute inset-0"></div>
      <div data-panel class="absolute popover flex flex-col gap-2.5" style="max-width:min(92vw,420px);width:360px">
        <div class="flex items-center justify-between">
          <span class="font-bold text-[12px] text-[#823f82]">pick a colour</span>
          <button type="button" data-close class="icon-btn text-[var(--muted2)]"><i data-lucide="x" class="w-4 h-4"></i></button>
        </div>
        ${simple ? "" : `<div class="text-[11px] font-semibold text-[var(--muted2)]">${palette.count} distinguishable at ${Math.round(intensity * 100)}%</div>`}
        <div data-grid class="flex gap-1 overflow-x-auto pb-1"></div>
        <div class="flex items-center gap-2 border-t border-dashed border-[var(--border-soft)] pt-2 text-xs">
          <span class="font-semibold text-[var(--muted)]">custom</span>
          <input type="color" data-raw class="w-8 h-6 rounded border border-[var(--border)]" />
          <span data-snapnote class="text-[var(--muted2)] flex-1 text-[11px]"></span>
          <button type="button" data-usesnap class="btn-secondary py-1 px-2 text-[11px]">Use</button>
        </div>
        ${
          simple
            ? ""
            : `<div class="border-t border-dashed border-[var(--border-soft)] pt-2 flex flex-col gap-1.5">
          <span class="font-bold text-[11px] text-[#823f82]">fine-tune RGB</span>
          <div class="flex items-center gap-2">
            <div data-rgbprev class="w-7 h-7 rounded-md border-2 border-[var(--ink)] flex-none" style="background:${startHex}"></div>
            <input type="text" data-rgbhex value="${startHex}" class="input-themed w-[78px] font-mono text-[11.5px] py-1" />
          </div>
          <div class="flex items-center gap-1.5"><span class="font-bold text-[10px] text-[var(--red)] w-3">R</span><input type="range" data-r min="0" max="255" value="${rr}" class="flex-1" style="accent-color:var(--red)" /><span data-rval class="font-bold text-[10px] font-mono w-[26px] text-right">${rr}</span></div>
          <div class="flex items-center gap-1.5"><span class="font-bold text-[10px] text-[#4c9463] w-3">G</span><input type="range" data-g min="0" max="255" value="${gg}" class="flex-1" style="accent-color:#4c9463" /><span data-gval class="font-bold text-[10px] font-mono w-[26px] text-right">${gg}</span></div>
          <div class="flex items-center gap-1.5"><span class="font-bold text-[10px] text-[#3f6ea8] w-3">B</span><input type="range" data-b min="0" max="255" value="${bb}" class="flex-1" style="accent-color:#3f6ea8" /><span data-bval class="font-bold text-[10px] font-mono w-[26px] text-right">${bb}</span></div>
          <button type="button" data-usergb class="btn-primary text-[12px] py-1.5">use this colour</button>
        </div>`
        }
      </div>
    `;
    document.body.appendChild(el);
    this.el = el;
    window.lucide?.createIcons?.();

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
        b.type = "button";
        b.className = `swatch-crayon w-5 h-11 ${isCurrent ? "is-selected" : ""}`;
        b.style.background = swatchStyle(entry.duty);
        b.title = entry.off ? "off" : `${col.name} · ${entry.duty.join(",")}`;
        b.addEventListener("click", () => {
          this.onPick?.(entry.duty.slice());
          this.close();
        });
        colEl.appendChild(b);
      }
      grid.appendChild(colEl);
    }

    const raw = el.querySelector("[data-raw]");
    const note = el.querySelector("[data-snapnote]");
    const useBtn = el.querySelector("[data-usesnap]");
    let snapped = null;
    raw.value = startHex;
    const updateSnap = () => {
      const wanted = displayHexToAuthored(raw.value);
      snapped = snapToPalette(wanted, palette);
      if (!snapped) {
        note.textContent = "";
        return;
      }
      if (snapped.deltaE < JND / 2) {
        note.innerHTML = `<span style="color:var(--teal)">already a panel colour</span>`;
      } else {
        note.innerHTML = snapped.off
          ? `snaps to off`
          : `snaps to <span style="color:${snapped.hex}">${snapped.name}</span>`;
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

    if (!simple) {
      const prev = el.querySelector("[data-rgbprev]");
      const hexIn = el.querySelector("[data-rgbhex]");
      const syncRgbUi = () => {
        const hex = rgbToHex(rr, gg, bb);
        if (prev) prev.style.background = hex;
        if (hexIn) hexIn.value = hex;
        el.querySelector("[data-rval]").textContent = String(rr);
        el.querySelector("[data-gval]").textContent = String(gg);
        el.querySelector("[data-bval]").textContent = String(bb);
        el.querySelector("[data-r]").value = String(rr);
        el.querySelector("[data-g]").value = String(gg);
        el.querySelector("[data-b]").value = String(bb);
      };
      el.querySelector("[data-r]")?.addEventListener("input", (e) => {
        rr = Number(e.target.value);
        syncRgbUi();
      });
      el.querySelector("[data-g]")?.addEventListener("input", (e) => {
        gg = Number(e.target.value);
        syncRgbUi();
      });
      el.querySelector("[data-b]")?.addEventListener("input", (e) => {
        bb = Number(e.target.value);
        syncRgbUi();
      });
      hexIn?.addEventListener("change", (e) => {
        const v = e.target.value.trim();
        if (!/^#?[0-9a-fA-F]{6}$/.test(v)) return;
        const h = v.startsWith("#") ? v : "#" + v;
        [rr, gg, bb] = hexToRgb(h);
        syncRgbUi();
      });
      el.querySelector("[data-usergb]")?.addEventListener("click", () => {
        const hex = rgbToHex(rr, gg, bb);
        const duty = displayHexToAuthored(hex);
        const sn = snapToPalette(duty, palette);
        this.onPick?.((sn?.duty || duty).slice());
        this.close();
      });
    }

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

  invalidate() {
    this._palette = null;
    this._paletteIntensity = null;
  }
}
