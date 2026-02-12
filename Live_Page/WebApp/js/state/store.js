/**
 * Centralized State Management
 *
 * Reactive state with batched rendering for performance.
 */

export const state = {
    // Hub connection state (existing BLE backend)
    hubConnected: false,
    hubDeviceName: null,
    hubConnecting: false,
    hubConnectionMode: null, // "ble" or "serial"
    hubValidated: false, // Whether hub sent "ready" handshake
    hubVersion: null, // Hub firmware version from ready message
    hubMac: null, // Hub MAC address from ready message
    hubValidationEnabled: true, // Whether to validate hub on connection (disabled during setup/flashing)
    pythonReady: false, // PyScript initialization state

    // Browser compatibility
    isBrowserCompatible: true, // Web Serial API support check

    // UI state (new design features)
    showSettings: false,
    showConnectionWarning: false,
    flashMessageBox: false,
    showBrowserCompatibilityModal: false, // Blocking modal for incompatible browsers
    showPermissionBlockedModal: false, // Modal for popup/permission blocking issues
    showErrorDetailModal: false, // Modal for detailed error messages with troubleshooting
    errorDetail: null, // Error data: {title, message, causes[], solutions[]}

    // Device scanning toggle (webapp setting)
    deviceScanningEnabled: true, // Enabled by default - passive tracking via battery messages
    
    // Beta games toggle (webapp setting)
    showBetaGames: false, // Hidden by default - users can enable for testing

    // Device state
    range: 40, // 0-100 slider value (40 = "Close")
    allDevices: [],
    moduleNicknames: {},
    lastUpdateTime: null,

    // Message state
    messageHistory: [],
    currentMessage: "",

    // UI state
    showCommandPalette: false,
    showDeviceList: false,
    showMessageDetails: false,
    viewingMessage: null,
    editingDeviceId: null,
    
    // Connection state sync
    connectionLastChecked: null
};

// Render callbacks - components register themselves here
const renderCallbacks = new Set();

// Batch state updates
let updatesPending = null;
let renderScheduled = false;

/**
 * Register callback for state changes.
 * @returns {Function} Cleanup function
 */
export function onStateChange(callback) {
    renderCallbacks.add(callback);
    return () => renderCallbacks.delete(callback);
}

/**
 * Update state and trigger re-renders (batched).
 */
export function setState(updates) {
    Object.assign(state, updates);

    if (!renderScheduled) {
        renderScheduled = true;
        requestAnimationFrame(() => {
            renderCallbacks.forEach((cb) => {
                cb(state);
            });
            renderScheduled = false;
        });
    }
}

/**
 * Get computed values
 */
// Convert slider position (1-100) to RSSI threshold
function sliderToRSSI(position) {
    if (position === 100) return -999; // "All" - no cutoff
    // Map 1-99 to RSSI range: -30 (closest) to -90 (farthest)
    // Linear interpolation: position 1 = -30, position 99 = -90
    return -30 - ((position - 1) / 98) * 60;
}

// Get range label for slider position
export function getRangeLabel(position) {
    if (position === 100) return "All";
    if (position >= 75) return "Far";
    if (position >= 50) return "Distant";
    if (position >= 25) return "Close";
    if (position >= 2) return "Near";
    return "Here";
}

/**
 * Get list of all available devices from passive tracking.
 * 
 * Devices are automatically tracked via battery messages sent every 60s.
 * The hub maintains a list of recently seen devices and sends updates every 30s.
 * Devices that haven't been seen for 5+ minutes are automatically expired.
 * 
 * @returns {Array} All devices seen recently (includes battery%, RSSI, last seen time)
 * 
 * Device Information:
 * - Battery percentage (from module battery messages)
 * - RSSI signal strength (hub's reception of module signals)
 * - Last seen timestamp (for age/stale detection)
 * - Stale warning (>3 minutes = warning, >5 minutes = removed)
 * 
 * Usage:
 * const availableDevices = getAvailableDevices();
 * // Returns all devices with recent battery messages
 */
export function getAvailableDevices() {
    // Check hub connection first - return empty array if disconnected
    if (!state.hubConnected) {
        return [];
    }
    
    // Return all devices from passive tracking (updated every 30s by hub)
    return state.allDevices || [];
}
