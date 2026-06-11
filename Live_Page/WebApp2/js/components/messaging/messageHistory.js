/**
 * Playground Control App - Message History Component
 */

import { getCommandIcon, getSignalIcon } from '../common/icons.js';
import { getRelativeTime, countDevicesByType } from '../../utils/helpers.js';
import { getCommandLabel } from '../../utils/constants.js';
import { createWelcomeState } from '../states/welcomeState.js';
import { createConnectedEmptyState } from '../states/connectedEmptyState.js';
import HubSetupModal from '../modals/hubSetupModal.js';

function isRenderableMessage(message) {
  if (!message) return false;
  if (message.messageType === 'bundle') return true;
  if (message.direction === 'received') return true;
  if (message.direction === 'system') return true;
  return Boolean(message.command && message.command.trim() !== '');
}

function batteryLevelFromPct(batteryPct) {
  if (batteryPct === null || batteryPct === undefined) return null;
  const pct = Number(batteryPct);
  if (Number.isNaN(pct)) return null;
  if (pct >= 75) return 'full';
  if (pct >= 50) return 'high';
  if (pct >= 25) return 'medium';
  return 'low';
}

function createReceivedBubble(message, onMessageClick) {
  const bubble = document.createElement('div');
  bubble.className = 'bg-slate-100 text-gray-900 rounded-2xl rounded-bl-sm shadow-md p-3 mr-auto max-w-[85%] cursor-pointer message-bubble';

  const title = document.createElement('div');
  title.className = 'font-medium mb-1';
  title.textContent = message.wandName || message.mac || 'Wand';

  const row = document.createElement('div');
  row.className = 'flex items-center justify-between gap-2';

  const statusRow = document.createElement('div');
  statusRow.className = 'flex items-center gap-2 text-xs text-gray-600';

  const batteryPct = message.battery !== null && message.battery !== undefined
    ? Math.round(message.battery)
    : '?';
  const batterySpan = document.createElement('span');
  batterySpan.textContent = 'Battery: ' + batteryPct + '%';
  statusRow.appendChild(batterySpan);

  const signalIcon = getSignalIcon(message.signalLevel);
  signalIcon.className = signalIcon.className.replace('w-4 h-4', 'w-5 h-5');
  statusRow.appendChild(signalIcon);

  const timeSpan = document.createElement('div');
  timeSpan.className = 'text-xs opacity-60';
  timeSpan.textContent = getRelativeTime(message.timestamp);

  row.appendChild(statusRow);
  row.appendChild(timeSpan);

  bubble.appendChild(title);
  bubble.appendChild(row);
  bubble.onclick = () => onMessageClick(message);
  return bubble;
}

function createBundleBubble(message, onMessageClick) {
  const bubble = document.createElement('div');
  bubble.className = 'bg-indigo-50 text-indigo-900 rounded-2xl rounded-bl-sm shadow-md p-3 mr-auto max-w-[85%] cursor-pointer message-bubble';
  bubble.innerHTML = `
    <div class="font-medium mb-1">${message.count} wands responded</div>
    <div class="text-xs opacity-70">Tap to view device list</div>
  `;
  bubble.onclick = () => onMessageClick(message);
  return bubble;
}

function createSystemBubble(message) {
  const bubble = document.createElement('div');
  bubble.className = 'bg-gray-100 text-gray-600 rounded-2xl rounded-bl-sm shadow-sm p-3 mr-auto max-w-[85%] text-sm message-bubble';
  bubble.textContent = message.text || '';
  return bubble;
}

export function createMessageHistory(messages, onMessageClick, hubConnected = false, onHubConnect = null, connectionMode = 'ble', pythonReady = false) {
  const container = document.createElement('div');

  const validMessages = messages.filter(isRenderableMessage);

  const handleSetupHub = async () => {
    console.log('Setup Hub clicked (from welcome state)');

    try {
      if (!navigator.serial) {
        alert('Web Serial API not available. Please use Chrome or Edge browser.');
        return;
      }

      const modal = new HubSetupModal();
      await modal.show();
    } catch (error) {
      console.error('Error setting up hub:', error);
      alert('Error: ' + error.message);
    }
  };

  if (validMessages.length === 0 && !hubConnected && onHubConnect) {
    return createWelcomeState(onHubConnect, handleSetupHub, pythonReady);
  }

  if (validMessages.length === 0) {
    return createConnectedEmptyState(() => {
      const messageInput = document.querySelector('#messageInput');
      if (messageInput) {
        messageInput.focus();
        messageInput.click();
      }
    });
  }

  container.className = 'flex-1 overflow-y-auto p-3 space-y-2 bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 message-history';

  validMessages.forEach(message => {
    if (message.messageType === 'bundle') {
      container.appendChild(createBundleBubble(message, onMessageClick));
      return;
    }
    if (message.direction === 'system') {
      container.appendChild(createSystemBubble(message));
      return;
    }
    if (message.direction === 'received') {
      container.appendChild(createReceivedBubble(message, onMessageClick));
      return;
    }

    const bubble = document.createElement('div');
    bubble.className = 'bg-white text-gray-900 rounded-2xl rounded-br-sm shadow-md p-3 ml-auto max-w-[85%] cursor-pointer message-bubble flex items-start gap-2';
    bubble.onclick = () => onMessageClick(message);

    const commandLabel = getCommandLabel(message.command);
    const icon = getCommandIcon(commandLabel, 'small');
    if (icon && icon instanceof Node) {
      bubble.appendChild(icon);
    }

    const { moduleCount, extensionCount, buttonCount } = countDevicesByType(message.modules);

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
