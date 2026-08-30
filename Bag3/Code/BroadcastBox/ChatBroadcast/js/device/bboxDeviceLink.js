/**
 * bboxDeviceLink.js — Broadcast Box serial lifecycle (adapted from deviceLink.js).
 * Connect resolves on port open; liveness from any typed message (hello or heartbeat).
 */

import { SerialAdapter } from "./serialAdapter.js";
import { ReplController } from "./replController.js";
import { BboxLink } from "./bboxLink.js";
import { installBoxFirmware, pushPayload } from "./boxFirmwareInstaller.js";
import { logInfo, logWarn, toText } from "./serialLog.js";

const FORWARDED_EVENTS = [
  "hello", "heartbeat", "fatal", "bye", "error", "repl",
  "armed", "card_present", "card_written", "info",
];

const EXPECTED_DEVICE = "broadcast_box";

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

export class BboxDeviceLink {
  constructor() {
    this.adapter = new SerialAdapter();
    this.repl = new ReplController(this.adapter);
    this.json = null;
    this.running = false;
    this.atRepl = false;
    this.wrongDevice = false;
    this.deviceInfo = null;
    this._autoRecoverArmed = false;
    this._listeners = new Map();
  }

  isConnected() {
    return this.adapter.isConnected();
  }

  isRunning() {
    return this.running;
  }

  on(type, cb) {
    if (!this._listeners.has(type)) this._listeners.set(type, new Set());
    this._listeners.get(type).add(cb);
    return () => this._listeners.get(type)?.delete(cb);
  }

  _emit(type, payload) {
    this._listeners.get(type)?.forEach((cb) => cb(payload));
  }

  _markRunning(obj) {
    if (obj?.type === "hello") {
      if (obj.device && obj.device !== EXPECTED_DEVICE) {
        this.wrongDevice = true;
        this.running = false;
        logWarn(`wrong device on hello: ${obj.device} (expected ${EXPECTED_DEVICE})`);
        this._emit("wrong_device", obj);
        return;
      }
      this.deviceInfo = obj;
      this.wrongDevice = false;
    }
    if (obj?.type) {
      this.running = true;
      this.atRepl = false;
    }
  }

  _attachJson() {
    const json = new BboxLink(this.adapter);
    json.start();
    this.json = json;
    for (const type of FORWARDED_EVENTS) {
      json.on(type, (obj) => {
        this._markRunning(obj);
        this._emit(type, obj);
      });
    }
    json.on("*", (obj) => this._markRunning(obj));
    json.on("bye", () => {
      this.running = false;
    });
    json.on("repl", (info) => {
      this.running = false;
      this.atRepl = true;
      this._emit("repl", info);
      if (this._autoRecoverArmed) {
        this._autoRecoverArmed = false;
        logWarn(`REPL detected (${info?.reason}) — attempting one automatic firmware restart`);
        this.restartFirmware().catch((e) => logWarn(`auto-restart failed: ${e.message}`));
      } else {
        logWarn(`REPL detected (${info?.reason}) — not auto-restarting again`);
      }
    });
    return json;
  }

  _detachJson() {
    this.json?.stop();
    this.json = null;
    this.running = false;
    this.atRepl = false;
    this.wrongDevice = false;
    this.deviceInfo = null;
  }

  async connect() {
    logInfo("=== connect() begin ===");
    this._autoRecoverArmed = true;
    this.atRepl = false;
    this.wrongDevice = false;
    await this.adapter.connect();
    const json = this._attachJson();
    logInfo("sending proactive hello probe (fire-and-forget)");
    json.hello({ timeoutMs: 4000 }).catch((e) => logWarn(`hello probe: ${e.message}`));
    logInfo("=== connect() returned (port open; awaiting device messages) ===");
  }

  async probe() {
    logInfo("=== probe: begin (read-only) ===");
    await this.adapter.logSignals("probe start");
    await this.adapter.write("\r\n");
    await sleep(500);
    await this.adapter.write('{"cmd":"hello","id":9001}\n');
    await sleep(1200);
    logInfo("=== probe: end ===");
  }

  async restartFirmware({ timeoutMs = 12000 } = {}) {
    logInfo("=== restartFirmware: Ctrl-C then Ctrl-D ===");
    this._autoRecoverArmed = false;
    if (!this.json) this._attachJson();
    await this.adapter.write("\x03");
    await sleep(200);
    await this.adapter.write("\x04");
    const state = await this.waitForRunning(timeoutMs);
    logInfo(state === "running" ? "restartFirmware: firmware is up" : `restartFirmware: ${state}`);
    return state;
  }

  /** Resolve 'running' on any typed message, 'unknown' on timeout, never 'absent'. */
  waitForRunning(timeoutMs = 10000) {
    return new Promise((resolve) => {
      let done = false;
      const off = this.on("*", (obj) => {
        if (done || !obj?.type) return;
        done = true;
        off();
        resolve("running");
      });
      setTimeout(() => {
        if (done) return;
        done = true;
        off();
        resolve("unknown");
      }, timeoutMs);
    });
  }

  async sendRaw(text) {
    const s = text.endsWith("\n") ? text : text + "\n";
    await this.adapter.write(s);
  }

  async installFirmware(onProgress) {
    this._detachJson();
    try {
      await installBoxFirmware(this.repl, this.adapter, onProgress);
      return true;
    } finally {
      this._attachJson();
    }
  }

  async sendGame(code, meta, onProgress) {
    this._detachJson();
    let pushResult;
    try {
      pushResult = await pushPayload(this.repl, this.adapter, code, onProgress);
    } finally {
      this._attachJson();
    }
    if (!pushResult.ok) return pushResult;
    try {
      onProgress?.({ current: 2, total: 2, file: "arm", status: "uploading" });
      await this.json.arm();
      onProgress?.({ current: 2, total: 2, file: "arm", status: "uploaded" });
      return { ok: true };
    } catch (e) {
      return { ok: false, error: "Code sent, but the Box could not arm for card writing. Try Send again." };
    }
  }

  async disconnect() {
    this._detachJson();
    await this.adapter.disconnect();
  }

  _requireJson() {
    if (!this.json) throw new Error("not connected — call connect() first");
    return this.json;
  }

  arm() {
    return this._requireJson().arm();
  }

  disarm() {
    return this._requireJson().disarm();
  }

  copySerialLog() {
    return toText();
  }
}

export function createDeviceLink() {
  return new BboxDeviceLink();
}
