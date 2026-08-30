/**
 * bboxLink.js — thin JSON-line protocol for Broadcast Box firmware.
 * Modeled on ndjsonLink.js; only line buffering, id correlation, brace-prefix
 * drops, REPL echo detection, and Box commands/events.
 */

import { logIn, logOut, logDrop, logInfo, logWarn, logError } from "./serialLog.js";

let nextId = 1;

export class BboxLink {
  constructor(adapter) {
    this.adapter = adapter;
    this.capabilities = { broadcastBox: true };
    this._buf = "";
    this._pending = new Map();
    this._listeners = new Map();
    this._boundOnData = this._onData.bind(this);
  }

  start() {
    this.adapter.clearBacklog();
    this.adapter.onData = this._boundOnData;
    logInfo("bboxLink attached (JSON line mode)");
  }

  stop() {
    if (this.adapter.onData === this._boundOnData) this.adapter.onData = null;
    for (const { reject } of this._pending.values()) reject(new Error("link stopped"));
    this._pending.clear();
    logInfo("bboxLink detached");
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
    this.adapter.clearBacklog();

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
      let obj;
      try {
        obj = JSON.parse(line);
      } catch (e) {
        logWarn(`JSON parse failed: ${e.message}`, { line: line.slice(0, 200) });
        continue;
      }
      if (obj.cmd !== undefined && obj.type === undefined) {
        logWarn(`echo of our own command '${obj.cmd}' -- device is at the REPL`);
        this._emit("repl", { reason: "command echoed", line });
        continue;
      }

      logIn(line, { type: obj.type ?? null, id: obj.id ?? null });
      const id = obj.id;
      if (id !== undefined && this._pending.has(id)) {
        this._pending.get(id).resolve(obj);
        this._pending.delete(id);
      }
      if (obj.type) this._emit(obj.type, obj);
    }
    if (this._buf.length) {
      logInfo(`holding ${this._buf.length}B partial line (no newline yet)`);
    }
  }

  send(cmd, { timeoutMs = 5000 } = {}) {
    const id = nextId++;
    const payload = { ...cmd, id };
    // MicroPython's REPL readline submits on '\r', not bare '\n' -- a lone
    // '\n' is swallowed as "still typing" and never echoed back, which is
    // why a hello sent at '>>>' used to hang until timeout instead of
    // tripping the command-echo REPL-detection below. '\r\n' submits at
    // the REPL AND is accepted by json_link.py's running-firmware parser
    // (it strips the '\r' when it finds the '\n').
    const text = JSON.stringify(payload) + "\r\n";
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
            reject(new Error(`${obj.code}: ${obj.msg || ""}`.trim()));
          } else resolve(obj);
        },
        reject,
      });
      this.adapter.writeChunked(text, 256, 10).catch(reject);
    });
  }

  hello({ timeoutMs = 4000 } = {}) {
    return this.send({ cmd: "hello" }, { timeoutMs });
  }

  info() {
    return this.send({ cmd: "info" });
  }

  arm() {
    return this.send({ cmd: "arm" }, { timeoutMs: 15000 });
  }

  disarm() {
    return this.send({ cmd: "disarm" });
  }

  async enterRepl() {
    await this.send({ cmd: "repl" }, { timeoutMs: 2000 }).catch(() => {});
    this.stop();
  }

  reboot({ hard = false } = {}) {
    return this.send({ cmd: "reboot", hard }, { timeoutMs: 2000 }).catch(() => {});
  }
}
