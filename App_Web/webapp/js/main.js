/**
 * Smart Playground Control - Main Application Controller
 * 
 * Main App class orchestrating the frontend application. Manages component
 * rendering, state synchronization, and Python backend communication.
 * 
 * Key Responsibilities:
 * - App initialization and Python integration
 * - Component lifecycle and DOM rendering
 * - State coordination with reactive updates
 * - Event handling and connection management
 * - Error handling and user feedback
 * 
 * Architecture:
 * - Functional component pattern with reactive state
 * - Event-driven Python-JavaScript communication
 * - Mobile-first responsive design
 * 
 * Dependencies:
 * - state/store.js (centralized state)
 * - utils/pyBridge.js (Python bridge)
 * - components/* (UI modules)
 */

import { state, setState, getAvailableDevices, onStateChange } from "./state/store.js";
import { PyBridge } from "./utils/pyBridge.js";

// Use global PyBridge as fallback if import fails
const PyBridgeToUse = PyBridge || window.PyBridge;

// Ensure PyBridge is available
if (!PyBridgeToUse) {
    console.error("PyBridge not available! Check module loading.");
}
import { formatDisplayTime } from "./utils/helpers.js";
import { createRecipientBar } from "./components/messaging/recipientBar.js";
import { createMessageHistory } from "./components/messaging/messageHistory.js";
import { createMessageInput } from "./components/messaging/messageInput.js";
import { createDeviceListOverlay } from "./components/overlays/deviceListOverlay.js";
import { createMessageDetailsOverlay } from "./components/overlays/messageDetailsOverlay.js";
import { createConnectionWarningModal } from "./components/modals/connectionWarningModal.js";
import { createSettingsOverlay } from "./components/overlays/settingsOverlay.js";
import { showToast } from "./components/common/toast.js";
import { createBrowserCompatibilityModal, isBrowserCompatible } from "./components/modals/browserCompatibilityModal.js";
import { createPermissionBlockedModal, isPermissionBlockedError } from "./components/modals/permissionBlockedModal.js";
import { createErrorDetailModal, showSerialConnectionLostError, showPortInUseError } from "./components/modals/errorDetailModal.js";
import HubSetupModal from "./components/modals/hubSetupModal.js";

/**
 * Unified error handler for Python backend responses.
 * 
 * @param {Object} result - Python function result with status field
 * @param {string} context - Context description for logging
 * @returns {boolean} - True if error, false if normal operation
 */
function handleError(result, context) {
    if (!result || !result.status) {
        console.error(`${context}: Invalid result format`, result);
        showToast("Unexpected response from backend", "error");
        return true;
    }
    
    // Handle different status types
    switch (result.status) {
        case "success":
        case "sent":
        case "disconnected":
            // These are successful operations, not errors
            return false;
            
        case "cancelled":
            // User cancelled - this is normal, don't show error
            console.log(`${context}: User cancelled operation`);
            return false;
            
        case "error":
            // Real error - show to user
            const errorMsg = result.error || "Unknown error";
            console.error(`${context}: ${errorMsg}`);
            showToast(`Error: ${errorMsg}`, "error");
            return true;
            
        default:
            // Unknown status - treat as error
            console.error(`${context}: Unknown status '${result.status}'`, result);
            showToast(`Unexpected status: ${result.status}`, "error");
            return true;
    }
}

/**
 * Sync connection state with Python backend (polls status and updates state).
 * 
 * @returns {Promise<boolean>} - True if state changed
 */
async function syncConnectionState() {
    try {
        const status = await PyBridgeToUse.getConnectionStatus();
        // Only log if state actually changes (reduce noise)
        
        const wasConnected = state.hubConnected;
        const wasDevice = state.hubDeviceName;
        
        // If disconnecting, cancel any pending device scans
        const newState = {
            hubConnected: status.connected,
            hubDeviceName: status.device,
            hubConnecting: false, // Clear connecting state
        };
        
        setState(newState);
        
        const stateChanged = (wasConnected !== status.connected) || (wasDevice !== status.device);
        if (stateChanged) {
            console.log(`Connection state changed: ${wasConnected}->${status.connected}, device: ${wasDevice}->${status.device}`);
        }
        
        return stateChanged;
    } catch (e) {
        console.error("Failed to sync connection state:", e);
        return false;
    }
}

class App {
    constructor() {
        this.container = document.getElementById("root");
        this.components = {};
        this._hubValidationTimeout = null;
        this.init();
    }

    async init() {
        /**
         * Initialize app: check compatibility, setup callbacks, register events, render UI.
         */
        // Check browser compatibility first
        const browserCompatible = isBrowserCompatible();
        console.log('Browser compatibility check:', browserCompatible ? '✓ Compatible' : '✗ Not compatible');
        
        // Initialize with empty device list - will be populated by Python backend
        setState({
            allDevices: [],
            lastUpdateTime: null,
            isBrowserCompatible: browserCompatible,
            showBrowserCompatibilityModal: !browserCompatible,
        });

        // Add click-outside handler for command palette
        this.setupClickOutsideHandler();

        // Wait for Python to be ready, then initialize
        this.initializePython();

        // Direct function for Python to call (with hub timestamp for age calculation)
        window.onDevicesUpdated = (devices, hubTimestamp) => {
            console.log("=" + "=".repeat(80));
            console.log("🟢 JavaScript window.onDevicesUpdated() CALLED");
            console.log(`📋 Received ${devices?.length || 0} devices from Python`);
            
            // Special logging for empty device list
            if (!devices || devices.length === 0) {
                console.log("📭 EMPTY device list - clearing all devices from UI");
            }
            
            console.log(`⏰ Hub timestamp: ${hubTimestamp}`);
            console.log(`📊 State before update: ${state.allDevices?.length || 0} devices`);
            console.log("=" + "=".repeat(80));
            
            // Process each device to calculate age and convert timestamps
            const processedDevices = devices.map((device, index) => {
                // Calculate device age in milliseconds
                const ageMs = hubTimestamp - device.last_seen;
                
                // Convert to local browser time (Date object)
                // Age = how long ago device was last seen
                // Current time - age = when device was last seen
                const lastSeenTime = new Date(Date.now() - ageMs);
                
                // Use hub's authoritative staleness flag (hub marks stale after 1 minute)
                const isStale = device.is_stale || false;
                
                console.log(`  Device ${index + 1}: ${device.name} | RSSI: ${device.rssi} | Battery: ${device.battery_pct}% | Age: ${ageMs}ms | Stale: ${isStale}`);
                
                return {
                    ...device,
                    lastSeenTime,   // Date object for getRelativeTime()
                    isStale         // Boolean for UI warning (from hub)
                };
            });
            
            console.log(`✅ Processed ${processedDevices.length} devices, updating state...`);
            
            setState({
                allDevices: processedDevices,
                lastUpdateTime: new Date(),
            });
            
            console.log(`✅ State updated! New device count: ${state.allDevices?.length || 0}`);
            
            // Confirm empty list was set
            if (processedDevices.length === 0) {
                console.log("📭 UI state now shows ZERO devices (empty list applied)");
            }
        };

        // Direct function calls only - no event listeners needed
        
        // Store reference to app methods for use in error modals and other components
        window.appHandleHubConnect = () => this.handleHubConnect();
        window.appShowHubSetup = async () => {
            const modal = new HubSetupModal();
            await modal.show();
        };

        // ⚠️ DEPRECATED: BLE connection callbacks - NOT USED
        // Bluetooth was never implemented. These are kept to prevent errors from old code.
        window.onBLEConnected = () => {
            console.error("❌ onBLEConnected called - BLE not supported");
        };

        // Hub "ready" handshake validation (called when hub sends ready message)
        window.onHubReady = (data) => {
            console.log("✅ Hub ready handshake received:", data);
            console.log(`  Version: ${data?.version}`);
            console.log(`  MAC: ${data?.mac}`);
            console.log(`  Timestamp: ${data?.timestamp}`);
            
            // Store hub info and mark as validated
            state.hubVersion = data?.version;
            state.hubMac = data?.mac;
            state.hubValidated = true;
            
            // Clear validation timeout if set
            if (this._hubValidationTimeout) {
                clearTimeout(this._hubValidationTimeout);
                this._hubValidationTimeout = null;
            }
            
            console.log("Hub identity validated successfully (via ready message)");
            
            // NOW we can set hubConnected: true and exit connecting state
            setState({ 
                hubConnected: true,
                hubConnecting: false 
            });
            showToast("Connected to USB Serial hub", "success");
        };
        
        // Hub heartbeat validation (hubs send heartbeat every 5s, accept this as validation too)
        window.onHubHeartbeat = (data) => {
            // If not yet validated, accept heartbeat as validation
            // (means we connected to an already-running hub that sent its "ready" before we connected)
            if (!state.hubValidated) {
                console.log("✅ Hub identity validated via heartbeat (hub was already running)");
                console.log(`  Uptime: ${data?.uptime}ms`);
                console.log(`  Timestamp: ${data?.timestamp}`);
                state.hubValidated = true;
                
                // Clear validation timeout if set
                if (this._hubValidationTimeout) {
                    clearTimeout(this._hubValidationTimeout);
                    this._hubValidationTimeout = null;
                }
                
                // NOW we can set hubConnected: true and exit connecting state
                setState({ 
                    hubConnected: true,
                    hubConnecting: false 
                });
                showToast("Connected to USB Serial hub", "success");
            }
            // Heartbeats continue after validation for connection health monitoring
        };

        // Direct function for Python to call (both BLE and Serial connections)
        window.onHubConnected = (data) => {
            console.log("Hub connected:", data);
            const mode = data?.mode || "ble";
            
            if (mode === "ble") {
                // BLE: Show connected immediately (no validation needed)
                setState({
                    hubConnected: true,
                    hubDeviceName: data?.deviceName,
                    hubConnectionMode: mode,
                    hubConnecting: false,
                });
                showToast("Connected to Bluetooth hub", "success");
            } else {
                // Serial: Keep in "connecting" state until validation completes
                // DON'T set hubConnected: true yet! Wait for onHubReady/onHubHeartbeat
                // UNLESS validation is disabled (during setup/flashing)
                if (state.hubValidationEnabled) {
                    setState({
                        hubConnected: false,  // STAY disconnected until validated
                        hubDeviceName: data?.deviceName,
                        hubConnectionMode: mode,
                        hubConnecting: true,  // KEEP showing loading state
                    });
                    console.log("   Serial connected, now validating hub...");
                } else {
                    // Validation disabled (setup mode) - set connected immediately
                    setState({
                        hubConnected: true,  // Connected for setup/REPL access
                        hubDeviceName: data?.deviceName,
                        hubConnectionMode: mode,
                        hubConnecting: false,
                    });
                    console.log("   Serial connected (validation disabled for setup mode)");
                }
            }
            // For serial, toast will show after validation in onHubReady/onHubHeartbeat
            
            // Start validation timeout for serial connections (hub should send "ready" or "heartbeat" within 10s)
            // Hubs send "ready" on boot (1-3s) and heartbeat every 5s, so 10s timeout allows for boot + first message
            // SKIP validation if hubValidationEnabled is false (during setup/flashing)
            if (mode === "serial" && state.hubValidationEnabled) {
                console.log("⏱️ Starting hub validation timeout (10 seconds)...");
                console.log("   Waiting for 'ready' handshake or 'heartbeat' message...");
                console.log("   💡 If you just plugged in the hub, wait 2-3 seconds for it to boot before connecting");
                this._hubValidationTimeout = setTimeout(async () => {
                    console.warn("⚠️ Hub validation timeout - no hub messages received after 10 seconds");
                    
                    // Double-check: validation might have been disabled (e.g., setup modal opened)
                    if (!state.hubValidationEnabled) {
                        console.log("⏭️ Validation was disabled - ignoring timeout");
                        return;
                    }
                    
                    // Check if hub was validated
                    if (!state.hubValidated) {
                        console.error("❌ Connected device is not a hub (no ready message)");
                        console.log("   Keeping serial connection open for potential reset...");
                        
                        // DON'T disconnect - keep serial connection open so we can reset without re-prompting
                        // Just update UI state to show "not validated"
                        setState({
                            hubConnected: false,  // UI shows disconnected
                            hubConnecting: false,
                            hubValidated: false,
                            // But we keep the serial connection open in the background
                        });
                        
                        // Show error modal with simple action buttons
                        setState({
                            showErrorDetailModal: true,
                            errorDetail: {
                                title: "Not a Hub Device",
                                message: "Choose an option below:",
                                actions: [
                                    {
                                        type: 'button',
                                        id: 'tryReset',
                                        label: 'Retry',
                                        icon: 'refresh-cw',
                                        style: 'primary',
                                        disabled: false,
                                        onClick: async () => {
                                            try {
                                                console.log('🔄 Performing software reset on device...');
                                                
                                                // Close modal
                                                setState({ 
                                                    showErrorDetailModal: false,
                                                    errorDetail: null,
                                                    hubConnecting: true,  // Show connecting state
                                                });
                                                
                                                // Show toast
                                                showToast("Resetting device...", "info");
                                                
                                                // Disable validation during reset
                                                setState({ hubValidationEnabled: false });
                                                
                                                // Perform hard reset (will reboot and run main.py)
                                                await PyBridgeToUse.hardResetDevice();
                                                
                                                console.log('✅ Device reset complete, re-enabling validation...');
                                                
                                                // Re-enable validation and mark as validated to prevent immediate timeout
                                                setState({ 
                                                    hubValidationEnabled: true,
                                                    hubValidated: false,  // Will be set to true when ready/heartbeat received
                                                    hubConnected: false,   // Will be set to true when validated
                                                    hubConnecting: true,   // Keep showing connecting
                                                });
                                                
                                                // Start a new validation timeout
                                                if (this._hubValidationTimeout) {
                                                    clearTimeout(this._hubValidationTimeout);
                                                }
                                                this._hubValidationTimeout = setTimeout(async () => {
                                                    if (!state.hubValidated) {
                                                        console.warn("⚠️ Device still not responding after reset");
                                                        // Disconnect this time since reset didn't help
                                                        await PyBridgeToUse.disconnectHubSerial();
                                                        showToast("Device reset failed - not a hub", "error");
                                                    }
                                                }, 10000);
                                                
                                            } catch (error) {
                                                console.error('❌ Reset error:', error);
                                                showToast("Reset failed: " + error.message, "error");
                                                setState({ hubConnecting: false });
                                            }
                                        }
                                    },
                                    {
                                        type: 'button',
                                        id: 'setupHub',
                                        label: 'Setup as Hub',
                                        icon: 'upload-cloud',
                                        style: 'secondary',
                                        disabled: false,
                                        onClick: () => {
                                            // Close error modal
                                            setState({ 
                                                showErrorDetailModal: false,
                                                errorDetail: null 
                                            });
                                            // Open hub setup modal (will use existing serial connection)
                                            window.appShowHubSetup();
                                        }
                                    },
                                    {
                                        type: 'button',
                                        id: 'connectDifferent',
                                        label: 'Connect Different Device',
                                        icon: 'plug',
                                        style: 'secondary',
                                        disabled: false,
                                        onClick: async () => {
                                            try {
                                                console.log('🔌 Disconnecting current device to connect to a different one...');
                                                
                                                // Close error modal
                                                setState({ 
                                                    showErrorDetailModal: false,
                                                    errorDetail: null 
                                                });
                                                
                                                // Disconnect from current device
                                                await PyBridgeToUse.disconnectHubSerial();
                                                console.log('✅ Disconnected successfully');
                                                
                                                // Small delay to ensure clean disconnect
                                                await new Promise(resolve => setTimeout(resolve, 300));
                                                
                                                // Trigger connection flow (will prompt for device selection)
                                                window.appHandleHubConnect();
                                                
                                            } catch (error) {
                                                console.error('❌ Disconnect error:', error);
                                                // Continue to connection anyway
                                                window.appHandleHubConnect();
                                            }
                                        }
                                    }
                                ]
                            }
                        });
                    }
                }, 10000); // 10 second timeout (allows for boot time 1-3s + heartbeat at 5s)
            }
            
            // No auto-refresh needed - using passive battery tracking
            // Devices will appear automatically within 0-60s as they send battery messages
            if (state.deviceScanningEnabled) {
                console.log("Passive device tracking active - devices will appear within 60s");
            } else {
                console.log("Device scanning disabled - command-only mode");
            }
        };

        // Direct function calls only - no event listeners needed

        // ⚠️ DEPRECATED: BLE disconnection callback - NOT USED  
        window.onBLEDisconnected = () => {
            console.error("❌ onBLEDisconnected called - BLE not supported");
        };

        // Universal hub disconnected callback (for both BLE and Serial)
        window.onHubDisconnected = () => {
            console.log("Hub disconnected");
            
            // Clear validation timeout if active
            if (this._hubValidationTimeout) {
                clearTimeout(this._hubValidationTimeout);
                this._hubValidationTimeout = null;
            }
            
            setState({
                hubConnected: false,
                hubDeviceName: null,
                hubConnectionMode: null,
                hubConnecting: false,
                hubValidated: false,
                hubValidationEnabled: true,  // Re-enable validation for next connection
                hubVersion: null,
                hubMac: null,
            });
        };
        
        // Callback for showing detailed error modals (called from Python)
        window.showSerialConnectionLostError = () => {
            console.log("Serial connection lost - showing error modal");
            showSerialConnectionLostError();
        };
        
        // Expose method to clear hub validation timeout (used by setup modal)
        window.clearHubValidationTimeout = () => {
            if (this._hubValidationTimeout) {
                console.log("🔕 Clearing hub validation timeout");
                clearTimeout(this._hubValidationTimeout);
                this._hubValidationTimeout = null;
            }
        };

        // Direct function calls only - no event listeners needed

        // Register for state changes
        onStateChange(() => this.render());

        // Start auto-disconnect detection
        this.startConnectionMonitoring();

        // Initial render
        this.render();
    }

    startConnectionMonitoring() {
        /**
         * Poll hub connection status every 30s to detect disconnections.
         */
        // Clear any existing monitor to prevent duplicates
        if (this.connectionMonitor) {
            clearInterval(this.connectionMonitor);
        }
        
        this.connectionMonitor = setInterval(async () => {
            // Only poll when we think we're connected
            if (state.hubConnected) {
                const stateChanged = await syncConnectionState();
                if (stateChanged) {
                    console.log("Connection state changed during auto-check");
                }
                // Removed noisy "Auto-checking..." log - only log changes
            }
        }, 30000); // Check every 30 seconds (was 5s - reduced to minimize BLE interference)
    }

    async initializePython() {
        console.log("Waiting for Python to initialize...");
        
        // Python functions are available directly - no event needed

        // Also try waiting for functions to be available
        if (typeof PyBridgeToUse.waitForPython === 'function') {
            const isReady = await PyBridgeToUse.waitForPython(10000);
            if (isReady) {
                console.log("Python backend ready!");
                setState({ pythonReady: true });
                await this.loadPythonData();
            } else {
                console.warn("Python not ready after 10 second timeout.");
                setState({ pythonReady: true }); // Allow UI to proceed anyway
            }
        } else {
            console.error("PyBridge.waitForPython is not a function!");
            console.log("Available PyBridge methods:", Object.keys(PyBridgeToUse));
            setState({ pythonReady: true }); // Allow UI to proceed anyway
        }
    }

    async loadPythonData() {
        try {
            // Check connection status first
            if (typeof PyBridgeToUse.getConnectionStatus === 'function') {
                const status = await PyBridgeToUse.getConnectionStatus();
                if (status && status.connected) {
                    setState({
                        hubConnected: true,
                        hubDeviceName: status.device,
                    });
                    
                    // Only get devices if connected
                    if (typeof PyBridgeToUse.getDevices === 'function') {
                        const devices = await PyBridgeToUse.getDevices();
                        setState({
                            allDevices: devices || [],
                            lastUpdateTime: new Date(),
                        });
                    }
                }
            } else {
                console.error("PyBridge.getConnectionStatus is not a function!");
            }
        } catch (e) {
            console.log("Python data loading failed:", e);
        }
    }

    render() {
        const devices = getAvailableDevices();
        // Allow sending if hub is connected, even if no devices detected
        // (device scan can be unreliable but commands may still work)
        const canSend = state.currentMessage && state.hubConnected;

        // Don't clear and rebuild if an overlay is showing
        if (state.showDeviceList || state.showMessageDetails) {
            // Just update the overlay that's showing
            if (state.showDeviceList && this.components.deviceListOverlay) {
                const newOverlay = createDeviceListOverlay(
                    devices,
                    state.range,
                    state.editingDeviceId,
                    state.moduleNicknames,
                    () => {
                        setState({ showDeviceList: false });
                        this.components.deviceListOverlay.style.display = "none";
                    },
                    (range) => setState({ range }),
                    (deviceId) => setState({ editingDeviceId: deviceId }),
                    (deviceId, nickname) => {
                        setState({
                            moduleNicknames: {
                                ...state.moduleNicknames,
                                [deviceId]: nickname.trim() || undefined,
                            },
                            editingDeviceId: null,
                        });
                    },
                    state.hubConnected,
                    () => this.handleHubConnect(),
                    state.hubConnecting, // Pass connecting state
                );
                this.components.deviceListOverlay.replaceWith(newOverlay);
                this.components.deviceListOverlay = newOverlay;
                this.components.deviceListOverlay.style.display = "flex";
                if (window.lucide) window.lucide.createIcons();
            }
            return;
        }

        // Don't rebuild main UI if settings overlay is open
        // (prevents disconnect issues when toggling settings)
        if (state.showSettings) {
            // Settings overlay handles its own state - just ensure it's rendered
            if (!this.components.settingsOverlay) {
                this.components.settingsOverlay = createSettingsOverlay(() => this.handleSettingsBack());
                this.container.appendChild(this.components.settingsOverlay);
                if (window.lucide) window.lucide.createIcons();
            }
            return;
        }
        
        // Clear container
        this.container.innerHTML = "";
        this.container.className = "flex flex-col max-w-md mx-auto bg-white relative";


        // Create components
        const recipientBar = createRecipientBar(
            devices,
            state.range,
            state.lastUpdateTime,
            (range) => setState({ range }),
            () => {
                setState({ showDeviceList: true });
                this.components.deviceListOverlay.style.display = "flex";
            },
            state.hubConnected,
            state.hubDeviceName,
            () => this.handleHubConnect(),
            () => this.handleHubDisconnect(),
            () => this.handleSettingsClick(),
            state.pythonReady, // Pass Python initialization state
            state.deviceScanningEnabled, // Pass device scanning toggle
            state.isBrowserCompatible, // Pass browser compatibility status
            state.hubConnecting, // Pass hub connecting state
        );

        const messageHistory = createMessageHistory(
            state.messageHistory, 
            (message) => {
                setState({ viewingMessage: message, showMessageDetails: true });
                this.components.messageDetailsOverlay.style.display = "flex";
                this.renderMessageDetails();
            },
            state.hubConnected,
            () => this.handleHubConnect(),
            state.hubConnectionMode || 'ble',
            state.pythonReady
        );

        const messageInput = createMessageInput(
            state.currentMessage,
            state.showCommandPalette,
            canSend,
            () => setState({ showCommandPalette: true }),
            (command) => setState({ currentMessage: command.id }),
            () => setState({ currentMessage: "" }),
            () => this.handleSendMessage(),
            state.flashMessageBox,
        );

        this.components.deviceListOverlay = createDeviceListOverlay(
            devices,
            state.range,
            state.editingDeviceId,
            state.moduleNicknames,
            () => {
                setState({ showDeviceList: false });
                this.components.deviceListOverlay.style.display = "none";
            },
            (range) => setState({ range }),
            (deviceId) => setState({ editingDeviceId: deviceId }),
            (deviceId, nickname) => {
                setState({
                    moduleNicknames: {
                        ...state.moduleNicknames,
                        [deviceId]: nickname.trim() || undefined,
                    },
                    editingDeviceId: null,
                });
            },
            state.hubConnected,
            () => this.handleHubConnect(),
            state.hubConnecting, // Pass connecting state
        );

        this.components.messageDetailsOverlay = createMessageDetailsOverlay(
            state.viewingMessage,
            state.moduleNicknames,
            () => {
                setState({ showMessageDetails: false, viewingMessage: null });
                this.components.messageDetailsOverlay.style.display = "none";
            },
            (message) => setState({ currentMessage: message.command, showCommandPalette: true }),
        );

        // Append to DOM
        this.container.appendChild(recipientBar);
        this.container.appendChild(messageHistory);
        this.container.appendChild(messageInput);
        this.container.appendChild(this.components.deviceListOverlay);
        this.container.appendChild(this.components.messageDetailsOverlay);
        
        // Add new overlay components
        if (state.showConnectionWarning) {
            // Remove existing modal if any
            if (this.components.connectionWarningModal) {
                this.components.connectionWarningModal.remove();
            }
            this.components.connectionWarningModal = createConnectionWarningModal(
                () => this.handleModalConnect(),
                () => this.handleModalCancel(),
            );
            this.container.appendChild(this.components.connectionWarningModal);
        } else if (this.components.connectionWarningModal) {
            // Remove modal if not showing
            this.components.connectionWarningModal.remove();
            this.components.connectionWarningModal = null;
        }
        
        if (state.showSettings) {
            // Remove old overlay if it exists before creating new one
            if (this.components.settingsOverlay) {
                this.components.settingsOverlay.remove();
            }
            this.components.settingsOverlay = createSettingsOverlay(() => this.handleSettingsBack());
            this.container.appendChild(this.components.settingsOverlay);
        } else if (this.components.settingsOverlay) {
            // Remove overlay when settings closed
            this.components.settingsOverlay.remove();
            this.components.settingsOverlay = null;
        }
        
        // Show browser compatibility modal if needed (blocking, highest z-index)
        if (state.showBrowserCompatibilityModal) {
            if (this.components.browserCompatibilityModal) {
                this.components.browserCompatibilityModal.remove();
            }
            this.components.browserCompatibilityModal = createBrowserCompatibilityModal();
            this.container.appendChild(this.components.browserCompatibilityModal);
        } else if (this.components.browserCompatibilityModal) {
            this.components.browserCompatibilityModal.remove();
            this.components.browserCompatibilityModal = null;
        }
        
        // Show permission blocked modal if needed
        if (state.showPermissionBlockedModal) {
            if (this.components.permissionBlockedModal) {
                this.components.permissionBlockedModal.remove();
            }
            this.components.permissionBlockedModal = createPermissionBlockedModal(
                () => setState({ showPermissionBlockedModal: false }),
                () => this.handleHubConnect()
            );
            this.container.appendChild(this.components.permissionBlockedModal);
        } else if (this.components.permissionBlockedModal) {
            this.components.permissionBlockedModal.remove();
            this.components.permissionBlockedModal = null;
        }
        
        // Show error detail modal if needed (for detailed error messages)
        if (state.showErrorDetailModal && state.errorDetail) {
            if (this.components.errorDetailModal) {
                this.components.errorDetailModal.remove();
            }
            this.components.errorDetailModal = createErrorDetailModal(state.errorDetail);
            this.container.appendChild(this.components.errorDetailModal);
        } else if (this.components.errorDetailModal) {
            this.components.errorDetailModal.remove();
            this.components.errorDetailModal = null;
        }

        // Initialize Lucide icons
        if (window.lucide) {
            window.lucide.createIcons();
        }

        // Handle overlay visibility
        if (state.showDeviceList) {
            this.components.deviceListOverlay.style.display = "flex";
            // Force re-creation of icons after showing overlay
            setTimeout(() => {
                if (window.lucide) {
                    window.lucide.createIcons();
                }
            }, 0);
        }
        if (state.showMessageDetails) {
            this.components.messageDetailsOverlay.style.display = "flex";
        }
    }

    renderMessageDetails() {
        // Re-render message details overlay
        const newOverlay = createMessageDetailsOverlay(
            state.viewingMessage,
            state.moduleNicknames,
            () => {
                setState({ showMessageDetails: false, viewingMessage: null });
                this.components.messageDetailsOverlay.style.display = "none";
            },
            (message) => setState({ currentMessage: message.command, showCommandPalette: true }),
        );

        this.components.messageDetailsOverlay.replaceWith(newOverlay);
        this.components.messageDetailsOverlay = newOverlay;
        this.components.messageDetailsOverlay.style.display = "flex";

        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    async handleSendMessage() {
        /**
         * Send command to modules (validates connection, devices, command; updates history).
         */
        // PRIORITY 1: Check hub connection first
        if (!state.hubConnected) {
            this.showConnectionWarningModal();
            return;
        }

        // PRIORITY 2: Log device availability (only if device scanning enabled)
        let devices = [];
        if (state.deviceScanningEnabled) {
            devices = getAvailableDevices();
            console.log("=== SEND MESSAGE: Device check ===");
            console.log("state.allDevices length:", state.allDevices?.length);
            console.log("getAvailableDevices() length:", devices?.length);
            console.log("All devices:", state.allDevices);
            console.log("Available devices:", devices);
            
            if (devices.length === 0) {
                console.log("⚠ No devices detected, but sending command anyway (broadcast mode)");
            }
        } else {
            console.log("=== SEND MESSAGE: Broadcast mode (device scanning disabled) ===");
        }

        // PRIORITY 4: Check message selection
        if (!state.currentMessage || state.currentMessage.trim() === "") {
            if (!state.showCommandPalette) {
                // Drawer closed - open it
                setState({ showCommandPalette: true });
            } else {
                // Drawer already open - flash message box
                this.flashMessageBox();
            }
            return;
        }

        const now = new Date();
        const newMessage = {
            id: Date.now(),
            command: state.currentMessage,
            modules: state.deviceScanningEnabled ? devices.map((d) => d.name) : ["All Modules"],
            timestamp: now,
            displayTime: formatDisplayTime(now),
        };

        setState({
            messageHistory: [...state.messageHistory, newMessage],
            currentMessage: "",
            showCommandPalette: false,
        });

        // SEND COMMAND VIA SERIAL/BLE
        try {
            // Use RSSI threshold only if device scanning is enabled, otherwise broadcast to all
            let rssiThreshold;
            if (state.deviceScanningEnabled) {
                // Convert range slider to RSSI threshold
                rssiThreshold = state.range === 100 ? "all" : Math.round(-30 - ((state.range - 1) / 98) * 60).toString();
            } else {
                // Broadcast mode - send to all modules
                rssiThreshold = "all";
            }

            const result = await PyBridgeToUse.sendCommandToHub(newMessage.command, rssiThreshold);

            // Use unified error handler
            const isError = handleError(result, "Send Command");
            
            if (result.status === "sent") {
                console.log("Command sent to hub:", newMessage.command, "with threshold:", rssiThreshold);
            } else if (isError) {
                // Error handler already showed toast
                console.log("Command send failed");
            }
        } catch (e) {
            console.error("Send error:", e);
            showToast(`Error sending command: ${e.message}`, "error");
        }
    }

    async validateHub() {
        const boardInfo = await PyBridgeToUse.getBoardInfo();
        if (boardInfo.status !== "success") {
            console.error("❌ Failed to read device information:", boardInfo.error);
            showToast("Failed to validate device type", "error");
            
            // Disconnect since validation failed
            await PyBridgeToUse.disconnectHubSerial();
            setState({ hubConnecting: false });
            return false;
        }
        const boardType = boardInfo.info;
        console.log("Board type: ", boardInfo);

        const isESPDevice = boardType.toUpperCase().includes("ESP");

        if (!isESPDevice) {
            console.error(`❌ Device is not an ESP. Detected: ${boardInfo}`);
            showToast(`Wrong device type.\nNeed ESP for ESP-NOW.\nDetected: ${boardInfo}`, "error");
            
            // Disconnect the wrong device
            await PyBridgeToUse.disconnectHubSerial();
            setState({ hubConnecting: false });
            return false;
        }

        console.log(`✅ Validated: Device is ESP32 (${boardType})`);
        return true;
    }

    async handleHubConnect() {
        // Connect directly via Serial (no modal - BLE removed for now)
        setState({ 
            hubConnecting: true,
            hubValidated: false,
            hubVersion: null,
            hubMac: null
        });
        
        try {
            const result = await PyBridgeToUse.connectHubSerial();
            
            if (result.status === "success") {
                console.log("✅ Serial connected:", result.device);
                // Don't show success yet - onHubConnected callback will update state
                // and keep hubConnecting: true until validation completes
                // (Python's connect_hub_serial calls onHubConnected which sets the state)

                
                // No manual refresh needed - passive tracking via battery messages
                // Devices will appear automatically within 0-60s
            } else if (result.status === "cancelled") {
                console.log("❌ Serial connection cancelled by user");
                setState({ hubConnecting: false });
            } else {
                console.error("❌ Serial connection failed:", result.error);
                setState({ hubConnecting: false });
                
                // Check if this is a permission/popup blocking issue
                if (isPermissionBlockedError(result)) {
                    console.log("⚠️ Permission blocked - showing troubleshooting modal");
                    setState({ showPermissionBlockedModal: true });
                } else if (result.error && result.error.includes("in use") || result.error && result.error.includes("busy")) {
                    // Show detailed error modal for port in use (not just a toast)
                    showPortInUseError();
                } else if (result.error && result.error.includes("not available")) {
                    showToast("❌ Use Chrome or Edge browser for USB connection", "error");
                } else {
                    showToast("Connection failed: " + (result.error || "Unknown error"), "error");
                }
            }
        } catch (error) {
            console.error("❌ Serial connection error:", error);
            setState({ hubConnecting: false });
            
            // Check if this is a permission/popup blocking issue
            if (isPermissionBlockedError(error)) {
                console.log("⚠️ Permission blocked - showing troubleshooting modal");
                setState({ showPermissionBlockedModal: true });
            } else {
                showToast("Connection error: " + error.message, "error");
            }
        }
    }

    async handleHubDisconnect() {
        try {
            // Disconnect based on connection mode
            let result;
            if (state.hubConnectionMode === "serial") {
                result = await PyBridgeToUse.disconnectHubSerial();
            } else {
                result = await PyBridgeToUse.disconnectHub();
            }
            console.log("Disconnect result:", result);
            
            // Use unified error handler
            handleError(result, "Hub Disconnect");
            
            // Clear connection state
            setState({
                hubConnected: false,
                hubDeviceName: null,
                hubConnectionMode: null
            });
            
            // Always sync state after disconnect attempt
            await syncConnectionState();
        } catch (e) {
            console.error("Disconnect error:", e);
            showToast("Error disconnecting from hub", "error");
            // Sync state even on exception
            await syncConnectionState();
        }
    }

    // UI event handlers
    handleSettingsClick() {
        setState({ showSettings: true });
    }

    handleSettingsBack() {
        setState({ showSettings: false });
    }

    showConnectionWarningModal() {
        setState({ showConnectionWarning: true });
    }

    handleModalConnect() {
        this.handleHubConnect();
        setState({ showConnectionWarning: false });
        // Remove modal from DOM
        if (this.components.connectionWarningModal) {
            this.components.connectionWarningModal.remove();
            this.components.connectionWarningModal = null;
        }
    }

    handleModalCancel() {
        setState({ showConnectionWarning: false });
        // Remove modal from DOM
        if (this.components.connectionWarningModal) {
            this.components.connectionWarningModal.remove();
            this.components.connectionWarningModal = null;
        }
    }

    flashMessageBox() {
        setState({ flashMessageBox: true });
        setTimeout(() => {
            setState({ flashMessageBox: false });
        }, 500);
    }

    setupClickOutsideHandler() {
        // Add document click listener to close command palette when clicking outside
        document.addEventListener('click', (event) => {
            // Only close if command palette is currently open
            if (!state.showCommandPalette) return;

            // Check if click is on message input area, message history, or any modal/overlay
            const messageInput = document.querySelector('#messageInput');
            const commandPalette = document.querySelector('.command-palette');
            const messageHistory = document.querySelector('.message-history');
            
            // Check for overlays and modals by their class names and structure
            const deviceListOverlay = document.querySelector('.absolute.inset-0.bg-white.z-50');
            const messageDetailsOverlay = document.querySelector('.absolute.inset-0.bg-white.z-50');
            const connectionWarningModal = document.querySelector('.absolute.inset-0.bg-black.bg-opacity-50.z-50');
            const settingsOverlay = document.querySelector('.absolute.inset-0.bg-white.z-50');

            // Check if click is within any of these elements
            const isClickOnMessageInput = messageInput && messageInput.contains(event.target);
            const isClickOnCommandPalette = commandPalette && commandPalette.contains(event.target);
            
            // Only consider it a click on message history if it's on a message bubble, not the empty container
            const isClickOnMessageBubble = messageHistory && messageHistory.contains(event.target) && 
                                         event.target.closest('.message-bubble');
            
            // Check if click is on any overlay or modal
            const isClickOnOverlay = (deviceListOverlay && deviceListOverlay.contains(event.target)) ||
                                   (messageDetailsOverlay && messageDetailsOverlay.contains(event.target)) ||
                                   (connectionWarningModal && connectionWarningModal.contains(event.target)) ||
                                   (settingsOverlay && settingsOverlay.contains(event.target));

            // If click is not on message input, command palette, message bubble, or any overlay/modal, close the command palette
            if (!isClickOnMessageInput && !isClickOnCommandPalette && !isClickOnMessageBubble && !isClickOnOverlay) {
                setState({ showCommandPalette: false });
            }
        });
    }

}

// Initialize app
try {
    const app = new App();
} catch (error) {
    console.error("Error creating App:", error);
}
