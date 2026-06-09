/**
 * Permission Blocked Modal
 * 
 * Shows when browser supports Web Serial but permission dialog is blocked.
 */

export function createPermissionBlockedModal(onDismiss, onRetry) {
    const modal = document.createElement('div');
    modal.className = 'absolute inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4';
    
    modal.innerHTML = `
        <div class="bg-white rounded-2xl p-6 max-w-md mx-auto shadow-2xl" onclick="event.stopPropagation()">
            <div class="flex flex-col items-center text-center">
                <!-- Warning Icon -->
                <div class="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center mb-4">
                    <i data-lucide="shield-alert" class="w-8 h-8 text-amber-600"></i>
                </div>
                
                <!-- Heading -->
                <h2 class="text-lg font-semibold text-gray-900 mb-2">
                    Device Selection Blocked
                </h2>
                
                <!-- Description -->
                <p class="text-sm text-gray-600 mb-4 leading-relaxed">
                    Your browser supports USB connections, but the device selection dialog was blocked.
                    This usually happens due to popup blockers or permission settings.
                </p>
                
                <!-- Troubleshooting Steps -->
                <div class="bg-gray-50 rounded-lg p-4 mb-4 w-full text-left">
                    <p class="text-xs font-semibold text-gray-700 mb-3">Try these steps:</p>
                    <div class="space-y-2.5 text-xs text-gray-600">
                        <div class="flex items-start gap-2">
                            <div class="w-5 h-5 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                                <span class="text-xs font-bold text-blue-600">1</span>
                            </div>
                            <div>
                                <span class="font-medium text-gray-900">Check popup blockers</span><br/>
                                Look for a blocked popup icon in your browser's address bar
                            </div>
                        </div>
                        
                        <div class="flex items-start gap-2">
                            <div class="w-5 h-5 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                                <span class="text-xs font-bold text-blue-600">2</span>
                            </div>
                            <div>
                                <span class="font-medium text-gray-900">Check permissions</span><br/>
                                Click the lock icon in the address bar and allow serial port access
                            </div>
                        </div>
                        
                        <div class="flex items-start gap-2">
                            <div class="w-5 h-5 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                                <span class="text-xs font-bold text-blue-600">3</span>
                            </div>
                            <div>
                                <span class="font-medium text-gray-900">User gesture required</span><br/>
                                Make sure you clicked the Connect button directly (don't use automated scripts)
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Action Buttons -->
                <div class="flex gap-2 w-full">
                    <button id="retryBtn" class="flex-1 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2">
                        <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                        Try Again
                    </button>
                    <button id="dismissBtn" class="flex-1 px-4 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium rounded-lg transition-colors">
                        Close
                    </button>
                </div>
                
                <!-- Additional Help -->
                <div class="mt-4 text-xs text-gray-500">
                    Still having issues? Check your browser's site permissions for this page.
                </div>
            </div>
        </div>
    `;
    
    // Attach event handlers
    const retryBtn = modal.querySelector('#retryBtn');
    const dismissBtn = modal.querySelector('#dismissBtn');
    
    if (retryBtn) {
        retryBtn.onclick = () => {
            modal.remove();
            if (onRetry) onRetry();
        };
    }
    
    if (dismissBtn) {
        dismissBtn.onclick = () => {
            modal.remove();
            if (onDismiss) onDismiss();
        };
    }
    
    // Allow clicking backdrop to dismiss
    modal.onclick = (e) => {
        if (e.target === modal) {
            modal.remove();
            if (onDismiss) onDismiss();
        }
    };
    
    return modal;
}

/**
 * Check if an error is a permission/popup blocking error
 * @param {Error|Object} error - Error object or result from Python
 * @returns {boolean} True if this is a permission blocking issue
 */
export function isPermissionBlockedError(error) {
    const errorMsg = error?.message || error?.error || String(error);
    return errorMsg.includes('No port selected by the user') ||
           errorMsg.includes('requestPort') ||
           errorMsg.includes('User gesture');
}

