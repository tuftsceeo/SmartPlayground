/**
 * Toast Notification Component
 * Provides user-friendly error messages without intrusive alerts
 */

export function showToast(message, type = 'error', duration = 3000) {
    // Remove existing toast if any
    const existingToast = document.querySelector('.toast-notification');
    if (existingToast) {
        existingToast.remove();
    }

    const toast = document.createElement('div');
    toast.className = `toast-notification fixed top-4 right-4 z-50 px-3 py-2 rounded-lg shadow-sm border transition-all duration-300 transform translate-x-full`;
    
    // Set styling based on type - matching the app's muted color scheme
    if (type === 'error') {
        toast.className += ' bg-red-50 border-red-200 text-red-800';
    } else if (type === 'success') {
        toast.className += ' bg-green-50 border-green-200 text-green-800';
    } else if (type === 'warning') {
        toast.className += ' bg-amber-50 border-amber-200 text-amber-800';
    } else {
        toast.className += ' bg-gray-50 border-gray-200 text-gray-800';
    }

    toast.innerHTML = `
        <div class="flex items-center gap-2">
            <i data-lucide="${type === 'error' ? 'alert-circle' : type === 'success' ? 'check-circle' : 'info'}" class="w-3.5 h-3.5 flex-shrink-0"></i>
            <span class="text-xs font-medium">${message}</span>
            <button class="ml-2 text-gray-400 hover:text-gray-600 transition-colors" onclick="this.parentElement.parentElement.remove()">
                <i data-lucide="x" class="w-3 h-3"></i>
            </button>
        </div>
    `;

    document.body.appendChild(toast);

    // Animate in
    setTimeout(() => {
        toast.classList.remove('translate-x-full');
    }, 10);

    // Auto remove after duration
    setTimeout(() => {
        if (toast.parentElement) {
            toast.classList.add('translate-x-full');
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.remove();
                }
            }, 300);
        }
    }, duration);

    // Initialize icons
    if (window.lucide) {
        window.lucide.createIcons();
    }

    return toast;
}
