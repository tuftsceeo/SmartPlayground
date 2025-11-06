/**
 * Smart Playground Control - Main Application Controller
 * 
 * This module contains the main App class that orchestrates the entire frontend application.
 * It manages the component rendering, state synchronization, and
 * communication with the Python backend via PyBridge.
 * 
 * Key Responsibilities:
 * - Application initialization and Python backend integration
 * - Component lifecycle management and DOM rendering
 * - State management coordination with reactive updates
 * - Event handling for user interactions and system events
 * - BLE connection management and device communication
 * - Error handling and user feedback via toasts and modals
 * 
 * Architecture:
 * - Single App class managing entire application state
 * - Component-based UI with functional component pattern
 * - Reactive rendering triggered by state changes
 * - Event-driven communication with Python backend
 * - Mobile-first responsive design with touch optimizations
 * 
 * Dependencies:
 * - state/store.js: Centralized state management
 * - utils/pyBridge.js: Python-JavaScript communication bridge
 * - components/*: UI component modules
 * - utils/helpers.js: Utility functions
 * 
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
import { createRecipientBar } from "./components/recipientBar.js";
import { createMessageHistory } from "./components/messageHistory.js";
import { createMessageInput } from "./components/messageInput.js";
import { createDeviceListOverlay } from "./components/deviceListOverlay.js";
import { createMessageDetailsOverlay } from "./components/messageDetailsOverlay.js";
import { createConnectionWarningModal } from "./components/connectionWarningModal.js";
import { createSettingsOverlay } from "./components/settingsOverlay.js";
import { showToast } from "./components/toast.js";

/**
 * Unified error handler for Python backend responses.
 * 
 * This function provides consistent error handling across all Python function calls.
 * It distinguishes between real errors (which should show toasts) and user-initiated
 * cancellations (which should be handled silently).
 * 
 * @param {Object} result - Python function result with status field
 * @param {string} context - Context description for logging
 * @returns {boolean} - True if handled as error, false if normal operation
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
 * Synchronize connection state with Python backend.
 * 
 * This function polls the Python backend to get the actual BLE connection status
 * and updates the JavaScript state accordingly. It's called after connection
 * operations and can be used for auto-disconnect detection.
 * 
 * @returns {Promise<boolean>} - True if state was updated, false if no change
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
        this.REFRESH_TIMEOUT_MS = 7000; // 7 seconds (hub scans for 5s + 2s buffer for BLE resume/response)
        this.MAX_GATT_RETRIES = 2; // Retry GATT errors 2 times (3 total attempts)
        this.init();
    }

    async init() {
        /**
         * Initialize the application and set up all core systems.
         * 
         * This method handles the complete application startup sequence including:
         * - Setting up Python backend integration and event handlers
         * - Registering state change listeners for reactive updates
         * - Configuring click-outside handlers for UI interactions
         * - Performing initial render of all components
         * 
         * Initialization Flow:
         * 1. Initialize with empty device list
         * 2. Set up direct function callbacks for Python integration
         * 3. Register event listeners for Python backend events
         * 4. Set up state management and reactive rendering
         * 5. Initialize Python backend when ready
         * 6. Render initial UI components
         * 
         * Error Handling:
         * - Graceful fallback if Python unavailable
         * - Comprehensive logging for debugging initialization issues
         * - Continues operation even if some systems fail to initialize
         */
        // Initialize with empty device list - will be populated by Python backend
        setState({
            allDevices: [],
            lastUpdateTime: null,
        });

        // Add click-outside handler for command palette
        this.setupClickOutsideHandler();

        // Wait for Python to be ready, then initialize
        this.initializePython();

        // Direct function for Python to call
        window.onDevicesUpdated = (devices) => {
            console.log("=== JavaScript onDevicesUpdated called ===");
            console.log(`Received ${devices?.length || 0} devices from hub`);
            
            // Clear refresh timeout since we got a response
            if (this.refreshTimeout) {
                clearTimeout(this.refreshTimeout);
                this.refreshTimeout = null;
                console.log("Cleared refresh timeout (successful response)");
            }
            
            setState({
                allDevices: devices,
                lastUpdateTime: new Date(),
                isRefreshing: false, // Clear loading state when devices received
            });
        };

        // Direct function calls only - no event listeners needed

        // Direct function for Python to call
        window.onBLEConnected = (data) => {
            console.log("Direct BLE connected call:", data);
            console.log("Data type:", typeof data);
            console.log("Data keys:", Object.keys(data || {}));
            console.log("Device name:", data?.deviceName);
            setState({
                hubConnected: true,
                hubDeviceName: data?.deviceName,
                hubConnecting: false,
            });
            
            // Auto-refresh devices on connection
            console.log("Auto-refreshing devices on BLE connection...");
            this.handleRefreshDevices();
        };

        // Direct function calls only - no event listeners needed

        // Direct function for Python to call
        window.onBLEDisconnected = () => {
            console.log("Direct BLE disconnected call");
            setState({
                hubConnected: false,
                hubDeviceName: null,
                hubConnecting: false,
                isRefreshing: false, // Cancel any pending device scans
            });
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
         * Start auto-disconnect detection by polling Python backend.
         * 
         * IMPORTANT: Polling paused during ESP-NOW device scans to prevent
         * BLE traffic from interfering with ESP-NOW IRQ on ESP32-C3's shared radio.
         * 
         * This method sets up a polling mechanism that checks the actual BLE
         * connection status every 30 seconds when connected AND not scanning.
         * It helps detect unexpected disconnections that might not trigger the
         * normal disconnect callbacks.
         * 
         * Timing rationale:
         * - 30 second interval (was 5s) reduces BLE traffic by 6x
         * - Skips polling during device scans (isRefreshing flag)
         * - Only logs when state actually changes (reduces noise)
         * 
         * Note: Interval runs for application lifetime. This is acceptable for MVP.
         * For production, consider storing interval ID and clearing on app cleanup.
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
        this.container.className = "flex flex-col max-w-2xl mx-auto bg-white relative";


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
        );

        const messageHistory = createMessageHistory(state.messageHistory, (message) => {
            setState({ viewingMessage: message, showMessageDetails: true });
            this.components.messageDetailsOverlay.style.display = "flex";
            this.renderMessageDetails();
        });

        const messageInput = createMessageInput(
            state.currentMessage,
            state.showCommandPalette,
            canSend,
            () => setState({ showCommandPalette: true }),
            (command) => setState({ currentMessage: command.label }),
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
         * Handle command transmission to playground modules with comprehensive validation.
         * 
         * This method implements a priority-based validation system to ensure commands
         * are only sent when all prerequisites are met. It handles connection checking,
         * device availability validation, command selection verification, and actual
         * command transmission via the BLE hub.
         * 
         * Validation Priority Order:
         * 1. PRIORITY 1: Hub connection status (must be connected)
         * 2. PRIORITY 2: Device availability (must have devices in range)
         * 3. PRIORITY 3: Command selection (must have selected a command)
         * 
         * Process Flow:
         * 1. Check BLE hub connection, show warning modal if disconnected
         * 2. Verify devices are available within selected range
         * 3. Validate command selection, open palette if needed
         * 4. Refresh device list to ensure current data
         * 5. Warn user if device count changed during refresh
         * 6. Format and send command via BLE to hub
         * 7. Update message history and clear input
         * 
         * Error Handling:
         * - Connection warnings with modal prompts
         * - Device availability checks with user feedback
         * - Command validation with visual feedback (flashing)
         * - BLE transmission error handling with toast notifications
         * 
         * User Experience:
         * - Progressive disclosure of requirements (connection → devices → command)
         * - Visual feedback for all validation states
         * - Confirmation prompts for potentially destructive actions
         * - Automatic state cleanup after successful transmission
         */
        // PRIORITY 1: Check hub connection first
        if (!state.hubConnected) {
            this.showConnectionWarningModal();
            return;
        }

        // PRIORITY 2: Check if refresh is in progress
        if (state.isRefreshing) {
            showToast("Please wait for device scan to complete", "warning");
            return;
        }

        // PRIORITY 3: Log device availability (but don't block sending)
        // Device scan can be unreliable, but commands may still work via ESP-NOW broadcast
        const devices = getAvailableDevices();
        console.log("=== SEND MESSAGE: Device check ===");
        console.log("state.allDevices length:", state.allDevices?.length);
        console.log("getAvailableDevices() length:", devices?.length);
        console.log("All devices:", state.allDevices);
        console.log("Available devices:", devices);
        
        if (devices.length === 0) {
            console.log("⚠ No devices detected, but sending command anyway (broadcast mode)");
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
            modules: devices.map((d) => d.name),
            timestamp: now,
            displayTime: formatDisplayTime(now),
        };

        setState({
            messageHistory: [...state.messageHistory, newMessage],
            currentMessage: "",
            showCommandPalette: false,
        });

        // SEND COMMAND VIA BLE (UPDATED)
        try {
            // Convert range slider to RSSI threshold
            const rssiThreshold = state.range === 100 ? "all" : Math.round(-30 - ((state.range - 1) / 98) * 60).toString();

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
         * Refresh device list from ESP32 hub with RSSI-based filtering.
         * 
         * This method performs a device discovery cycle by sending a PING command
         * with an RSSI threshold to the hub. Only modules that can receive the hub's
         * broadcast at the specified signal strength will respond.
         * 
         * IMPORTANT: Filtering happens at the module level, not client-side!
         * - Hub broadcasts PING with RSSI threshold
         * - Only modules with strong enough signal respond
         * - This ensures modules CAN receive commands at that strength
         * 
         * Parameters:
         * -----------
         * rssiThreshold : int or null
         *     RSSI threshold in dBm (e.g., -60)
         *     If null, uses current slider position converted to RSSI
         * retryCount : int (internal)
         *     Number of retry attempts so far
         * 
         * Visual Feedback:
         * - Shows loading spinner during entire ping/response cycle
         * - Maximum 7 second timeout per attempt (5s scan + 2s buffer)
         * - Loading state shown in recipient bar and device list overlay
         * 
         * Error Handling:
         * - GATT errors: Automatically retries up to MAX_GATT_RETRIES times with 1s delays
         * - Empty device lists: No retry (legitimate result)
         * - Timeout per attempt: 7 seconds (hub scans for 5s + buffer for response)
         * - Silent retries (no user interruption)
         */
        
        // Prevent concurrent refreshes (but allow internal retries)
        if (state.isRefreshing && retryCount === 0) {
            console.log("Refresh already in progress, ignoring duplicate request");
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
                setState({ isRefreshing: false });
                
                // Silent failure - no toast to avoid interruption
                
            } else {
                // Non-GATT error - clear state immediately
                console.error("Non-GATT error during refresh:", e);
                
                if (this.refreshTimeout) {
                    clearTimeout(this.refreshTimeout);
                    this.refreshTimeout = null;
                }
                setState({ isRefreshing: false });
            }
        }
    }

    async handleHubConnect() {
        setState({ hubConnecting: true });

        try {
            const result = await PyBridgeToUse.connectHub();
            console.log("ConnectHub result:", result);

            // Use unified error handler
            const isError = handleError(result, "BLE Connection");
            
            if (result.status === "success") {
                console.log("Successfully connected to hub");
                // State will be updated by the BLE connected event
            } else if (result.status === "cancelled") {
                // User cancelled - handled by error handler (no toast shown)
                console.log("User cancelled BLE connection");
                setState({ hubConnecting: false });
            } else if (isError) {
                // Real error occurred - error handler already showed toast
                setState({ hubConnecting: false });
            }
            
            // Always sync state after connection attempt
            await syncConnectionState();
        } catch (e) {
            // Handle exceptions that don't go through Python result format
            console.error("BLE connection exception:", e);
            showToast("Bluetooth connection failed. Please try again.", "error");
            setState({ hubConnecting: false });
        }
    }

    async handleHubDisconnect() {
        try {
            const result = await PyBridgeToUse.disconnectHub();
            console.log("Disconnect result:", result);
            
            // Use unified error handler
            handleError(result, "Hub Disconnect");
            
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
