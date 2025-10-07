/**
 * Smart Playground Control - Centralized State Management
 *
 * This module implements a reactive state management system for the application.
 * It provides centralized state storage with automatic component re-rendering
 * when state changes occur, similar to Redux or Vuex but simpler and lighter.
 *
 * Key Features:
 * - Centralized application state in a single object
 * - Reactive updates - components automatically re-render on state changes
 * - Batched rendering using requestAnimationFrame for performance
 * - Computed values for derived state (device filtering, RSSI calculations)
 * - Component registration system for state change notifications
 * - Optimized updates for specific state changes (e.g., refresh animations)
 *
 * State Structure:
 * - Device management: allDevices, range, moduleNicknames, lastUpdateTime
 * - Connection status: hubConnected, hubDeviceName, hubConnecting
 * - UI state: overlays, modals, input states, refresh status
 * - Message system: messageHistory, currentMessage, command palette
 *
 * Usage Pattern:
 * 1. Components register with onStateChange() to receive updates
 * 2. Components call setState() to update state and trigger re-renders
 * 3. Computed functions provide derived values (getAvailableDevices, getRangeLabel)
 * 4. State changes automatically propagate to all registered components
 *
 */

export const state = {
    // Hub connection state (existing BLE backend)
    hubConnected: false,
    hubDeviceName: null,
    hubConnecting: false,
    pythonReady: false, // PyScript initialization state

    // UI state (new design features)
    showSettings: false,
    showConnectionWarning: false,
    flashMessageBox: false,

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
    isRefreshing: false,
    
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
 * Special Optimizations:
 * - isRefreshing-only updates skip full re-renders and only update button states
 * - Batched rendering prevents multiple renders in the same frame
 * - requestAnimationFrame ensures renders happen at optimal timing
 * 
 * State Update Flow:
 * 1. Merge updates into current state
 * 2. Check for optimization opportunities (isRefreshing-only)
 * 3. Schedule render callback execution
 * 4. Execute all registered component callbacks
 * 
 * Performance Features:
 * - Prevents duplicate renders in the same frame
 * - Direct DOM manipulation for specific optimizations
 * - Batched callback execution for efficiency
 */
export function setState(updates) {
    // Check if ONLY isRefreshing is being updated
    const keys = Object.keys(updates);
    const isRefreshingOnly = keys.length === 1 && keys[0] === "isRefreshing";

    Object.assign(state, updates);

    // Don't re-render for isRefreshing only - just update button
    if (isRefreshingOnly) {
        const btn = document.getElementById("refreshBtn");
        if (btn) {
            if (state.isRefreshing) {
                btn.classList.add("animate-spin");
            } else {
                btn.classList.remove("animate-spin");
            }
        }
        return; // EXIT - don't schedule render
    }

    // Always trigger render for other changes
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
 * Get list of all available devices (NO client-side filtering).
 * 
 * IMPORTANT: Filtering is done at the module level, not here!
 * 
 * When the slider changes, a PING command is sent with the RSSI threshold.
 * Only modules that can receive the hub's signal at that strength respond.
 * This ensures the device list only contains modules that can actually
 * receive commands at the current range setting.
 * 
 * @returns {Array} All devices from last PING response
 * 
 * Why No Client-Side Filtering:
 * - Hub's RSSI receiving FROM modules ≠ modules' RSSI receiving FROM hub
 * - What matters: Can modules receive hub's commands?
 * - Solution: Modules self-filter by only responding if RSSI is strong enough
 * 
 * Usage:
 * const availableDevices = getAvailableDevices();
 * // Returns all devices that responded to last PING at current range
 */
export function getAvailableDevices() {
    // Check hub connection first - return empty array if disconnected
    if (!state.hubConnected) {
        return [];
    }
    
    // Return all devices from last refresh - they've already been filtered
    // by the PING command sent with RSSI threshold
    return state.allDevices || [];
}
