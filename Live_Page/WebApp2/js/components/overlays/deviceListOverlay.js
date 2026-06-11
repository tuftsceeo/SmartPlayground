/**
 * Playground Control App - Device List Overlay
 */

import { getDeviceIcon, getSignalIcon, getBatteryIcon } from '../common/icons.js';
import { getRelativeTime } from '../../utils/helpers.js';

export function createDeviceListOverlay(devices, lastPolledTime, onClose, hubConnected, onHubConnect, hubConnecting = false) {
  const overlay = document.createElement('div');
  overlay.className = 'absolute inset-0 bg-white z-50 flex flex-col';
  overlay.style.display = 'none';

  const lastPolledLabel = lastPolledTime
    ? 'Last polled ' + getRelativeTime(lastPolledTime)
    : 'Send Ask Device Status to update';

  overlay.innerHTML = `
    <div class="bg-white border-b border-gray-200 px-4 py-3">
      <div class="flex items-center gap-3">
        <button class="w-9 h-9 flex items-center justify-center rounded-full shadow-md hover:shadow-lg transition-all hover:scale-110 hover:-translate-x-1 active:scale-95 bg-teal-400 hover:bg-teal-500" id="backBtn">
          <i data-lucide="arrow-left" class="w-5 h-5 text-white"></i>
        </button>
        <div class="flex-1 min-w-0">
          <h2 class="text-lg font-semibold text-gray-900">Devices</h2>
          <p class="text-xs text-gray-500 truncate">${lastPolledLabel}</p>
        </div>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto" id="deviceList"></div>
  `;

  const backBtn = overlay.querySelector('#backBtn');
  backBtn.onclick = onClose;

  const deviceList = overlay.querySelector('#deviceList');

  if (!hubConnected) {
    const isDisabled = hubConnecting;
    deviceList.innerHTML = `
      <div class="flex flex-col items-center justify-center py-16 px-4">
        <i data-lucide="plug" class="w-16 h-16 mb-4" style="color: #8fd3c9;"></i>
        <div class="text-base font-semibold text-gray-900 mb-2">Let's Get Connected!</div>
        <div class="text-sm text-gray-500 mb-6">Plug in your control module to start playing</div>
        <button ${isDisabled ? 'disabled' : ''} class="px-6 py-3 bg-blue-400 hover:bg-blue-500 text-white text-sm font-semibold rounded-lg transition-all shadow-md flex items-center gap-2 ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]'}" id="connectBtn">
          <i data-lucide="plug" class="w-4 h-4"></i>
          ${hubConnecting ? 'Connecting...' : 'Connect to Controller'}
        </button>
      </div>
    `;

    const connectBtn = deviceList.querySelector('#connectBtn');
    if (!isDisabled && connectBtn) {
      connectBtn.onclick = (e) => {
        e.stopPropagation();
        onHubConnect();
      };
    }
  } else if (devices.length === 0) {
    deviceList.innerHTML = `
      <div class="flex flex-col items-center justify-center py-16 px-4">
        <i data-lucide="radio" class="w-16 h-16 mb-4" style="color: #6b9bd1;"></i>
        <div class="text-base font-semibold text-gray-900 mb-2">No device data yet</div>
        <div class="text-sm text-gray-500 text-center">Send <strong>Ask Device Status</strong> from the chat to poll wands in range.</div>
      </div>
    `;
  } else {
    devices.forEach(device => {
      const card = document.createElement('div');
      card.className = 'px-4 py-4 border-b border-gray-100 device-card flex items-start gap-3';

      const iconWrapper = document.createElement('div');
      iconWrapper.className = 'flex-shrink-0 mt-1';
      iconWrapper.appendChild(getDeviceIcon(device.type || 'module', 'medium'));
      card.appendChild(iconWrapper);

      const displayName = device.name || device.id;
      const batteryPct = device.battery_pct !== undefined && device.battery_pct !== null
        ? Math.round(device.battery_pct)
        : '?';

      const contentDiv = document.createElement('div');
      contentDiv.className = 'flex-1 min-w-0';
      contentDiv.innerHTML = `
        <div class="font-semibold text-gray-900 text-base mb-1">${displayName}</div>
        <div class="text-xs text-gray-500 mb-1.5">Module • ${device.id}</div>
        <div class="text-xs text-gray-600">Battery: ${batteryPct}%</div>
      `;
      card.appendChild(contentDiv);

      const statusDiv = document.createElement('div');
      statusDiv.className = 'flex items-center gap-2 flex-shrink-0';

      const signalIcon = getSignalIcon(device.signal);
      signalIcon.className = signalIcon.className.replace('w-4 h-4', 'w-5 h-5');
      statusDiv.appendChild(signalIcon);

      const batteryIcon = getBatteryIcon(device.battery);
      batteryIcon.className = batteryIcon.className.replace('w-4 h-4', 'w-5 h-5');
      statusDiv.appendChild(batteryIcon);

      card.appendChild(statusDiv);
      deviceList.appendChild(card);
    });
  }

  return overlay;
}
