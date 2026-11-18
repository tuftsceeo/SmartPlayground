/**
 * deviceLink.js -- THE SEAM (see plan §Device layer). Everything above
 * this module (deviceBar.js, main.js) talks only to a DeviceLink
 * instance; it owns the serial connection lifecycle and forwards to
 * NdjsonLink once the device is heard from.
 *
 * CONNECTION MODEL -- mirrors Live_Page/WebApp2's proven pattern
 * (mpy/hub_serial.py's connect() + main.py's on_serial_data "ready"
 * handler) rather than a synchronous request/reply probe:
 *
 *   connect() opens the port and starts listening, and returns as soon as
 *   the PORT is open -- it does NOT wait for a reply from the device.
 *   Whether the firmware is running is reported later, asynchronously,
 *   via the 'hello' event, whenever icon_server.py's one-shot boot
 *   announcement (or a reply to the best-effort probe below) actually
 *   arrives.
 *
 * This matters because opening a Web Serial port to this board appears to
 * reset it (observed empirically: a read-loop "device has been lost"
 * error immediately after connect, with the OS-level port re-appearing at
 * the same path moments later -- a USB CDC re-enumeration, i.e. a reboot).
 * A synchronous "wait up to 1.5s for a reply, else declare needs-install"
 * probe races that reboot and was losing the race essentially every time.
 * WebApp2 sidesteps this entirely by never blocking on the handshake --
 * the UI just shows "connected" and flips to "running" whenever the
 * unsolicited boot hello shows up, however long that takes.
 *
 * NdjsonLink is DETACHED before any raw-REPL work (installFirmware) and
 * re-attached after: NdjsonLink._onData() calls adapter.clearBacklog() on
 * every chunk, which would wipe the shared backlog replController.js's
 * readUntil() depends on for cross-chunk pattern matching -- the two
 * consumers can't safely run against the same adapter at once.
 */

import { SerialAdapter } from "./serialAdapter.js";
import { ReplController } from "./replController.js";
import { NdjsonLink } from "./ndjsonLink.js";
import { installFirmware } from "./firmwareInstaller.js";
import { logInfo, logWarn } from "./serialLog.js";

const FORWARDED_EVENTS = ["hello", "heartbeat", "fatal", "bye", "error", "repl"];

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

export class DeviceLink {
  constructor() {
    this.adapter = new SerialAdapter();
    this.repl = new ReplController(this.adapter);
    this.json = null; // NdjsonLink, attached whenever we're not mid-REPL-install
    this.capabilities = { liveFrames: false, fileOps: false };
    this.running = false; // flips true on the FIRST 'hello' seen since connect()
    this.atRepl = false; // board is parked at '>>>' -- firmware not running
    this._autoRecoverArmed = false; // one-shot REPL auto-recovery per connect()
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

  _attachJson() {
    const json = new NdjsonLink(this.adapter);
    json.start();
    this.json = json;
    this.capabilities = { ...json.capabilities };
    for (const type of FORWARDED_EVENTS) json.on(type, (obj) => this._emit(type, obj));
    json.on("hello", () => {
      this.running = true;
      this.atRepl = false;
    });
    json.on("bye", () => {
      this.running = false;
    });
    json.on("repl", (info) => {
      this.running = false;
      this.atRepl = true;
      // One-shot: recover automatically the first time we notice the board
      // is parked at the prompt, but never loop -- if the restart doesn't
      // take, the UI offers a manual button rather than hammering Ctrl-D.
      if (this._autoRecoverArmed) {
        this._autoRecoverArmed = false;
        logWarn(`REPL detected (${info?.reason}) -- attempting one automatic firmware restart`);
        this.restartFirmware().catch((e) => logWarn(`auto-restart failed: ${e.message}`));
      } else {
        logWarn(`REPL detected (${info?.reason}) -- not auto-restarting again; use Restart firmware`);
      }
    });
    return json;
  }

  _detachJson() {
    this.json?.stop();
    this.json = null;
    this.running = false;
    this.atRepl = false;
    this.capabilities = { liveFrames: false, fileOps: false };
  }

  /**
   * Open the port and start listening. Resolves as soon as the port is
   * open -- does NOT wait for the device to say anything. Subscribe to
   * 'hello' to know when icon_server.py is confirmed running.
   */
  async connect() {
    logInfo("=== connect() begin ===");
    this._autoRecoverArmed = true; // arm one-shot REPL recovery for this session
    this.atRepl = false;
    await this.adapter.connect();
    const json = this._attachJson();

    // Best-effort proactive probe, in case the device did NOT reset on
    // connect and is already idling (so it won't otherwise say anything
    // unprompted). Fire-and-forget: a timeout here must never affect
    // connect()'s own resolution, and the reply -- if it comes -- arrives
    // through the same 'hello' listener above either way, since it's the
    // exact same {"type":"hello"} shape as the boot announcement.
    logInfo("sending proactive hello probe (fire-and-forget)");
    json.hello({ timeoutMs: 4000 }).catch((e) => logWarn(`hello probe: ${e.message}`));
    logInfo("=== connect() returned (port open; awaiting device hello) ===");
  }

  /**
   * NON-DESTRUCTIVE diagnostics for the Serial Monitor's "Probe" button.
   *
   * An earlier version of this sent Ctrl-C to "interrupt any running
   * program" -- which KILLED the running firmware and dropped the board to
   * the REPL, turning a working link into a broken one. Never interrupt
   * from a diagnostic: probing must be safe to click at any time. Use
   * restartFirmware() when you actually intend to restart.
   */
  async probe() {
    logInfo("=== probe: begin (read-only, will not interrupt the firmware) ===");
    await this.adapter.logSignals("probe start");

    logInfo("probe 1/2: bare newline (does anything respond at all?)");
    await this.adapter.write("\r\n");
    await sleep(500);

    logInfo("probe 2/2: hello line");
    await this.adapter.write('{"cmd":"hello","id":9001}\n');
    await sleep(1200);

    logInfo(
      "=== probe: end. A 'hello' reply = firmware running. " +
        "An echo of our own command, or '>>>' = board is at the REPL (use Restart firmware). " +
        "No RX at all = nothing is reaching us. ==="
    );
  }

  /**
   * Get from "sitting at the MicroPython REPL" back to "running
   * icon_server.py", without reinstalling anything.
   *
   * Ctrl-C first only to clear any half-typed line in the REPL's input
   * buffer (harmless when already AT the prompt), then Ctrl-D, which is a
   * soft reset -- it re-runs boot.py and main.py, so the firmware starts
   * and announces itself with its usual hello.
   */
  async restartFirmware({ timeoutMs = 12000 } = {}) {
    logInfo("=== restartFirmware: Ctrl-C (clear REPL line) then Ctrl-D (soft reset) ===");
    this._autoRecoverArmed = false; // an explicit restart supersedes auto-recovery
    if (!this.json) this._attachJson(); // waitForHello listens on parsed events
    await this.adapter.write("\x03");
    await sleep(200);
    await this.adapter.write("\x04");
    const ok = await this.waitForHello(timeoutMs);
    logInfo(ok ? "restartFirmware: hello received -- firmware is up" : "restartFirmware: no hello before timeout");
    return ok;
  }

  /** Resolve true on the next 'hello', false on timeout. */
  waitForHello(timeoutMs = 10000) {
    return new Promise((resolve) => {
      let done = false;
      const off = this.on("hello", () => {
        if (done) return;
        done = true;
        off();
        resolve(true);
      });
      setTimeout(() => {
        if (done) return;
        done = true;
        off();
        resolve(false);
      }, timeoutMs);
    });
  }

  /** Send an arbitrary raw string from the monitor's input box. */
  async sendRaw(text) {
    const s = text.endsWith("\n") ? text : text + "\n";
    await this.adapter.write(s);
  }

  /** Explicit, user-triggered action -- never auto-invoked from connect(). */
  async installFirmware(onProgress) {
    this._detachJson(); // see module docstring -- must not race readUntil()
    try {
      await installFirmware(this.repl, this.adapter, onProgress); // enters REPL itself
      return true;
    } finally {
      // ALWAYS re-attach, including on failure. Leaving the JSON link
      // detached makes the app permanently deaf: bytes still arrive, but
      // nothing parses them into events, so even a later successful restart
      // looks like silence. That is what turned one install timeout into
      // "no hello" on every subsequent attempt.
      this._attachJson();
    }
  }

  async disconnect() {
    this._detachJson();
    await this.adapter.disconnect();
  }

  // ── forwarded API (throws if the port isn't open) ──────────────────
  _requireJson() {
    if (!this.json) throw new Error("not connected -- call connect() first");
    return this.json;
  }

  sendFrame(frame, opts) {
    return this._requireJson().sendFrame(frame, opts);
  }
  setIntensity(value, opts) {
    return this._requireJson().setIntensity(value, opts);
  }
  clear() {
    return this._requireJson().clear();
  }
  listIcons() {
    return this._requireJson().listIcons();
  }
  showIcon(name) {
    return this._requireJson().showIcon(name);
  }
  saveIcon(name, frame, opts) {
    return this._requireJson().saveIcon(name, frame, opts);
  }
  deleteIcon(name) {
    return this._requireJson().deleteIcon(name);
  }
  setCycle(on, opts) {
    return this._requireJson().setCycle(on, opts);
  }
}
