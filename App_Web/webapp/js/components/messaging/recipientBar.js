/**
 * Recipient Bar Component
 * 
 * Top control bar: device count, range slider, connection status, settings.
 * Click to open device list, drag slider to filter by RSSI.
 */

import { getDeviceIcon } from '../common/icons.js';
import { getRangeLabel } from '../../state/store.js';
import { getRelativeTime } from '../../utils/helpers.js';
import { createBluetoothStatusButton } from '../connection/bluetoothStatusButton.js';
import { createSettingsButton } from '../common/settingsButton.js';

export function createRecipientBar(devices, range, lastUpdateTime, onRangeChange, onClick, onRefresh, hubConnected, hubDeviceName, onHubConnect, onHubDisconnect, onSettingsClick, isRefreshing = false, pythonReady = true, deviceScanningEnabled = false, isBrowserCompatible = true) {
  const container = document.createElement('div');
  container.className = `bg-white border-b border-gray-200 px-4 py-2 ${deviceScanningEnabled ? 'cursor-pointer' : ''}`;
  if (deviceScanningEnabled) {
    container.onclick = onClick;
  }
  
  container.innerHTML = `
    <div class="flex items-center gap-3 mb-2">
      <span class="text-gray-500 text-sm">To:</span>
      ${deviceScanningEnabled ? `
        <span class="text-gray-700 text-sm font-medium">${devices.length} device${devices.length !== 1 ? 's' : ''}</span>
        ${isRefreshing ? '<i data-lucide="loader" class="w-4 h-4 text-gray-500 animate-spin"></i>' : ''}
      ` : `
        <span class="text-gray-700 text-sm font-medium">All Modules</span>
      `}
      
      <!-- Hub Status Controls (right-aligned) -->
      <div class="flex items-center gap-1 ml-auto">
        <div id="bluetoothStatusButton"></div>
        <div id="settingsButton"></div>
      </div>
    </div>
    
    ${deviceScanningEnabled ? `
      <!-- Device Icons or Placeholder -->
      <div class="device-icons-container flex items-center -space-x-2 mb-2" style="min-height: 48px;">
        <div class="device-avatars flex items-center -space-x-2"></div>
        <div class="flex-1"></div>
        <button class="flex items-center gap-1 text-xs cursor-pointer px-2 py-1 rounded transition-colors touchable"  style="width: 80px" id="updateTimeBtn">
          <i data-lucide="clock" class="w-3 h-3"></i>
          <span id="updateTime"></span>
        </button>
      </div>
      
      <div class="flex items-center gap-3">
        <span class="text-xs text-gray-500 whitespace-nowrap">Near</span>
        <input type="range" class="flex-1 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-gray-600" 
               min="1" max="100" step="1" value="${range}">
        <span class="text-xs text-gray-500 whitespace-nowrap">Far</span>
        <span class="text-xs font-medium text-gray-700 text-right whitespace-nowrap" style="width: 50px">${getRangeLabel(range)}</span>
      </div>
    ` : ''}
  `;
  
  // Add device avatars or placeholder (only if device scanning enabled)
  if (deviceScanningEnabled) {
    const avatarsContainer = container.querySelector('.device-avatars');
    
    if (avatarsContainer) {
      if (devices.length === 0) {
        // Show placeholder when no devices
        const placeholder = document.createElement('div');
        placeholder.className = 'w-12 h-12 rounded-full flex items-center justify-center border-2 border-gray-200 bg-white';
        placeholder.innerHTML = '<i data-lucide="plug" class="w-6 h-6 text-gray-300"></i>';
        avatarsContainer.appendChild(placeholder);
      } else {
        // Show actual device icons
        const maxVisible = 5;
        devices.slice(0, maxVisible).forEach(device => {
          const wrapper = document.createElement('div');
          wrapper.className = 'border-2 border-white rounded-full';
          wrapper.appendChild(getDeviceIcon(device.type, 'medium'));
          avatarsContainer.appendChild(wrapper);
        });
      }
    }
    
    // Update timestamp display
    const updateTimeBtn = container.querySelector('#updateTimeBtn');
    const updateTimeSpan = container.querySelector('#updateTime');
    if (updateTimeBtn && updateTimeSpan) {
      if (lastUpdateTime) {
        const relTime = getRelativeTime(lastUpdateTime);
        updateTimeSpan.textContent = relTime;
        
        // Color red if > 5 minutes old
        const ageMinutes = (new Date() - lastUpdateTime) / 60000;
        if (ageMinutes > 5) {
          updateTimeSpan.className = 'text-red-600 font-medium';
        } else {
          updateTimeSpan.className = 'text-gray-600';
        }
      } else {
        updateTimeSpan.textContent = 'never';
        updateTimeSpan.className = 'text-gray-400';
      }
      
      // Click timestamp to refresh
      updateTimeBtn.onclick = (e) => {
        e.stopPropagation();
        onRefresh();
      };
    }
    
    // Range slider handler - trigger refresh on change
    const slider = container.querySelector('input[type="range"]');
    if (slider) {
      slider.onclick = (e) => e.stopPropagation();
      slider.onchange = (e) => {
        onRangeChange(parseInt(e.target.value));
        onRefresh();
      };
    }
  }
  
  // Add BLE status and settings buttons
  const bluetoothButtonContainer = container.querySelector('#bluetoothStatusButton');
  const settingsButtonContainer = container.querySelector('#settingsButton');
  
  const bluetoothButton = createBluetoothStatusButton(hubConnected, hubDeviceName, onHubConnect, onHubDisconnect, pythonReady, isBrowserCompatible);
  const settingsButton = createSettingsButton(onSettingsClick);
  
  bluetoothButtonContainer.appendChild(bluetoothButton);
  settingsButtonContainer.appendChild(settingsButton);
  
  return container;
}