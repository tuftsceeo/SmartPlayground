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
        <button class="w-9 h-9 flex items-center justify-center rounded-full transition-colors" id="backBtn">
          <i data-lucide="arrow-left" class="w-5 h-5 text-gray-700"></i>
        </button>
        <h2 class="text-lg font-semibold text-gray-900">Devices</h2>
      </div>
      <div class="text-xs text-gray-500 mt-1 ml-12">
        Auto-updates every 30s
      </div>
    </div>
    
    <div class="flex-1 overflow-y-auto" id="deviceList"></div>
  `;
  
  // Event handlers
  overlay.querySelector('#backBtn').onclick = onClose;

  
  // Add devices
  const deviceList = overlay.querySelector('#deviceList');
  
  if (!hubConnected) {
    // Hub disconnected state
    const isDisabled = hubConnecting;
    deviceList.innerHTML = `
      <div class="flex flex-col items-center justify-center py-16 px-4">
        <i data-lucide="unplug" class="w-12 h-12 text-gray-400 mb-4"></i>
        <div class="text-sm font-medium text-gray-900 mb-6">Hub Disconnected</div>
        <button ${isDisabled ? 'disabled' : ''} class="px-6 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2 ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-blue-700'}" id="connectBtn">
          <i data-lucide="plug" class="w-4 h-4"></i>
          ${hubConnecting ? 'Connecting...' : 'Connect to Hub'}
        </button>
      </div>
    `;
    
    // Add connect button handler
    if (!isDisabled) {
      deviceList.querySelector('#connectBtn').onclick = (e) => {
        e.stopPropagation();
        onHubConnect();
      };
    }
  } else if (devices.length === 0) {
    deviceList.innerHTML = '<div class="text-center text-gray-400 py-12 text-sm">No devices in range</div>';
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
                    class="w-full px-2 py-1 border border-gray-300 rounded text-base font-semibold text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 mb-1" id="edit-${device.id}" autofocus>`
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
          <i data-lucide="pencil" class="w-4 h-4 text-gray-500"></i>
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