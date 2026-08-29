/**
 * cropModal.js -- crop / scale / frame an imported image before it enters
 * the pipeline.
 *
 * Cropper.js (vendored, see vendor/README.md) provides the INTERACTION
 * only: drag, zoom, 1:1 aspect lock, handles, guides, keyboard. The actual
 * resampling is NOT done with getCroppedCanvas() -- we take the crop
 * rectangle from getData() and hand it to decode.js:renderWorking(), so the
 * smoothing policy stays under our control (nearest-neighbour when
 * upscaling keeps flat-colour art on the exact-fill segmentation path).
 *
 * The live 16x16 panel is the point of this dialog: at this resolution the
 * only question that matters is whether the subject still reads once it's
 * 16 pixels wide, and that is impossible to judge from the full-size image.
 * It is a box-average of the crop -- honest about framing and silhouette,
 * but NOT the final segmented colours (labelled as such in the UI).
 */

import { W, H, WORK } from "../pipeline/constants.js";
import { computeRects } from "../pipeline/decode.js";
import { state } from "../state/store.js";

const PREVIEW_PX = 160; // on-screen size of the 16x16 panel

export class CropModal {
  constructor() {
    this.el = null;
    this.cropper = null;
    this.source = null;
    this.onApply = null;
    this._raf = 0;
  }

  /**
   * @param {object} source  from decode.js:loadSource()
   * @param {object} transform  current transform (mode/crop/smoothing)
   * @param {(t:object)=>void} onApply
   */
  open(source, transform, onApply) {
    if (!window.Cropper) {
      alert("Cropper.js failed to load (vendor/cropper.min.js). Crop tool unavailable.");
      return;
    }
    this.source = source;
    this.onApply = onApply;
    this.transform = { ...transform };
    const simple = state.uiMode === "simple";

    const el = document.createElement("div");
    el.className = "fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4";
    el.innerHTML = `
      <div class="bg-neutral-900 border border-neutral-700 rounded-lg shadow-2xl w-full max-w-4xl flex flex-col max-h-full">
        <div class="px-4 py-2 border-b border-neutral-800 flex items-center gap-3">
          <span class="font-semibold text-neutral-100">Crop &amp; scale</span>
          <span class="text-xs text-neutral-500">source ${source.width}×${source.height}px → ${W}×${H} icon</span>
          <button id="cmClose" class="ml-auto text-neutral-500 hover:text-neutral-200 text-lg leading-none">&times;</button>
        </div>

        <div class="flex-1 overflow-auto p-4 grid grid-cols-[1fr_200px] gap-4">
          <div>
            <div class="bg-neutral-950 rounded" style="max-height:52vh">
              <img id="cmImage" src="${source.objectUrl}" alt="" style="max-width:100%; display:block" />
            </div>
            <div class="flex flex-wrap items-center gap-2 mt-3 text-xs">
              <span class="text-neutral-500">framing:</span>
              <button data-preset="contain" class="px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200">Whole image</button>
              <button data-preset="cover" class="px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200">Fill square</button>
              <button data-preset="reset" class="px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200">Reset crop</button>
              ${
                simple
                  ? ""
                  : `<label class="flex items-center gap-1 text-neutral-400 ml-2">
                <input type="checkbox" id="cmSquare" checked /> lock to square
              </label>
              <label class="flex items-center gap-1 text-neutral-400">
                smoothing
                <select id="cmSmooth" class="bg-neutral-800 border border-neutral-700 rounded px-1 py-0.5 text-neutral-200">
                  <option value="auto">auto</option>
                  <option value="on">on (blend)</option>
                  <option value="off">off (nearest)</option>
                </select>
              </label>`
              }
            </div>
            ${simple ? "" : `<div class="text-[11px] text-neutral-600 mt-2" id="cmHint"></div>`}
          </div>

          <div class="flex flex-col gap-3">
            <div>
              <div class="text-[11px] text-neutral-500 mb-1">${W}×${H} framing preview</div>
              <canvas id="cmPreview" class="pixelated bg-neutral-950 rounded border border-neutral-800"
                      width="${W}" height="${H}"
                      style="width:${PREVIEW_PX}px;height:${PREVIEW_PX}px"></canvas>
              <div class="text-[10px] text-neutral-600 mt-1 leading-snug">
                Shows silhouette &amp; framing only -- final colours come from
                segmentation after you apply.
              </div>
            </div>
            <div>
              <div class="text-[11px] text-neutral-500 mb-1">at actual size</div>
              <canvas id="cmTiny" class="pixelated bg-neutral-950 rounded border border-neutral-800"
                      width="${W}" height="${H}"
                      style="width:${W * 2}px;height:${H * 2}px"></canvas>
            </div>
            ${simple ? "" : `<div id="cmStats" class="text-[11px] text-neutral-500 leading-snug"></div>`}
          </div>
        </div>

        <div class="px-4 py-2 border-t border-neutral-800 flex items-center gap-2">
          <button id="cmCancel" class="px-3 py-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-sm ml-auto">Cancel</button>
          <button id="cmApply" class="px-3 py-1.5 rounded bg-emerald-800 hover:bg-emerald-700 text-emerald-100 text-sm">Apply</button>
        </div>
      </div>
    `;
    document.body.appendChild(el);
    this.el = el;

    this.previewCtx = el.querySelector("#cmPreview").getContext("2d", { willReadFrequently: true });
    this.tinyCtx = el.querySelector("#cmTiny").getContext("2d");
    this.statsEl = el.querySelector("#cmStats");
    this.hintEl = el.querySelector("#cmHint");

    const img = el.querySelector("#cmImage");
    const squareBox = el.querySelector("#cmSquare");
    const smoothSel = el.querySelector("#cmSmooth");
    if (smoothSel) smoothSel.value = this.transform.smoothing || "auto";

    this.cropper = new window.Cropper(img, {
      viewMode: 1, // crop box stays within the image
      aspectRatio: 1,
      autoCropArea: 1,
      background: false,
      responsive: true,
      guides: true,
      center: true,
      dragMode: "move", // drag pans the image; handles resize the box
      toggleDragModeOnDblclick: false,
      ready: () => {
        if (this.transform.crop) this.cropper.setData(this.transform.crop);
        else this._applyPreset(this.transform.mode === "cover" ? "cover" : "contain");
        this._schedulePreview();
      },
      crop: () => this._schedulePreview(),
      zoom: () => this._schedulePreview(),
    });

    squareBox?.addEventListener("change", (e) => {
      this.cropper.setAspectRatio(e.target.checked ? 1 : NaN);
      this._schedulePreview();
    });
    smoothSel?.addEventListener("change", (e) => {
      this.transform.smoothing = e.target.value;
      this._schedulePreview();
    });
    el.querySelectorAll("[data-preset]").forEach((b) =>
      b.addEventListener("click", () => this._applyPreset(b.dataset.preset))
    );

    el.querySelector("#cmApply").addEventListener("click", () => this._apply());
    el.querySelector("#cmCancel").addEventListener("click", () => this.close());
    el.querySelector("#cmClose").addEventListener("click", () => this.close());
    el.addEventListener("mousedown", (e) => {
      if (e.target === el) this.close();
    });
    this._keyHandler = (e) => {
      if (e.key === "Escape") this.close();
      if (e.key === "Enter") this._apply();
    };
    window.addEventListener("keydown", this._keyHandler);
  }

  _applyPreset(preset) {
    const c = this.cropper;
    if (!c) return;
    if (preset === "reset") {
      c.reset();
      c.setAspectRatio(this.el.querySelector("#cmSquare").checked ? 1 : NaN);
    } else if (preset === "cover") {
      // Largest centered square of the source.
      const side = Math.min(this.source.width, this.source.height);
      c.setData({
        x: (this.source.width - side) / 2,
        y: (this.source.height - side) / 2,
        width: side,
        height: side,
      });
    } else if (preset === "contain") {
      // Whole image inside a square box -> letterboxed, matching fit 'contain'.
      const side = Math.max(this.source.width, this.source.height);
      c.setData({
        x: (this.source.width - side) / 2,
        y: (this.source.height - side) / 2,
        width: side,
        height: side,
      });
    }
    this._schedulePreview();
  }

  /** Coalesce preview redraws to one per frame -- crop fires continuously. */
  _schedulePreview() {
    if (this._raf) return;
    this._raf = requestAnimationFrame(() => {
      this._raf = 0;
      this._drawPreview();
    });
  }

  _currentTransform() {
    const d = this.cropper.getData(true); // rounded, source-pixel coords
    return { ...this.transform, mode: "crop", crop: { x: d.x, y: d.y, width: d.width, height: d.height } };
  }

  _drawPreview() {
    if (!this.cropper) return;
    const xform = this._currentTransform();
    const { src } = computeRects(this.source, xform);

    // Box-average the crop straight down to WxH. Deliberately independent of
    // the real pipeline: this is a framing aid that must stay instant, and it
    // renders even for crops the segmenter would later reject.
    const tmp = document.createElement("canvas");
    tmp.width = W;
    tmp.height = H;
    const tctx = tmp.getContext("2d", { willReadFrequently: true });
    tctx.imageSmoothingEnabled = true;
    tctx.imageSmoothingQuality = "high";
    tctx.clearRect(0, 0, W, H);
    try {
      tctx.drawImage(this.source.drawable, src.x, src.y, src.w, src.h, 0, 0, W, H);
    } catch {
      return; // degenerate rect mid-drag
    }

    for (const ctx of [this.previewCtx, this.tinyCtx]) {
      ctx.imageSmoothingEnabled = false;
      ctx.clearRect(0, 0, W, H);
      ctx.drawImage(tmp, 0, 0);
    }

    // Report the effective scale, and warn when upscaling hard -- a 40px
    // source blown up to 512 has no detail to give the segmenter.
    const scale = WORK / src.w;
    const pct = (scale * 100).toFixed(0);
    const d = xform.crop;
    if (this.statsEl) this.statsEl.textContent = `crop ${Math.round(d.width)}×${Math.round(d.height)}px → ${WORK}×${WORK} (${pct}%)`;
    if (this.hintEl) {
      if (src.w < W * 4) {
        this.hintEl.textContent = `Heads up: this crop is only ${Math.round(src.w)}px wide, under ${W * 4}px, so it will be upscaled a lot -- expect soft edges and a noisy segmentation.`;
        this.hintEl.className = "text-[11px] text-amber-500 mt-2";
      } else {
        this.hintEl.textContent = "Drag to pan, scroll or pinch to zoom, drag the handles to resize the crop box.";
        this.hintEl.className = "text-[11px] text-neutral-600 mt-2";
      }
    }
  }

  _apply() {
    if (!this.cropper) return;
    const xform = this._currentTransform();
    const cb = this.onApply;
    this.close();
    cb?.(xform);
  }

  close() {
    window.removeEventListener("keydown", this._keyHandler);
    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = 0;
    this.cropper?.destroy();
    this.cropper = null;
    this.el?.remove();
    this.el = null;
  }
}
