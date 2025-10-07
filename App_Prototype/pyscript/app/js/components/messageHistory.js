/**
 * Playground Control App - Message History Component
 */

import { getCommandIcon } from './icons.js';
import { getRelativeTime, countDevicesByType } from '../utils/helpers.js';

export function createMessageHistory(messages, onMessageClick) {
  const container = document.createElement('div');
  container.className = 'flex-1 overflow-y-auto p-3 space-y-2 bg-gray-50 message-history';
  
  // Filter out any messages with empty commands
  const validMessages = messages.filter(m => m.command && m.command.trim() !== '');
  
  if (validMessages.length === 0) {
    container.innerHTML = '<div class="text-center text-gray-400 py-12 text-sm">No messages sent yet</div>';
    return container;
  }
  
  validMessages.forEach(message => {
    const bubble = document.createElement('div');
    bubble.className = 'bg-gray-200 text-gray-900 rounded-2xl rounded-br-sm p-3 ml-auto max-w-[85%] cursor-pointer message-bubble flex items-start gap-2';
    bubble.onclick = () => onMessageClick(message);
    
    const icon = getCommandIcon(message.command, 'small');
    // Append icon first
    if (icon && icon instanceof Node) {
      bubble.appendChild(icon);
    }
    
    const { moduleCount, extensionCount, buttonCount } = countDevicesByType(message.modules);
    
    // Create content div separately to avoid innerHTML += which removes the icon
    const contentDiv = document.createElement('div');
    contentDiv.className = 'flex-1 min-w-0';
    contentDiv.innerHTML = `
        <div class="font-medium mb-1">${message.command}</div>
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-1">
            ${moduleCount > 0 ? `<div class="flex items-center gap-0.5"><div class="w-4 h-4 rounded-full bg-gray-500 flex items-center justify-center"><i data-lucide="smartphone" class="w-2.5 h-2.5 text-white"></i></div><span class="text-xs">×${moduleCount}</span></div>` : ''}
            ${extensionCount > 0 ? `<div class="flex items-center gap-0.5"><div class="w-4 h-4 rounded-full bg-gray-600 flex items-center justify-center"><i data-lucide="box" class="w-2.5 h-2.5 text-white"></i></div><span class="text-xs">×${extensionCount}</span></div>` : ''}
            ${buttonCount > 0 ? `<div class="flex items-center gap-0.5"><div class="w-4 h-4 rounded-full bg-gray-500 flex items-center justify-center"><i data-lucide="circle-dot" class="w-2.5 h-2.5 text-white"></i></div><span class="text-xs">×${buttonCount}</span></div>` : ''}
          </div>
          <div class="text-xs opacity-60">${getRelativeTime(message.timestamp)}</div>
        </div>
    `;
    
    bubble.appendChild(contentDiv);
    container.appendChild(bubble);
  });
  
  return container;
}
