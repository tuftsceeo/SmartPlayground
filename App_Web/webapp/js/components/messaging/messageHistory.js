/**
 * Playground Control App - Message History Component
 */

import { getCommandIcon } from '../common/icons.js';
import { getRelativeTime, countDevicesByType } from '../../utils/helpers.js';
import { getCommandLabel } from '../../utils/constants.js';
import { createWelcomeState } from '../states/welcomeState.js';
import { createConnectedEmptyState } from '../states/connectedEmptyState.js';
import HubSetupModal from '../modals/hubSetupModal.js';

export function createMessageHistory(messages, onMessageClick, hubConnected = false, onHubConnect = null, connectionMode = 'ble', pythonReady = false) {
  const container = document.createElement('div');
  
  // Filter out any messages with empty commands
  const validMessages = messages.filter(m => m.command && m.command.trim() !== '');
  
  // Setup hub callback for welcome state (before connection)
  const handleSetupHub = async () => {
    console.log('Setup Hub clicked (from welcome state)');
    
    try {
      // Check Web Serial API availability
      if (!navigator.serial) {
        alert('Web Serial API not available. Please use Chrome or Edge browser.');
        return;
      }
      
      console.log('Opening Hub Setup modal...');
      
      // Create and show modal in loading state
      const modal = new HubSetupModal();
      await modal.show();
      
    } catch (error) {
        console.error('Error setting up hub:', error);
        alert('Error: ' + error.message);
    }
  };
  
  // Show welcome state if no messages AND not connected
  if (validMessages.length === 0 && !hubConnected && onHubConnect) {
    return createWelcomeState(onHubConnect, handleSetupHub, pythonReady);
  }
  
  // Show connected empty state if no messages but hub is connected  
  if (validMessages.length === 0) {
    return createConnectedEmptyState(() => {
      // Focus the message input field when user clicks on the empty state
      const messageInput = document.querySelector('#messageInput');
      if (messageInput) {
        messageInput.focus();
        messageInput.click(); // Trigger click to open command palette
      }
    });
  }
  
  // Show message history
  container.className = 'flex-1 overflow-y-auto p-3 space-y-2 bg-gray-50 message-history';
  
  validMessages.forEach(message => {
    const bubble = document.createElement('div');
    bubble.className = 'bg-gray-200 text-gray-900 rounded-2xl rounded-br-sm p-3 ml-auto max-w-[85%] cursor-pointer message-bubble flex items-start gap-2';
    bubble.onclick = () => onMessageClick(message);
    
    // Convert command ID to label for display and icon lookup
    const commandLabel = getCommandLabel(message.command);
    const icon = getCommandIcon(commandLabel, 'small');
    // Append icon first
    if (icon && icon instanceof Node) {
      bubble.appendChild(icon);
    }
    
    const { moduleCount, extensionCount, buttonCount } = countDevicesByType(message.modules);
    
    // Create content div separately to avoid innerHTML += which removes the icon
    const contentDiv = document.createElement('div');
    contentDiv.className = 'flex-1 min-w-0';
    contentDiv.innerHTML = `
        <div class="font-medium mb-1">${commandLabel}</div>
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
