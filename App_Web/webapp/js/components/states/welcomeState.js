/**
 * Welcome State Component
 * 
 * Onboarding instructions when no hub is connected.
 */

import HubSetupModal from '../modals/hubSetupModal.js';

export function createWelcomeState(onConnect, onSetupHub, pythonReady = false) {
    const container = document.createElement('div');
    container.className = 'flex-1 flex items-center justify-center p-4 bg-gray-50 overflow-y-auto';
    
    const isDisabled = !pythonReady;
    const disabledClasses = isDisabled ? 'opacity-50 cursor-not-allowed' : '';
    
    container.innerHTML = `
        <div class="max-w-sm mx-auto text-center">
            <!-- Icon -->
            <div class="mb-3 flex justify-center">
                <div class="w-16 h-16 rounded-full bg-gradient-to-br from-blue-100 to-blue-50 flex items-center justify-center">
                    <i data-lucide="cable" class="w-8 h-8 text-blue-600"></i>
                </div>
            </div>
            
            <!-- Heading -->
            <h2 class="text-lg font-bold text-gray-900 mb-3">
                Welcome to Smart Playground Control
            </h2>
            
            <!-- Instructions -->
            <div class="space-y-2 mb-5 px-2">
                <div class="flex items-start gap-3 text-left">
                    <div class="w-6 h-6 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <span class="text-xs font-bold text-blue-500">1</span>
                    </div>
                    <div class="flex-1">
                        <p class="text-sm text-gray-700">
                            Connect ESP32 via USB
                        </p>
                    </div>
                </div>
                
                <div class="flex items-start gap-3 text-left">
                    <div class="w-6 h-6 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <span class="text-xs font-bold text-blue-500">2</span>
                    </div>
                    <div class="flex-1">
                        <p class="text-sm text-gray-700">
                            Choose connection option below
                        </p>
                    </div>
                </div>
            </div>
            
            <!-- CTA Buttons -->
            <div class="space-y-3">
                <button id="welcomeConnectBtn" ${isDisabled ? 'disabled' : ''} class="w-full px-6 py-3 bg-blue-600 text-white text-base font-semibold rounded-lg transition-colors shadow-md flex items-center justify-center gap-2 ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-blue-700 hover:shadow-lg'}">
                    <i data-lucide="plug" class="w-5 h-5"></i>
                    ${isDisabled ? 'Initializing...' : 'Connect to Existing Hub'}
                </button>
                
                <button id="welcomeSetupBtn" ${isDisabled ? 'disabled' : ''} class="w-full px-3 py-2 bg-white text-gray-600 text-xs font-normal rounded-lg transition-colors border border-gray-300 flex items-center justify-center gap-1.5 ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-50 hover:border-gray-400'}">
                    <i data-lucide="upload-cloud" class="w-3.5 h-3.5"></i>
                    Setup as New Hub (ESP32)
                </button>
            </div>
        </div>
    `;
    
    // Attach click handlers (only if Python is ready)
    const connectBtn = container.querySelector('#welcomeConnectBtn');
    if (connectBtn && onConnect && pythonReady) {
        connectBtn.onclick = onConnect;
    }
    
    const setupBtn = container.querySelector('#welcomeSetupBtn');
    if (setupBtn && onSetupHub && pythonReady) {
        setupBtn.onclick = onSetupHub;
    }
    
    return container;
}

