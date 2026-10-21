/**
 * Payload helpers shared by the bus hosts (<sim-room>, the display panel,
 * later the JS peers). Bus payloads are Uint8Array; Python hands frames
 * across as hex strings (sim_state.radio_send / deliver_enow).
 */

const enc = new TextEncoder();
const dec = new TextDecoder("utf-8", { fatal: true });

export function hexToBytes(hex) {
  const s = String(hex);
  if (s.length % 2) throw new TypeError(`odd-length hex: ${s.length}`);
  const out = new Uint8Array(s.length / 2);
  for (let i = 0; i < out.length; i++) {
    const v = parseInt(s.substr(i * 2, 2), 16);
    if (Number.isNaN(v)) throw new TypeError(`bad hex at ${i * 2}`);
    out[i] = v;
  }
  return out;
}

export function bytesToHex(bytes) {
  return Array.from(bytes, (b) => (b & 0xff).toString(16).padStart(2, "0")).join("");
}

/** A dict/list goes out as JSON text, a string as UTF-8, bytes unchanged. */
export function encodePayload(msg) {
  if (msg instanceof Uint8Array) return msg;
  if (typeof msg === "string") return enc.encode(msg);
  return enc.encode(JSON.stringify(msg));
}

/**
 * { text, json }: text is the UTF-8 decoding, or null for binary; json is
 * the parsed value when the text is JSON, else undefined.
 */
export function decodePayload(bytes) {
  let text = null;
  try {
    text = dec.decode(bytes);
  } catch {
    return { text: null, json: undefined };
  }
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    json = undefined;
  }
  return { text, json };
}
