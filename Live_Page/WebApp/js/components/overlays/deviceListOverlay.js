/**
 * Playground Control App - Device List Overlay
 */

import { getDeviceIcon, getSignalIcon, getBatteryIcon } from '../common/icons.js';
import { getRangeLabel } from '../../state/store.js';
import { getRelativeTime } from '../../utils/helpers.js';

export function createDeviceListOverlay(devices, range, editingDeviceId, nicknames, onClose, onRangeChange, onStartEdit, onSaveNickname, hubConnected, onHubConnect, hubConnecting = false) {
  const overlay = document.createElement('div');
  overlay.className = 'absolute inset-0 bg-white z-50 flex flex-col';
  overlay.style.display = 'none';
  
  overlay.innerHTML = `
    <div class="bg-white border-b border-gray-200 px-4 py-3">
      <div class="flex items-center gap-3">
        <button class="w-9 h-9 flex items-center justify-center rounded-full shadow-md hover:shadow-lg transition-all hover:scale-110 hover:-translate-x-1 active:scale-95 bg-teal-400 hover:bg-teal-500" id="backBtn">
          <i data-lucide="arrow-left" class="w-5 h-5 text-white"></i>
        </button>
        <h2 class="text-lg font-semibold text-gray-900">Devices</h2>
      </div>
     
    </div>
    
    <div class="flex-1 overflow-y-auto" id="deviceList"></div>
  `;
  
  // Event handlers
  const backBtn = overlay.querySelector('#backBtn');
  backBtn.onclick = onClose;

  
  // Add devices
  const deviceList = overlay.querySelector('#deviceList');
  
  if (!hubConnected) {
    // Hub disconnected state - more encouraging
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
    
    // Add connect button handler
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
        <i data-lucide="radio-tower" class="w-16 h-16 mb-4" style="color: #bf75c9;"></i>
        <div class="text-base font-semibold text-gray-900 mb-2">Looking for Devices...</div>
        <div class="text-sm text-gray-500">Make sure your plushies are turned on and nearby</div>
      </div>
    `;
  } else {
    devices.forEach(device => {
      const card = document.createElement('div');
      card.className = 'px-4 py-4 border-b border-gray-100 device-card flex items-start gap-3';
      
      // Device icon
      const iconWrapper = document.createElement('div');
      iconWrapper.className = 'flex-shrink-0 mt-1';
      iconWrapper.appendChild(getDeviceIcon(device.type, 'medium'));
      card.appendChild(iconWrapper);
      
      const displayName = nicknames[device.id] || device.id;
      const isEditing = editingDeviceId === device.id;
      
      // Format last seen time and stale status
      const lastSeenText = device.lastSeenTime ? getRelativeTime(device.lastSeenTime) : 'unknown';
      const isStale = device.isStale || false;
      
      // Handle unknown battery percentage
      const batteryPct = device.battery_pct !== undefined && device.battery_pct !== null 
        ? Math.round(device.battery_pct) 
        : '?';
      
      // Content section
      const contentDiv = document.createElement('div');
      contentDiv.className = 'flex-1 min-w-0';
      contentDiv.innerHTML = `
        ${isEditing 
          ? `<input type="text" value="${displayName === device.id ? '' : displayName}" placeholder="${device.id}" 
                    class="w-full px-2 py-1 border border-gray-300 rounded text-base font-semibold text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400 mb-1" id="edit-${device.id}" autofocus>`
          : `<div class="font-semibold text-gray-900 text-base mb-1">${displayName}</div>`
        }
        <div class="text-xs text-gray-500 mb-1.5">
          ${device.type === 'module' ? 'Module' : device.type === 'extension' ? 'Extension' : 'Button'} • ${device.id}
        </div>
        <div class="flex items-center gap-3 text-xs">
          <span class="${batteryPct === '?' ? 'text-gray-400' : batteryPct < 20 ? 'text-red-600 font-medium' : 'text-gray-600'}">
            Battery: ${batteryPct}%
          </span>
          <span class="${isStale ? 'text-amber-600 font-medium' : 'text-gray-600'}">
            ${lastSeenText}${isStale ? ' ⚠' : ''}
          </span>
        </div>
      `;
      card.appendChild(contentDiv);
      
      // Status icons section
      const statusDiv = document.createElement('div');
      statusDiv.className = 'flex items-center gap-2 flex-shrink-0';
      statusDiv.id = `status-${device.id}`;
      
      // Add signal and battery icons (larger size)
      const signalIcon = getSignalIcon(device.signal);
      signalIcon.className = signalIcon.className.replace('w-4 h-4', 'w-5 h-5');
      statusDiv.appendChild(signalIcon);
      
      const batteryIcon = getBatteryIcon(device.battery);
      batteryIcon.className = batteryIcon.className.replace('w-4 h-4', 'w-5 h-5');
      statusDiv.appendChild(batteryIcon);
      
      // Edit button
      statusDiv.innerHTML += `
        <button class="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors" id="edit-btn-${device.id}">
          <i data-lucide="pencil" class="w-4 h-4" style="color: #a082cf;"></i>
        </button>
      `;
      
      card.appendChild(statusDiv);
      
      // Edit handlers
      if (isEditing) {
        const input = contentDiv.querySelector(`#edit-${device.id}`);
        input.onblur = () => onSaveNickname(device.id, input.value);
        input.onkeydown = (e) => {
          if (e.key === 'Enter') onSaveNickname(device.id, input.value);
        };
      } else {
        statusDiv.querySelector(`#edit-btn-${device.id}`).onclick = (e) => {
          e.stopPropagation();
          onStartEdit(device.id);
        };
      }
      
      deviceList.appendChild(card);
    });
  }
  
  return overlay;
}