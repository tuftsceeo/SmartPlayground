/**
 * deviceBar.js -- plug trigger + anchored Device popover (advanced).
 * Install/restart/12V/probe/mA live in the hardware drawer, not here.
 */

function deviceBtnStyle(state) {
  if (state.deviceRunning) return { bg: "#dff3e3", border: "#4c9463", color: "#356b47", dot: "#4c9463" };
  if (!state.deviceConnected) return { bg: "#f0d9f4", border: "#8a4a92", color: "#6b3572", dot: "#c9c0aa" };
  if (state.deviceAtRepl) return { bg: "#fdf0c8", border: "#a9871f", color: "#8a6d15", dot: "#b95d52" };
  return { bg: "#fdf0c8", border: "#a9871f", color: "#8a6d15", dot: "#e2a93d" };
}

export function createDeviceBar(state, cb) {
  const el = document.createElement("div");
  el.className = "relative flex items-center";
  const st = deviceBtnStyle(state);
  const open = !!state.devicePanelOpen;
  const waitingAnim = state.deviceConnected && !state.deviceRunning && !state.deviceAtRepl ? "is-waiting" : "";

  let panelBody = "";
  if (open) {
    if (!state.deviceSupported) {
      panelBody = `<div class="font-semibold text-[12.5px] text-[var(--muted)]">Web Serial isn't available (Chrome/Edge only).</div>`;
    } else if (!state.deviceConnected) {
      panelBody = `
        <div class="flex items-center gap-2">
          <span class="status-dot" style="background:#c9c0aa"></span>
          <span class="font-semibold text-[12.5px] text-[var(--muted)]">Not connected</span>
        </div>
        <button type="button" id="connectBtn" class="btn-primary">Connect device</button>`;
    } else if (!state.deviceRunning) {
      const atRepl = state.deviceAtRepl;
      panelBody = `
        <div class="flex items-center gap-2">
          <span class="status-dot ${atRepl ? "" : "is-waiting"}" style="background:${atRepl ? "#b95d52" : "#e2a93d"}"></span>
          <span class="font-semibold text-[12.5px]" style="color:${atRepl ? "#8a3a30" : "var(--hw-ink)"}">
            ${atRepl ? "At MicroPython prompt — firmware not running" : "Connected · waiting for device…"}
          </span>
        </div>
        <div class="font-semibold text-[11px] text-[var(--muted2)] leading-snug">
          ${
            atRepl
              ? "The board is sitting at >>> — open Hardware & serial debug to restart firmware."
              : "Powering up the icon firmware — this can take a few seconds. Open Hardware & serial debug if it doesn't settle."
          }
        </div>
        <button type="button" id="disconnectBtn" class="btn-secondary">Disconnect</button>`;
    } else {
      const refusal = state.deviceLastRefusal;
      const mem = state.deviceMemFree ? `${Math.round(state.deviceMemFree / 1024)}KB free` : "";
      panelBody = `
        <div class="flex items-center gap-2">
          <span class="status-dot" style="background:#4c9463"></span>
          <span class="font-semibold text-[12.5px] text-[#356b47]">Connected${mem ? ` · ${mem}` : ""}</span>
          <button type="button" id="disconnectBtn" class="ml-auto font-semibold text-[11px] text-[var(--muted2)] underline bg-transparent border-none cursor-pointer">disconnect</button>
        </div>
        <button type="button" id="livePushBtn" class="flex items-center justify-between border-2 border-[var(--border)] rounded-[11px] px-2.5 py-2 cursor-pointer bg-transparent w-full"
                ${state.deviceCapabilities.liveFrames ? "" : "disabled"}>
          <span class="font-bold text-[12.5px] text-[#823f82]">Show on device</span>
          <div class="toggle-switch ${state.devicePushEnabled ? "is-on" : ""}"></div>
        </button>
        ${
          refusal
            ? `<div class="bg-[var(--red-soft)] border-2 border-[var(--red)] rounded-[11px] p-2.5 font-semibold text-[11.5px] text-[#8a3a30] leading-snug">
                Too bright for the connected power.
                <div class="flex gap-2.5 mt-1.5">
                  <button type="button" id="applySuggestedBtn" class="underline bg-transparent border-none cursor-pointer text-inherit">lower brightness to ${Math.round(refusal.suggestedIntensity * 100)}%</button>
                  <button type="button" id="flashAnywayBtn" class="underline bg-transparent border-none cursor-pointer text-inherit">flash anyway (2s)</button>
                </div>
              </div>`
            : ""
        }
        <div class="flex items-center justify-between">
          <span class="panel-label">on-device icons</span>
          <button type="button" id="refreshIconsBtn" class="font-semibold text-[11px] text-[var(--muted2)] underline bg-transparent border-none cursor-pointer">refresh</button>
        </div>
        <div class="flex flex-col gap-1.5 max-h-[120px] overflow-y-auto">
          ${
            state.deviceIcons.length
              ? state.deviceIcons
                  .map(
                    (ic) => `
            <div class="flex items-center gap-2 border-2 border-[var(--border)] rounded-[9px] px-2 py-1.5" data-device-icon="${ic.name}">
              <span class="flex-1 font-bold text-[12px]">${ic.name} <span class="font-semibold text-[10.5px] text-[var(--muted2)]">(${ic.bytes}B)</span></span>
              <button type="button" data-load class="font-bold text-[11px] text-[var(--teal)] bg-transparent border-none cursor-pointer">load</button>
              <button type="button" data-delete class="font-bold text-[11px] text-[var(--red)] bg-transparent border-none cursor-pointer">del</button>
            </div>`
                  )
                  .join("")
              : `<span class="font-semibold text-[11.5px] text-[#c9c0aa]">none yet</span>`
          }
        </div>
        <button type="button" id="saveToDeviceBtn" class="btn-primary" ${state.mode ? "" : "disabled"}>Save current icon to device</button>`;
    }
  }

  el.innerHTML = `
    <button type="button" id="deviceTrigger" title="Device" class="icon-btn-square"
            style="background:${st.bg};border-color:${st.border};color:${st.color};position:relative">
      <i data-lucide="plug-zap" class="w-[17px] h-[17px]"></i>
      <span class="status-dot ${waitingAnim}" style="position:absolute;top:-3px;right:-3px;width:11px;height:11px;background:${st.dot};border:2px solid var(--card)"></span>
    </button>
    ${
      open
        ? `<div class="popover absolute right-0 top-full mt-2 w-[300px] flex flex-col gap-2.5 z-20">
            <div class="flex justify-between items-center">
              <span class="font-bold text-[13px]">Device</span>
              <button type="button" id="deviceClose" class="icon-btn text-[var(--muted2)]"><i data-lucide="x" class="w-4 h-4"></i></button>
            </div>
            ${panelBody}
          </div>`
        : ""
    }
  `;

  el.querySelector("#deviceTrigger")?.addEventListener("click", () => cb.onTogglePanel?.());
  el.querySelector("#deviceClose")?.addEventListener("click", () => cb.onTogglePanel?.());
  el.querySelector("#connectBtn")?.addEventListener("click", cb.onConnect);
  el.querySelector("#disconnectBtn")?.addEventListener("click", cb.onDisconnect);
  el.querySelector("#livePushBtn")?.addEventListener("click", () => cb.onToggleLivePush(!state.devicePushEnabled));
  el.querySelector("#refreshIconsBtn")?.addEventListener("click", cb.onRefreshIcons);
  el.querySelector("#saveToDeviceBtn")?.addEventListener("click", cb.onSaveToDevice);
  const refusal = state.deviceLastRefusal;
  el.querySelector("#applySuggestedBtn")?.addEventListener("click", () =>
    cb.onApplySuggestedIntensity(refusal.suggestedIntensity)
  );
  el.querySelector("#flashAnywayBtn")?.addEventListener("click", cb.onFlashAnyway);
  el.querySelectorAll("[data-device-icon]").forEach((row) => {
    const name = row.dataset.deviceIcon;
    row.querySelector("[data-load]")?.addEventListener("click", () => cb.onLoadFromDevice(name));
    row.querySelector("[data-delete]")?.addEventListener("click", () => cb.onDeleteFromDevice(name));
  });

  return el;
}
