/**
 * simpleDeviceBar.js -- plug trigger + Device popover (no install/restart/12V).
 */

function deviceBtnStyle(state) {
  if (state.deviceRunning) return { bg: "#dff3e3", border: "#4c9463", color: "#356b47", dot: "#4c9463" };
  if (!state.deviceConnected) return { bg: "#f0d9f4", border: "#8a4a92", color: "#6b3572", dot: "#c9c0aa" };
  return { bg: "#fdf0c8", border: "#a9871f", color: "#8a6d15", dot: "#e2a93d" };
}

export function createSimpleDeviceBar(state, cb) {
  const el = document.createElement("div");
  el.className = "relative flex items-center";
  const st = deviceBtnStyle(state);
  const open = !!state.devicePanelOpen;
  const waitingAnim = state.deviceConnected && !state.deviceRunning ? "is-waiting" : "";

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
      panelBody = `
        <div class="flex items-center gap-2">
          <span class="status-dot is-waiting" style="background:#e2a93d"></span>
          <span class="font-semibold text-[12.5px]" style="color:var(--hw-ink)">Connected · waiting…</span>
        </div>
        <div class="font-semibold text-[11px] text-[var(--muted2)]">Switch to advanced mode for firmware install/restart.</div>
        <button type="button" id="disconnectBtn" class="btn-secondary">Disconnect</button>`;
    } else {
      const refusal = state.deviceLastRefusal;
      panelBody = `
        <div class="flex items-center gap-2">
          <span class="status-dot" style="background:#4c9463"></span>
          <span class="font-semibold text-[12.5px] text-[#356b47]">Connected</span>
          <button type="button" id="disconnectBtn" class="ml-auto font-semibold text-[11px] text-[var(--muted2)] underline bg-transparent border-none cursor-pointer">disconnect</button>
        </div>
        <button type="button" id="livePushBtn" class="flex items-center justify-between border-2 border-[var(--border)] rounded-[11px] px-2.5 py-2 cursor-pointer bg-transparent w-full"
                ${state.deviceCapabilities.liveFrames ? "" : "disabled"}>
          <span class="font-bold text-[12.5px] text-[#823f82]">Show on device</span>
          <div class="toggle-switch ${state.devicePushEnabled ? "is-on" : ""}"></div>
        </button>
        ${
          refusal
            ? `<div class="bg-[var(--red-soft)] border-2 border-[var(--red)] rounded-[11px] p-2.5 font-semibold text-[11.5px] text-[#8a3a30]">
                Too bright for safe display.
                <button type="button" id="applySuggestedBtn" class="underline bg-transparent border-none cursor-pointer text-inherit ml-1">Lower brightness</button>
              </div>`
            : ""
        }
        <div class="flex items-center justify-between">
          <span class="panel-label">Saved icons</span>
          <button type="button" id="refreshIconsBtn" class="font-semibold text-[11px] text-[var(--muted2)] underline bg-transparent border-none cursor-pointer">refresh</button>
        </div>
        <div class="flex flex-col gap-1.5 max-h-[120px] overflow-y-auto">
          ${
            state.deviceIcons.length
              ? state.deviceIcons
                  .map(
                    (ic) => `
            <div class="flex items-center gap-2 border-2 border-[var(--border)] rounded-[9px] px-2 py-1.5" data-device-icon="${ic.name}">
              <span class="flex-1 font-bold text-[12px] truncate">${ic.name}</span>
              <button type="button" data-load class="font-bold text-[11px] text-[var(--teal)] bg-transparent border-none cursor-pointer">show</button>
              <button type="button" data-delete class="icon-btn text-[var(--red)]" title="Delete"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button>
            </div>`
                  )
                  .join("")
              : `<span class="font-semibold text-[11.5px] text-[#c9c0aa]">none yet</span>`
          }
        </div>
        <button type="button" id="saveToDeviceBtn" class="btn-primary" ${state.mode ? "" : "disabled"}>Save to device</button>`;
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
  el.querySelectorAll("[data-device-icon]").forEach((row) => {
    const name = row.dataset.deviceIcon;
    row.querySelector("[data-load]")?.addEventListener("click", () => cb.onLoadFromDevice(name));
    row.querySelector("[data-delete]")?.addEventListener("click", () => cb.onDeleteFromDevice(name));
  });

  return el;
}
