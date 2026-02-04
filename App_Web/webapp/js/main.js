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
            console.log(`⏰ Hub timestamp: ${hubTimestamp}`);
            console.log(`📊 State before update: ${state.allDevices?.length || 0} devices`);
            console.log("=" + "=".repeat(80));
            
            // Process each device to calculate age and stale status
            const processedDevices = devices.map((device, index) => {
                // Calculate device age in milliseconds
                const ageMs = hubTimestamp - device.last_seen;
                
                // Convert to local browser time (Date object)
                // Age = how long ago device was last seen
                // Current time - age = when device was last seen
                const lastSeenTime = new Date(Date.now() - ageMs);
                
                // Mark as stale if not seen for more than 3 minutes
                const isStale = ageMs > 180000;  // 3 minutes in milliseconds
                
                console.log(`  Device ${index + 1}: ${device.name} | RSSI: ${device.rssi} | Battery: ${device.battery_pct}% | Age: ${ageMs}ms | Stale: ${isStale}`);
                
                return {
                    ...device,
                    lastSeenTime,   // Date object for getRelativeTime()
                    isStale         // Boolean for UI warning
                };
            });
            
            console.log(`✅ Processed ${processedDevices.length} devices, updating state...`);
            
            setState({
                allDevices: processedDevices,
                lastUpdateTime: new Date(),
            });
            
            console.log(`✅ State updated! New device count: ${state.allDevices?.length || 0}`);
        };

        // Direct function calls only - no event listeners needed

        // Direct function for Python to call (BLE connections)
        window.onBLEConnected = (data) => {
            console.log("Direct BLE connected call:", data);
            console.log("Data type:", typeof data);
            console.log("Data keys:", Object.keys(data || {}));
            console.log("Device name:", data?.deviceName);
            setState({
                hubConnected: true,
                hubDeviceName: data?.deviceName,
                hubConnectionMode: "ble",
                hubConnecting: false,
            });
        };

        // Direct function for Python to call (both BLE and Serial connections)
        window.onHubConnected = (data) => {
            console.log("Hub connected:", data);
            const mode = data?.mode || "ble";
            setState({
                hubConnected: true,
                hubDeviceName: data?.deviceName,
                hubConnectionMode: mode,
                hubConnecting: false,
            });
            showToast(`Connected to ${mode === "serial" ? "USB Serial" : "Bluetooth"} hub`, "success");
            
            // No auto-refresh needed - using passive battery tracking
            // Devices will appear automatically within 0-60s as they send battery messages
            if (state.deviceScanningEnabled) {
                console.log("Passive device tracking active - devices will appear within 60s");
            } else {
                console.log("Device scanning disabled - command-only mode");
            }
        };

        // Direct function calls only - no event listeners needed

        // Direct function for Python to call
        window.onBLEDisconnected = () => {
            console.log("Direct BLE disconnected call");
            
            setState({
                hubConnected: false,
                hubDeviceName: null,
                hubConnectionMode: null,
                hubConnecting: false,
            });
        };

        // Universal hub disconnected callback (for both BLE and Serial)
        window.onHubDisconnected = () => {
            console.log("Hub disconnected");
            
            setState({
                hubConnected: false,
                hubDeviceName: null,
                hubConnectionMode: null,
                hubConnecting: false,
            });
        };
        
        // Callback for showing detailed error modals (called from Python)
        window.showSerialConnectionLostError = () => {
            console.log("Serial connection lost - showing error modal");
            showSerialConnectionLostError();
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

    async handleHubConnect() {
        // Connect directly via Serial (no modal - BLE removed for now)
        setState({ hubConnecting: true });
        
        try {
            const result = await PyBridgeToUse.connectHubSerial();
            
            if (result.status === "success") {
                console.log("✅ Serial connected:", result.device);
                setState({
                    hubConnected: true,
                    hubDeviceName: result.device,
                    hubConnectionMode: "serial",
                    hubConnecting: false
                });
                
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
