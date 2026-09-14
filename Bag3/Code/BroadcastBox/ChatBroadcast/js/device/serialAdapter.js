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
    this.waiters = []; // [{pattern, resolve}] -- readUntil() callers
    // DIAGNOSTIC (temporary -- hang hypothesis test, see chat): tag each
    // waiters array with an id so readUntil()'s timeout callback can log
    // whether it's still looking at the array its waiter was pushed into.
    this._waiterArraySeq = 0;
    this._waiterSeq = 0;
    this.waiters._arrId = ++this._waiterArraySeq;
    this.onData = null; // optional: (chunk:string) => void, called for every decoded chunk
    this.onClose = null; // optional: (reason:string) => void, fired once when the read loop dies
    this.readLoopActive = false;
    this._readLoopPromise = null;
    this._rxBytes = 0;
    this._txBytes = 0;
    this._closeFired = false;
    this._wireGlobalDisconnect();
  }

  /** A device yanked (or reset hard enough to re-enumerate) surfaces here. */
  _wireGlobalDisconnect() {
    if (!("serial" in navigator) || SerialAdapter._globalWired) return;
    SerialAdapter._globalWired = true;
    // DIAGNOSTIC (temporary): count + timestamp each dispatch to check
    // whether one physical unplug fires this listener once or many times,
    // and whether repeats share the same port identity.
    let connectSeq = 0;
    let disconnectSeq = 0;
    navigator.serial.addEventListener("connect", (e) => {
      connectSeq += 1;
      logInfo(`navigator.serial 'connect' event [#${connectSeq} @ ${Date.now()}]`, describePort(e.target));
    });
    navigator.serial.addEventListener("disconnect", (e) => {
      disconnectSeq += 1;
      logWarn(`navigator.serial 'disconnect' event -- device went away [#${disconnectSeq} @ ${Date.now()}]`, describePort(e.target));
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

    await this.logSignals("after open");
    this._startReadLoop();
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
    // DIAGNOSTIC (temporary -- hang hypothesis test): log the outgoing
    // array's id/length before reassigning, and the new array's id after,
    // so a stuck readUntil() timeout can be matched against this moment.
    logWarn(`disconnect(): discarding waiters array #${this.waiters._arrId} (len=${this.waiters.length})`);
    this.waiters = [];
    this.waiters._arrId = ++this._waiterArraySeq;
    logWarn(`disconnect(): now on waiters array #${this.waiters._arrId}`);
    logInfo(`disconnected (session totals: tx ${this._txBytes}B, rx ${this._rxBytes}B)`);
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
    // NOTE: .filter() also reassigns this.waiters to a new array -- this is
    // the SAME hazard as disconnect()'s `this.waiters = []` (see chat: the
    // hang hypothesis test). It means any other still-pending waiter's
    // timeout closure now holds a stale array reference too, independent of
    // any disconnect. Not fixing here yet -- carrying the diagnostic tag
    // forward only, so this path doesn't produce false-positive mismatches
    // while testing the disconnect-specific hypothesis.
    const arrId = this.waiters._arrId;
    this.waiters = this.waiters.filter((w) => {
      const i = this.readBuf.indexOf(w.pattern);
      if (i < 0) return true;
      const consumed = this.readBuf.slice(0, i + w.pattern.length);
      this.readBuf = this.readBuf.slice(i + w.pattern.length);
      logInfo(`readUntil matched ${JSON.stringify(w.pattern)}`);
      w.resolve({ found: true, text: consumed });
      return false;
    });
    this.waiters._arrId = arrId;
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
      const waiter = { pattern, resolve };
      this.waiters.push(waiter);
      // DIAGNOSTIC (temporary -- hang hypothesis test): tag this waiter with
      // the id of the array it was actually pushed into, so the timeout
      // callback below can report whether disconnect() swapped that array
      // out from under it.
      const registeredArrId = this.waiters._arrId;
      const waiterId = ++this._waiterSeq;
      logInfo(`readUntil #${waiterId} waiting for ${JSON.stringify(pattern)} (${timeoutMs}ms) on waiters array #${registeredArrId}`);
      setTimeout(() => {
        const idx = this.waiters.indexOf(waiter);
        logInfo(`readUntil #${waiterId} timeout fired: checking waiters array #${this.waiters._arrId} (registered on #${registeredArrId}), idx=${idx}`);
        if (idx >= 0) {
          this.waiters.splice(idx, 1);
          logWarn(`readUntil #${waiterId} TIMEOUT after ${timeoutMs}ms waiting for ${JSON.stringify(pattern)}`);
          resolve({ found: false, text: "" });
        } else {
          logWarn(`readUntil #${waiterId} timeout fired but waiter is not in the CURRENT waiters array (#${this.waiters._arrId} != #${registeredArrId}) -- promise is ORPHANED, will never resolve`);
        }
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
