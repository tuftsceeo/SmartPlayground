/**
 * ndjsonLink.js -- talks the newline-delimited-JSON protocol to a device
 * running icon_server.py (see icon_server.py / json_link.py and the plan
 * §Protocol). Built on serialAdapter.js's raw byte layer; unrelated to
 * replController.js's REPL byte protocol -- those are two different
 * "modes" the device can be in (see deviceLink.js for switching between
 * them).
 *
 * Frame payload correctness (base64 packing, LUT truncation model, cell
 * ordering) is verified against a hardware simulation in
 * webapp/js/utils -- see icon_matrix.py/icon_server.py's own docstrings.
 * This module's line-framing/request-correlation logic is NOT yet
 * exercised against a real serial link from this session.
 */

import { logIn, logOut, logDrop, logInfo, logWarn, logError } from "./serialLog.js";

let nextId = 1;

function bytesToBase64(bytes) {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

export class NdjsonLink {
  constructor(adapter) {
    this.adapter = adapter;
    this.capabilities = { liveFrames: true, fileOps: true };
    this._buf = "";
    this._pending = new Map(); // id -> {resolve, reject}
    this._listeners = new Map(); // type -> Set<fn>
    this._boundOnData = this._onData.bind(this);
  }

  start() {
    this.adapter.clearBacklog();
    this.adapter.onData = this._boundOnData;
    logInfo("ndjsonLink attached (JSON line mode)");
  }

  stop() {
    if (this.adapter.onData === this._boundOnData) this.adapter.onData = null;
    const n = this._pending.size;
    for (const { reject } of this._pending.values()) reject(new Error("link stopped"));
    this._pending.clear();
    logInfo(`ndjsonLink detached${n ? ` (${n} pending request(s) abandoned)` : ""}`);
  }

  on(type, cb) {
    if (!this._listeners.has(type)) this._listeners.set(type, new Set());
    this._listeners.get(type).add(cb);
    return () => this._listeners.get(type)?.delete(cb);
  }

  _emit(type, obj) {
    this._listeners.get(type)?.forEach((cb) => cb(obj));
    this._listeners.get("*")?.forEach((cb) => cb(obj));
  }

  _onData(chunk) {
    this._buf += chunk;
    // Nothing else consumes adapter.readBuf while in JSON mode (no REPL
    // waiters active) -- clear it here so it can't grow unbounded over a
    // long live-preview session.
    this.adapter.clearBacklog();

    let i;
    while ((i = this._buf.indexOf("\n")) >= 0) {
      const line = this._buf.slice(0, i).trim();
      this._buf = this._buf.slice(i + 1);
      if (!line) continue;
      if (line[0] !== "{") {
        // debug/boot banner/REPL echo -- ignored by design, but LOG it:
        // if the device is talking and we're discarding all of it, this is
        // where that shows up.
        logDrop(line, { reason: "does not start with '{'" });
        // A MicroPython prompt or banner means the firmware is NOT running
        // -- the device is sitting at the REPL and will only ECHO our
        // commands, never answer them. Surface it so the UI can offer (or
        // perform) a restart instead of waiting forever.
        if (line.includes(">>>") || line.includes("MicroPython v") || line.includes('Type "help()"')) {
          this._emit("repl", { reason: "prompt/banner seen", line });
        }
        continue;
      }
      let obj;
      try {
        obj = JSON.parse(line);
      } catch (e) {
        logWarn(`JSON parse failed: ${e.message}`, { line: line.slice(0, 200) });
        continue;
      }
      // Our own command echoed back: device replies ALWAYS carry `type` and
      // never `cmd`, so a `cmd` key arriving inbound means the MicroPython
      // REPL is echoing our input rather than icon_server.py answering it.
      // (Observed verbatim in a real session: TX {"cmd":"hello","id":9002}
      // -> RX {"cmd":"hello","id":9002}.)
      if (obj.cmd !== undefined && obj.type === undefined) {
        logWarn(`echo of our own command '${obj.cmd}' -- device is at the REPL, not running the firmware`);
        this._emit("repl", { reason: "command echoed", line });
        continue;
      }

      logIn(line, { type: obj.type ?? null, id: obj.id ?? null });
      const id = obj.id;
      if (id !== undefined && this._pending.has(id)) {
        this._pending.get(id).resolve(obj);
        this._pending.delete(id);
      } else if (id !== undefined) {
        logInfo(`reply id ${id} had no waiting request (unsolicited or already timed out)`);
      }
      if (obj.type) this._emit(obj.type, obj);
    }
    if (this._buf.length) {
      logInfo(`holding ${this._buf.length}B partial line (no newline yet)`);
    }
  }

  /** Send one command, correlated by `id`, resolving with the matching reply. */
  send(cmd, { timeoutMs = 3000 } = {}) {
    const id = nextId++;
    const payload = { ...cmd, id };
    const text = JSON.stringify(payload) + "\n";
    logOut(text.trim(), { cmd: cmd.cmd, id, timeoutMs });
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this._pending.delete(id);
        logWarn(`TIMEOUT after ${timeoutMs}ms waiting for reply to '${cmd.cmd}' (id ${id})`);
        reject(new Error(`timed out waiting for reply to ${cmd.cmd} (id ${id})`));
      }, timeoutMs);
      this._pending.set(id, {
        resolve: (obj) => {
          clearTimeout(timer);
          if (obj.type === "error") {
            logError(`device replied error to '${cmd.cmd}': ${obj.code} ${obj.msg || ""}`.trim());
            reject(new Error(`${obj.code}: ${obj.msg || ""}`.trim()));
          } else resolve(obj);
        },
        reject,
      });
      // 256B/10ms pacing -- the USB stdin ring buffer is small and a
      // ~1050-char base64 frame line is bigger than it; see the plan's
      // firmware risk #1.
      this.adapter.writeChunked(text, 256, 10).catch(reject);
    });
  }

  hello({ timeoutMs = 1500 } = {}) {
    // Short timeout: this doubles as the "is icon_server.py already running,
    // or does this port need firmware installed?" probe -- see deviceLink.js.
    return this.send({ cmd: "hello" }, { timeoutMs });
  }

  info() {
    return this.send({ cmd: "info" });
  }

  /** frame: Uint8Array(768), authored (unscaled) RGB triples, row-major top-left. */
  sendFrame(frame, { ack = true } = {}) {
    return this.send({ cmd: "frame", d: bytesToBase64(frame), ack }, { timeoutMs: 2000 });
  }

  setIntensity(value, { persist = false } = {}) {
    return this.send({ cmd: "intensity", value, persist });
  }

  clear() {
    return this.send({ cmd: "clear" });
  }

  listIcons() {
    return this.send({ cmd: "list" }).then((r) => r.list);
  }

  showIcon(name) {
    return this.send({ cmd: "show", name });
  }

  /** frame is optional: omit to save what's currently displayed on the matrix. */
  saveIcon(name, frame, { overwrite = false } = {}) {
    const body = { cmd: "save", name, overwrite };
    if (frame) body.d = bytesToBase64(frame);
    return this.send(body, { timeoutMs: 5000 });
  }

  deleteIcon(name) {
    return this.send({ cmd: "delete", name });
  }

  setCycle(on, { holdMs = 4000, names = null } = {}) {
    return this.send({ cmd: "cycle", on, hold_ms: holdMs, names });
  }

  /** Drop back to the MicroPython REPL (deterministic escape hatch). */
  async enterRepl() {
    const p = this.send({ cmd: "repl" }, { timeoutMs: 2000 }).catch(() => {});
    await p;
    this.stop();
  }

  reboot({ hard = false } = {}) {
    return this.send({ cmd: "reboot", hard }, { timeoutMs: 2000 }).catch(() => {});
  }
}
