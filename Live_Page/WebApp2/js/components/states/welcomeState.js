/**
 * Welcome State Component
 * 
 * Onboarding splash screen for new users.
 */

import HubSetupModal from '../modals/hubSetupModal.js';
import { state } from '../../state/store.js';

export function createWelcomeState(onConnect, onSetupHub, pythonReady = false) {
    const container = document.createElement('div');
    container.className = 'flex-1 flex items-center justify-center p-4 bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 overflow-y-auto';
    
    const isDisabled = !pythonReady || state.hubConnecting;
    
    container.innerHTML = `
        <div class="max-w-md mx-auto w-full space-y-4">
            <!-- Welcome Header -->
            <div class="text-center space-y-2">
                <div class="flex justify-center">
                    <div class="w-16 h-16 rounded-full flex items-center justify-center shadow-md" style="background-color: #a082cf;">
                        <i data-lucide="sparkles" class="w-8 h-8 text-white"></i>
                    </div>
                </div>
                
                <h1 class="text-xl font-bold text-gray-900">
                    Welcome to Smart Playground!
                </h1>
                
                <p class="text-sm text-gray-600 px-2">
                    Control your plushies and create fun play experiences.
                </p>
            </div>
            
            <!-- Learn More Button - Prominent -->
            <a 
                href="https://sites.tufts.edu/smartplayground/" 
                target="_blank" 
                rel="noopener noreferrer"
                class="block w-full px-4 py-3 text-white text-sm font-semibold rounded-lg shadow-md transition-all hover:shadow-lg hover:scale-[1.01] active:scale-[0.99]"
                style="background-color: #bf75c9;"
                onmouseover="this.style.backgroundColor='#af65b9'"
                onmouseout="this.style.backgroundColor='#bf75c9'"
            >
                <div class="flex items-center justify-center gap-2">
                    <i data-lucide="external-link" class="w-5 h-5"></i>
                    <span>Learn More About This Project</span>
                </div>
            </a>
            
            <!-- Getting Started Card -->
            <div class="bg-white rounded-xl shadow-md p-4 space-y-3">
                <h2 class="text-base font-bold text-gray-900 text-center">
                    Getting Started
                </h2>
                
                <!-- Connection Steps -->
                <div class="space-y-2">
                    <div class="flex items-center gap-2.5">
                        <div class="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm bg-teal-400">
                            <span class="text-xs font-bold text-white">1</span>
                        </div>
                        <p class="text-sm text-gray-700">
                            Connect control module via USB
                        </p>
                    </div>
                    
                    <div class="flex items-center gap-2.5">
                        <div class="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm bg-blue-400">
                            <span class="text-xs font-bold text-white">2</span>
                        </div>
                        <p class="text-sm text-gray-700">
                            Choose an option below to continue
                        </p>
                    </div>
                </div>
                
                <!-- Action Buttons -->
                <div class="space-y-2 pt-1">
                    <button 
                        id="welcomeConnectBtn" 
                        ${isDisabled ? 'disabled' : ''} 
                        class="w-full px-4 py-3 bg-blue-400 hover:bg-blue-500 text-white text-sm font-semibold rounded-lg transition-all shadow-md flex items-center justify-center gap-2 ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:shadow-lg hover:scale-[1.01] active:scale-[0.99]'}"
                    >
                        <i data-lucide="plug" class="w-5 h-5"></i>
                        ${!pythonReady ? 'Initializing...' : state.hubConnecting ? 'Connecting...' : 'Connect to Existing Controller'}
                    </button>
                    
                    <button 
                        id="welcomeSetupBtn" 
                        ${isDisabled ? 'disabled' : ''} 
                        class="w-full px-4 py-2.5 bg-white text-gray-700 text-sm font-medium rounded-lg transition-all border-2 border-gray-200 flex items-center justify-center gap-2 ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-gray-300 hover:bg-gray-50 hover:scale-[1.01] active:scale-[0.99]'}"
                    >
                        <i data-lucide="upload-cloud" class="w-4 h-4"></i>
                        ${state.hubConnecting ? 'Connecting...' : 'Setup or Update Controller Software'}
                    </button>
                </div>
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