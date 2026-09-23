/**
 * wandDeviceLink.js — direct-USB wand lifecycle, sibling to bboxDeviceLink.js.
 *
 * The wand's JSON telemetry (MockWand/main.py's `_emit()`) is output-only:
 * there is no command listener on the device, because polling stdin would
 * add work to a timing-sensitive NFC/LED loop. So unlike BboxDeviceLink,
 * this link never sends `{"cmd":...}` and never nudges for identity --
 * `identity` is volunteered once at boot (missed if the host attaches
 * later), and `heartbeat` (idle loop only, ~5s) is what actually proves
 * the link is alive. A running game blocks the wand's loop for its whole
 * duration, same as the Box's SERVE mode blocks its main loop -- see
 * app.js's game_start/game_end handlers.
 */

import { SerialAdapter } from "./serialAdapter.js";
import { ReplController } from "./replController.js";
import { BboxLink } from "./bboxLink.js"; // generic NDJSON line reader -- not Box-specific despite the name
import { installGameOnWand } from "./wandGameInstaller.js";
import { logInfo, logWarn, toText } from "./serialLog.js";

const FORWARDED_EVENTS = ["identity", "heartbeat", "game_start", "game_end", "error", "repl", "booting"];

const EXPECTED_DEVICE = "wand";

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

export class WandDeviceLink {
  kind = "wand";

  constructor() {
    this.adapter = new SerialAdapter();
    this.repl = new ReplController(this.adapter);
    this.json = null;
    this.running = false;
    this.atRepl = false;
    this.wrongDevice = false;
    this.deviceInfo = null;
    this._listeners = new Map();
    this.adapter.onClose = (reason) => {
      logWarn(`wand adapter onClose: ${reason}`);
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
    json.on("*", (obj) => {
      this._markRunning(obj);
      this._emit("*", obj);
    });
    json.on("repl", (info) => {
      this.running = false;
      this.atRepl = true;
      this._emit("repl", info);
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
    logInfo("=== wand connect() begin ===");
    this.atRepl = false;
    this.wrongDevice = false;
    await this.adapter.connect();
    this._attachJson();
    logInfo("=== wand connect() returned (port open; awaiting identity/heartbeat) ===");
  }

  /**
   * Ctrl-C then Ctrl-D over the raw adapter -- ordinary MicroPython REPL
   * recovery, nothing Box-specific about it (same bytes as
   * BboxDeviceLink.restartFirmware(), which is why router.js's "stuck"/
   * "no-answer" restart button works unmodified for a wand too).
   */
  async restartFirmware({ timeoutMs = 12000 } = {}) {
    logInfo("=== wand restartFirmware: Ctrl-C then Ctrl-D ===");
    if (!this.json) this._attachJson();
    await this.adapter.write("\x03");
    await sleep(200);
    await this.adapter.write("\x04");
    const state = await this.waitForRunning(timeoutMs);
    logInfo(state === "running" ? "wand restartFirmware: firmware is up" : `wand restartFirmware: ${state}`);
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

  /**
   * Push a game file to /games/<slug>.py and, unless suppressed, queue it
   * to auto-launch on the wand's next boot.
   * @param {string} code
   * @param {{ slug?: string, destLabel?: string, autoLaunch?: boolean }} [meta]
   */
  async sendGame(code, meta = {}, onProgress) {
    this._detachJson();
    let result;
    try {
      result = await installGameOnWand(this.repl, this.adapter, code, onProgress, meta);
    } finally {
      this._attachJson();
    }
    return result;
  }

  async disconnect() {
    this._detachJson();
    await this.adapter.disconnect();
  }

  copySerialLog() {
    return toText();
  }
}

export function createWandDeviceLink() {
  return new WandDeviceLink();
}
