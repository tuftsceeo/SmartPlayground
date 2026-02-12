/**
 * Settings Button Component
 * Always visible settings button with proper styling
 */

export function createSettingsButton(onClick) {
    const button = document.createElement('button');
    button.className = 'w-8 h-8 flex items-center justify-center rounded-full transition-colors flex-shrink-0';
    button.title = 'Settings';
    
    button.innerHTML = '<i data-lucide="settings" class="w-4 h-4 text-gray-600"></i>';
    
    button.onclick = (e) => {
        e.stopPropagation();
        onClick();
    };
    
    return button;
}
