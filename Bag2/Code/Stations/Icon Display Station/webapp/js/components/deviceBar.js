/**
 * deviceBar.js -- connect/install/live-push panel, wired to a DeviceLink
 * (see js/device/deviceLink.js). See the plan §Device layer / §Brightness
 * control / §Power guard for what each control does.
 */

export function createDeviceBar(state, cb) {
  const el = document.createElement("div");
  el.className = "p-3 border-t border-neutral-800 text-xs flex flex-col gap-2";

  if (!state.deviceSupported) {
    el.innerHTML = `<div class="text-neutral-500">Web Serial isn't available in this browser (Chrome/Edge only).</div>`;
    return el;
  }

  if (!state.deviceConnected) {
    el.innerHTML = `
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-neutral-600"></span>
        <span class="text-neutral-400">Device: not connected</span>
      </div>
      <button id="connectBtn" class="w-full px-2 py-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200">Connect device</button>
    `;
    el.querySelector("#connectBtn").addEventListener("click", cb.onConnect);
    return el;
  }

  if (!state.deviceRunning) {
    // Connection is asynchronous (see deviceLink.js) -- the port is open,
    // but whether icon_server.py is running is reported later via an
    // unsolicited 'hello' that can take a few seconds. This is a waiting
    // state, not a failure; "Install" is always available as an explicit
    // manual escape hatch, not something auto-triggered by a timeout.
    const atRepl = state.deviceAtRepl;
    el.innerHTML = `
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 rounded-full ${atRepl ? "bg-red-500" : "bg-amber-500 animate-pulse"}"></span>
        <span class="text-neutral-400">${
          atRepl ? "At MicroPython prompt -- firmware not running" : "Connected -- waiting for device…"
        }</span>
      </div>
      <div class="text-neutral-600">${
        atRepl
          ? "The board is sitting at &gt;&gt;&gt; so it only echoes commands. Restart the firmware to get it running again."
          : "If this doesn't settle in a few seconds, try Restart firmware, or install it if this board has never had it."
      }</div>
      ${
        state.deviceRestarting
          ? `<div class="text-neutral-400">Restarting…</div>`
          : `<button id="restartBtn" class="w-full px-2 py-1.5 rounded ${
              atRepl ? "bg-emerald-900 hover:bg-emerald-800 text-emerald-200" : "bg-neutral-800 hover:bg-neutral-700 text-neutral-200"
            }">Restart firmware</button>`
      }
      ${
        state.deviceInstalling
          ? `<div class="text-neutral-400">Installing… ${state.deviceInstallProgress ? `${state.deviceInstallProgress.file} (${state.deviceInstallProgress.current}/${state.deviceInstallProgress.total})` : ""}</div>`
          : `<button id="installBtn" class="w-full px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-400">Install icon firmware (first time only)</button>`
      }
      <button id="disconnectBtn" class="w-full px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-400">Disconnect</button>
    `;
    if (!state.deviceInstalling) el.querySelector("#installBtn").addEventListener("click", cb.onInstall);
    if (!state.deviceRestarting) el.querySelector("#restartBtn").addEventListener("click", cb.onRestart);
    el.querySelector("#disconnectBtn").addEventListener("click", cb.onDisconnect);
    return el;
  }

  const refusal = state.deviceLastRefusal;

  el.innerHTML = `
    <div class="flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
      <span class="text-neutral-400">Device connected${state.deviceMemFree ? ` · ${Math.round(state.deviceMemFree / 1024)}KB free` : ""}</span>
      <button id="disconnectBtn" class="ml-auto text-neutral-600 hover:text-neutral-300">disconnect</button>
    </div>

    <label class="flex items-center gap-2">
      <input type="checkbox" id="livePushToggle" ${state.devicePushEnabled ? "checked" : ""} ${state.deviceCapabilities.liveFrames ? "" : "disabled"} />
      Live push
      ${!state.deviceCapabilities.liveFrames ? '<span class="text-neutral-600" title="This firmware build does not support live frames">(unsupported)</span>' : ""}
    </label>

    <label class="flex items-center gap-2 text-neutral-500">
      <input type="checkbox" id="twelveVToggle" ${state.deviceTwelveV ? "checked" : ""} />
      12V / power injection (raises the current ceiling -- unverified, see readme)
    </label>

    ${
      state.deviceLastCurrentMa != null
        ? `<div class="text-neutral-500">est. draw: ${Math.round(state.deviceLastCurrentMa)}mA</div>`
        : ""
    }

    ${
      refusal
        ? `<div class="p-2 rounded bg-red-950 text-red-300">
            est. ${Math.round(refusal.estimatedMa)}mA exceeds the ${Math.round(refusal.ceilingMa)}mA limit.
            <button id="applySuggestedBtn" class="underline">Drop brightness to ${Math.round(refusal.suggestedIntensity * 100)}%</button>
            or <button id="flashAnywayBtn" class="underline">flash anyway (2s)</button>.
          </div>`
        : ""
    }

    <div class="flex items-center justify-between mt-1">
      <span class="text-neutral-500">on-device icons</span>
      <button id="refreshIconsBtn" class="text-neutral-500 hover:text-neutral-300">refresh</button>
    </div>
    <div class="flex flex-col gap-1 max-h-32 overflow-y-auto">
      ${
        state.deviceIcons.length
          ? state.deviceIcons
              .map(
                (ic) => `
        <div class="flex items-center gap-1" data-device-icon="${ic.name}">
          <span class="flex-1 truncate">${ic.name} <span class="text-neutral-600">(${ic.bytes}B)</span></span>
          <button data-load class="px-1.5 py-0.5 rounded bg-neutral-800 hover:bg-neutral-700">load</button>
          <button data-delete class="px-1.5 py-0.5 rounded bg-neutral-800 hover:bg-red-900">del</button>
        </div>`
              )
              .join("")
          : `<div class="text-neutral-600">none</div>`
      }
    </div>
    <button id="saveToDeviceBtn" class="w-full px-2 py-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200" ${state.mode ? "" : "disabled"}>Save current icon to device</button>
  `;

  el.querySelector("#disconnectBtn").addEventListener("click", cb.onDisconnect);
  el.querySelector("#livePushToggle")?.addEventListener("change", (e) => cb.onToggleLivePush(e.target.checked));
  el.querySelector("#twelveVToggle")?.addEventListener("change", (e) => cb.onToggleTwelveV(e.target.checked));
  el.querySelector("#refreshIconsBtn")?.addEventListener("click", cb.onRefreshIcons);
  el.querySelector("#saveToDeviceBtn")?.addEventListener("click", cb.onSaveToDevice);
  el.querySelector("#applySuggestedBtn")?.addEventListener("click", () => cb.onApplySuggestedIntensity(refusal.suggestedIntensity));
  el.querySelector("#flashAnywayBtn")?.addEventListener("click", cb.onFlashAnyway);

  el.querySelectorAll("[data-device-icon]").forEach((row) => {
    const name = row.dataset.deviceIcon;
    row.querySelector("[data-load]")?.addEventListener("click", () => cb.onLoadFromDevice(name));
    row.querySelector("[data-delete]")?.addEventListener("click", () => cb.onDeleteFromDevice(name));
  });

  return el;
}
