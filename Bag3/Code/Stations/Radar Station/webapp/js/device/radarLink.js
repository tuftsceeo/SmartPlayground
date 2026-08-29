/**
 * radarLink.js -- talks the newline-delimited-JSON protocol to a device
 * running radar_server.py (see radar_server.py / json_link.py and the
 * top-level plan's "Wire protocol" section). Built on serialAdapter.js's
 * raw byte layer. Structurally adapted from the Icon Display Station's
 * ndjsonLink.js (same line-framing / request-correlation idiom), but the
 * message set is this station's own: `hello`/`info`/`stream`/`raw`/
 * `mode`/`repl`/`reboot` as request/reply commands, and `targets`/
 * `tracks`/`events`/`heartbeat`/`fatal` as unsolicited streamed lines
 * subscribed via `.on(type, cb)`.
 */

import { logIn, logOut, logDrop, logInfo, logWarn, logError } from "./serialLog.js";

let nextId = 1;

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
        // debug/boot banner/REPL echo -- ignored by design (see
        // json_link.py's line filter), but LOG it: if the device is
        // talking and we're discarding all of it, this is where that shows.
        logDrop(line, { reason: "does not start with '{'" });
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
      // Our own command echoed back (device is at the REPL, not running
      // the firmware): replies always carry `type`, never `cmd`.
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
