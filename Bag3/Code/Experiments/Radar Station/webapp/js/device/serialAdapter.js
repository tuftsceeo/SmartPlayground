/**
 * serialAdapter.js -- Web Serial wrapper: port lifecycle, continuous
 * read loop, raw write. No readUntil/waiters, no chunked-write pacing.
 * radarLink.js owns the NDJSON protocol on top of this.
 */

import { logTx, logRx, logInfo, logWarn, logError } from "./serialLog.js";

export class SerialAdapter {
  constructor() {
    this.port = null;
    this.reader = null;
    this.writer = null;
    this.onData = null; // (chunk:string) => void, called for every decoded chunk
    this.readLoopActive = false;
    this._rxBytes = 0;
    this._txBytes = 0;
    this._wireGlobalDisconnect();
  }

  _wireGlobalDisconnect() {
    if (!("serial" in navigator) || SerialAdapter._globalWired) return;
    SerialAdapter._globalWired = true;
    navigator.serial.addEventListener("connect", (e) => {
      logInfo("navigator.serial 'connect' event", describePort(e.target));
    });
    navigator.serial.addEventListener("disconnect", (e) => {
      logWarn("navigator.serial 'disconnect' event -- device went away", describePort(e.target));
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

    const baudRate = opts.baudRate ?? 115200; // ignored by native USB-CDC in practice
    await port.open({ baudRate });
    logInfo(`port.open({ baudRate: ${baudRate} }) OK`, {
      readable: !!port.readable,
      writable: !!port.writable,
    });

    this.port = port;
    this.reader = port.readable.getReader();
    this.writer = port.writable.getWriter();
    this._rxBytes = 0;
    this._txBytes = 0;
    this._startReadLoop();
  }

  async disconnect() {
    logInfo("disconnect() requested");
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
    logInfo(`disconnected (session totals: tx ${this._txBytes}B, rx ${this._rxBytes}B)`);
  }

  /** Raw write -- string or Uint8Array, no framing, no pacing (commands are tiny). */
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

  async writeLine(text) {
    await this.write(text.endsWith("\n") ? text : text + "\n");
  }

  _startReadLoop() {
    this.readLoopActive = true;
    const decoder = new TextDecoder();
    logInfo("read loop starting");
    (async () => {
      try {
        while (this.readLoopActive) {
          const { value, done } = await this.reader.read();
          if (done) {
            logWarn("read loop: stream reported done (port closed by the other side)");
            break;
          }
          if (!value) continue;
          this._rxBytes += value.length;
          const chunk = decoder.decode(value, { stream: true });
          logRx(chunk, { bytes: value.length });
          this.onData?.(chunk);
        }
        logInfo("read loop exited cleanly");
      } catch (e) {
        if (this.readLoopActive) {
          logError(`read loop error: ${e.name}: ${e.message}`);
          console.error("serialAdapter: read loop error", e);
        } else {
          logInfo(`read loop cancelled: ${e.name}`);
        }
      }
    })();
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
