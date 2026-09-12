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
    el.className = "modal-overlay";
    el.innerHTML = `
      <div class="modal-card max-h-full overflow-hidden">
        <div class="px-[22px] py-3.5 border-b-2 border-[var(--border)] flex items-center gap-2.5">
          <i data-lucide="scissors" class="w-4 h-4 text-[var(--muted)]"></i>
          <span class="font-bold text-[15px]">Crop &amp; scale</span>
          <span class="font-semibold text-[11.5px] text-[var(--muted2)]">frame the photo before it enters the icon</span>
          <button type="button" id="cmClose" class="ml-auto icon-btn text-[var(--muted2)]"><i data-lucide="x" class="w-5 h-5"></i></button>
        </div>

        <div class="flex-1 overflow-auto p-5 grid grid-cols-[1fr_190px] gap-4">
          <div>
            <div class="bg-[var(--canvas-bg)] rounded-xl overflow-hidden" style="max-height:52vh">
              <img id="cmImage" src="${source.objectUrl}" alt="" style="max-width:100%; display:block" />
            </div>
            <div class="flex flex-wrap items-center gap-2 mt-3">
              <button type="button" data-preset="contain" class="btn-pill">Whole image</button>
              <button type="button" data-preset="cover" class="btn-pill">Fill square</button>
              <button type="button" data-preset="reset" class="btn-pill">Reset crop</button>
              ${
                simple
                  ? ""
                  : `<label class="flex items-center gap-1.5 font-semibold text-[11.5px] text-[var(--muted)] ml-2 cursor-pointer">
                <input type="checkbox" id="cmSquare" checked class="accent-[var(--teal)]" /> lock to square
              </label>
              <label class="flex items-center gap-1.5 font-semibold text-[11.5px] text-[var(--muted)]">
                smoothing
                <select id="cmSmooth" class="select-themed text-[11.5px] py-1 px-1.5">
                  <option value="auto">auto</option>
                  <option value="on">on (blend)</option>
                  <option value="off">off (nearest)</option>
                </select>
              </label>`
              }
            </div>
            ${simple ? "" : `<div class="font-semibold text-[11px] text-[var(--muted2)] mt-2.5 leading-snug" id="cmHint"></div>`}
          </div>

          <div class="flex flex-col gap-2.5">
            <div>
              <span class="panel-label">framing preview</span>
              <canvas id="cmPreview" class="pixelated rounded-[10px] border-2 border-[var(--ink)] mt-1.5"
                      width="${W}" height="${H}"
                      style="width:130px;height:130px;background:var(--canvas-bg);display:block"></canvas>
              <div class="font-semibold text-[10.5px] text-[var(--muted2)] mt-1.5 leading-snug">
                shows silhouette &amp; framing only — final colours come from segmentation after you apply
              </div>
            </div>
            <div>
              <span class="panel-label">at actual size</span>
              <canvas id="cmTiny" class="pixelated rounded-lg border-2 border-[var(--border)] mt-1.5"
                      width="${W}" height="${H}"
                      style="width:${W * 2}px;height:${H * 2}px;background:var(--canvas-bg);display:block"></canvas>
            </div>
            ${simple ? "" : `<div id="cmStats" class="font-semibold text-[11px] text-[var(--muted)] leading-snug border-t border-dashed border-[var(--border-soft)] pt-2"></div>`}
          </div>
        </div>

        <div class="px-[22px] py-3.5 border-t-2 border-[var(--border)] flex items-center gap-2.5">
          <button type="button" id="cmCancel" class="btn-secondary ml-auto">Cancel</button>
          <button type="button" id="cmApply" class="btn-primary">Apply</button>
        </div>
      </div>
    `;
    document.body.appendChild(el);
    this.el = el;
    window.lucide?.createIcons?.();

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
        this.hintEl.className = "font-semibold text-[11px] text-[#b45309] mt-2.5 leading-snug";
      } else {
        this.hintEl.textContent = "Drag to pan, scroll or pinch to zoom, drag the handles to resize the crop box.";
        this.hintEl.className = "font-semibold text-[11px] text-[var(--muted2)] mt-2.5 leading-snug";
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
