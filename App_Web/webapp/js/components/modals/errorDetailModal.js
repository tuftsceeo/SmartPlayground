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
    const actions = errorData.actions || []; // New: support for action buttons
    
    modal.innerHTML = `
        <div class="bg-white rounded-xl p-6 max-w-sm mx-auto shadow-xl border border-gray-200 text-center" onclick="event.stopPropagation()">
            <div class="flex flex-col">
                <!-- Header with Icon (matching welcome state style) -->
                <div class="mb-3 flex justify-center">
                    <div class="w-16 h-16 rounded-full bg-gradient-to-br from-amber-100 to-amber-50 flex items-center justify-center">
                        <i data-lucide="alert-triangle" class="w-8 h-8 text-amber-600"></i>
                    </div>
                </div>
                
                <!-- Title -->
                <h2 class="text-lg font-bold text-gray-900 mb-3">
                    ${title}
                </h2>
                
                <!-- Message -->
                ${message ? `<p class="text-sm text-gray-600 mb-4">${message}</p>` : ''}
                
                <!-- Action Buttons (if provided) -->
                ${actions.length > 0 ? `
                <div class="space-y-3">
                    ${actions.map((action, index) => {
                        if (action.type === 'button') {
                            // Primary or secondary button (matching welcome state style)
                            const isPrimary = action.style === 'primary';
                            const isDisabled = action.disabled || false;
                            return `
                                <button data-action-id="${action.id}" ${isDisabled ? 'disabled' : ''} class="w-full ${isPrimary ? 'px-6 py-3 bg-blue-600 text-white text-base font-semibold shadow-md' : 'px-3 py-2 bg-white text-gray-600 text-xs font-normal border border-gray-300'} rounded-lg transition-colors flex items-center justify-center ${isPrimary ? 'gap-2' : 'gap-1.5'} ${isDisabled ? 'opacity-50 cursor-not-allowed' : isPrimary ? 'hover:bg-blue-700 hover:shadow-lg' : 'hover:bg-gray-50 hover:border-gray-400'}">
                                    ${action.icon ? `<i data-lucide="${action.icon}" class="${isPrimary ? 'w-5 h-5' : 'w-3.5 h-3.5'}"></i>` : ''}
                                    ${action.label}
                                </button>
                            `;
                        } else if (action.type === 'section') {
                            // Instructional section with optional button
                            const isDisabled = action.disabled || (action.button && action.button.disabled) || false;
                            return `
                                <div class="space-y-2 px-2">
                                    <p class="text-sm text-gray-600 font-medium">${action.label}</p>
                                    ${action.steps ? `
                                    <div class="space-y-2 mb-4">
                                        ${action.steps.map((step, idx) => `
                                            <div class="flex items-start gap-3 text-left">
                                                <div class="w-6 h-6 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                                                    <span class="text-xs font-bold text-blue-500">${idx + 1}</span>
                                                </div>
                                                <div class="flex-1">
                                                    <p class="text-sm text-gray-700">${step}</p>
                                                </div>
                                            </div>
                                        `).join('')}
                                    </div>
                                    ` : ''}
                                    ${action.button ? `
                                    <button data-action-id="${action.button.id}" ${isDisabled ? 'disabled' : ''} class="w-full px-6 py-3 bg-blue-600 text-white text-base font-semibold rounded-lg transition-colors shadow-md flex items-center justify-center gap-2 ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-blue-700 hover:shadow-lg'}">
                                        ${action.button.icon ? `<i data-lucide="${action.button.icon}" class="w-5 h-5"></i>` : ''}
                                        ${action.button.label}
                                    </button>
                                    ` : ''}
                                </div>
                            `;
                        }
                        return '';
                    }).join('')}
                </div>
                ` : ''}
                
                <!-- Solutions (legacy text list) -->
                ${solutions.length > 0 && actions.length === 0 ? `
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
                
                <!-- Close Button (only show if no actions provided) -->
                ${actions.length === 0 ? `
                <button id="closeBtn" class="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
                    Got it
                </button>
                ` : ''}
            </div>
        </div>
    `;
    
    // Attach event handlers
    const closeBtn = modal.querySelector('#closeBtn');
    if (closeBtn) {
        closeBtn.onclick = (e) => {
            e.stopPropagation();
            setState({ 
                showErrorDetailModal: false,
                errorDetail: null 
            });
        };
    }
    
    // Attach action button handlers
    actions.forEach(action => {
        if (action.type === 'button' && action.onClick) {
            const btn = modal.querySelector(`[data-action-id="${action.id}"]`);
            if (btn) {
                btn.onclick = (e) => {
                    e.stopPropagation();
                    action.onClick();
                };
            }
        } else if (action.type === 'section' && action.button && action.button.onClick) {
            const btn = modal.querySelector(`[data-action-id="${action.button.id}"]`);
            if (btn) {
                btn.onclick = (e) => {
                    e.stopPropagation();
                    action.button.onClick();
                };
            }
        }
    });
    
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

