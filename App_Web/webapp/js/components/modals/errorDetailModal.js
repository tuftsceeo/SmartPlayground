/**
 * Error Detail Modal
 * 
 * Detailed error messages with troubleshooting steps (for errors needing more than a toast).
 */

import { setState } from "../../state/store.js";

export function createErrorDetailModal(errorData) {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4';
    modal.id = 'errorDetailModal';
    
    // Parse error data
    const title = errorData.title || "Error";
    const message = errorData.message || "";
    const causes = errorData.causes || [];
    const solutions = errorData.solutions || [];
    
    modal.innerHTML = `
        <div class="bg-white rounded-xl p-6 max-w-sm mx-auto shadow-xl border border-gray-200" onclick="event.stopPropagation()">
            <div class="flex flex-col">
                <!-- Header -->
                <div class="flex items-center gap-3 mb-3">
                    <div class="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
                        <i data-lucide="alert-circle" class="w-5 h-5 text-gray-700"></i>
                    </div>
                    <div class="flex-1">
                        <h2 class="text-base font-semibold text-gray-900">
                            ${title}
                        </h2>
                        ${message ? `<p class="text-xs text-gray-600 mt-0.5">${message}</p>` : ''}
                    </div>
                </div>
                
                <!-- Solutions -->
                ${solutions.length > 0 ? `
                <div class="border-t border-gray-100 pt-3 mb-4">
                    <div class="space-y-2 text-sm text-gray-700">
                        ${solutions.map((solution, index) => `
                            <div class="flex items-start gap-2">
                                <span class="text-gray-400 font-medium mt-0.5">${index + 1}.</span>
                                <span>${solution}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
                
                <!-- Action Button -->
                <button id="closeBtn" class="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
                    Got it
                </button>
            </div>
        </div>
    `;
    
    // Attach event handlers
    const closeBtn = modal.querySelector('#closeBtn');
    closeBtn.onclick = (e) => {
        e.stopPropagation();
        setState({ 
            showErrorDetailModal: false,
            errorDetail: null 
        });
    };
    
    // Close on backdrop click
    modal.onclick = (e) => {
        if (e.target === modal) {
            setState({ 
                showErrorDetailModal: false,
                errorDetail: null 
            });
        }
    };
    
    // Close on Escape key
    const handleEscape = (e) => {
        if (e.key === 'Escape') {
            setState({ 
                showErrorDetailModal: false,
                errorDetail: null 
            });
            document.removeEventListener('keydown', handleEscape);
        }
    };
    document.addEventListener('keydown', handleEscape);
    
    // Initialize Lucide icons after adding to DOM
    setTimeout(() => {
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }, 0);
    
    return modal;
}

/**
 * Helper function to show serial connection lost error
 */
export function showSerialConnectionLostError() {
    setState({
        showErrorDetailModal: true,
        errorDetail: {
            title: "Connection Lost",
            message: "USB cable disconnected or hub reset.",
            causes: [],
            solutions: [
                "Check USB cable",
                "Close other apps (Thonny, Arduino IDE)",
                "Click 'Disconnected' button to reconnect"
            ]
        }
    });
}

/**
 * Helper function to show port in use error
 */
export function showPortInUseError() {
    setState({
        showErrorDetailModal: true,
        errorDetail: {
            title: "Port In Use",
            message: "Another app is using the serial port.",
            causes: [],
            solutions: [
                "Close Thonny or Arduino IDE",
                "Close other browser tabs",
                "Try connecting again"
            ]
        }
    });
}

