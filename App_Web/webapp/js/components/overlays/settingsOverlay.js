/**
 * Settings Overlay Component
 * App settings including device scanning toggle
 */

import { state, setState } from '../../state/store.js';

export function createSettingsOverlay(onBack) {
    const overlay = document.createElement('div');
    overlay.className = 'absolute inset-0 bg-white z-50 flex flex-col';
    
    overlay.innerHTML = `
        <div class="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3">
            <button class="w-9 h-9 flex items-center justify-center rounded-full transition-colors" id="backBtn">
                <i data-lucide="arrow-left" class="w-5 h-5 text-gray-700"></i>
            </button>
            <h2 class="text-lg font-semibold text-gray-900">Settings</h2>
        </div>
        <div class="flex-1 overflow-y-auto p-4">
            <!-- Device List Section -->
            <div class="bg-white rounded-xl border border-gray-200 overflow-hidden mb-4">
                <div class="px-4 py-3 border-b border-gray-200">
                    <h3 class="font-semibold text-gray-900">Device Management</h3>
                </div>
                <div class="p-4">
                    <label class="flex items-center justify-between cursor-pointer">
                        <div class="flex-1">
                            <div class="font-medium text-gray-900">Show Device List</div>
                            <div class="text-sm text-gray-500 mt-1">
                                Display nearby modules via passive battery tracking (updates every 30s). Disable for command-only mode.
                            </div>
                        </div>
                        <div class="ml-4">
                            <input type="checkbox" id="deviceScanningToggle" 
                                   class="sr-only peer" 
                                   ${state.deviceScanningEnabled ? 'checked' : ''}>
                            <div class="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                        </div>
                    </label>
                    <div class="mt-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
                        <strong>Passive Tracking:</strong> Hub listens for battery messages (sent every 60s by modules). 
                        No active scanning = no ESP-NOW buffer overflows. Discovery time: 0-60 seconds.
                    </div>
                </div>
            </div>
            
            <!-- Version Section -->
            <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div class="px-4 py-3 border-b border-gray-200">
                    <h3 class="font-semibold text-gray-900">About</h3>
                </div>
                <div class="p-4">
                    <div class="flex items-center justify-between">
                        <span class="text-sm text-gray-500">Version</span>
                        <span class="text-sm font-mono text-gray-900" id="appVersion">Loading...</span>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Event handlers
    overlay.querySelector('#backBtn').onclick = onBack;
    
    // Toggle handler
    const toggle = overlay.querySelector('#deviceScanningToggle');
    toggle.onchange = (e) => {
        setState({ deviceScanningEnabled: e.target.checked });
        console.log(`Device scanning ${e.target.checked ? 'enabled' : 'disabled'}`);
    };
    
    // Load and display version
    fetch('/version.json')
        .then(response => response.json())
        .then(data => {
            const versionElement = overlay.querySelector('#appVersion');
            if (versionElement) {
                // Show main version (or beta if needed)
                versionElement.textContent = data.main.full_version;
            }
        })
        .catch(error => {
            console.warn('Could not load version:', error);
            const versionElement = overlay.querySelector('#appVersion');
            if (versionElement) {
                versionElement.textContent = 'Unknown';
            }
        });
    
    return overlay;
}
