/**
 * Connection Warning Modal Component
 * Shows when user tries to send without hub connection
 */

export function createConnectionWarningModal(onConnect, onCancel) {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4';
    
    modal.innerHTML = `
        <div class="bg-white rounded-xl p-6 max-w-sm mx-auto shadow-xl border border-gray-200 text-center" onclick="event.stopPropagation()">
            <div class="flex flex-col">
                <!-- Icon matching error modal style -->
                <div class="mb-3 flex justify-center">
                    <div class="w-16 h-16 rounded-full bg-gradient-to-br from-amber-100 to-amber-50 flex items-center justify-center">
                        <i data-lucide="unplug" class="w-8 h-8 text-amber-600"></i>
                    </div>
                </div>
                
                <!-- Title -->
                <h2 class="text-lg font-bold text-gray-900 mb-3">
                    Hub Disconnected
                </h2>
                
                <!-- Message -->
                <p class="text-sm text-gray-600 mb-5">
                    Connect to a hub to send commands
                </p>
                
                <!-- Buttons -->
                <div class="space-y-3">
                    <button class="w-full px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white text-base font-semibold rounded-lg transition-colors shadow-md hover:shadow-lg flex items-center justify-center gap-2" id="connectBtn">
                        <i data-lucide="plug" class="w-5 h-5"></i>
                        Connect to Hub
                    </button>
                    <button class="text-sm text-gray-500 hover:text-gray-700 transition-colors" id="cancelBtn">
                        Cancel
                    </button>
                </div>
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
