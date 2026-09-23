/**
 * serialAdapter.js -- thin Web Serial wrapper: port lifecycle, a
 * continuous read loop with pattern-waiters, and paced chunked writes.
 * Modeled on Live_Page/Flasher/js/serial.js's SerialEngine (its shared-
 * buffer-with-waiters design avoids the lock-acquire-per-read churn of
 * WebApp2's mpy/hub_serial.py) -- see the plan §Device layer.
 *
 * This module owns ONLY the browser API surface. It knows nothing about
 * MicroPython's REPL protocol or the icon JSON protocol -- those live in
 * replController.js and ndjsonLink.js, both built on top of this.
 *
 * Everything that crosses the wire is recorded via serialLog.js so a
 * connection failure can be diagnosed from the page's Serial Monitor
 * rather than by guessing.
 */

import { logTx, logRx, logInfo, logWarn, logError } from "./serialLog.js";

const SERIAL_CHUNK = 256; // bytes per paced write -- USB stdin ring buffer is small (~512B), see plan
const SERIAL_CHUNK_DELAY_MS = 10;

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

export class SerialAdapter {
  constructor() {
    this.port = null;
    this.reader = null;
    this.writer = null;
    this.readBuf = ""; // accumulated decoded text not yet claimed by a waiter
    this.waiters = []; // [{pattern, resolve, settled}] -- readUntil() callers
    this.onData = null; // optional: (chunk:string) => void, called for every decoded chunk
    this.onClose = null; // optional: (reason:string) => void, fired once when the read loop dies
    this.readLoopActive = false;
    this._readLoopPromise = null;
    this._rxBytes = 0;
    this._txBytes = 0;
    this._closeFired = false;
    this._lastPortInfo = null; // {usbVendorId, usbProductId} of the last port opened via connect() -- lets reopenLastPort() find it again in getPorts() without a new requestPort() prompt
    this._wireGlobalDisconnect();
  }

  /**
   * A device yanked (or reset hard enough to re-enumerate) surfaces here.
   * Confirmed on hardware (see chat) that one physical unplug can fire this
   * listener a dozen times in under 5ms, all reporting the identical port
   * (same usbVendorId/usbProductId) -- consistent with the browser dispatching
   * once per stale SerialPort object the page has accumulated across earlier
   * requestPort() calls this session, not per physical event. Logging is
   * de-duplicated by port identity within a short window so the log (and
   * anything reacting to it) isn't misled into thinking the device dropped
   * and came back a dozen times.
   */
  _wireGlobalDisconnect() {
    if (!("serial" in navigator) || SerialAdapter._globalWired) return;
    SerialAdapter._globalWired = true;
    const DEDUPE_MS = 250;
    let lastConnectKey = null, lastConnectAt = 0;
    let lastDisconnectKey = null, lastDisconnectAt = 0;
    navigator.serial.addEventListener("connect", (e) => {
      const info = describePort(e.target);
      const key = `${info.usbVendorId}:${info.usbProductId}`;
      const now = Date.now();
      if (key === lastConnectKey && now - lastConnectAt < DEDUPE_MS) return;
      lastConnectKey = key;
      lastConnectAt = now;
      logInfo("navigator.serial 'connect' event", info);
    });
    navigator.serial.addEventListener("disconnect", (e) => {
      const info = describePort(e.target);
      const key = `${info.usbVendorId}:${info.usbProductId}`;
      const now = Date.now();
      if (key === lastDisconnectKey && now - lastDisconnectAt < DEDUPE_MS) return;
      lastDisconnectKey = key;
      lastDisconnectAt = now;
      logWarn("navigator.serial 'disconnect' event -- device went away", info);
    });
  }

  isConnected() {
    return this.port !== null && this.port.readable !== null;
  }

  async connect(opts = {}) {
    if (!("serial" in navigator)) {
      throw new Error("Web Serial isn't available in this browser (Chrome/Edge only).");
    }

    const granted = await navigator.serial.getPorts();
    logInfo(`requestPort() -- ${granted.length} port(s) already granted to this origin`);

    const port = await navigator.serial.requestPort(); // no filters -- user picks any port
    logInfo("port selected", describePort(port));

    const baudRate = opts.baudRate ?? 115200;
    await port.open({ baudRate });
    logInfo(`port.open({ baudRate: ${baudRate} }) OK`, {
      readable: !!port.readable,
      writable: !!port.writable,
    });

    this.port = port;
    this.reader = port.readable.getReader();
    this.writer = port.writable.getWriter();
    this.readBuf = "";
    this._rxBytes = 0;
    this._txBytes = 0;
    this._lastPortInfo = describePort(port);

    await this.logSignals("after open");
    this._startReadLoop();
  }

  /**
   * Reopen the same physical port after an unplanned drop (e.g. the
   * device's own soft-reset re-enumerating its native USB), without
   * prompting the user again. requestPort() always shows a picker and
   * needs a user gesture; getPorts() returns ports this origin was
   * already granted, and opening one of those needs neither. Works
   * identically for the Box and the Dial -- this only cares about the
   * previously-seen USB vendor/product id, not what device it is.
   * Resolves false (never throws) on anything short of success: no
   * matching granted port, or that port refusing to open (already open
   * elsewhere, or genuinely gone) -- the caller's timeout/retry logic is
   * what decides how long to keep hoping.
   */
  async reopenLastPort(opts = {}) {
    if (!("serial" in navigator) || !this._lastPortInfo) return false;
    let granted;
    try {
      granted = await navigator.serial.getPorts();
    } catch (e) {
      logWarn(`reopenLastPort: getPorts() failed: ${e.message}`);
      return false;
    }
    const match = granted.find((p) => {
      const info = describePort(p);
      return info.usbVendorId === this._lastPortInfo.usbVendorId
        && info.usbProductId === this._lastPortInfo.usbProductId;
    });
    if (!match) {
      logInfo("reopenLastPort: no previously granted port matches", this._lastPortInfo);
      return false;
    }
    try {
      const baudRate = opts.baudRate ?? 115200;
      await match.open({ baudRate });
    } catch (e) {
      logWarn(`reopenLastPort: open() failed: ${e.message}`);
      return false;
    }
    logInfo("reopenLastPort: reopened without prompting", describePort(match));
    this.port = match;
    this.reader = match.readable.getReader();
    this.writer = match.writable.getWriter();
    this.readBuf = "";
    this._rxBytes = 0;
    this._txBytes = 0;
    await this.logSignals("after reopen");
    this._startReadLoop();
    return true;
  }

  /**
   * Control-signal state. Worth logging explicitly: this board is a native
   * "USB JTAG_serial debug unit", where DTR/RTS are wired to reset/boot
   * strapping, so a signal transition can reboot the chip mid-session.
   */
  async logSignals(when) {
    if (!this.port?.getSignals) {
      logInfo(`signals (${when}): getSignals() unsupported`);
      return null;
    }
    try {
      const s = await this.port.getSignals();
      logInfo(`signals (${when})`, s);
      return s;
    } catch (e) {
      logWarn(`signals (${when}) read failed: ${e.message}`);
      return null;
    }
  }

  /** Explicit DTR/RTS control, so the effect on this board is observable. */
  async setSignals(signals) {
    if (!this.port?.setSignals) {
      logWarn("setSignals() unsupported on this port");
      return;
    }
    try {
      await this.port.setSignals(signals);
      logInfo("setSignals()", signals);
      await this.logSignals("after setSignals");
    } catch (e) {
      logError(`setSignals() failed: ${e.message}`, signals);
    }
  }

  async disconnect() {
    logInfo("disconnect() requested");
    // Mark intentional so the read-loop exit does not fire onClose.
    this._closeFired = true;
    this.readLoopActive = false;
    try {
      await this.reader?.cancel();
    } catch {
      /* already gone */
    }
    try {
      this.reader?.releaseLock();
    } catch {
      /* already released */
    }
    try {
      this.writer?.releaseLock();
    } catch {
      /* already released */
    }
    try {
      await this.port?.close();
    } catch (e) {
      logWarn(`port.close() threw: ${e.message}`);
    }
    this.port = null;
    this.reader = null;
    this.writer = null;
    this.readBuf = "";
    this._releaseWaiters("port disconnected");
    logInfo(`disconnected (session totals: tx ${this._txBytes}B, rx ${this._rxBytes}B)`);
  }

  /**
   * Resolve every still-pending readUntil() immediately with found:false,
   * rather than leaving them for their own setTimeout.
   *
   * Confirmed on hardware (see chat: send-overlay hang investigation) that
   * simply reassigning `this.waiters = []` here orphaned any waiter already
   * in flight: its setTimeout closure captured the OLD array, so its later
   * `indexOf` lookup against the NEW array always returned -1 and the
   * `if (idx >= 0)` guard silently skipped calling resolve() -- the promise
   * never settled, which is what kept confirmSend()'s send-confirm-overlay
   * stuck on "Sending..." forever. Each waiter now carries its own
   * `settled` flag instead of relying on array identity, so it resolves
   * exactly once regardless of which array object holds it.
   */
  _releaseWaiters(reason) {
    const pending = this.waiters;
    this.waiters = [];
    for (const w of pending) {
      if (w.settled) continue;
      w.settled = true;
      logWarn(`readUntil for ${JSON.stringify(w.pattern)} released early: ${reason}`);
      w.resolve({ found: false, text: "", closed: true });
    }
  }

  /** Raw write -- string or Uint8Array, no framing. */
  async write(data) {
    const bytes = typeof data === "string" ? new TextEncoder().encode(data) : data;
    if (!this.writer) {
      logError(`write(${bytes.length}B) failed -- no writer (not connected)`);
      throw new Error("Not connected to serial port");
    }
    logTx(typeof data === "string" ? data : `<${bytes.length} binary bytes>`, { bytes: bytes.length });
    await this.writer.write(bytes);
    this._txBytes += bytes.length;
  }

  /** Paced write in SERIAL_CHUNK-byte pieces -- see module docstring. */
  async writeChunked(data, chunkSize = SERIAL_CHUNK, delayMs = SERIAL_CHUNK_DELAY_MS) {
    const bytes = typeof data === "string" ? new TextEncoder().encode(data) : data;
    if (!this.writer) {
      logError(`writeChunked(${bytes.length}B) failed -- no writer (not connected)`);
      throw new Error("Not connected to serial port");
    }
    const nChunks = Math.ceil(bytes.length / chunkSize);
    logTx(typeof data === "string" ? data : `<${bytes.length} binary bytes>`, {
      bytes: bytes.length,
      chunks: nChunks,
      chunkSize,
    });
    for (let i = 0; i < bytes.length; i += chunkSize) {
      await this.writer.write(bytes.subarray(i, i + chunkSize));
      if (i + chunkSize < bytes.length) await sleep(delayMs);
    }
    this._txBytes += bytes.length;
  }

  /** Write one JSON command as a line (used by ndjsonLink). */
  async writeLine(text) {
    await this.write(text.endsWith("\n") ? text : text + "\n");
  }

  /** Null the port and fire onClose once. Called from both read-loop exits. */
  _fireClose(reason) {
    if (this._closeFired) return;
    this._closeFired = true;
    this.readLoopActive = false;
    this.port = null;
    this.reader = null;
    this.writer = null;
    logWarn(`serial close: ${reason}`);
    // Release BEFORE onClose: app.js's close handler calls disconnect() as
    // part of handling this event, and by then any in-flight readUntil()
    // (e.g. the one confirmSend() is awaiting deep inside pushPayload())
    // should already be unblocked -- not still waiting on disconnect() to
    // get around to it, and not left for its own now-irrelevant timeout.
    this._releaseWaiters(`adapter closed: ${reason}`);
    try {
      this.onClose?.(reason);
    } catch (e) {
      logError(`onClose callback threw: ${e.message}`);
    }
  }

  _startReadLoop() {
    this.readLoopActive = true;
    this._closeFired = false;
    const decoder = new TextDecoder();
    logInfo("read loop starting");
    this._readLoopPromise = (async () => {
      let closeReason = null;
      try {
        while (this.readLoopActive) {
          const { value, done } = await this.reader.read();
          if (done) {
            logWarn("read loop: stream reported done (port closed by the other side)");
            closeReason = "stream done";
            break;
          }
          if (!value) continue;
          this._rxBytes += value.length;
          const chunk = decoder.decode(value, { stream: true });
          logRx(chunk, { bytes: value.length });
          this.readBuf += chunk;
          this._resolveWaiters();
          this.onData?.(chunk);
        }
        if (!closeReason && this.readLoopActive) {
          closeReason = "read loop exited";
        }
        logInfo("read loop exited cleanly");
      } catch (e) {
        // The single most diagnostic line in the whole app: a device that
        // resets or is unplugged lands here as "The device has been lost".
        if (this.readLoopActive) {
          logError(`read loop error: ${e.name}: ${e.message}`);
          console.error("serialAdapter: read loop error", e);
          closeReason = `${e.name}: ${e.message}`;
        } else {
          logInfo(`read loop cancelled: ${e.name}`);
        }
      }
      // Intentional disconnect() sets readLoopActive=false before cancel —
      // do not fire onClose for that path (caller already knows).
      if (closeReason) this._fireClose(closeReason);
    })();
  }

  _resolveWaiters() {
    if (!this.waiters.length) return;
    this.waiters = this.waiters.filter((w) => {
      const i = this.readBuf.indexOf(w.pattern);
      if (i < 0) return true;
      const consumed = this.readBuf.slice(0, i + w.pattern.length);
      this.readBuf = this.readBuf.slice(i + w.pattern.length);
      logInfo(`readUntil matched ${JSON.stringify(w.pattern)}`);
      w.settled = true;
      w.resolve({ found: true, text: consumed });
      return false;
    });
  }

  /** Wait until `pattern` appears in the incoming stream, or timeoutMs elapses. */
  readUntil(pattern, timeoutMs = 5000) {
    return new Promise((resolve) => {
      // check backlog first
      const i = this.readBuf.indexOf(pattern);
      if (i >= 0) {
        const consumed = this.readBuf.slice(0, i + pattern.length);
        this.readBuf = this.readBuf.slice(i + pattern.length);
        logInfo(`readUntil ${JSON.stringify(pattern)} satisfied from backlog`);
        resolve({ found: true, text: consumed });
        return;
      }
      // `settled` (not array membership) is the single source of truth for
      // whether this waiter still needs resolving -- a match, a disconnect,
      // and this timeout can all race to be the one that settles it, and
      // exactly one must win regardless of which `this.waiters` array
      // object is live at that moment (see _releaseWaiters()).
      const waiter = { pattern, resolve, settled: false };
      this.waiters.push(waiter);
      logInfo(`readUntil waiting for ${JSON.stringify(pattern)} (${timeoutMs}ms)`);
      setTimeout(() => {
        if (waiter.settled) return;
        waiter.settled = true;
        const idx = this.waiters.indexOf(waiter);
        if (idx >= 0) this.waiters.splice(idx, 1);
        logWarn(`readUntil TIMEOUT after ${timeoutMs}ms waiting for ${JSON.stringify(pattern)}`);
        resolve({ found: false, text: "" });
      }, timeoutMs);
    });
  }

  /** Drop any buffered/backlog text (used when switching protocol modes). */
  clearBacklog() {
    this.readBuf = "";
  }
}

function describePort(port) {
  try {
    const info = port?.getInfo?.() ?? {};
    return {
      usbVendorId: info.usbVendorId ?? null,
      usbProductId: info.usbProductId ?? null,
    };
  } catch {
    return {};
  }
}
