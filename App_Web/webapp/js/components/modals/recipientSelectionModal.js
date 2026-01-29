/**
 * Recipient Selection Modal Component
 * 
 * Bottom sheet modal for selecting recipient targeting mode:
 * - All: Broadcast to all devices
 * - Near: Send to devices within RSSI threshold (-60 dBm)
 * - Target: Send to specific selected device
 */

import { state, setState, setTargetingMode, getNearDeviceCount } from "../../state/store.js";

/**
 * Create and show the recipient selection modal.
 * 
 * @param {Function} onDeviceListOpen - Callback to open device list overlay for Target mode
 */
export function showRecipientSelectionModal(onDeviceListOpen) {
    // Remove existing modal if present
    const existing = document.getElementById('recipientSelectionModal');
    if (existing) {
        existing.remove();
    }
    
    // Create and show new modal
    const modal = createRecipientSelectionModal(onDeviceListOpen);
    document.body.appendChild(modal);
    
    // Trigger animation after DOM insertion
    requestAnimationFrame(() => {
        const backdrop = modal.querySelector('.modal-backdrop');
        const panel = modal.querySelector('.modal-panel');
        
        backdrop.classList.add('show');
        setTimeout(() => panel.classList.add('show'), 10);
    });
    
    // Initialize Lucide icons
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

/**
 * Create the recipient selection modal element.
 */
function createRecipientSelectionModal(onDeviceListOpen) {
    const modal = document.createElement('div');
    modal.id = 'recipientSelectionModal';
    modal.className = 'fixed inset-0 z-50';
    
    // Get current state values
    const nearCount = getNearDeviceCount();
    const currentMode = state.targetingMode;
    const selectedDeviceName = state.selectedDevice ? state.selectedDevice.name || state.selectedDevice.id : null;
    
    modal.innerHTML = `
        <!-- Backdrop -->
        <div class="modal-backdrop fixed inset-0 bg-black bg-opacity-40 transition-opacity duration-300 opacity-0"></div>
        
        <!-- Modal Panel -->
        <div class="modal-panel fixed bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-2xl max-w-md mx-auto transform translate-y-full transition-transform duration-300 ease-out">
            <!-- Drag Handle -->
            <div class="flex justify-center pt-2 pb-1">
                <div class="w-10 h-1 bg-gray-300 rounded-full"></div>
            </div>
            
            <!-- Header -->
            <div class="px-4 py-3 border-b border-gray-200">
                <h3 class="font-semibold text-gray-900">Send To</h3>
            </div>
            
            <!-- Options -->
            <div class="p-2">
                <!-- All Devices Option -->
                <button class="mode-option w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left hover:bg-gray-50 transition-colors" data-mode="all">
                    <div class="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
                        <i data-lucide="radio" class="w-5 h-5 text-gray-600"></i>
                    </div>
                    <div class="flex-1">
                        <div class="font-medium text-gray-900">All Devices</div>
                        <div class="text-xs text-gray-500">Broadcast to everyone</div>
                    </div>
                    <i data-lucide="check" class="w-5 h-5 text-blue-500 ${currentMode === 'all' ? '' : 'opacity-0'}" id="check-all"></i>
                </button>
                
                <!-- Near Option -->
                <button class="mode-option w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left hover:bg-gray-50 transition-colors" data-mode="near">
                    <div class="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
                        <i data-lucide="circle-dot" class="w-5 h-5 text-gray-600"></i>
                    </div>
                    <div class="flex-1">
                        <div class="font-medium text-gray-900">Near</div>
                        <div class="text-xs text-gray-500" id="near-count">${nearCount} in range</div>
                    </div>
                    <i data-lucide="check" class="w-5 h-5 text-blue-500 ${currentMode === 'near' ? '' : 'opacity-0'}" id="check-near"></i>
                </button>
                
                <!-- Target Option -->
                <button class="mode-option w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left hover:bg-gray-50 transition-colors" data-mode="target">
                    <div class="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
                        <i data-lucide="user" class="w-5 h-5 text-gray-600"></i>
                    </div>
                    <div class="flex-1">
                        <div class="font-medium text-gray-900">Select Device</div>
                        <div class="text-xs text-gray-500" id="target-name">
                            ${selectedDeviceName || 'Choose one'}
                        </div>
                    </div>
                    <i data-lucide="chevron-right" class="w-5 h-5 text-gray-400"></i>
                </button>
            </div>
            
            <div class="h-8"></div>
        </div>
    `;
    
    // Add event listeners
    const backdrop = modal.querySelector('.modal-backdrop');
    const panel = modal.querySelector('.modal-panel');
    
    // Close modal on backdrop click
    backdrop.addEventListener('click', () => closeModal(modal));
    
    // Mode selection handlers
    modal.querySelectorAll('.mode-option').forEach(btn => {
        btn.addEventListener('click', function() {
            const mode = this.dataset.mode;
            
            if (mode === 'target') {
                // Open device list overlay for selection
                closeModal(modal);
                if (onDeviceListOpen) {
                    onDeviceListOpen();
                }
            } else {
                // Direct mode selection (All or Near)
                setTargetingMode(mode);
                closeModal(modal);
            }
        });
    });
    
    return modal;
}

/**
 * Close the modal with animation.
 */
function closeModal(modal) {
    const backdrop = modal.querySelector('.modal-backdrop');
    const panel = modal.querySelector('.modal-panel');
    
    backdrop.classList.remove('show');
    panel.classList.remove('show');
    
    // Remove from DOM after animation completes
    setTimeout(() => {
        modal.remove();
    }, 300);
}
