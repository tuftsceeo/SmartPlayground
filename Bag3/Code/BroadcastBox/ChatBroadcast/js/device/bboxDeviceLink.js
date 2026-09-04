/**
 * bboxDeviceLink.js — Broadcast Box serial lifecycle (adapted from deviceLink.js).
 * Connect resolves on port open. Liveness comes from any typed message --
 * in practice `heartbeat`, which the Box sends unconditionally every 5s.
 * `identity` is a question about what the device is, never the gate for
 * considering the link up: it is volunteered only once per boot, so a host
 * that attaches later never sees it.
 */

import { SerialAdapter } from "./serialAdapter.js";
import { ReplController } from "./replController.js";
import { BboxLink } from "./bboxLink.js";
import { installBoxFirmware, pushPayload } from "./boxFirmwareInstaller.js";
import { logInfo, logWarn, toText } from "./serialLog.js";

const FORWARDED_EVENTS = [
  "identity", "heartbeat", "fatal", "bye", "error", "repl",
  "armed", "card_present", "card_written", "info", "mode",
  "games", "stats", "ok", "booting",
];

/** Must exceed GRACE_S (~1s) + NFC init; plan §3.1. Kept for callers that
 *  want a single long-deadline probe (restartFirmware's waitForRunning). */
export const VALIDATE_LIMIT_MS = 8000;

/** Per-nudge deadline. Short on purpose: the retry loop re-asks every
 *  IDENTIFY_NUDGE_MS, so a single unanswered probe should give up quickly
 *  rather than overlapping the next one. */
const NUDGE_TIMEOUT_MS = 2000;

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
    this.adapter.onClose = (reason) => {
      logWarn(`adapter onClose: ${reason}`);
      this.running = false;
      this._emit("close", { reason });
    };
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
    if (obj?.type === "identity") {
      if (obj.device && obj.device !== EXPECTED_DEVICE) {
        this.wrongDevice = true;
        this.running = false;
        logWarn(`wrong device on identity: ${obj.device} (expected ${EXPECTED_DEVICE})`);
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
        if (type !== "booting") this._markRunning(obj);
        this._emit(type, obj);
      });
    }
    // waitForRunning() listens for this on `this`, not on `json` -- without
    // forwarding it here, restartFirmware() always times out to "unknown"
    // even when identity/heartbeat arrive fine right after, because nothing
    // ever emits "*" on the BboxDeviceLink instance itself.
    json.on("*", (obj) => {
      this._markRunning(obj);
      this._emit("*", obj);
    });
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
    this._attachJson();
    // Fire the first identify without awaiting it. The reply arrives as an
    // ordinary `identity` event either way, so awaiting bought nothing and cost
    // the caller the full timeout sitting in "connecting…" before the UI
    // could even show "waking up the Box". Retries are the host's job now
    // (App._armIdentifyNudge), because one probe can cross a busy moment on the
    // Box and nothing would ever ask again.
    this.nudgeIdentify().catch(() => {});
    logInfo("=== connect() returned (port open; awaiting device messages) ===");
  }

  /**
   * Ask the Box to identify itself. Never throws — a timeout here is normal
   * (the Box may still be booting, or mid-serve with its main loop blocked),
   * and the caller decides when silence has gone on too long.
   * @returns {Promise<boolean>} true if the Box replied
   */
  async nudgeIdentify({ timeoutMs = NUDGE_TIMEOUT_MS } = {}) {
    if (!this.json) return false;
    try {
      await this.json.identify({ timeoutMs });
      return true;
    } catch (e) {
      logWarn(`identify nudge: ${e.message}`);
      return false;
    }
  }

  async probe() {
    logInfo("=== probe: begin (read-only) ===");
    await this.adapter.logSignals("probe start");
    await this.adapter.write("\r\n");
    await sleep(500);
    // '\r\n', not bare '\n' -- see bboxLink.js send() for why a lone '\n'
    // never submits at the raw REPL and used to hang this probe forever.
    await this.adapter.write('{"cmd":"identify","id":9001}\r\n');
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
    const s = text.endsWith("\n") ? text : text + "\r\n";
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

  /**
   * @param {string} code
   * @param {{ destPath?: string, destLabel?: string }} [meta]
   */
  async sendGame(code, meta = {}, onProgress) {
    this._detachJson();
    let pushResult;
    try {
      pushResult = await pushPayload(this.repl, this.adapter, code, onProgress, meta);
    } finally {
      this._attachJson();
    }
    return pushResult;
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

  sendCmd(cmd, opts) {
    return this._requireJson().send(cmd, opts);
  }

  copySerialLog() {
    return toText();
  }
}

export function createDeviceLink() {
  return new BboxDeviceLink();
}
