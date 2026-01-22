/**
 * Connection Warning Modal Component
 * Shows when user tries to send without Bluetooth connection
 */

export function createConnectionWarningModal(onConnect, onCancel) {
    const modal = document.createElement('div');
    modal.className = 'absolute inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center';
    
    modal.innerHTML = `
        <div class="bg-white rounded-2xl p-8 mx-4 max-w-sm" onclick="event.stopPropagation()">
            <div class="flex flex-col items-center">
                <i data-lucide="bluetooth-off" class="w-12 h-12 text-gray-400 mb-4"></i>
                <div class="text-lg font-semibold text-gray-900 mb-6">Bluetooth Disconnected</div>
                <button class="w-full px-6 py-2.5 bg-amber-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2 mb-3" id="connectBtn">
                    <i data-lucide="bluetooth" class="w-4 h-4"></i>
                    Connect
                </button>
                <button class="text-sm text-gray-500 transition-colors" id="cancelBtn">
                    Cancel
                </button>
            </div>
        </div>
    `;
    
    // Event handlers
    modal.querySelector('#connectBtn').onclick = (e) => {
        e.stopPropagation();
        onConnect();
    };
    
    modal.querySelector('#cancelBtn').onclick = (e) => {
        e.stopPropagation();
        onCancel();
    };
    
    // Close on backdrop click
    modal.onclick = (e) => {
        if (e.target === modal) {
            onCancel();
        }
    };
    
    return modal;
}
