/**
 * Bluetooth Status Button Component
 * Displays BLE connection status with proper styling and layout stability
 */

export function createBluetoothStatusButton(isConnected, deviceName, onConnect, onDisconnect, pythonReady = true) {
    const button = document.createElement('button');
    
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
    button.title = isConnected ? "Disconnect Bluetooth" : "Connect Bluetooth";
    
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
        <i data-lucide="bluetooth" class="w-3.5 h-3.5 flex-shrink-0 ${
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
