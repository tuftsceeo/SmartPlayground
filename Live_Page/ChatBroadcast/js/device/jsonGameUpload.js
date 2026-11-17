/**
 * jsonGameUpload.js — send a game to the Dial over its JSON link, with no
 * reset (stress-test plan S5 step 4). The Dial keeps running, so USB stays up
 * and its pull counts survive. Firmware that offers this says `upload: 1` in
 * its identity (BDialFirmware/game_upload.py has the device side); anything
 * else still goes through pushPayload()'s raw-REPL path.
 *
 * Commands, one reply each: file.begin {path, size, sha}, file.chunk {seq,
 * data}, file.end, then games.rescan {active} once every file is written.
 */

/** Raw bytes per chunk; matches game_upload.CHUNK_RAW. A 1 KB chunk is a
 *  ~1.4 KB JSON line, well under the link's 4096-byte line limit. */
export const CHUNK_RAW = 1024;

const STEP_TIMEOUT_MS = 5000;

export function supportsJsonUpload(info) {
  return info?.device === "broadcast_dial" && info?.upload >= 1;
}

function toBytes(content) {
  return typeof content === "string" ? new TextEncoder().encode(content) : content;
}

async function sha256Hex(bytes) {
  const d = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(d), (b) => b.toString(16).padStart(2, "0")).join("");
}

function b64(bytes) {
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s);
}

/** Every file the raw-REPL path would write, in the same order. */
export function gameFiles(code, meta = {}) {
  const dest = meta.destPath || "/flash/payload.py";
  const files = [{ path: dest, content: code }];
  if (Array.isArray(meta.tags) && meta.tags.length) {
    files.push({ path: dest.replace(/\.py$/, "") + ".tags.json", content: JSON.stringify(meta.tags) });
  }
  for (const x of meta.extraFiles || []) {
    if (x?.path && x.content !== undefined) files.push({ path: x.path, content: x.content });
  }
  return files;
}

/**
 * @param {(cmd: object, opts: object) => Promise<object>} sendCmd  rejects on an error reply
 * @returns {Promise<{ok: true, restarted: false, live: true, active: string}>}
 */
export async function uploadGameOverJson(sendCmd, code, meta = {}, onProgress) {
  const files = gameFiles(code, meta);
  const opts = { timeoutMs: STEP_TIMEOUT_MS };
  let n = 0;
  for (const f of files) {
    n++;
    const name = f.path.split("/").pop();
    onProgress?.({ current: n, total: files.length, file: name, status: "uploading" });
    const bytes = toBytes(f.content);
    await sendCmd({ cmd: "file.begin", path: f.path, size: bytes.length, sha: await sha256Hex(bytes) }, opts);
    try {
      for (let seq = 0, i = 0; i < bytes.length; seq++, i += CHUNK_RAW) {
        await sendCmd({ cmd: "file.chunk", seq, data: b64(bytes.subarray(i, i + CHUNK_RAW)) }, opts);
      }
      await sendCmd({ cmd: "file.end" }, opts);
    } catch (e) {
      await sendCmd({ cmd: "file.abort" }, opts).catch(() => {});
      throw e;
    }
  }
  const slug = (files[0].path.split("/").pop() || "").replace(/\.py$/, "");
  const r = await sendCmd({ cmd: "games.rescan", active: slug }, { timeoutMs: 8000 });
  onProgress?.({ current: files.length, total: files.length, file: files[0].path.split("/").pop(), status: "done" });
  return { ok: true, restarted: false, live: true, active: r?.active };
}
