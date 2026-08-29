/**
 * radarLink.js -- NDJSON protocol client for radar_server.py, on top of
 * serialAdapter.js. Request/reply: hello/info/stream/raw/mode/repl/reboot.
 * Unsolicited, subscribed via .on(type, cb): targets/tracks/events/
 * heartbeat/fatal.
 */

import { logIn, logOut, logDrop, logInfo, logWarn, logError } from "./serialLog.js";

let nextId = 1;

/** Split a line into top-level {...} substrings. Recovers from the device
 * dropping the newline between two back-to-back send() calls, which
 * otherwise merges two JSON objects into one unparseable line. */
function splitJsonObjects(line) {
  const objs = [];
  let depth = 0, start = -1, inStr = false, esc = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inStr) {
      if (esc) esc = false;
      else if (c === "\\") esc = true;
      else if (c === '"') inStr = false;
      continue;
    }
    if (c === '"') {
      inStr = true;
    } else if (c === "{") {
      if (depth === 0) start = i;
      depth++;
    } else if (c === "}") {
      depth--;
      if (depth === 0 && start >= 0) {
        objs.push(line.slice(start, i + 1));
        start = -1;
      }
    }
  }
  return objs;
}

export class RadarLink {
  constructor(adapter) {
    this.adapter = adapter;
    this._buf = "";
    this._pending = new Map(); // id -> {resolve, reject}
    this._listeners = new Map(); // type -> Set<fn>
    this._boundOnData = this._onData.bind(this);
  }

  start() {
    this.adapter.onData = this._boundOnData;
    logInfo("radarLink attached (JSON line mode)");
  }

  stop() {
    if (this.adapter.onData === this._boundOnData) this.adapter.onData = null;
    const n = this._pending.size;
    for (const { reject } of this._pending.values()) reject(new Error("link stopped"));
    this._pending.clear();
    logInfo(`radarLink detached${n ? ` (${n} pending request(s) abandoned)` : ""}`);
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
    let i;
    while ((i = this._buf.indexOf("\n")) >= 0) {
      const line = this._buf.slice(0, i).trim();
      this._buf = this._buf.slice(i + 1);
      if (!line) continue;
      if (line[0] !== "{") {
        logDrop(line, { reason: "does not start with '{'" });
        if (line.includes(">>>") || line.includes("MicroPython v") || line.includes('Type "help()"')) {
          this._emit("repl", { reason: "prompt/banner seen", line });
        }
        continue;
      }
      this._handleLine(line);
    }
  }

  _handleLine(line) {
    let obj;
    try {
      obj = JSON.parse(line);
    } catch (e) {
      // The device can drop the newline between two back-to-back send()
      // calls, merging two JSON objects into one line with no separator.
      // Recover by splitting on balanced braces instead of losing both.
      const parts = splitJsonObjects(line);
      if (parts.length > 1) {
        logWarn(`JSON parse failed, recovered ${parts.length} concatenated objects`, { line: line.slice(0, 200) });
        for (const part of parts) this._handleLine(part);
        return;
      }
      logWarn(`JSON parse failed: ${e.message}`, { line: line.slice(0, 200) });
      return;
    }
    // Our own command echoed back (device is at the REPL, not running
    // the firmware): replies always carry `type`, never `cmd`.
    if (obj.cmd !== undefined && obj.type === undefined) {
      logWarn(`echo of our own command '${obj.cmd}' -- device is at the REPL, not running the firmware`);
      this._emit("repl", { reason: "command echoed", line });
      return;
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
      this.adapter.write(text).catch(reject);
    });
  }

  hello({ timeoutMs = 1500 } = {}) {
    return this.send({ cmd: "hello" }, { timeoutMs });
  }

  /** Resolves on the next unsolicited or replied `hello`. */
  waitForHello(timeoutMs = 12000) {
    return new Promise((resolve, reject) => {
      const off = this.on("hello", (obj) => {
        clearTimeout(timer);
        off();
        resolve(obj);
      });
      const timer = setTimeout(() => {
        off();
        reject(new Error("timed out waiting for hello"));
      }, timeoutMs);
    });
  }

  /** Recovery from a device stuck at the REPL prompt: Ctrl-C (clear any
   * partial line) then Ctrl-D (soft reset, re-runs main.py). Read-only
   * otherwise -- never sent from a probe against a running device. */
  async restartFirmware({ timeoutMs = 12000 } = {}) {
    const waiting = this.waitForHello(timeoutMs);
    await this.adapter.write("\x03");
    await new Promise((r) => setTimeout(r, 200));
    await this.adapter.write("\x04");
    return waiting;
  }

  info() {
    return this.send({ cmd: "info" });
  }

  setStream(on) {
    return this.send({ cmd: "stream", on });
  }

  setRaw(on) {
    return this.send({ cmd: "raw", on });
  }

  setMode(value) {
    return this.send({ cmd: "mode", value }, { timeoutMs: 2000 });
  }

  async enterRepl() {
    const p = this.send({ cmd: "repl" }, { timeoutMs: 2000 }).catch(() => {});
    await p;
    this.stop();
  }

  reboot({ hard = false } = {}) {
    return this.send({ cmd: "reboot", hard }, { timeoutMs: 2000 }).catch(() => {});
  }
}
