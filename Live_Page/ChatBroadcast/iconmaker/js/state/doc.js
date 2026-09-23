/**
 * doc.js -- the NON-reactive document: big typed arrays and anything that
 * would be wasteful to push through setState/innerHTML rebuilds on every
 * interactive edit. Nothing subscribes to this; main.js reads/writes it
 * directly and calls paint() on the persistent canvases. See plan
 * §App architecture / recompute tiers.
 */

export const doc = {
  source: null, // decode.js loadSource() handle -- kept so the crop tool can
                 // re-render without re-decoding the original file
  transform: null, // {mode, crop, smoothing} currently applied to `source`
  imageData: null, // WORKxWORK ImageData, tier T0
  labels: null, // Int16Array(WORK*WORK), tier T1/T2
  coverageBySeg: null, // Array<Float64Array(256)>, tier T2
  opaqueCoverage: null, // Float64Array(256), tier T2
  ringMatch: null,
  ringTotal: null,
  bgMatch: null,

  overlay: new Map(), // flatIndex -> [r,g,b], hand-painted cells
  undoStack: [], // snapshots of overlay (Map) before each stroke

  rasterPixels: null, // Array<[r,g,b]>, post connect-pass, PRE overlay/floor (tier T4 cache)
  pixels: null, // Array<[r,g,b]>, post overlay+floor -- what's actually shown/exported
  winner: null, // Int16Array(256), segment id per cell or -1

  existingMap: null, // the loaded maps/<name>.json, or null
};

export function resetDoc() {
  // NOTE: doc.source/transform are deliberately NOT cleared here -- resetDoc
  // runs on every resegment, and the crop tool must keep working against the
  // already-decoded original. releaseSource() handles the actual teardown.
  doc.imageData = null;
  doc.labels = null;
  doc.coverageBySeg = null;
  doc.opaqueCoverage = null;
  doc.ringMatch = null;
  doc.ringTotal = null;
  doc.bgMatch = null;
  doc.overlay = new Map();
  doc.undoStack = [];
  doc.rasterPixels = null;
  doc.pixels = null;
  doc.winner = null;
  doc.existingMap = null;
}

/** Free the previous source's ImageBitmap + object URL before loading a new one. */
export function releaseSource() {
  try {
    doc.source?.dispose?.();
  } catch {
    /* already gone */
  }
  doc.source = null;
  doc.transform = null;
}

export function overlayToObject() {
  const out = {};
  for (const [k, v] of doc.overlay) out[k] = v;
  return out;
}

export function overlayFromObject(obj) {
  const m = new Map();
  for (const [k, v] of Object.entries(obj || {})) m.set(Number(k), v.slice());
  return m;
}

export function pushUndoSnapshot() {
  const snap = new Map();
  for (const [k, v] of doc.overlay) snap.set(k, v.slice());
  doc.undoStack.push(snap);
  if (doc.undoStack.length > 50) doc.undoStack.shift();
}

export function popUndo() {
  if (!doc.undoStack.length) return false;
  doc.overlay = doc.undoStack.pop();
  return true;
}
