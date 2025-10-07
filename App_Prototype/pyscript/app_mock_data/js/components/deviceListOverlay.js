/**
 * Playground Control App - Device List Overlay
 */

import { getDeviceIcon, getSignalIcon, getBatteryIcon } from './icons.js';
import { getRangeLabel } from '../state/store.js';

export function createDeviceListOverlay(devices, range, isRefreshing, editingDeviceId, nicknames, onClose, onRangeChange, onRefresh, onStartEdit, onSaveNickname) {
  const overlay = document.createElement('div');
  overlay.className = 'absolute inset-0 bg-white z-50 flex flex-col';
  overlay.style.display = 'none';
  
  overlay.innerHTML = `
    <div class="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3">
      <button class="w-9 h-9 flex items-center justify-center rounded-full transition-colors" id="backBtn">
        <i data-lucide="arrow-left" class="w-5 h-5 text-gray-700"></i>
      </button>
      <h2 class="text-lg font-semibold text-gray-900">Devices</h2>
      <button class="ml-auto w-9 h-9 flex items-center justify-center rounded-full transition-colors ${isRefreshing ? 'animate-spin' : ''}" id="refreshBtn">
        <i data-lucide="refresh-cw" class="w-5 h-5 text-gray-700"></i>
      </button>
    </div>
    
    <div class="px-4 py-3 bg-blue-50 border-b border-blue-200">
      <div class="flex items-center gap-2 mb-3">
        <i data-lucide="info" class="w-4 h-4 text-blue-600"></i>
        <span class="text-sm font-medium text-blue-800">Demo Mode</span>
      </div>
      <div class="text-xs text-blue-700 mb-3">
        App demonstration with a virtual hub and simulated devices.<br> 
        No Bluetooth connection to devices present.
      </div>
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
  overlay.querySelector('#refreshBtn').onclick = onRefresh;
  overlay.querySelector('#rangeSlider').onchange = (e) => onRangeChange(parseInt(e.target.value));
  
  // Add devices
  const deviceList = overlay.querySelector('#deviceList');
  
  if (devices.length === 0) {
    deviceList.innerHTML = `
      <div class="text-center py-12 px-4">
        <i data-lucide="wifi-off" class="w-8 h-8 text-gray-400 mx-auto mb-3"></i>
        <div class="text-sm text-gray-600 mb-2">No simulated devices in range</div>
        <div class="text-xs text-gray-500">Try adjusting the range slider or refresh the device list</div>
      </div>
    `;
  } else {
    devices.forEach(device => {
      const card = document.createElement('div');
      card.className = 'px-4 py-3 border-b border-gray-100 device-card flex items-center gap-3';
      
      card.appendChild(getDeviceIcon(device.type, 'medium'));
      
      const displayName = nicknames[device.id] || device.id;
      const isEditing = editingDeviceId === device.id;
      
      card.innerHTML += `
        <div class="flex-1 min-w-0">
          ${isEditing 
            ? `<input type="text" value="${displayName === device.id ? '' : displayName}" placeholder="${device.id}" 
                      class="w-full px-2 py-1 border border-gray-300 rounded text-sm font-medium text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500" id="edit-${device.id}" autofocus>`
            : `<div class="font-medium text-gray-900">${displayName}</div>`
          }
          <div class="text-xs text-gray-500">${device.type === 'module' ? 'Module' : device.type === 'extension' ? 'Extension' : 'Button'} • ${device.id}</div>
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