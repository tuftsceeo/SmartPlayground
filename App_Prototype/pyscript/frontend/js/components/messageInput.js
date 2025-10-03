/**
 * Playground Control App - Message Input Component
 */

import { getCommandIcon } from './icons.js';
import { COMMANDS } from '../utils/constants.js';

export function createMessageInput(currentMessage, showPalette, canSend, onInputClick, onCommandSelect, onClearMessage, onSendMessage) {
  const container = document.createElement('div');
  container.className = 'bg-white border-t border-gray-200';
  
  container.innerHTML = `
    <div class="flex items-center gap-2 p-3">
      <div class="flex-1 bg-gray-100 rounded-full px-4 py-2.5 flex items-center gap-2 cursor-text" id="messageInput">
        ${currentMessage 
          ? `<div id="commandIcon"></div><span class="text-gray-800 text-sm flex-1">${currentMessage}</span><button class="w-5 h-5 rounded-full bg-gray-300 hover:bg-gray-400 flex items-center justify-center transition-colors flex-shrink-0" id="clearBtn"><i data-lucide="x" class="w-3 h-3 text-gray-600"></i></button>`
          : '<span class="text-gray-400 text-sm">Select a command...</span>'
        }
      </div>
      <button class="w-10 h-10 rounded-full flex items-center justify-center transition-all ${canSend ? 'bg-blue-500 hover:bg-blue-600 text-white' : 'bg-gray-300 text-gray-500 cursor-not-allowed'}" id="sendBtn" ${!canSend ? 'disabled' : ''}>
        <i data-lucide="send" class="w-4 h-4"></i>
      </button>
    </div>
    <div class="command-palette transition-all duration-300 ease-out ${showPalette ? 'max-h-80 opacity-100' : 'max-h-0 opacity-0 overflow-hidden'}">
      <div class="flex flex-wrap justify-evenly gap-3 px-2 pb-3 max-h-80 overflow-y-auto" id="commands"></div>
    </div>
  `;
  
  // Add command icon if message selected
  if (currentMessage) {
    const iconContainer = container.querySelector('#commandIcon');
    iconContainer.appendChild(getCommandIcon(currentMessage, 'small'));
  }
  
  // Event handlers
  container.querySelector('#messageInput').onclick = onInputClick;
  
  if (currentMessage) {
    container.querySelector('#clearBtn').onclick = (e) => {
      e.stopPropagation();
      onClearMessage();
    };
  }
  
  container.querySelector('#sendBtn').onclick = onSendMessage;
  
  // Add command buttons
  const commandsContainer = container.querySelector('#commands');
  COMMANDS.forEach(command => {
    const btn = document.createElement('button');
    btn.className = 'bg-gray-100 rounded-2xl p-3 flex-shrink-0 hover:bg-gray-200 transition-all active:scale-95 flex flex-col items-center gap-2';
    btn.onclick = () => onCommandSelect(command);
    
    btn.appendChild(getCommandIcon(command.label, 'large'));
    btn.innerHTML += `<span class="text-xs text-gray-600 font-medium whitespace-nowrap">${command.label}</span>`;
    
    commandsContainer.appendChild(btn);
  });
  
  return container;
}