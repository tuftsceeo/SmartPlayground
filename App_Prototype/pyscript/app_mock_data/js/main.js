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

console.log("main.js loading...");

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

console.log("All imports loaded");

class App {
    constructor() {
        console.log("App constructor called");
        this.container = document.getElementById("root");
        console.log("Container element:", this.container);
        this.components = {};
        this.init();
    }

    async init() {
        /**
         * Initialize the application and set up all core systems.
         * 
         * This method handles the complete application startup sequence including:
         * - Loading mock device data for immediate UI feedback
         * - Setting up Python backend integration and event handlers
         * - Registering state change listeners for reactive updates
         * - Configuring click-outside handlers for UI interactions
         * - Performing initial render of all components
         * 
         * Initialization Flow:
         * 1. Load mock devices for immediate UI responsiveness
         * 2. Set up direct function callbacks for Python integration
         * 3. Register event listeners for Python backend events
         * 4. Set up state management and reactive rendering
         * 5. Initialize Python backend when ready
         * 6. Render initial UI components
         * 
         * Error Handling:
         * - Graceful fallback to mock data if Python unavailable
         * - Comprehensive logging for debugging initialization issues
         * - Continues operation even if some systems fail to initialize
         */
        console.log("init() called");

        // Demo mode: Initialize with demo devices
        const demoDevices = [
            { id: "M-A3F821", name: "M-A3F821", type: "module", rssi: -25, signal: 3, battery: "full" },
            { id: "M-B4C932", name: "M-B4C932", type: "module", rssi: -40, signal: 3, battery: "high" },
            { id: "M-C5D043", name: "M-C5D043", type: "module", rssi: -58, signal: 2, battery: "medium" },
            { id: "E-D6E154", name: "E-D6E154", type: "extension", rssi: -48, signal: 2, battery: "high" },
            { id: "E-E7F265", name: "E-E7F265", type: "extension", rssi: -78, signal: 1, battery: "low" },
            { id: "B-F8G376", name: "B-F8G376", type: "button", rssi: -85, signal: 1, battery: "medium" },
        ];

        setState({
            allDevices: demoDevices,
            lastUpdateTime: new Date(),
            hubConnected: true,  // Demo mode is always "connected"
            hubDeviceName: "Demo Hub",
        });
        console.log("Demo devices loaded:", demoDevices);

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

        // Listen for device updates (fallback)
        PyBridgeToUse.on("devices-updated", (devices) => {
            console.log("Event-based devices updated:", devices);
            setState({
                allDevices: devices,
                lastUpdateTime: new Date(),
            });
        });
        PyBridgeToUse.on("message-sent", (data) => console.log("Message sent:", data));

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

        // Listen for BLE connection events (fallback)
        PyBridgeToUse.on("ble-connected", (data) => {
            console.log("Event-based BLE connected:", data);
            console.log("Data type:", typeof data);
            console.log("Data keys:", Object.keys(data || {}));
            console.log("Device name:", data?.deviceName);
            setState({
                hubConnected: true,
                hubDeviceName: data?.deviceName,
                hubConnecting: false,
            });
        });

        // Direct function for Python to call
        window.onBLEDisconnected = () => {
            console.log("Direct BLE disconnected call");
            setState({
                hubConnected: false,
                hubDeviceName: null,
                hubConnecting: false,
            });
        };

        // Listen for BLE disconnection events (fallback)
        PyBridgeToUse.on("ble-disconnected", () => {
            console.log("Event-based BLE disconnected");
            setState({
                hubConnected: false,
                hubDeviceName: null,
                hubConnecting: false,
            });
        });

        // Register for state changes
        onStateChange(() => this.render());
        console.log("Registered state change listener");

        // Initial render
        console.log("Calling initial render...");
        this.render();
        console.log("init() complete");
    }

    async initializePython() {
        console.log("Waiting for Python to be ready...");
        
        // Listen for Python ready event
        window.addEventListener('py-ready', async () => {
            console.log("Python ready event received");
            await this.loadPythonData();
        });

        // Also try waiting for functions to be available
        if (typeof PyBridgeToUse.waitForPython === 'function') {
            const isReady = await PyBridgeToUse.waitForPython(5000);
            if (isReady) {
                console.log("Python functions are ready");
                await this.loadPythonData();
            } else {
                console.warn("Python not ready after timeout, using mock data");
            }
        } else {
            console.error("PyBridge.waitForPython is not a function!");
            console.log("Available PyBridge methods:", Object.keys(PyBridgeToUse));
        }
    }

    async loadPythonData() {
        try {
            console.log("Demo: loadPythonData called - skipping Python calls in demo mode");
            
            // Demo mode: Skip Python calls since we already have demo data loaded
            // The demo devices are already loaded in init()
            console.log("Demo: Using pre-loaded demo devices");
            
        } catch (e) {
            console.log("Demo: Python data loading skipped:", e);
        }
    }

    render() {
        console.log("render() called, isRefreshing:", state.isRefreshing);
        const devices = getAvailableDevices();
        console.log("Available devices:", devices);
        const canSend = state.currentMessage && devices.length > 0;

        // Don't clear and rebuild if an overlay is showing
        if (state.showDeviceList || state.showMessageDetails) {
            console.log("Overlay is open, skipping full render");
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
        console.log("Container cleared and styled");


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

        console.log("Creating message input component...");
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
        console.log("Message input created:", messageInput);

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
        console.log("Appending components to DOM...");
        console.log("Recipient bar:", recipientBar);
        console.log("Message history:", messageHistory);
        console.log("Message input:", messageInput);

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

        console.log("All components appended. Container children count:", this.container.children.length);

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
        // Demo mode: Skip connection check since we're always "connected"
        // PRIORITY 1: Check hub connection first (disabled in demo mode)
        // if (!state.hubConnected) {
        //     this.showConnectionWarningModal();
        //     return;
        // }

        // PRIORITY 2: Check if devices are available
        const devicesBefore = getAvailableDevices();
        if (devicesBefore.length === 0) {
            showToast("Demo: No simulated devices in range. Try adjusting the range slider.", "warning");
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

        // DEMO MODE: Simulate command sending
        try {
            console.log("Demo: Simulating command sending...");
            
            // Simulate command processing delay
            await new Promise(resolve => setTimeout(resolve, 500));
            
            // Simulate device response variations
            const currentDevices = state.allDevices;
            const updatedDevices = currentDevices.map(device => {
                // Simulate slight RSSI variations after command
                const variation = Math.floor(Math.random() * 6) - 3; // -3 to +3
                const newRssi = Math.max(-100, Math.min(-10, device.rssi + variation));
                
                // Update signal strength based on new RSSI
                let newSignal;
                if (newRssi >= -50) newSignal = 3;
                else if (newRssi >= -70) newSignal = 2;
                else if (newRssi >= -85) newSignal = 1;
                else newSignal = 0;
                
                return {
                    ...device,
                    rssi: newRssi,
                    signal: newSignal
                };
            });
            
            // Update devices with simulated response
            setState({
                allDevices: updatedDevices,
                lastUpdateTime: new Date(),
            });
            
            console.log("Demo: Command simulated successfully:", newMessage.command);
            showToast(`Demo: Command "${newMessage.command}" sent to ${devices.length} simulated devices`, "success");
            
        } catch (e) {
            console.error("Demo: Command simulation error:", e);
            showToast(`Demo: Error in command simulation: ${e.message}`, "error");
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
        console.log("=== REFRESH START ===");
        console.log("Current state.allDevices:", state.allDevices);

        setState({ isRefreshing: true });
        console.log("Set isRefreshing: true");

        // Update button state directly
        const refreshBtn = this.components.deviceListOverlay?.querySelector("#refreshBtn");
        if (refreshBtn) {
            console.log("Adding spin to button");
            refreshBtn.classList.add("animate-spin");
        } else {
            console.log("WARNING: refreshBtn not found");
        }

        try {
            console.log('Demo: Simulating device refresh...');
            
            // Demo mode: Simulate device refresh with slight variations
            const currentDevices = state.allDevices;
            const updatedDevices = currentDevices.map(device => {
                // Simulate slight RSSI variations
                const variation = Math.floor(Math.random() * 10) - 5; // -5 to +5
                const newRssi = Math.max(-100, Math.min(-10, device.rssi + variation));
                
                // Update signal strength based on new RSSI
                let newSignal;
                if (newRssi >= -50) newSignal = 3;
                else if (newRssi >= -70) newSignal = 2;
                else if (newRssi >= -85) newSignal = 1;
                else newSignal = 0;
                
                return {
                    ...device,
                    rssi: newRssi,
                    signal: newSignal
                };
            });
            
            console.log("Demo: Updated devices with simulated variations");
            setState({
                allDevices: updatedDevices,
                lastUpdateTime: new Date(),
            });
            console.log("Demo: State updated with simulated device refresh");
        } catch (e) {
            console.log("Demo: Device refresh simulation failed:", e);
        }

        console.log("Setting timeout for isRefreshing: false...");
        setTimeout(() => {
            console.log("Timeout fired, setting isRefreshing: false");
            setState({ isRefreshing: false });
            // Remove spin directly
            const refreshBtn = this.components.deviceListOverlay?.querySelector("#refreshBtn");
            if (refreshBtn) {
                refreshBtn.classList.remove("animate-spin");
            }
        }, 1000);
    }

    async handleHubConnect() {
        console.log("Demo: Hub is already connected in demo mode");
        // Demo mode: Hub is always "connected"
        setState({ 
            hubConnected: true, 
            hubDeviceName: "Demo Hub",
            hubConnecting: false 
        });
        showToast("Demo: Connected to virtual hub (simulated)", "success");
    }

    async handleHubDisconnect() {
        console.log("Demo: Simulating hub disconnection...");
        setState({ 
            hubConnected: false, 
            hubDeviceName: null,
            hubConnecting: false 
        });
        showToast("Demo: Disconnected from virtual hub (simulated)", "info");
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
console.log("About to create App instance...");
try {
    const app = new App();
    console.log("App created successfully:", app);
} catch (error) {
    console.error("Error creating App:", error);
}
