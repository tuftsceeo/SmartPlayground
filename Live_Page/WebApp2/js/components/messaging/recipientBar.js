/**
 * Recipient Bar Component
 *
 * Top control bar: broadcast target label, connection status, settings.
 */

import { createHubStatusButton } from '../connection/hubStatusButton.js';
import { createSettingsButton } from '../common/settingsButton.js';

export function createRecipientBar(hubConnected, hubDeviceName, onHubConnect, onHubDisconnect, onSettingsClick, onDevicesClick, pythonReady = true, isBrowserCompatible = true, hubConnecting = false) {
  const container = document.createElement('div');
  container.className = 'bg-white border-b border-gray-200 px-4 py-2';

  container.innerHTML = `
    <div class="flex items-center gap-3">
      <span class="text-gray-500 text-sm">To:</span>
      <span class="text-gray-700 text-sm font-medium">All Wands</span>

      <div class="flex items-center gap-1 ml-auto">
        <div id="hubStatusButton"></div>
        ${hubConnected ? `
        <button class="w-8 h-8 flex items-center justify-center rounded-full transition-colors flex-shrink-0" id="devicesBtn" title="Devices">
          <i data-lucide="smartphone" class="w-4 h-4 text-gray-600"></i>
        </button>` : ''}
        <div id="settingsButton"></div>
      </div>
    </div>
  `;

  const hubStatusButtonContainer = container.querySelector('#hubStatusButton');
  const settingsButtonContainer = container.querySelector('#settingsButton');
  const devicesBtn = container.querySelector('#devicesBtn');

  const hubStatusButton = createHubStatusButton(hubConnected, hubDeviceName, onHubConnect, onHubDisconnect, pythonReady, isBrowserCompatible, hubConnecting);
  const settingsButton = createSettingsButton(onSettingsClick);

  if (devicesBtn && onDevicesClick) {
    devicesBtn.onclick = onDevicesClick;
  }

  hubStatusButtonContainer.appendChild(hubStatusButton);
  settingsButtonContainer.appendChild(settingsButton);

  return container;
}
