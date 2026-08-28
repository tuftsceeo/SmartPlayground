/**
 * serialMonitor.js -- a live view of everything on the serial channel.
 *
 * Deliberately built as a PERSISTENT, imperatively-updated element
 * appended to <body>, not a component rebuilt by the store's render pass:
 * a log that loses its scroll position (or rebuilds thousands of rows) on
 * every state change is useless for debugging. Same reasoning as the
 * persistent canvases -- see plan §App architecture.
 */

import { subscribe, getEntries, clear, toText, setPaused, isPaused, DIR } from "../device/serialLog.js";

const COLORS = {
  [DIR.TX]: "text-sky-400",
  [DIR.RX]: "text-emerald-400",
  [DIR.OUT]: "text-sky-300 font-semibold",
  [DIR.IN]: "text-emerald-300 font-semibold",
  [DIR.DROP]: "text-neutral-500",
  [DIR.INFO]: "text-neutral-400",
  [DIR.WARN]: "text-amber-400",
  [DIR.ERROR]: "text-red-400",
};

const LABELS = {
  [DIR.TX]: "TX",
  [DIR.RX]: "RX",
  [DIR.OUT]: "→",
  [DIR.IN]: "←",
  [DIR.DROP]: "drop",
  [DIR.INFO]: "info",
  [DIR.WARN]: "warn",
  [DIR.ERROR]: "ERR",
};

export class SerialMonitor {
  constructor({ onProbe, onSendRaw, onRestart, onConnect, onDisconnect } = {}) {
    this.onProbe = onProbe;
    this.onSendRaw = onSendRaw;
    this.onRestart = onRestart;
    this.onConnect = onConnect;
    this.onDisconnect = onDisconnect;
    this._connected = false;
    this.open = false;
    this.autoscroll = true;
    this.showRaw = true; // include byte-level TX/RX, not just parsed JSON
    this.t0 = null;
    this._build();
    subscribe((entry) => this._onEntry(entry));
  }

  _build() {
    const root = document.createElement("div");
    root.className = "fixed bottom-0 left-0 right-0 z-40 flex flex-col";
    root.innerHTML = `
      <div class="flex items-center gap-2 px-3 py-1.5 bg-neutral-900 border-t border-neutral-700 text-xs">
        <button id="smToggle" class="px-2 py-0.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200">
          Serial Monitor
        </button>
        <span id="smCount" class="text-neutral-500">0</span>
        <span id="smLast" class="text-neutral-600 truncate flex-1"></span>
        <label class="flex items-center gap-1 text-neutral-500">
          <input type="checkbox" id="smRaw" checked /> raw bytes
        </label>
        <label class="flex items-center gap-1 text-neutral-500">
          <input type="checkbox" id="smAuto" checked /> autoscroll
        </label>
        <button id="smPause" class="px-2 py-0.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300">Pause</button>
        <button id="smConn" class="px-2 py-0.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200" title="Connect / disconnect the serial port">Connect</button>
        <button id="smProbe" class="px-2 py-0.5 rounded bg-indigo-900 hover:bg-indigo-800 text-indigo-200" title="Read-only: asks the device to identify itself. Will not interrupt the firmware.">Probe</button>
        <button id="smRestart" class="px-2 py-0.5 rounded bg-emerald-900 hover:bg-emerald-800 text-emerald-200" title="Ctrl-C then Ctrl-D: soft-reset the board so main.py runs again">Restart fw</button>
        <button id="smCopy" class="px-2 py-0.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300">Copy</button>
        <button id="smClear" class="px-2 py-0.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300">Clear</button>
      </div>
      <div id="smBody" class="hidden flex-col bg-neutral-950 border-t border-neutral-800">
        <div id="smLog" class="h-48 overflow-y-auto font-mono text-[11px] leading-relaxed px-3 py-2"></div>
        <div class="flex items-center gap-2 px-3 py-1.5 border-t border-neutral-800">
          <input id="smInput" placeholder='{"cmd":"hello"}   (Enter to send, newline appended)'
                 class="flex-1 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 font-mono text-[11px] text-neutral-200" />
          <button id="smSend" class="px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-xs">Send</button>
        </div>
      </div>
    `;
    document.body.appendChild(root);

    this.root = root;
    this.body = root.querySelector("#smBody");
    this.logEl = root.querySelector("#smLog");
    this.countEl = root.querySelector("#smCount");
    this.lastEl = root.querySelector("#smLast");
    this.input = root.querySelector("#smInput");

    root.querySelector("#smToggle").addEventListener("click", () => this.toggle());
    root.querySelector("#smRaw").addEventListener("change", (e) => {
      this.showRaw = e.target.checked;
      this._redraw();
    });
    root.querySelector("#smAuto").addEventListener("change", (e) => {
      this.autoscroll = e.target.checked;
    });
    const pauseBtn = root.querySelector("#smPause");
    pauseBtn.addEventListener("click", () => {
      setPaused(!isPaused());
      pauseBtn.textContent = isPaused() ? "Resume" : "Pause";
      pauseBtn.className = isPaused()
        ? "px-2 py-0.5 rounded bg-amber-900 hover:bg-amber-800 text-amber-200"
        : "px-2 py-0.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300";
    });
    root.querySelector("#smProbe").addEventListener("click", () => {
      if (!this.open) this.toggle();
      this.onProbe?.();
    });
    root.querySelector("#smCopy").addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(toText());
        this._flash(root.querySelector("#smCopy"), "Copied");
      } catch {
        // Clipboard can be blocked; fall back to a download so the log is
        // still retrievable for a bug report.
        const blob = new Blob([toText()], { type: "text/plain" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "serial-log.txt";
        a.click();
      }
    });
    root.querySelector("#smClear").addEventListener("click", () => clear());
    root.querySelector("#smSend").addEventListener("click", () => this._send());
    this.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") this._send();
    });

    root.querySelector("#smRestart").addEventListener("click", () => this.onRestart?.());
    this.connBtn = root.querySelector("#smConn");
    this.connBtn.addEventListener("click", () => {
      if (this._connected) this.onDisconnect?.();
      else this.onConnect?.();
    });

    // Reserve space so the monitor bar never covers the app's own content.
    this._reserveSpace();
    window.addEventListener("resize", () => this._reserveSpace());
  }

  /**
   * Reflect device state in the always-visible monitor bar. The device
   * panel lives at the bottom of a scrollable column and can be below the
   * fold, so these controls need to be reachable here too.
   */
  setDeviceState({ connected, running, atRepl }) {
    this._connected = connected;
    this.connBtn.textContent = connected ? "Disconnect" : "Connect";
    this.connBtn.className = connected
      ? "px-2 py-0.5 rounded bg-red-900 hover:bg-red-800 text-red-200"
      : "px-2 py-0.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200";
    const dot = running ? "🟢" : atRepl ? "🔴" : connected ? "🟡" : "⚪";
    this.connBtn.title = `${dot} ${
      !connected ? "port closed" : running ? "firmware running" : atRepl ? "at REPL prompt" : "port open, awaiting device"
    }`;
  }

  _send() {
    const text = this.input.value.trim();
    if (!text) return;
    this.onSendRaw?.(text);
    this.input.value = "";
  }

  _flash(btn, label) {
    const old = btn.textContent;
    btn.textContent = label;
    setTimeout(() => (btn.textContent = old), 1200);
  }

  toggle() {
    this.open = !this.open;
    this.body.classList.toggle("hidden", !this.open);
    this.body.classList.toggle("flex", this.open);
    if (this.open) this._redraw();
    this._reserveSpace();
  }

  /**
   * The monitor is position:fixed at the bottom, so without matching body
   * padding an open panel COVERS the app's own bottom content -- including
   * the device panel with the connect/restart buttons. Reserve exactly the
   * monitor's height instead of guessing.
   */
  _reserveSpace() {
    requestAnimationFrame(() => {
      document.body.style.paddingBottom = `${this.root.offsetHeight}px`;
    });
  }

  _visible(entry) {
    if (this.showRaw) return true;
    return entry.dir !== DIR.TX && entry.dir !== DIR.RX;
  }

  _rowFor(entry) {
    if (this.t0 === null) this.t0 = entry.t;
    const ms = (entry.t - this.t0).toFixed(0).padStart(6);
    const row = document.createElement("div");
    row.className = "whitespace-pre-wrap break-all";
    const trunc = entry.truncated ? ` …(${entry.fullLength}B)` : "";
    const meta = entry.meta ? ` ${JSON.stringify(entry.meta)}` : "";
    row.innerHTML =
      `<span class="text-neutral-700">${ms}ms</span> ` +
      `<span class="${COLORS[entry.dir] || "text-neutral-400"}">${(LABELS[entry.dir] || entry.dir).padEnd(4)}</span> ` +
      `<span class="${COLORS[entry.dir] || "text-neutral-300"}">${escapeHtml(entry.text)}</span>` +
      `<span class="text-neutral-700">${escapeHtml(trunc + meta)}</span>`;
    return row;
  }

  _onEntry(entry) {
    if (entry === null) {
      this.t0 = null;
      this._redraw();
      this.countEl.textContent = "0";
      this.lastEl.textContent = "";
      return;
    }
    this.countEl.textContent = String(getEntries().length);
    // Always surface the newest line in the collapsed bar, so a failure is
    // visible without opening the panel.
    this.lastEl.textContent = `${LABELS[entry.dir] || entry.dir}: ${entry.text.slice(0, 120)}`;
    this.lastEl.className = `truncate flex-1 ${COLORS[entry.dir] || "text-neutral-600"}`;
    if (!this.open || !this._visible(entry)) return;
    this.logEl.appendChild(this._rowFor(entry));
    while (this.logEl.childElementCount > 1200) this.logEl.removeChild(this.logEl.firstChild);
    if (this.autoscroll) this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  _redraw() {
    this.logEl.innerHTML = "";
    this.t0 = null;
    for (const e of getEntries()) {
      if (this._visible(e)) this.logEl.appendChild(this._rowFor(e));
    }
    if (this.autoscroll) this.logEl.scrollTop = this.logEl.scrollHeight;
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}
