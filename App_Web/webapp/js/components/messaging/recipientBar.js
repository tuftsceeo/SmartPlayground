/**
 * Recipient Bar Component
 * 
 * Top control bar: device targeting, device icons, connection status, settings.
 * Tap "To:" area to open recipient selection modal.
 */

import { getDeviceIcon } from '../common/icons.js';
import { getNearDeviceCount, getNearDevices } from '../../state/store.js';
import { getRelativeTime } from '../../utils/helpers.js';
import { createBluetoothStatusButton } from '../connection/bluetoothStatusButton.js';
import { createSettingsButton } from '../common/settingsButton.js';

export function createRecipientBar(devices, targetingMode, selectedDevice, lastUpdateTime, onRecipientClick, onDeviceListClick, hubConnected, hubDeviceName, onHubConnect, onHubDisconnect, onSettingsClick, pythonReady = true, deviceScanningEnabled = false, isBrowserCompatible = true) {
  const container = document.createElement('div');
  container.className = 'bg-white border-b border-gray-200 px-4 py-3';
  
  // Get recipient label based on targeting mode
  let recipientLabel = 'All Modules';
  if (deviceScanningEnabled) {
    if (targetingMode === 'all') {
      recipientLabel = 'All Devices';
    } else if (targetingMode === 'near') {
      const nearCount = getNearDeviceCount();
      recipientLabel = `Near (${nearCount})`;
    } else if (targetingMode === 'target' && selectedDevice) {
      recipientLabel = selectedDevice.name || selectedDevice.id;
    } else {
      recipientLabel = 'All Devices'; // Fallback
    }
  }
  
  container.innerHTML = `
    <div class="flex items-center gap-3 mb-2">
      <!-- Clickable recipient selector -->
      ${deviceScanningEnabled ? `
        <button class="flex items-center gap-2 hover:bg-gray-50 rounded-lg px-2 py-1 -ml-2 transition-colors" id="recipientBtn">
          <span class="text-gray-500 text-sm">To:</span>
          <span class="text-gray-900 text-sm font-medium" id="recipientLabel">${recipientLabel}</span>
          <i data-lucide="chevron-down" class="w-4 h-4 text-gray-400"></i>
        </button>
      ` : `
        <span class="text-gray-500 text-sm">To:</span>
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
      <div class="device-icons-container flex items-center justify-between" style="min-height: 40px;">
        <div class="device-avatars flex items-center -space-x-2"></div>
        
        <button class="flex items-center gap-1 text-xs text-gray-500 hover:bg-gray-100 px-2 py-1 rounded transition-colors" id="updateTimeBtn">
          <i data-lucide="clock" class="w-3 h-3"></i>
          <span id="updateTime"></span>
        </button>
      </div>
    ` : ''}
  `;
  
  // Add recipient button click handler
  if (deviceScanningEnabled) {
    const recipientBtn = container.querySelector('#recipientBtn');
    if (recipientBtn) {
      recipientBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (onRecipientClick) {
          onRecipientClick();
        }
      });
    }
  }
  
  // Add device avatars or placeholder (only if device scanning enabled)
  if (deviceScanningEnabled) {
    const avatarsContainer = container.querySelector('.device-avatars');
    
    if (avatarsContainer) {
      // Filter devices based on targeting mode
      let displayDevices = [];
      
      if (targetingMode === 'all') {
        displayDevices = devices;
      } else if (targetingMode === 'near') {
        displayDevices = getNearDevices();
      } else if (targetingMode === 'target' && selectedDevice) {
        // Show only the selected device
        displayDevices = devices.filter(d => d.mac === selectedDevice.mac || d.id === selectedDevice.id);
      }
      
      if (displayDevices.length === 0) {
        // Show placeholder
        const placeholder = document.createElement('div');
        if (devices.length === 0) {
          // No devices at all - show searching indicator
          placeholder.className = 'w-10 h-10 rounded-full flex items-center justify-center border-2 border-gray-200 bg-white';
          const recentUpdate = lastUpdateTime && (new Date() - lastUpdateTime) < 35000;
          const animateClass = recentUpdate ? 'animate-spin' : '';
          placeholder.innerHTML = `<i data-lucide="loader" class="w-5 h-5 text-gray-400 ${animateClass}"></i>`;
        } else {
          // Devices exist but none match filter - show message
          placeholder.className = 'text-xs text-gray-400 italic';
          placeholder.textContent = 'No devices in range';
        }
        avatarsContainer.appendChild(placeholder);
      } else {
        // Show actual device icons (filtered)
        const maxVisible = 5;
        displayDevices.slice(0, maxVisible).forEach(device => {
          const wrapper = document.createElement('div');
          wrapper.className = 'border-2 border-white rounded-full';
          wrapper.appendChild(getDeviceIcon(device.type, 'medium'));
          wrapper.title = device.name || device.id;
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
      
      // Click timestamp to open device list
      updateTimeBtn.onclick = (e) => {
        e.stopPropagation();
        if (onDeviceListClick) {
          onDeviceListClick();
        }
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