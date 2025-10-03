/**
 * Playground Control App - Message Details Overlay
 */

import { getCommandIcon, getDeviceIcon } from './icons.js';
import { getRelativeTime, getDeviceType } from '../utils/helpers.js';

export function createMessageDetailsOverlay(message, nicknames, onClose, onResend) {
  const overlay = document.createElement('div');
  overlay.className = 'absolute inset-0 bg-white z-50 flex flex-col';
  overlay.style.display = 'none';
  
  if (!message) return overlay;
  
  overlay.innerHTML = `
    <div class="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3">
      <button class="w-9 h-9 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors" id="backBtn">
        <i data-lucide="arrow-left" class="w-5 h-5 text-gray-700"></i>
      </button>
      <h2 class="text-lg font-semibold text-gray-900">Message Details</h2>
    </div>
    
    <div class="flex-1 overflow-y-auto p-4">
      <div class="bg-gray-50 rounded-2xl p-4 space-y-4">
        <div>
          <div class="text-xs text-gray-500 mb-2">Command</div>
          <div class="flex items-center gap-3" id="commandSection">
            <span class="font-semibold text-lg">${message.command}</span>
          </div>
        </div>
        
        <div>
          <div class="text-xs text-gray-500 mb-2">Sent To</div>
          <div class="space-y-2" id="recipientsList"></div>
        </div>
        
        <div>
          <div class="text-xs text-gray-500 mb-2">Time Sent</div>
          <div class="text-sm">
            <div class="font-medium">${message.displayTime}</div>
            <div class="text-gray-600">${getRelativeTime(message.timestamp)}</div>
          </div>
        </div>
      </div>
      
      <button class="w-full mt-4 bg-gray-700 hover:bg-gray-800 text-white rounded-xl py-3 font-medium transition-colors" id="resendBtn">
        Send Again
      </button>
    </div>
  `;
  
  // Add command icon
  const commandSection = overlay.querySelector('#commandSection');
  commandSection.insertBefore(getCommandIcon(message.command, 'small'), commandSection.firstChild);
  
  // Add recipients
  const recipientsList = overlay.querySelector('#recipientsList');
  message.modules.forEach(deviceId => {
    const div = document.createElement('div');
    div.className = 'flex items-center gap-2';
    
    const type = getDeviceType(deviceId);
    div.appendChild(getDeviceIcon(type, 'small'));
    
    const displayName = nicknames[deviceId] || deviceId;
    div.innerHTML += `<span class="text-sm font-medium">${displayName}</span>`;
    
    recipientsList.appendChild(div);
  });
  
  // Event handlers
  overlay.querySelector('#backBtn').onclick = onClose;
  overlay.querySelector('#resendBtn').onclick = () => {
    onResend(message);
    onClose();
  };
  
  return overlay;
}
