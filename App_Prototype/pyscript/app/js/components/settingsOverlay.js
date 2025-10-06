/**
 * Settings Overlay Component
 * Basic settings overlay with placeholder content
 */

export function createSettingsOverlay(onBack) {
    const overlay = document.createElement('div');
    overlay.className = 'absolute inset-0 bg-white z-50 flex flex-col';
    
    overlay.innerHTML = `
        <div class="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3">
            <button class="w-9 h-9 flex items-center justify-center rounded-full transition-colors" id="backBtn">
                <i data-lucide="arrow-left" class="w-5 h-5 text-gray-700"></i>
            </button>
            <h2 class="text-lg font-semibold text-gray-900">Settings</h2>
        </div>
        <div class="flex-1 overflow-y-auto p-4">
            <div class="text-center text-gray-400 py-12 text-sm">
                Settings placeholder
            </div>
        </div>
    `;
    
    // Event handler
    overlay.querySelector('#backBtn').onclick = onBack;
    
    return overlay;
}
