/**
 * Playground Control App - Recipient Bar Component
 */

import { getDeviceIcon } from './icons.js';
import { getRangeLabel } from '../state/store.js';
import { getRelativeTime } from '../utils/helpers.js';

export function createRecipientBar(devices, range, lastUpdateTime, onRangeChange, onClick, onRefresh) {
  const container = document.createElement('div');
  container.className = 'bg-white border-b border-gray-200 px-4 py-2 cursor-pointer';
  container.onclick = onClick;
  
  container.innerHTML = `
    <div class="flex items-center gap-3 mb-2">
      <span class="text-gray-500 text-sm">To:</span>
      <span class="text-gray-700 text-sm font-medium">${devices.length} device${devices.length !== 1 ? 's' : ''}</span>
    </div>
    <div class="flex items-center gap-3 mb-2">
      <div class="device-avatars flex items-center -space-x-2"></div>
      <div class="flex-1"></div>
      <button class="flex items-center gap-1 text-xs cursor-pointer hover:bg-gray-100 px-2 py-1 rounded transition-colors"  style="width: 80px" id="updateTimeBtn">
        <i data-lucide="clock" class="w-3 h-3"></i>
        <span id="updateTime"></span>
      </button>
    </div>
    <div class="flex items-center gap-3">
      <span class="text-xs text-gray-500 whitespace-nowrap">Near</span>
      <input type="range" class="flex-1 h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-gray-600" 
             min="1" max="100" step="1" value="${range}">
      <span class="text-xs text-gray-500 whitespace-nowrap">Far</span>
      <span class="text-xs font-medium text-gray-700 text-right whitespace-nowrap" style="width: 50px">${getRangeLabel(range)}</span>
    </div>
  `;
  
  // Add device avatars
  const avatarsContainer = container.querySelector('.device-avatars');
  const maxVisible = 5;
  devices.slice(0, maxVisible).forEach(device => {
    const wrapper = document.createElement('div');
    wrapper.className = 'border-2 border-white rounded-full';
    wrapper.appendChild(getDeviceIcon(device.type, 'medium'));
    avatarsContainer.appendChild(wrapper);
  });
  
  // Update timestamp display
  const updateTimeBtn = container.querySelector('#updateTimeBtn');
  const updateTimeSpan = container.querySelector('#updateTime');
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
  
  // Range slider handler - trigger refresh on change
  const slider = container.querySelector('input[type="range"]');
  slider.onclick = (e) => e.stopPropagation();
  slider.onchange = (e) => {
    onRangeChange(parseInt(e.target.value));
    onRefresh();
  };
  
  return container;
}