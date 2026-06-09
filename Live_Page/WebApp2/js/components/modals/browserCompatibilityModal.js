/**
 * Browser Compatibility Modal
 * 
 * Blocking modal for browsers without Web Serial API.
 * Requires Chrome/Edge 89+, Opera 75+ on desktop.
 */

export function createBrowserCompatibilityModal() {
    const modal = document.createElement('div');
    modal.className = 'absolute inset-0 bg-black bg-opacity-75 z-[100] flex items-center justify-center p-4';
    modal.style.backdropFilter = 'blur(4px)';
    
    modal.innerHTML = `
        <div class="bg-white rounded-2xl p-8 max-w-md mx-auto shadow-2xl" onclick="event.stopPropagation()">
            <div class="flex flex-col items-center text-center">
                <!-- Error Icon -->
                <div class="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mb-4">
                    <i data-lucide="alert-triangle" class="w-8 h-8 text-red-600"></i>
                </div>
                
                <!-- Heading -->
                <h2 class="text-xl font-semibold text-gray-900 mb-2">Browser Not Supported</h2>
                
                <!-- Description -->
                <p class="text-sm text-gray-600 mb-6 leading-relaxed">
                    This app requires <strong>Web Serial API</strong> to connect to the hub via USB. 
                    Your current browser or device doesn't support this feature.
                </p>
                
                <!-- Supported Browsers -->
                <div class="bg-gray-50 rounded-lg p-4 mb-6 w-full">
                    <p class="text-xs font-medium text-gray-700 mb-3">Use these browsers <strong>on a desktop/laptop computer</strong>:</p>
                    <div class="space-y-2 mb-3">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-full bg-white flex items-center justify-center shadow-sm">
                                <i data-lucide="chrome" class="w-5 h-5 text-blue-600"></i>
                            </div>
                            <span class="text-sm text-gray-900 font-medium">Google Chrome (Desktop)</span>
                        </div>
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-full bg-white flex items-center justify-center shadow-sm">
                                <i data-lucide="square" class="w-5 h-5 text-blue-500"></i>
                            </div>
                            <span class="text-sm text-gray-900 font-medium">Microsoft Edge (Desktop)</span>
                        </div>
                    </div>
                </div>
                
                <!-- Current Browser Info -->
                <div class="text-xs text-gray-500 mb-4">
                    <span class="font-medium">Current browser:</span>
                    <span id="browserName" class="ml-1"></span>
                </div>
                
                <!-- Help Link -->
                <a href="https://developer.mozilla.org/en-US/docs/Web/API/Web_Serial_API#browser_compatibility" 
                   target="_blank" 
                   class="text-xs text-blue-600 hover:text-blue-700 underline">
                    Learn more about browser compatibility
                </a>
            </div>
        </div>
    `;
    
    // Detect and display browser name
    const browserNameSpan = modal.querySelector('#browserName');
    if (browserNameSpan) {
        browserNameSpan.textContent = detectBrowserName();
    }
    
    return modal;
}

/**
 * Check if the browser supports Web Serial API
 * Note: Mobile devices don't support Web Serial, even Chrome/Edge mobile
 * @returns {boolean} True if browser is compatible, false otherwise
 */
export function isBrowserCompatible() {
    // Check for Web Serial API support
    if (!('serial' in navigator)) {
        return false;
    }
    
    // Mobile devices don't support Web Serial API, even Chrome/Edge
    if (isMobileDevice()) {
        return false;
    }
    
    return true;
}

/**
 * Detect if running on a mobile device
 * @returns {boolean} True if mobile device
 */
function isMobileDevice() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || 
           (navigator.maxTouchPoints && navigator.maxTouchPoints > 1 && /Mobi/i.test(navigator.userAgent));
}

/**
 * Detect browser name for display purposes
 * @returns {string} Browser name
 */
function detectBrowserName() {
    const userAgent = navigator.userAgent;
    const isMobile = isMobileDevice();
    
    let browserName = 'Unknown Browser';
    
    if (userAgent.includes('Edg/')) {
        browserName = 'Microsoft Edge';
    } else if (userAgent.includes('Chrome/') && !userAgent.includes('Edg/')) {
        browserName = 'Google Chrome';
    } else if (userAgent.includes('Firefox/')) {
        browserName = 'Mozilla Firefox';
    } else if (userAgent.includes('Safari/') && !userAgent.includes('Chrome/')) {
        browserName = 'Safari';
    } else if (userAgent.includes('Opera/') || userAgent.includes('OPR/')) {
        browserName = 'Opera';
    }
    
    // Add mobile indicator if applicable
    if (isMobile) {
        browserName += ' (Mobile)';
    }
    
    return browserName;
}

