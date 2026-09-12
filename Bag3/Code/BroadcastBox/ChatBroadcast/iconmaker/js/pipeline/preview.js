/**
 * preview.js -- simulated-LED render, ported from iconlib/preview.py but
 * using three composited canvases instead of Pillow's per-pixel additive
 * loop (see plan §Preview compose for why plain shadowBlur under
 * source-over is wrong: it occludes overlapping glows instead of summing
 * them, the way Python's whole-layer Gaussian + clamped add does).
 *
 * Honest about what it's good for: cell on/off, silhouette, thin-feature
 * survival, relative brightness ordering -- NOT absolute hue. Sign off on
 * hue only from the real matrix (see readme.md).
 */

import { W, H, PREVIEW_SCALE, DOT_RADIUS, BLOOM_RADIUS, PREVIEW_BG } from "./constants.js";
import { predictLedAppearance } from "./ledcolor.js";

const isBlack = (p) => p[0] === 0 && p[1] === 0 && p[2] === 0;

/**
 * @param {Array<[number,number,number]>} pixels  flat 256, row-major, authored bytes
 * @param {number} intensity
 * @param {HTMLCanvasElement} [canvas]  reused if given, else created
 * @returns {HTMLCanvasElement}
 */
export function renderPreview(pixels, intensity, canvas) {
  const size = W * PREVIEW_SCALE;
  canvas = canvas || document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");

  const dots = document.createElement("canvas");
  dots.width = size;
  dots.height = size;
  const dctx = dots.getContext("2d");
  dctx.fillStyle = "rgb(0, 0, 0)";
  dctx.fillRect(0, 0, size, size);
  dctx.globalCompositeOperation = "lighter"; // sums overlapping glows, matches Python's additive clamp

  for (let row = 0; row < H; row++) {
    for (let col = 0; col < W; col++) {
      const rgb = pixels[row * W + col];
      if (isBlack(rgb)) continue;
      const seen = predictLedAppearance(rgb, intensity);
      const cx = col * PREVIEW_SCALE + PREVIEW_SCALE / 2;
      const cy = row * PREVIEW_SCALE + PREVIEW_SCALE / 2;
      dctx.fillStyle = `rgb(${seen[0]}, ${seen[1]}, ${seen[2]})`;
      dctx.beginPath();
      dctx.arc(cx, cy, DOT_RADIUS, 0, Math.PI * 2);
      dctx.fill();
    }
  }

  const bloom = document.createElement("canvas");
  bloom.width = size;
  bloom.height = size;
  const bctx = bloom.getContext("2d");
  bctx.filter = `blur(${BLOOM_RADIUS}px)`; // true Gaussian, stdDev == BLOOM_RADIUS px
  bctx.drawImage(dots, 0, 0);

  ctx.globalCompositeOperation = "source-over";
  ctx.fillStyle = `rgb(${PREVIEW_BG[0]}, ${PREVIEW_BG[1]}, ${PREVIEW_BG[2]})`;
  ctx.fillRect(0, 0, size, size);
  ctx.globalAlpha = 0.35; // Image.blend(bg, bloom, 0.35)
  ctx.drawImage(bloom, 0, 0);
  ctx.globalAlpha = 1.0;
  ctx.globalCompositeOperation = "lighter"; // clamped additive sharp layer on top
  ctx.drawImage(dots, 0, 0);
  ctx.globalCompositeOperation = "source-over";

  return canvas;
}

export function previewToBlob(canvas) {
  return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}
