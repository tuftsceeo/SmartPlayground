/**
 * serialMonitor.js -- hardware drawer body (serial log + firmware + power).
 * Persistent element; main.js mounts it into #hwDrawerMount after each shell build.
 */
import { subscribe, getEntries, clear, toText, setPaused, isPaused, DIR } from "../device/serialLog.js";

const COLORS = {
  [DIR.TX]: "text-sky-600",
  [DIR.RX]: "text-emerald-700",
  [DIR.OUT]: "text-sky-700 font-semibold",
  [DIR.IN]: "text-emerald-800 font-semibold",
  [DIR.DROP]: "text-[#b9985a]",
  [DIR.INFO]: "text-[var(--hw-ink)]",
  [DIR.WARN]: "text-amber-700",
  [DIR.ERROR]: "text-[var(--red)]",
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
  constructor({
    onProbe,
    onSendRaw,
    onRestart,
    onConnect,
    onDisconnect,
    onInstall,
    onToggleTwelveV,
  } = {}) {
    this.onProbe = onProbe;
    this.onSendRaw = onSendRaw;
    this.onRestart = onRestart;
    this.onConnect = onConnect;
    this.onDisconnect = onDisconnect;
    this.onInstall = onInstall;
    this.onToggleTwelveV = onToggleTwelveV;
    this._connected = false;
    this._twelveV = false;
    this._currentMa = null;
    this.open = false;
    this.autoscroll = true;
    this.showRaw = true;
    this.t0 = null;
    this._build();
    subscribe((entry) => this._onEntry(entry));
  }

  _build() {
    const root = document.createElement("div");
    root.className = "bg-[var(--hw-bg)] border-t-2 border-[#f0dba0] px-6 py-5 flex gap-5 font-[Nunito,sans-serif]";
    root.innerHTML = `
      <div class="flex-1 flex flex-col gap-2 min-w-0">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="panel-label" style="color:var(--hw-ink)">Serial monitor</span>
          <span id="smCount" class="font-semibold text-[11px] text-[#b9985a]">0</span>
          <span id="smLast" class="font-semibold text-[11px] text-[#b9985a] truncate flex-1"></span>
          <label class="flex items-center gap-1 font-semibold text-[11px] text-[var(--hw-ink)]">
            <input type="checkbox" id="smRaw" checked /> raw
          </label>
          <label class="flex items-center gap-1 font-semibold text-[11px] text-[var(--hw-ink)]">
            <input type="checkbox" id="smAuto" checked /> autoscroll
          </label>
          <button type="button" id="smPause" class="btn-pill text-[11px] py-1 px-2 border-[#e2c98f] text-[var(--hw-ink)]">Pause</button>
          <button type="button" id="smCopy" class="btn-pill text-[11px] py-1 px-2 border-[#e2c98f] text-[var(--hw-ink)]"><i data-lucide="copy" class="w-3 h-3 inline"></i></button>
          <button type="button" id="smClear" class="btn-pill text-[11px] py-1 px-2 border-[#e2c98f] text-[var(--hw-ink)]">Clear</button>
        </div>
        <div id="smLog" class="bg-[#1c1408] text-[#e8d9a0] font-mono text-[11px] rounded-[9px] p-2.5 h-[150px] overflow-y-auto flex flex-col gap-0.5"></div>
        <div class="flex gap-2">
          <input id="smInput" type="text" placeholder="send command…"
                 class="flex-1 font-semibold text-[11px] font-mono border-[1.5px] border-[#f0dba0] rounded-[7px] px-2 py-1.5 bg-white" />
          <button type="button" id="smSend" class="font-bold text-[11px] px-3 py-1.5 rounded-[7px] bg-[var(--gold)] text-white border-none cursor-pointer flex items-center gap-1">
            <i data-lucide="send" class="w-3 h-3"></i> send
          </button>
        </div>
      </div>

      <div class="w-[190px] flex flex-col gap-2 flex-none">
        <span class="panel-label" style="color:var(--hw-ink)">Firmware</span>
        <button type="button" id="smConn" class="btn-pill border-[#e2c98f] text-[var(--hw-ink)] w-full">Connect</button>
        <button type="button" id="smProbe" class="btn-pill border-[#e2c98f] text-[var(--hw-ink)] w-full">Probe device</button>
        <button type="button" id="smRestart" class="btn-pill border-[#e2c98f] text-[var(--hw-ink)] w-full">Restart firmware</button>
        <button type="button" id="smInstall" class="btn-pill border-[#e2c98f] text-[var(--hw-ink)] w-full">Install firmware…</button>
        <span id="smFwStatus" class="font-semibold text-[10.5px] text-[#b9985a]"></span>
      </div>

      <div class="w-[190px] flex flex-col gap-2 flex-none">
        <span class="panel-label" style="color:var(--hw-ink)">Power</span>
        <button type="button" id="smTwelveV" class="flex items-center justify-between border-2 border-[#e2c98f] rounded-[9px] px-2.5 py-1.5 cursor-pointer bg-white w-full text-left">
          <span class="font-bold text-[11.5px] text-[var(--hw-ink)]">12V power injection</span>
          <div id="smTwelveVSwitch" class="toggle-switch"></div>
        </button>
        <div class="font-semibold text-[11px] text-[var(--hw-ink)] bg-white border-2 border-[#e2c98f] rounded-[9px] px-2.5 py-2">
          <div>est. draw</div>
          <div id="smDrawMa" class="font-bold text-[16px] font-mono text-[#356b47]">—</div>
          <div id="smDrawCeil" class="font-semibold text-[9.5px] text-[#b9985a]">ceiling —</div>
        </div>
      </div>
    `;

    this.root = root;
    this.body = root; // drawer body IS the root now
    this.logEl = root.querySelector("#smLog");
    this.countEl = root.querySelector("#smCount");
    this.lastEl = root.querySelector("#smLast");
    this.input = root.querySelector("#smInput");
    this.connBtn = root.querySelector("#smConn");
    this.twelveVSwitch = root.querySelector("#smTwelveVSwitch");
    this.drawMa = root.querySelector("#smDrawMa");
    this.drawCeil = root.querySelector("#smDrawCeil");

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
    });
    root.querySelector("#smProbe").addEventListener("click", () => this.onProbe?.());
    root.querySelector("#smCopy").addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(toText());
        this._flash(root.querySelector("#smCopy"), "Copied");
      } catch {
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
    root.querySelector("#smInstall").addEventListener("click", () => this.onInstall?.());
    this.connBtn.addEventListener("click", () => {
      if (this._connected) this.onDisconnect?.();
      else this.onConnect?.();
    });
    root.querySelector("#smTwelveV").addEventListener("click", () => {
      this.onToggleTwelveV?.(!this._twelveV);
    });
  }

  /** Attach (or re-attach) the persistent root into a layout mount. */
  mount(host) {
    if (!host) return;
    host.innerHTML = "";
    host.appendChild(this.root);
    window.lucide?.createIcons?.();
  }

  setDeviceState({ connected, running, atRepl }) {
    this._connected = connected;
    this.connBtn.textContent = connected ? "Disconnect" : "Connect";
    this.connBtn.style.background = connected ? "var(--red-soft)" : "#fff";
    this.connBtn.style.color = connected ? "#8a3a30" : "var(--hw-ink)";
    const status = this.root.querySelector("#smFwStatus");
    if (status) {
      status.textContent = !connected
        ? "port closed"
        : running
          ? "firmware running"
          : atRepl
            ? "at REPL prompt"
            : "awaiting device";
    }
  }

  setPowerState({ twelveV, currentMa, ceilingMa }) {
    this._twelveV = !!twelveV;
    this.twelveVSwitch?.classList.toggle("is-on", this._twelveV);
    if (this.drawMa) {
      this.drawMa.textContent = currentMa != null ? `${Math.round(currentMa)}mA` : "—";
      this.drawMa.style.color =
        currentMa != null && ceilingMa != null && currentMa > ceilingMa ? "var(--red)" : "#356b47";
    }
    if (this.drawCeil) {
      this.drawCeil.textContent = ceilingMa != null ? `ceiling ${Math.round(ceilingMa)}mA` : "ceiling —";
    }
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

  /** Compatibility with old open/toggle API — drawer visibility is owned by main. */
  toggle() {
    this.open = !this.open;
    if (this.open) this._redraw();
  }

  setOpen(open) {
    this.open = !!open;
    if (this.open) this._redraw();
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
      `<span class="text-[#6a5a30]">${ms}ms</span> ` +
      `<span class="${COLORS[entry.dir] || ""}">${(LABELS[entry.dir] || entry.dir).padEnd(4)}</span> ` +
      `<span class="${COLORS[entry.dir] || ""}">${escapeHtml(entry.text)}</span>` +
      `<span class="text-[#6a5a30]">${escapeHtml(trunc + meta)}</span>`;
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
    this.lastEl.textContent = `${LABELS[entry.dir] || entry.dir}: ${entry.text.slice(0, 120)}`;
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
