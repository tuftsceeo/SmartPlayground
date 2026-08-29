/**
 * simpleDeviceBar.js -- Connect, Show on device, Save, on-device file list.
 * Dev recovery controls (install/restart, 12V, mA) are omitted.
 */

export function createSimpleDeviceBar(state, cb) {
  const el = document.createElement("div");
  el.className = "p-3 border-t border-neutral-800 text-xs flex flex-col gap-2";

  if (!state.deviceSupported) {
    el.innerHTML = `<div class="text-neutral-500">Web Serial isn't available in this browser (Chrome/Edge only).</div>`;
    return el;
  }

  if (!state.deviceConnected) {
    el.innerHTML = `
      <button id="connectBtn" class="w-full px-3 py-2 rounded bg-emerald-900 hover:bg-emerald-800 text-emerald-100 flex items-center justify-center gap-2">
        <i data-lucide="usb" class="w-4 h-4"></i> Connect
      </button>
    `;
    el.querySelector("#connectBtn").addEventListener("click", cb.onConnect);
    return el;
  }

  if (!state.deviceRunning) {
    el.innerHTML = `
      <div class="text-neutral-500 text-center py-2">
        Connected — waiting for device…
        <div class="text-neutral-600 mt-1">Switch to advanced mode for firmware install/restart.</div>
      </div>
      <button id="disconnectBtn" class="w-full px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-400">Disconnect</button>
    `;
    el.querySelector("#disconnectBtn").addEventListener("click", cb.onDisconnect);
    return el;
  }

  const refusal = state.deviceLastRefusal;

  el.innerHTML = `
    <div class="flex gap-2">
      <button id="livePushBtn"
              class="flex-1 px-3 py-2 rounded ${
                state.devicePushEnabled
                  ? "bg-emerald-900 text-emerald-100"
                  : "bg-neutral-800 hover:bg-neutral-700 text-neutral-200"
              } flex items-center justify-center gap-2"
              ${state.deviceCapabilities.liveFrames ? "" : "disabled"}>
        <i data-lucide="monitor" class="w-4 h-4"></i>
        ${state.devicePushEnabled ? "Showing on device" : "Show on device"}
      </button>
      <button id="disconnectBtn" class="px-2 py-2 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-400" title="Disconnect">
        <i data-lucide="unplug" class="w-4 h-4"></i>
      </button>
    </div>

    ${
      refusal
        ? `<div class="p-2 rounded bg-red-950 text-red-300">
            Too bright for safe display.
            <button id="applySuggestedBtn" class="underline">Lower brightness</button>
          </div>`
        : ""
    }

    <div class="flex items-center justify-between mt-1">
      <span class="text-neutral-500">Saved icons</span>
      <button id="refreshIconsBtn" class="text-neutral-500 hover:text-neutral-300 p-1" title="Refresh">
        <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>
      </button>
    </div>
    <div class="flex flex-col gap-1 max-h-32 overflow-y-auto">
      ${
        state.deviceIcons.length
          ? state.deviceIcons
              .map(
                (ic) => `
        <div class="flex items-center gap-1" data-device-icon="${ic.name}">
          <span class="flex-1 truncate">${ic.name}</span>
          <button data-load class="px-1.5 py-0.5 rounded bg-neutral-800 hover:bg-neutral-700">show</button>
          <button data-delete class="px-1.5 py-0.5 rounded bg-neutral-800 hover:bg-red-900 p-1" title="Delete">
            <i data-lucide="trash-2" class="w-3 h-3"></i>
          </button>
        </div>`
              )
              .join("")
          : `<div class="text-neutral-600">none yet</div>`
      }
    </div>
    <button id="saveToDeviceBtn" class="w-full px-3 py-2 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 flex items-center justify-center gap-2"
            ${state.mode ? "" : "disabled"}>
      <i data-lucide="save" class="w-4 h-4"></i> Save to device
    </button>
  `;

  el.querySelector("#disconnectBtn").addEventListener("click", cb.onDisconnect);
  el.querySelector("#livePushBtn")?.addEventListener("click", () => cb.onToggleLivePush(!state.devicePushEnabled));
  el.querySelector("#refreshIconsBtn")?.addEventListener("click", cb.onRefreshIcons);
  el.querySelector("#saveToDeviceBtn")?.addEventListener("click", cb.onSaveToDevice);
  el.querySelector("#applySuggestedBtn")?.addEventListener("click", () => cb.onApplySuggestedIntensity(refusal.suggestedIntensity));

  el.querySelectorAll("[data-device-icon]").forEach((row) => {
    const name = row.dataset.deviceIcon;
    row.querySelector("[data-load]")?.addEventListener("click", () => cb.onLoadFromDevice(name));
    row.querySelector("[data-delete]")?.addEventListener("click", () => cb.onDeleteFromDevice(name));
  });

  return el;
}
