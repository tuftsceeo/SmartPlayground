/**
 * decode.js -- blob/File -> a fixed WORKxWORK working ImageData, replacing
 * PIL's Image.open().convert("RGBA").
 *
 * Two-stage by design, so the crop UI can re-render cheaply:
 *   loadSource(blob)              -> decode once, keep the bitmap around
 *   renderWorking(source, xform)  -> cheap redraw at any crop/fit
 * Dragging a crop handle must not re-decode a multi-megapixel JPEG.
 *
 * THE IDENTITY PATH EARNS ITS KEEP. A source already exactly WORKxWORK,
 * with fit 'contain' and no crop, is decoded losslessly by pngExact.js
 * rather than through a canvas. This is not ceremony: any resample (even a
 * nominal 1:1 blit with smoothing on) perturbs bytes and explodes the
 * exact-colour histogram from a handful of fills into thousands, which
 * pushes flat art off the exact-fill path and into the quantizer for no
 * reason. Chrome also premultiplies alpha regardless of the
 * premultiplyAlpha:'none' hint, adding drift at every AA edge pixel -- see
 * pngExact.js. Do not "simplify" this into a single canvas path.
 */

import { WORK } from "./constants.js";
import { decodePngExact } from "./pngExact.js";

/** Cheap PNG IHDR peek: dimensions without inflating the whole image. */
async function peekPngSize(blob) {
  try {
    const head = new Uint8Array(await blob.slice(0, 24).arrayBuffer());
    const sig = [137, 80, 78, 71, 13, 10, 26, 10];
    for (let i = 0; i < 8; i++) if (head[i] !== sig[i]) return null;
    const rd = (o) => (head[o] << 24) | (head[o + 1] << 16) | (head[o + 2] << 8) | head[o + 3];
    return { width: rd(16), height: rd(20) };
  } catch {
    return null;
  }
}

/**
 * createImageBitmap() rejects SVG in Chrome, and an SVG with only a viewBox
 * (no intrinsic width/height) rasterizes at 0x0 -- force a size in that case.
 */
function loadSvg(blob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      const w = img.naturalWidth || WORK;
      const h = img.naturalHeight || WORK;
      if (!img.naturalWidth || !img.naturalHeight) {
        img.width = WORK;
        img.height = WORK;
      }
      resolve({ drawable: img, width: w, height: h, revoke: () => URL.revokeObjectURL(url) });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("SVG could not be rasterized by the browser."));
    };
    img.src = url;
  });
}

async function loadDrawable(blob) {
  if (blob.type === "image/svg+xml") return loadSvg(blob);
  try {
    const bitmap = await createImageBitmap(blob, {
      premultiplyAlpha: "none",
      colorSpaceConversion: "none",
    });
    return { drawable: bitmap, width: bitmap.width, height: bitmap.height, revoke: () => bitmap.close?.() };
  } catch (e) {
    throw new Error(`This file could not be decoded as an image (${blob.type || "unknown type"}): ${e.message}`);
  }
}

/**
 * Decode a blob ONCE. Returns a reusable source handle:
 *   { width, height, drawable, exact, objectUrl, type }
 * `exact` is a byte-exact ImageData when the file is a WORKxWORK 8-bit
 * non-interlaced RGBA PNG, else null.
 * `objectUrl` is for the crop UI's <img> (Cropper.js needs an element).
 */
export async function loadSource(blob) {
  let exact = null;
  if (blob.type === "image/png" || blob.type === "") {
    // Only pay for the exact decode when it could actually be used.
    const size = await peekPngSize(blob);
    if (size && size.width === WORK && size.height === WORK) {
      exact = await decodePngExact(blob);
    }
  }

  const { drawable, width, height, revoke } = await loadDrawable(blob);

  return {
    blob,
    type: blob.type,
    drawable,
    width,
    height,
    exact,
    objectUrl: URL.createObjectURL(blob),
    dispose() {
      revoke?.();
      URL.revokeObjectURL(this.objectUrl);
    },
  };
}

/** The default transform for a freshly loaded source. */
export function defaultTransform(source) {
  const square = source.width === source.height;
  return {
    // A square source needs no framing decision; anything else defaults to
    // 'contain' (letterboxed) because the device is square and transparent
    // padding becomes off pixels -- almost always what you want for an icon.
    mode: square ? "contain" : "contain",
    crop: null, // {x,y,width,height} in SOURCE pixels, set by the crop tool
    smoothing: "auto",
  };
}

export function isIdentityTransform(source, xform) {
  return (
    !!source.exact &&
    source.exact.width === WORK &&
    source.exact.height === WORK &&
    xform.mode === "contain" &&
    !xform.crop
  );
}

/**
 * Compute the source rectangle and destination rectangle for a transform.
 * Exported so the crop UI can show the same framing it will actually get.
 */
export function computeRects(source, xform) {
  const sw = source.width;
  const sh = source.height;

  if (xform.crop) {
    const c = xform.crop;
    // Clamp into the image; Cropper can report slightly out-of-bounds rects.
    const x = Math.max(0, Math.min(sw, c.x));
    const y = Math.max(0, Math.min(sh, c.y));
    const w = Math.max(1, Math.min(sw - x, c.width));
    const h = Math.max(1, Math.min(sh - y, c.height));
    return { src: { x, y, w, h }, dst: { x: 0, y: 0, w: WORK, h: WORK } };
  }

  if (xform.mode === "stretch") {
    return { src: { x: 0, y: 0, w: sw, h: sh }, dst: { x: 0, y: 0, w: WORK, h: WORK } };
  }

  if (xform.mode === "cover") {
    // Largest centered square of the source, scaled to fill.
    const side = Math.min(sw, sh);
    return {
      src: { x: (sw - side) / 2, y: (sh - side) / 2, w: side, h: side },
      dst: { x: 0, y: 0, w: WORK, h: WORK },
    };
  }

  // 'contain': whole image, aspect preserved, transparent padding.
  const scale = Math.min(WORK / sw, WORK / sh);
  const dw = sw * scale;
  const dh = sh * scale;
  return {
    src: { x: 0, y: 0, w: sw, h: sh },
    dst: { x: (WORK - dw) / 2, y: (WORK - dh) / 2, w: dw, h: dh },
  };
}

/**
 * Draw `source` into a WORKxWORK ImageData under `xform`.
 * Cheap (a single drawImage) -- safe to call on every crop commit.
 */
export function renderWorking(source, xform) {
  if (isIdentityTransform(source, xform)) {
    return { imageData: source.exact, canvas: null, identity: true };
  }

  const { src, dst } = computeRects(source, xform);

  const canvas = document.createElement("canvas");
  canvas.width = WORK;
  canvas.height = WORK;
  const ctx = canvas.getContext("2d", { willReadFrequently: true, colorSpace: "srgb" });
  ctx.clearRect(0, 0, WORK, WORK); // transparent padding for 'contain'

  // SMOOTHING POLICY. Upscaling with nearest-neighbour keeps flat-colour
  // art's palette EXACT, which is what lets such an image stay on the
  // exact-fill segmentation path instead of falling back to the quantizer
  // -- strictly better output. Downscaling a photo wants real filtering.
  const scale = dst.w / src.w;
  let smooth;
  if (xform.smoothing === "on") smooth = true;
  else if (xform.smoothing === "off") smooth = false;
  else smooth = scale < 1; // 'auto'
  ctx.imageSmoothingEnabled = smooth;
  if (smooth) ctx.imageSmoothingQuality = "high";

  ctx.drawImage(source.drawable, src.x, src.y, src.w, src.h, dst.x, dst.y, dst.w, dst.h);

  return { imageData: ctx.getImageData(0, 0, WORK, WORK), canvas, identity: false };
}

/**
 * One-shot convenience used by the fixture loader and the simple import
 * path: decode and render in a single call.
 */
export async function decodeToWorking(blob, opts = {}) {
  const source = await loadSource(blob);
  const xform = { ...defaultTransform(source), ...(opts.transform || {}) };
  if (opts.fit) xform.mode = opts.fit;
  const { imageData, canvas, identity } = renderWorking(source, xform);
  return { imageData, canvas, identity, source, transform: xform };
}

/** Convenience: decode a same-origin URL (e.g. ../assets/apple.png). */
export async function decodeUrlToWorking(url, opts = {}) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`decodeUrlToWorking: fetch ${url} failed (${res.status})`);
  const blob = await res.blob();
  return decodeToWorking(blob, opts);
}
