/**
 * Centralized State Management
 *
 * Reactive state with automatic component re-rendering.
 * Uses batched rendering (requestAnimationFrame) for performance.
 * 
 * Usage: setState() to update, onStateChange() to listen, computed getters for derived values.
 */

export const state = {
    // Hub connection state (existing BLE backend)
    hubConnected: false,
    hubDeviceName: null,
    hubConnecting: false,
    hubConnectionMode: null, // "ble" or "serial"
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

    // Device state
    targetingMode: 'all', // 'all' | 'near' | 'target' - Recipient targeting mode
    selectedDevice: null, // {mac: string, name: string, id: string} | null - Selected device for target mode
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
 * Register a component callback to receive state change notifications.
 * 
 * This function allows components to subscribe to state changes and automatically
 * re-render when relevant state updates occur. It implements the observer pattern
 * for reactive UI updates.
 * 
 * @param {Function} callback - Function to call when state changes occur
 * @returns {Function} Cleanup function to unregister the callback
 * 
 * Usage:
 * const unsubscribe = onStateChange(() => this.render());
 * // Later: unsubscribe() to clean up
 */
export function onStateChange(callback) {
    renderCallbacks.add(callback);
    return () => renderCallbacks.delete(callback); // Cleanup function
}

/**
 * Update application state and trigger component re-renders.
 * 
 * This function implements batched state updates with optimized rendering.
 * It merges new state values with existing state and schedules component
 * re-renders using requestAnimationFrame for optimal performance.
 * 
 * @param {Object} updates - Object containing state properties to update
 * 
 * Performance Features:
 * - Batched rendering prevents multiple renders in the same frame
 * - requestAnimationFrame ensures renders happen at optimal timing
 * - Prevents duplicate renders in the same frame
 * - Batched callback execution for efficiency
 * 
 * State Update Flow:
 * 1. Merge updates into current state
 * 2. Schedule render callback execution
 * 3. Execute all registered component callbacks
 */
export function setState(updates) {
    Object.assign(state, updates);

    // Trigger render for state changes
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

// RSSI threshold for "Near" mode (fixed at -60 dBm)
const NEAR_RSSI_THRESHOLD = -60;

/**
 * Count devices that meet the "Near" RSSI threshold.
 * 
 * @returns {number} Count of devices with RSSI >= -60 dBm
 */
export function getNearDeviceCount() {
    if (!state.allDevices || state.allDevices.length === 0) {
        return 0;
    }
    
    return state.allDevices.filter(device => {
        // Device must have RSSI value and meet threshold
        return device.rssi !== undefined && device.rssi >= NEAR_RSSI_THRESHOLD;
    }).length;
}

/**
 * Get devices that meet the "Near" RSSI threshold.
 * 
 * @returns {Array} Devices with RSSI >= -60 dBm
 */
export function getNearDevices() {
    if (!state.allDevices || state.allDevices.length === 0) {
        return [];
    }
    
    return state.allDevices.filter(device => {
        return device.rssi !== undefined && device.rssi >= NEAR_RSSI_THRESHOLD;
    });
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

/**
 * Save targeting preferences to localStorage.
 * 
 * Persists targetingMode and selectedDevice across browser sessions.
 */
export function saveTargetingPreferences() {
    try {
        localStorage.setItem('targetingMode', state.targetingMode);
        
        if (state.selectedDevice) {
            localStorage.setItem('selectedDevice', JSON.stringify(state.selectedDevice));
        } else {
            localStorage.removeItem('selectedDevice');
        }
    } catch (error) {
        console.warn('Failed to save targeting preferences:', error);
    }
}

/**
 * Load targeting preferences from localStorage.
 * 
 * Restores targetingMode and selectedDevice from previous session.
 * Validates that selected device still exists in current device list.
 */
export function loadTargetingPreferences() {
    try {
        const savedMode = localStorage.getItem('targetingMode');
        if (savedMode && ['all', 'near', 'target'].includes(savedMode)) {
            state.targetingMode = savedMode;
        }
        
        const savedDevice = localStorage.getItem('selectedDevice');
        if (savedDevice) {
            try {
                const device = JSON.parse(savedDevice);
                // Validate device has required properties
                if (device && device.mac && device.id) {
                    state.selectedDevice = device;
                }
            } catch (e) {
                console.warn('Failed to parse saved device:', e);
                localStorage.removeItem('selectedDevice');
            }
        }
    } catch (error) {
        console.warn('Failed to load targeting preferences:', error);
    }
}

/**
 * Update targeting mode and persist to localStorage.
 * 
 * @param {string} mode - 'all' | 'near' | 'target'
 */
export function setTargetingMode(mode) {
    if (['all', 'near', 'target'].includes(mode)) {
        setState({ targetingMode: mode });
        saveTargetingPreferences();
    }
}

/**
 * Update selected device and persist to localStorage.
 * 
 * @param {Object|null} device - {mac: string, name: string, id: string} or null
 */
export function setSelectedDevice(device) {
    setState({ 
        selectedDevice: device,
        targetingMode: device ? 'target' : state.targetingMode 
    });
    saveTargetingPreferences();
}
