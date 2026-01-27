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
        
        // Cancel pending scans if we're disconnecting
        if (wasConnected && !status.connected) {
            newState.isRefreshing = false;
        }
        
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
        this.refreshTimeout = null; // Track refresh timeout to prevent hanging
        this.cooldownRetryTimeout = null; // Track pending cooldown retry
        this.REFRESH_TIMEOUT_MS = 7000; // 7 seconds (hub scans for 5s + 2s buffer for BLE resume/response)
        this.SCAN_COOLDOWN_MS = 2000; // 2 seconds minimum between scans (prevents radio conflicts)
        this.lastRefreshTime = 0; // Track last scan completion time
        this.MAX_GATT_RETRIES = 2; // Retry GATT errors 2 times (3 total attempts)
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
            console.log("=== JavaScript onDevicesUpdated called ===");
            console.log(`Received ${devices?.length || 0} devices from hub`);
            console.log(`Hub timestamp: ${hubTimestamp}`);
            
            // Clear refresh timeout since we got a response
            if (this.refreshTimeout) {
                clearTimeout(this.refreshTimeout);
                this.refreshTimeout = null;
                console.log("Cleared refresh timeout (successful response)");
            }
            
            // Update cooldown timer on successful scan completion
            this.lastRefreshTime = Date.now();
            
            // Process each device to calculate age and stale status
            const processedDevices = devices.map(device => {
                // Calculate device age in milliseconds
                const ageMs = hubTimestamp - device.last_seen;
                
                // Convert to local browser time (Date object)
                // Age = how long ago device was last seen
                // Current time - age = when device was last seen
                const lastSeenTime = new Date(Date.now() - ageMs);
                
                // Mark as stale if not seen for more than 3 minutes
                const isStale = ageMs > 180000;  // 3 minutes in milliseconds
                
                console.log(`Device ${device.id}: age=${ageMs}ms, lastSeen=${lastSeenTime.toISOString()}, stale=${isStale}`);
                
                return {
                    ...device,
                    lastSeenTime,   // Date object for getRelativeTime()
                    isStale         // Boolean for UI warning
                };
            });
            
            setState({
                allDevices: processedDevices,
                lastUpdateTime: new Date(),
                isRefreshing: false, // Clear loading state when devices received
            });
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
            
            // Auto-refresh devices on connection (only if scanning enabled)
            if (state.deviceScanningEnabled) {
                console.log("Auto-refreshing devices on connection...");
                this.handleRefreshDevices();
            } else {
                console.log("Device scanning disabled - skipping auto-refresh");
            }
        };

        // Direct function calls only - no event listeners needed

        // Direct function for Python to call
        window.onBLEDisconnected = () => {
            console.log("Direct BLE disconnected call");
            
            // Clean up any pending timeouts
            if (this.refreshTimeout) {
                clearTimeout(this.refreshTimeout);
                this.refreshTimeout = null;
            }
            if (this.cooldownRetryTimeout) {
                clearTimeout(this.cooldownRetryTimeout);
                this.cooldownRetryTimeout = null;
            }
            
            setState({
                hubConnected: false,
                hubDeviceName: null,
                hubConnectionMode: null,
                hubConnecting: false,
                isRefreshing: false, // Cancel any pending device scans
            });
        };

        // Universal hub disconnected callback (for both BLE and Serial)
        window.onHubDisconnected = () => {
            console.log("Hub disconnected");
            
            // Clean up any pending timeouts
            if (this.refreshTimeout) {
                clearTimeout(this.refreshTimeout);
                this.refreshTimeout = null;
            }
            if (this.cooldownRetryTimeout) {
                clearTimeout(this.cooldownRetryTimeout);
                this.cooldownRetryTimeout = null;
            }
            
            setState({
                hubConnected: false,
                hubDeviceName: null,
                hubConnectionMode: null,
                hubConnecting: false,
                isRefreshing: false, // Cancel any pending device scans
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
         * Poll connection status every 30s (paused during scans to avoid radio interference).
         */
        // Clear any existing monitor to prevent duplicates
        if (this.connectionMonitor) {
            clearInterval(this.connectionMonitor);
        }
        
        this.connectionMonitor = setInterval(async () => {
            // CRITICAL: Skip polling during ESP-NOW device scans
            // BLE traffic would interfere with ESP-NOW IRQ on ESP32-C3's shared radio
            if (state.isRefreshing) {
                // Silent skip - scan in progress
                return;
            }
            
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
                    state.isRefreshing,
                    state.editingDeviceId,
                    state.moduleNicknames,
                    () => {
                        setState({ showDeviceList: false });
                        this.components.deviceListOverlay.style.display = "none";
                    },
                    (range) => setState({ range }),
                    () => this.handleRefreshDevices(),
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
            () => this.handleRefreshDevices(),
            state.hubConnected,
            state.hubDeviceName,
            () => this.handleHubConnect(),
            () => this.handleHubDisconnect(),
            () => this.handleSettingsClick(),
            state.isRefreshing, // Pass refresh state for loading animation
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
            state.isRefreshing,
            state.editingDeviceId,
            state.moduleNicknames,
            () => {
                setState({ showDeviceList: false });
                this.components.deviceListOverlay.style.display = "none";
            },
            (range) => setState({ range }),
            () => this.handleRefreshDevices(),
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
            this.components.settingsOverlay = createSettingsOverlay(() => this.handleSettingsBack());
            this.container.appendChild(this.components.settingsOverlay);
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

        // PRIORITY 2: Check if refresh is in progress (only if device scanning enabled)
        if (state.deviceScanningEnabled && state.isRefreshing) {
            showToast("Please wait for device scan to complete", "warning");
            return;
        }

        // PRIORITY 3: Log device availability (only if device scanning enabled)
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

    async handleRefreshDevices(rssiThreshold = null, retryCount = 0) {
        /**
         * Refresh device list with RSSI filter (7s timeout, auto-retries GATT errors).
         * 
         * @param {number|null} rssiThreshold - RSSI in dBm or null for current slider value
         * @param {number} retryCount - Internal retry counter
         */
        
        // Skip device scanning if disabled in settings
        if (!state.deviceScanningEnabled) {
            console.log("Device scanning disabled - skipping PING");
            return;
        }
        
        // Prevent concurrent refreshes (but allow internal retries)
        if (state.isRefreshing && retryCount === 0) {
            console.log("Refresh already in progress, ignoring duplicate request");
            return;
        }
        
        // Cancel any pending cooldown retry (user triggered new scan)
        if (this.cooldownRetryTimeout) {
            clearTimeout(this.cooldownRetryTimeout);
            this.cooldownRetryTimeout = null;
            console.log("Cancelled pending cooldown retry (new scan requested)");
        }
        
        // Enforce cooldown period between scans (only for new scans, not retries)
        if (retryCount === 0 && this.lastRefreshTime > 0) {
            const timeSinceLastScan = Date.now() - this.lastRefreshTime;
            if (timeSinceLastScan < this.SCAN_COOLDOWN_MS) {
                const remainingCooldown = this.SCAN_COOLDOWN_MS - timeSinceLastScan;
                console.log(`⏳ Scan cooldown: Wait ${Math.ceil(remainingCooldown / 1000)}s (prevents ESP32-C3 radio conflicts)`);
                console.log(`   Will automatically retry in ${remainingCooldown}ms...`);
                
                // Calculate RSSI threshold NOW before scheduling retry
                let thresholdForRetry = rssiThreshold;
                if (thresholdForRetry === null) {
                    const sliderPosition = state.range;
                    if (sliderPosition === 100) {
                        thresholdForRetry = "all";
                    } else {
                        thresholdForRetry = Math.round(-30 - ((sliderPosition - 1) / 98) * 60);
                    }
                }
                
                // Automatically retry after cooldown expires
                this.cooldownRetryTimeout = setTimeout(() => {
                    console.log("⏰ Cooldown expired, retrying scan...");
                    this.cooldownRetryTimeout = null;
                    this.handleRefreshDevices(thresholdForRetry, 0);
                }, remainingCooldown);
                
                return;
            }
        }
        
        // Check if hub is connected before attempting scan
        if (!state.hubConnected) {
            console.warn("⚠️ Cannot scan: Hub not connected");
            return;
        }
        
        // Only set refreshing state on initial attempt
        if (retryCount === 0) {
            setState({ isRefreshing: true });
        }

        // Calculate RSSI threshold from slider if not provided (only on initial call)
        if (rssiThreshold === null && retryCount === 0) {
            const sliderPosition = state.range;
            if (sliderPosition === 100) {
                rssiThreshold = "all";
            } else {
                // Map 1-99 to RSSI range: -30 (closest) to -90 (farthest)
                rssiThreshold = Math.round(-30 - ((sliderPosition - 1) / 98) * 60);
            }
        }
        
        // Log attempt
        if (retryCount > 0) {
            console.log(`🔄 Retry ${retryCount}/${this.MAX_GATT_RETRIES} - RSSI threshold: ${rssiThreshold}`);
        } else {
            console.log(`Refreshing devices with RSSI threshold: ${rssiThreshold}`);
        }

        // Set up timeout to prevent hanging per attempt
        if (this.refreshTimeout) {
            clearTimeout(this.refreshTimeout);
            this.refreshTimeout = null;
        }
        
        this.refreshTimeout = setTimeout(() => {
            console.warn(`⚠️ Refresh timeout: No response within ${this.REFRESH_TIMEOUT_MS / 1000}s (attempt ${retryCount + 1})`);
            setState({ isRefreshing: false });
            this.lastRefreshTime = Date.now(); // Update cooldown timer
            this.refreshTimeout = null;
        }, this.REFRESH_TIMEOUT_MS);

        // Update button state directly for immediate feedback (only on first attempt)
        if (retryCount === 0) {
            const refreshBtn = this.components.deviceListOverlay?.querySelector("#refreshBtn");
            if (refreshBtn) {
                refreshBtn.classList.add("animate-spin");
            }
        }

        try {
            // Send PING with RSSI threshold
            const result = await PyBridgeToUse.refreshDevices(rssiThreshold);
            
            console.log("✓ PING sent, waiting for device responses from hub...");
            // Note: isRefreshing will be cleared by onDevicesUpdated callback
            // when hub sends back device list, OR by timeout
            
            // Empty array is legitimate - no retry needed
            
        } catch (e) {
            // Check if it's a GATT error that should be retried
            if (e.isGattError && retryCount < this.MAX_GATT_RETRIES) {
                console.warn(`⚠️ GATT error on attempt ${retryCount + 1}: ${e.message}`);
                console.log(`Retrying in 1 second... (${retryCount + 1}/${this.MAX_GATT_RETRIES} retries)`);
                
                // Clear current timeout
                if (this.refreshTimeout) {
                    clearTimeout(this.refreshTimeout);
                    this.refreshTimeout = null;
                }
                
                // Wait 1 second before retry (short delay for transient GATT errors)
                await new Promise(resolve => setTimeout(resolve, 1000));
                
                // Retry with same threshold, increment retry count
                return this.handleRefreshDevices(rssiThreshold, retryCount + 1);
                
            } else if (e.isGattError) {
                // Max retries reached for GATT error
                console.error(`❌ GATT error after ${this.MAX_GATT_RETRIES + 1} attempts: ${e.message}`);
                console.log("Clearing refresh state - user can retry manually");
                
                // Clear timeout and loading state
                if (this.refreshTimeout) {
                    clearTimeout(this.refreshTimeout);
                    this.refreshTimeout = null;
                }
                this.lastRefreshTime = Date.now(); // Update cooldown timer
                setState({ isRefreshing: false });
                
                // Silent failure - no toast to avoid interruption
                
            } else {
                // Non-GATT error - clear state immediately
                console.error("Non-GATT error during refresh:", e);
                
                if (this.refreshTimeout) {
                    clearTimeout(this.refreshTimeout);
                    this.refreshTimeout = null;
                }
                this.lastRefreshTime = Date.now(); // Update cooldown timer
                setState({ isRefreshing: false });
            }
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
                
                // Auto-refresh devices only if scanning is enabled
                if (state.deviceScanningEnabled) {
                    console.log("Auto-refreshing devices on connection...");
                    await this.handleRefreshDevices();
                }
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
