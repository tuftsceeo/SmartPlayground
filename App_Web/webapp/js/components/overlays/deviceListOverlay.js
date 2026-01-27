/**
 * Playground Control App - Device List Overlay
 */

import { getDeviceIcon, getSignalIcon, getBatteryIcon } from '../common/icons.js';
import { getRangeLabel } from '../../state/store.js';
import { getRelativeTime } from '../../utils/helpers.js';

export function createDeviceListOverlay(devices, range, isRefreshing, editingDeviceId, nicknames, onClose, onRangeChange, onRefresh, onStartEdit, onSaveNickname, hubConnected, onHubConnect) {
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
        <button class="ml-auto w-9 h-9 flex items-center justify-center rounded-full transition-colors opacity-50 cursor-not-allowed" id="refreshBtn" disabled title="Passive tracking (auto-updates every 30s)">
          <i data-lucide="refresh-cw" class="w-5 h-5 text-gray-700"></i>
        </button>
      </div>
      <div class="text-xs text-gray-500 mt-1 ml-12">
        Passive tracking active • Updates every 30s via battery messages
      </div>
    </div>
    
    <div class="px-4 py-3 bg-gray-50 border-b border-gray-200">
      <div class="flex items-center gap-3 mb-2">
        <span class="text-sm text-gray-700 font-medium">Range</span>
        <div class="flex-1"></div>
        <span class="text-sm font-semibold text-gray-700 text-right whitespace-nowrap" style="width: 70px">${getRangeLabel(range)}</span>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-xs text-gray-500 whitespace-nowrap">Near</span>
        <input type="range" class="flex-1 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-gray-600" 
               min="1" max="100" step="1" value="${range}" id="rangeSlider">
        <span class="text-xs text-gray-500 whitespace-nowrap">Far</span>
      </div>
    </div>
    
    <div class="flex-1 overflow-y-auto" id="deviceList"></div>
  `;
  
  // Event handlers
  overlay.querySelector('#backBtn').onclick = onClose;
  // Refresh button disabled for passive tracking - no manual refresh needed
  // overlay.querySelector('#refreshBtn').onclick = onRefresh;
  overlay.querySelector('#rangeSlider').onchange = (e) => {
    onRangeChange(parseInt(e.target.value));
    // No manual refresh needed with passive tracking
  };
  
  // Add devices
  const deviceList = overlay.querySelector('#deviceList');
  
  if (!hubConnected) {
    // Bluetooth disconnected state
    deviceList.innerHTML = `
      <div class="flex flex-col items-center justify-center py-16 px-4">
        <i data-lucide="bluetooth-off" class="w-12 h-12 text-gray-400 mb-4"></i>
        <div class="text-sm font-medium text-gray-900 mb-6">Bluetooth Disconnected</div>
        <button class="px-6 py-2.5 bg-amber-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2" id="connectBtn">
          <i data-lucide="bluetooth" class="w-4 h-4"></i>
          Connect
        </button>
      </div>
    `;
    
    // Add connect button handler
    deviceList.querySelector('#connectBtn').onclick = (e) => {
      e.stopPropagation();
      onHubConnect();
    };
  } else if (devices.length === 0) {
    deviceList.innerHTML = '<div class="text-center text-gray-400 py-12 text-sm">No devices in range</div>';
  } else {
    devices.forEach(device => {
      const card = document.createElement('div');
      card.className = 'px-4 py-3 border-b border-gray-100 device-card flex items-center gap-3';
      
      card.appendChild(getDeviceIcon(device.type, 'medium'));
      
      const displayName = nicknames[device.id] || device.id;
      const isEditing = editingDeviceId === device.id;
      
      // Format last seen time and stale status
      const lastSeenText = device.lastSeenTime ? getRelativeTime(device.lastSeenTime) : 'unknown';
      const isStale = device.isStale || false;
      const batteryPct = device.battery_pct !== undefined ? device.battery_pct : '?';
      
      card.innerHTML += `
        <div class="flex-1 min-w-0">
          ${isEditing 
            ? `<input type="text" value="${displayName === device.id ? '' : displayName}" placeholder="${device.id}" 
                      class="w-full px-2 py-1 border border-gray-300 rounded text-sm font-medium text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500" id="edit-${device.id}" autofocus>`
            : `<div class="font-medium text-gray-900">${displayName}</div>`
          }
          <div class="text-xs text-gray-500">
            ${device.type === 'module' ? 'Module' : device.type === 'extension' ? 'Extension' : 'Button'} • 
            ${device.id} • 
            Battery: ${batteryPct}% • 
            <span class="${isStale ? 'text-amber-600 font-medium' : ''}">
              ${lastSeenText}${isStale ? ' ⚠' : ''}
            </span>
          </div>
        </div>
        <div class="flex items-center gap-3" id="status-${device.id}">
          <button class="w-8 h-8 flex items-center justify-center rounded-full transition-colors" id="edit-btn-${device.id}">
            <i data-lucide="pencil" class="w-4 h-4 text-gray-500"></i>
          </button>
        </div>
      `;
      
      // Add status icons
      const statusContainer = card.querySelector(`#status-${device.id}`);
      statusContainer.insertBefore(getBatteryIcon(device.battery), statusContainer.firstChild);
      statusContainer.insertBefore(getSignalIcon(device.signal), statusContainer.firstChild);
      
      // Edit handlers
      if (isEditing) {
        const input = card.querySelector(`#edit-${device.id}`);
        input.onblur = () => onSaveNickname(device.id, input.value);
        input.onkeydown = (e) => {
          if (e.key === 'Enter') onSaveNickname(device.id, input.value);
        };
      } else {
        card.querySelector(`#edit-btn-${device.id}`).onclick = (e) => {
          e.stopPropagation();
          onStartEdit(device.id);
        };
      }
      
      deviceList.appendChild(card);
    });
  }
  
  return overlay;
}