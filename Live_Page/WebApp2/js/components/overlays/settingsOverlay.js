/**
 * Settings Overlay Component
 */

import { state, setState } from '../../state/store.js';

export function createSettingsOverlay(onBack) {
    const overlay = document.createElement('div');
    overlay.className = 'absolute inset-0 bg-white z-50 flex flex-col';

    overlay.innerHTML = `
        <div class="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3">
            <button class="w-9 h-9 flex items-center justify-center rounded-full shadow-md hover:shadow-lg transition-all hover:scale-110 hover:-translate-x-1 active:scale-95 bg-teal-400 hover:bg-teal-500" id="backBtn">
                <i data-lucide="arrow-left" class="w-5 h-5 text-white"></i>
            </button>
            <h2 class="text-lg font-semibold text-gray-900">Settings</h2>
        </div>
        <div class="flex-1 overflow-y-auto p-4 space-y-4">
            <div class="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
                <div class="px-4 py-3 border-b border-gray-100 bg-gray-50">
                    <div class="flex items-center gap-2">
                        <i data-lucide="telescope" class="w-5 h-5" style="color: #bf75c9;"></i>
                        <h3 class="font-semibold text-gray-900 text-base">Activities</h3>
                    </div>
                </div>
                <div class="p-4">
                    <label class="flex items-start gap-4 cursor-pointer">
                        <div class="flex-1 min-w-0">
                            <div class="font-semibold text-gray-900 text-base mb-1.5">Try New Games</div>
                            <div class="text-sm text-gray-600 leading-relaxed">
                                Show new games that are still being developed. These activities might not work perfectly yet.
                            </div>
                        </div>
                        <div class="flex-shrink-0 pt-1">
                            <input type="checkbox" id="betaGamesToggle"
                                   class="sr-only peer"
                                   ${state.showBetaGames ? 'checked' : ''}>
                            <div class="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-400"></div>
                        </div>
                    </label>
                </div>
            </div>

            <div class="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
                <div class="px-4 py-3 border-b border-gray-100 bg-gray-50">
                    <div class="flex items-center gap-2">
                        <i data-lucide="info" class="w-5 h-5" style="color: #93d5a8;"></i>
                        <h3 class="font-semibold text-gray-900 text-base">App Info</h3>
                    </div>
                </div>
                <div class="p-4">
                    <div class="flex items-center justify-between">
                        <span class="text-sm font-medium text-gray-600">Version</span>
                        <span class="text-sm font-mono font-medium text-gray-900" id="appVersion">Loading...</span>
                    </div>
                </div>
            </div>
        </div>
    `;

    const backBtn = overlay.querySelector('#backBtn');
    backBtn.onclick = onBack;

    const betaToggle = overlay.querySelector('#betaGamesToggle');
    betaToggle.onchange = (e) => {
        setState({ showBetaGames: e.target.checked });
        console.log(`Beta games ${e.target.checked ? 'enabled' : 'disabled'}`);
    };

    fetch('/version.json')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            const versionElement = overlay.querySelector('#appVersion');
            if (versionElement) {
                versionElement.textContent = data.main.full_version;
            }
        })
        .catch(error => {
            console.debug('Could not load version:', error.message);
            const versionElement = overlay.querySelector('#appVersion');
            if (versionElement) {
                versionElement.textContent = 'Unknown';
            }
        });

    return overlay;
}
