/**
 * serialLog.js -- a shared, subscribable ring buffer of everything that
 * happens on the serial channel. Vendored near-verbatim from the Icon
 * Display Station webapp (`Bag3/Code/Stations/Icon Display Station/
 * webapp/js/device/serialLog.js` on origin/icon_screen_simplify) -- see
 * the top-level plan's note on hand-duplicated shared libraries. The
 * point is that a failure to connect should be DIAGNOSABLE from the page
 * itself: port identity, control signals, raw bytes in both directions,
 * line framing decisions, request/reply correlation, and read-loop
 * lifecycle.
 *
 * Nothing here decides anything -- it only records. Producers are
 * serialAdapter.js (wire level) and radarLink.js (protocol level).
 */

const MAX_ENTRIES = 3000;
const PAYLOAD_PREVIEW = 400;

export const DIR = {
  TX: "tx",
  RX: "rx",
  OUT: "out",
  IN: "in",
  DROP: "drop",
  INFO: "info",
  WARN: "warn",
  ERROR: "error",
};

let entries = [];
let seq = 0;
const subscribers = new Set();
let paused = false;

export function escapeControl(s) {
  return String(s)
    .replace(/\x00/g, "<NUL>")
    .replace(/\x01/g, "<CTRL-A>")
    .replace(/\x02/g, "<CTRL-B>")
    .replace(/\x03/g, "<CTRL-C>")
    .replace(/\x04/g, "<CTRL-D>")
    .replace(/\x05/g, "<CTRL-E>")
    .replace(/\r/g, "\\r")
    .replace(/\n/g, "\\n");
}

export function log(dir, text, meta = null) {
  if (paused) return;
  let shown = escapeControl(text);
  let truncated = false;
  if (shown.length > PAYLOAD_PREVIEW) {
    shown = shown.slice(0, PAYLOAD_PREVIEW);
    truncated = true;
  }
  const entry = {
    id: ++seq,
    t: performance.now(),
    wall: new Date(),
    dir,
    text: shown,
    truncated,
    fullLength: String(text).length,
    meta,
  };
  entries.push(entry);
  if (entries.length > MAX_ENTRIES) entries = entries.slice(-MAX_ENTRIES);
  subscribers.forEach((cb) => {
    try {
      cb(entry);
    } catch (e) {
      console.error("serialLog subscriber threw", e);
    }
  });
  const tag = `[serial:${dir}]`;
  if (dir === DIR.ERROR) console.error(tag, text, meta ?? "");
  else if (dir === DIR.WARN) console.warn(tag, text, meta ?? "");
  else console.debug(tag, text, meta ?? "");
  return entry;
}

export const logTx = (t, m) => log(DIR.TX, t, m);
export const logRx = (t, m) => log(DIR.RX, t, m);
export const logOut = (t, m) => log(DIR.OUT, t, m);
export const logIn = (t, m) => log(DIR.IN, t, m);
export const logDrop = (t, m) => log(DIR.DROP, t, m);
export const logInfo = (t, m) => log(DIR.INFO, t, m);
export const logWarn = (t, m) => log(DIR.WARN, t, m);
export const logError = (t, m) => log(DIR.ERROR, t, m);

export function subscribe(cb) {
  subscribers.add(cb);
  return () => subscribers.delete(cb);
}

export function getEntries() {
  return entries;
}

export function clear() {
  entries = [];
  subscribers.forEach((cb) => cb(null));
}

export function setPaused(p) {
  paused = p;
}

export function isPaused() {
  return paused;
}

export function toText() {
  const t0 = entries.length ? entries[0].t : 0;
  const lines = entries.map((e) => {
    const ms = (e.t - t0).toFixed(0).padStart(7);
    const dir = e.dir.toUpperCase().padEnd(5);
    const trunc = e.truncated ? ` …(${e.fullLength}B total)` : "";
    const meta = e.meta ? ` ${JSON.stringify(e.meta)}` : "";
    return `${ms}ms ${dir} ${e.text}${trunc}${meta}`;
  });
  return [
    `# Radar Station serial log -- ${new Date().toISOString()}`,
    `# ${entries.length} entries`,
    `# UA: ${navigator.userAgent}`,
    "",
    ...lines,
  ].join("\n");
}
