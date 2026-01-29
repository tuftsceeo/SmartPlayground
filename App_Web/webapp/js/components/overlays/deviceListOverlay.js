/**
 * Playground Control App - Device List Overlay
 */

import { getDeviceIcon, getSignalIcon, getBatteryIcon } from '../common/icons.js';
import { getRelativeTime } from '../../utils/helpers.js';

export function createDeviceListOverlay(devices, editingDeviceId, nicknames, onClose, onStartEdit, onSaveNickname, hubConnected, onHubConnect, selectionMode = false, selectedDevice = null, onDeviceSelect = null) {
  const overlay = document.createElement('div');
  overlay.className = 'absolute inset-0 bg-white z-50 flex flex-col';
  overlay.style.display = 'none';
  
  overlay.innerHTML = `
    <div class="bg-white border-b border-gray-200 px-4 py-3">
      <div class="flex items-center gap-3">
        <button class="w-9 h-9 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors" id="backBtn">
          <i data-lucide="arrow-left" class="w-5 h-5 text-gray-700"></i>
        </button>
        <h2 class="text-lg font-semibold text-gray-900">${selectionMode ? 'Select Device' : 'Devices'}</h2>
      </div>
      ${!selectionMode ? `
        <div class="text-xs text-gray-500 mt-1 ml-12">
          Auto-updates every 30s
        </div>
      ` : ''}
    </div>
    
    <div class="flex-1 overflow-y-auto ${selectionMode ? 'px-4 py-3' : ''}" id="deviceList"></div>
  `;
  
  // Event handlers
  overlay.querySelector('#backBtn').onclick = onClose;
 
  
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
    deviceList.innerHTML = `<div class="text-center text-gray-400 py-12 text-sm">No devices in range</div>`;
  } else {
    // Container for device cards (spacing only in selection mode)
    const containerClass = selectionMode ? 'space-y-2' : '';
    if (containerClass && selectionMode) {
      deviceList.className += ' ' + containerClass;
    }
    
    devices.forEach(device => {
      const displayName = nicknames[device.id] || device.id;
      const isEditing = editingDeviceId === device.id;
      const isSelected = selectedDevice && (selectedDevice.mac === device.mac || selectedDevice.id === device.id);
      
      // Format last seen time and stale status
      const lastSeenText = device.lastSeenTime ? getRelativeTime(device.lastSeenTime) : 'unknown';
      const isStale = device.isStale || false;
      const batteryPct = device.battery_pct !== undefined ? device.battery_pct : '?';
      
      const card = document.createElement('button');
      
      if (selectionMode) {
        // Selection mode: rounded cards with radio buttons
        card.className = `device-item w-full bg-white rounded-2xl p-3 border border-gray-200 flex items-center gap-3 text-left transition-all hover:bg-gray-50 ${isSelected ? 'bg-blue-50 border-blue-300' : ''}`;
        card.dataset.mac = device.mac || '';
        card.dataset.rssi = device.rssi || '';
        card.dataset.name = displayName;
        card.dataset.id = device.id;
        
        card.innerHTML = `
          <!-- Radio button -->
          <div class="w-6 h-6 rounded-full border-2 ${isSelected ? 'border-blue-500' : 'border-gray-300'} flex items-center justify-center flex-shrink-0">
            <div class="w-3 h-3 rounded-full bg-blue-500 ${isSelected ? '' : 'opacity-0'}"></div>
          </div>
          
          <!-- Device info -->
          <div class="flex-1 min-w-0">
            <div class="font-medium text-gray-900">${displayName}</div>
            <div class="text-xs text-gray-500 font-mono">${device.mac || device.id}</div>
          </div>
          
          <!-- RSSI and time -->
          <div class="flex flex-col items-end gap-0.5 flex-shrink-0">
            <span class="text-xs font-medium ${device.rssi >= -60 ? 'text-green-600' : 'text-gray-400'}">
              ${device.rssi ? device.rssi + ' dBm' : 'N/A'}
            </span>
            <span class="text-xs text-gray-400">${lastSeenText}</span>
          </div>
        `;
        
        // Device selection handler
        card.addEventListener('click', () => {
          if (onDeviceSelect) {
            onDeviceSelect({
              mac: device.mac,
              id: device.id,
              name: displayName
            });
          }
        });
        
      } else {
        // Normal mode: list items with edit capability
        card.className = 'px-4 py-3 border-b border-gray-100 device-card flex items-center gap-3 cursor-default';
        card.disabled = true;
        
        const iconWrapper = document.createElement('div');
        iconWrapper.appendChild(getDeviceIcon(device.type, 'medium'));
        card.appendChild(iconWrapper);
        
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
            <button class="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors" id="edit-btn-${device.id}">
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
          const editBtn = card.querySelector(`#edit-btn-${device.id}`);
          if (editBtn) {
            editBtn.onclick = (e) => {
              e.stopPropagation();
              onStartEdit(device.id);
            };
          }
        }
      }
      
      deviceList.appendChild(card);
    });
  }
  
  return overlay;
}