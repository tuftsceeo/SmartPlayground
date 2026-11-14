/**
 * pngExact.js -- minimal PNG decoder for the lossless identity path.
 *
 * WHY THIS EXISTS: both createImageBitmap({premultiplyAlpha:'none'}) and
 * ImageDecoder({premultiplyAlpha:'none'}) were tested and BOTH still
 * round-trip semi-transparent pixels through premultiplied alpha
 * internally (confirmed empirically: a flat-fill source with alpha-only
 * AA edges, e.g. assets/apple.png's leaf, has a constant straight RGB
 * (101,156,53) at every alpha level in Pillow's raw decode, but Chrome's
 * canvas/ImageDecoder paths drift toward that value as alpha increases --
 * exactly the signature of premultiply-then-unpremultiply rounding, e.g.
 * at alpha=27: premul = round(101*27/255)=11, unpremul = round(11*255/27)
 * = 104, matching the observed drift precisely). This is a platform-level
 * limitation (the underlying decode surface is premultiplied regardless of
 * the API-level hint), not something fixable from application code.
 *
 * So for the lossless identity path (a 512x512, 8-bit, RGBA,
 * non-interlaced PNG -- true for all six committed assets), this module
 * decodes the file directly: parse chunks, inflate IDAT via the platform's
 * DecompressionStream('deflate') (zlib/RFC1950 -- no hand-rolled inflate
 * needed), then apply the PNG defilter (Sub/Up/Average/Paeth) in JS. The
 * result is raw straight-alpha RGBA bytes, exactly as stored in the file.
 *
 * Anything outside that shape (palette, non-8-bit, interlaced, or just
 * JPEG/WebP/SVG) falls back to the canvas decode path in decode.js -- P4's
 * arbitrary-import fit/scale modes already accept non-byte-exact decode,
 * so this limitation only matters for the identity fast path it targets.
 */

const SIGNATURE = [137, 80, 78, 71, 13, 10, 26, 10];

function readU32(bytes, offset) {
  return (bytes[offset] << 24) | (bytes[offset + 1] << 16) | (bytes[offset + 2] << 8) | bytes[offset + 3];
}

/** @returns {{ihdr: object, idat: Uint8Array}|null} null if not a supported PNG shape. */
function parsePng(bytes) {
  for (let i = 0; i < 8; i++) {
    if (bytes[i] !== SIGNATURE[i]) return null;
  }
  let offset = 8;
  let ihdr = null;
  const idatChunks = [];

  while (offset < bytes.length) {
    const length = readU32(bytes, offset);
    const type = String.fromCharCode(bytes[offset + 4], bytes[offset + 5], bytes[offset + 6], bytes[offset + 7]);
    const dataStart = offset + 8;

    if (type === "IHDR") {
      ihdr = {
        width: readU32(bytes, dataStart),
        height: readU32(bytes, dataStart + 4),
        bitDepth: bytes[dataStart + 8],
        colorType: bytes[dataStart + 9],
        compression: bytes[dataStart + 10],
        filter: bytes[dataStart + 11],
        interlace: bytes[dataStart + 12],
      };
    } else if (type === "IDAT") {
      idatChunks.push(bytes.subarray(dataStart, dataStart + length));
    } else if (type === "IEND") {
      break;
    }
    offset = dataStart + length + 4; // skip CRC
  }

  if (!ihdr) return null;
  const idatLen = idatChunks.reduce((s, c) => s + c.length, 0);
  const idat = new Uint8Array(idatLen);
  let o = 0;
  for (const c of idatChunks) {
    idat.set(c, o);
    o += c.length;
  }
  return { ihdr, idat };
}

async function inflateZlib(bytes) {
  const ds = new DecompressionStream("deflate"); // 'deflate' == zlib/RFC1950 per Compression Streams API
  const stream = new Blob([bytes]).stream().pipeThrough(ds);
  const buf = await new Response(stream).arrayBuffer();
  return new Uint8Array(buf);
}

function paeth(a, b, c) {
  const p = a + b - c;
  const pa = Math.abs(p - a);
  const pb = Math.abs(p - b);
  const pc = Math.abs(p - c);
  if (pa <= pb && pa <= pc) return a;
  if (pb <= pc) return b;
  return c;
}

/** Reverse PNG's per-scanline filtering. bpp = bytes per whole pixel (4 for RGBA8). */
function defilter(raw, width, height, bpp) {
  const stride = width * bpp;
  const out = new Uint8Array(height * stride);
  let rawOff = 0;
  let prevRowOff = -1; // -1 == "treat as all zero"

  for (let y = 0; y < height; y++) {
    const filterType = raw[rawOff++];
    const rowOff = y * stride;
    for (let x = 0; x < stride; x++) {
      const raw_ = raw[rawOff + x];
      const a = x >= bpp ? out[rowOff + x - bpp] : 0;
      const b = prevRowOff >= 0 ? out[prevRowOff + x] : 0;
      const c = prevRowOff >= 0 && x >= bpp ? out[prevRowOff + x - bpp] : 0;
      let v;
      switch (filterType) {
        case 0:
          v = raw_;
          break;
        case 1:
          v = raw_ + a;
          break;
        case 2:
          v = raw_ + b;
          break;
        case 3:
          v = raw_ + ((a + b) >> 1);
          break;
        case 4:
          v = raw_ + paeth(a, b, c);
          break;
        default:
          throw new Error(`pngExact: unknown filter type ${filterType} at row ${y}`);
      }
      out[rowOff + x] = v & 0xff;
    }
    rawOff += stride;
    prevRowOff = rowOff;
  }
  return out;
}

/**
 * Decode a PNG Blob to raw RGBA ImageData, bypassing all browser image
 * compositing. Only supports 8-bit RGBA (colorType 6), non-interlaced --
 * the shape of every asset this pipeline is byte-exact-critical for.
 * @returns {Promise<ImageData|null>} null if the PNG isn't that shape
 *   (caller should fall back to the canvas decode path).
 */
export async function decodePngExact(blob) {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  const parsed = parsePng(bytes);
  if (!parsed) return null;
  const { ihdr, idat } = parsed;

  if (ihdr.bitDepth !== 8 || ihdr.colorType !== 6 || ihdr.interlace !== 0) {
    return null; // fall back -- see module docstring
  }

  const inflated = await inflateZlib(idat);
  const rgba = defilter(inflated, ihdr.width, ihdr.height, 4);
  return new ImageData(new Uint8ClampedArray(rgba.buffer), ihdr.width, ihdr.height);
}
