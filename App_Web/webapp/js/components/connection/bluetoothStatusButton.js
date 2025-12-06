/**
 * Hub Status Button Component
 * Displays Serial/USB hub connection status with proper styling and layout stability
 */

export function createBluetoothStatusButton(isConnected, deviceName, onConnect, onDisconnect, pythonReady = true, isBrowserCompatible = true) {
    const button = document.createElement('button');
    
    // Show error state for incompatible browsers
    if (!isBrowserCompatible) {
        button.className = 'ble-status-button px-2 py-1 rounded-lg flex items-center gap-1.5 bg-red-100 cursor-not-allowed';
        button.style.width = '130px';
        button.title = "Browser not supported - Use Chrome or Edge";
        button.disabled = true;
        
        button.innerHTML = `
            <div class="status-dot w-1.5 h-1.5 rounded-full flex-shrink-0 bg-red-500"></div>
            <span class="text-xs text-red-800 font-medium flex-shrink-0">Not Supported</span>
            <div class="flex-1"></div>
            <i data-lucide="x-circle" class="w-3.5 h-3.5 flex-shrink-0 text-red-700"></i>
        `;
        
        return button;
    }
    
    // Show loading state while Python initializes
    if (!pythonReady) {
        button.className = 'ble-status-button px-2 py-1 rounded-lg flex items-center gap-1.5 bg-gray-100 cursor-wait';
        button.style.width = '130px';
        button.title = "Loading...";
        button.disabled = true;
        
        button.innerHTML = `
            <i data-lucide="loader" class="w-3.5 h-3.5 text-gray-500 animate-spin"></i>
            <span class="text-xs text-gray-600">Loading...</span>
        `;
        
        return button;
    }
    
    // Normal connected/disconnected states
    button.className = `ble-status-button px-2 py-1 rounded-lg flex items-center gap-1.5 transition-colors ${
        isConnected
            ? ''
            : 'bg-amber-100'
    }`;
    button.style.width = '130px'; // Fixed width to prevent layout shift
    button.title = isConnected ? "Disconnect Hub" : "Connect Hub (USB)";
    
    button.innerHTML = `
        <div class="status-dot w-1.5 h-1.5 rounded-full flex-shrink-0 ${
            isConnected ? 'bg-green-500 animate-pulse' : 'bg-amber-500'
        }"></div>
        <span class="status-text text-xs flex-shrink-0 ${
            isConnected ? 'text-gray-600' : 'text-amber-800 font-medium'
        }">
            ${isConnected ? 'Connected' : 'Disconnected'}
        </span>
        <div class="flex-1"></div>
        <i data-lucide="${isConnected ? 'cable' : 'plug'}" class="w-3.5 h-3.5 flex-shrink-0 ${
            isConnected ? 'text-green-600' : 'text-amber-700'
        }"></i>
    `;
    
    button.onclick = (e) => {
        e.stopPropagation();
        if (isConnected) {
            onDisconnect();
        } else {
            onConnect();
        }
    };
    
    return button;
}
