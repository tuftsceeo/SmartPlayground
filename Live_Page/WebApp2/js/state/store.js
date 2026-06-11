/**
 * Centralized State Management
 *
 * Reactive state with batched rendering for performance.
 */

export const state = {
    // Hub connection state
    hubConnected: false,
    hubDeviceName: null,
    hubConnecting: false,
    hubConnectionMode: null,
    hubValidated: false,
    hubVersion: null,
    hubMac: null,
    hubValidationEnabled: true,
    pythonReady: false,

    // Browser compatibility
    isBrowserCompatible: true,

    // UI state
    showSettings: false,
    showConnectionWarning: false,
    flashMessageBox: false,
    showBrowserCompatibilityModal: false,
    showPermissionBlockedModal: false,
    showErrorDetailModal: false,
    errorDetail: null,

    // Beta games toggle (webapp setting)
    showBetaGames: false,

    // Message state
    messageHistory: [],
    currentMessage: "",

    // Device status (updated by Ask Device Status poll)
    devices: [],
    lastPolledTime: null,
    showDeviceList: false,
    pollActive: false,

    // UI state
    showCommandPalette: false,
    showMessageDetails: false,
    viewingMessage: null,

    connectionLastChecked: null
};

const renderCallbacks = new Set();
let renderScheduled = false;

export function onStateChange(callback) {
    renderCallbacks.add(callback);
    return () => renderCallbacks.delete(callback);
}

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
