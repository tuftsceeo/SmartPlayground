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
        console.log("Sync connection state:", status);
        
        const wasConnected = state.hubConnected;
        const wasDevice = state.hubDeviceName;
        
        setState({
            hubConnected: status.connected,
            hubDeviceName: status.device,
            hubConnecting: false, // Clear connecting state
        });
        
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
            console.log("Direct devices updated call:", devices);
            console.log("Devices type:", typeof devices);
            console.log("Devices length:", devices?.length);
            console.log("First device:", devices?.[0]);
            setState({
                allDevices: devices,
                lastUpdateTime: new Date(),
            });
            console.log("State updated with devices");
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
        };

        // Direct function calls only - no event listeners needed

        // Direct function for Python to call
        window.onBLEDisconnected = () => {
            console.log("Direct BLE disconnected call");
            setState({
                hubConnected: false,
                hubDeviceName: null,
                hubConnecting: false,
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
         * This method sets up a polling mechanism that checks the actual BLE
         * connection status every 5 seconds when connected. It helps detect
         * unexpected disconnections that might not trigger the normal disconnect
         * callbacks.
         * 
         * Note: Interval runs for application lifetime. This is acceptable for MVP.
         * For production, consider storing interval ID and clearing on app cleanup.
         */
        // Clear any existing monitor to prevent duplicates
        if (this.connectionMonitor) {
            clearInterval(this.connectionMonitor);
        }
        
        this.connectionMonitor = setInterval(async () => {
            // Only poll when we think we're connected
            if (state.hubConnected) {
                console.log("Auto-checking connection status...");
                const stateChanged = await syncConnectionState();
                if (stateChanged) {
                    console.log("Connection state changed during auto-check");
                }
            }
        }, 5000); // Check every 5 seconds
    }

    async initializePython() {
        // Python functions are available directly - no event needed

        // Also try waiting for functions to be available
        if (typeof PyBridgeToUse.waitForPython === 'function') {
            const isReady = await PyBridgeToUse.waitForPython(10000);
            if (isReady) {
                await this.loadPythonData();
            } else {
                console.warn("Python not ready after 10 second timeout.");
            }
        } else {
            console.error("PyBridge.waitForPython is not a function!");
            console.log("Available PyBridge methods:", Object.keys(PyBridgeToUse));
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
        const canSend = state.currentMessage && devices.length > 0;

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

        // PRIORITY 2: Check if devices are available
        const devicesBefore = getAvailableDevices();
        if (devicesBefore.length === 0) {
            showToast("No devices available. Please check your connection and device range.", "warning");
            return;
        }

        // PRIORITY 3: Check message selection
        if (!state.currentMessage) {
            if (!state.showCommandPalette) {
                // Drawer closed - open it
                setState({ showCommandPalette: true });
            } else {
                // Drawer already open - flash message box
                this.flashMessageBox();
            }
            return;
        }

        // Refresh devices before sending
        await this.handleRefreshDevices();
        const devicesAfter = getAvailableDevices();

        // Warn if device list changed
        if (devicesBefore.length !== devicesAfter.length) {
            const confirmed = confirm(
                `Warning: Device list changed!\n\nBefore: ${devicesBefore.length} devices\nAfter: ${devicesAfter.length} devices\n\nSend message to ${devicesAfter.length} devices?`,
            );
            if (!confirmed) return;
        }

        // Use refreshed devices
        const devices = devicesAfter;

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

    async handleRefreshDevices() {
        /**
         * Refresh device list from ESP32 hub with visual feedback and state management.
         * 
         * This method performs a complete device discovery cycle by communicating with
         * the ESP32 hub to get the latest list of available playground modules. It
         * provides visual feedback during the refresh process and handles both success
         * and failure scenarios gracefully.
         * 
         * Refresh Process:
         * 1. Set refresh state to show loading animation
         * 2. Update UI immediately to show spinner on refresh button
         * 3. Call Python backend to request device scan from hub
         * 4. Hub broadcasts PING command via ESP-NOW to all modules
         * 5. Modules respond with their current status (RSSI, battery, etc.)
         * 6. Hub collects responses and sends device list back via BLE
         * 7. Python backend processes response and updates JavaScript state
         * 8. UI automatically re-renders with new device data
         * 
         * Visual Feedback:
         * - Immediate spinner animation on refresh button
         * - State management prevents multiple concurrent refreshes
         * - Minimum 1-second duration for user feedback consistency
         * - Automatic cleanup of loading states
         * 
         * Error Handling:
         * - Graceful fallback if Python backend unavailable
         * - Logging of all errors for debugging
         * - Guaranteed cleanup of loading states even on failure
         * - User feedback via console logging (not toast to avoid spam)
         * 
         * Performance Considerations:
         * - Direct DOM manipulation for immediate visual feedback
         * - Timeout-based cleanup to prevent stuck loading states
         * - State-based refresh prevention to avoid multiple concurrent requests
         */
        setState({ isRefreshing: true });

        // Update button state directly
        const refreshBtn = this.components.deviceListOverlay?.querySelector("#refreshBtn");
        if (refreshBtn) {
            refreshBtn.classList.add("animate-spin");
        }

        try {
            const devices = await PyBridgeToUse.refreshDevices();

            // Note: refreshDevices returns array directly, not status object
            // So we don't use handleError here
            setState({
                allDevices: devices || [],
                lastUpdateTime: new Date(),
            });
        } catch (e) {
            console.log("Python backend not ready, refresh command logged only:", e);
        }

        setTimeout(() => {
            setState({ isRefreshing: false });
            // Remove spin directly
            const refreshBtn = this.components.deviceListOverlay?.querySelector("#refreshBtn");
            if (refreshBtn) {
                refreshBtn.classList.remove("animate-spin");
            }
        }, 1000);
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
