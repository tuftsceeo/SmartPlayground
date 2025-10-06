/**
 * Playground Control App - Main Application
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
        console.log("init() called");

        // Use mock devices for now (Python call not completing)
        const mockDevices = [
            { id: "M-A3F821", name: "M-A3F821", type: "module", rssi: -25, signal: 3, battery: "full" },
            { id: "M-B4C932", name: "M-B4C932", type: "module", rssi: -40, signal: 3, battery: "high" },
            { id: "M-C5D043", name: "M-C5D043", type: "module", rssi: -58, signal: 2, battery: "medium" },
            { id: "E-D6E154", name: "E-D6E154", type: "extension", rssi: -48, signal: 2, battery: "high" },
            { id: "E-E7F265", name: "E-E7F265", type: "extension", rssi: -78, signal: 1, battery: "low" },
            { id: "B-F8G376", name: "B-F8G376", type: "button", rssi: -85, signal: 1, battery: "medium" },
        ];

        setState({
            allDevices: mockDevices,
            lastUpdateTime: new Date(),
        });
        console.log("Mock devices loaded:", mockDevices);

        // Add click-outside handler for command palette
        this.setupClickOutsideHandler();

        // Wait for Python to be ready, then initialize
        this.initializePython();

        // Listen for device updates
        PyBridgeToUse.on("devices-updated", (devices) =>
            setState({
                allDevices: devices,
                lastUpdateTime: new Date(),
            }),
        );
        PyBridgeToUse.on("message-sent", (data) => console.log("Message sent:", data));

        // Listen for BLE connection events
        PyBridgeToUse.on("ble-connected", (data) => {
            console.log("Hub connected:", data.deviceName);
            setState({
                hubConnected: true,
                hubDeviceName: data.deviceName,
                hubConnecting: false,
            });
        });

        PyBridgeToUse.on("ble-disconnected", () => {
            console.log("Hub disconnected");
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
            console.log("loadPythonData called");
            
            // Try to get real devices from Python
            if (typeof PyBridgeToUse.getDevices === 'function') {
                const devices = await PyBridgeToUse.getDevices();
                if (devices && devices.length > 0) {
                    console.log("Real devices from Python:", devices);
                    setState({
                        allDevices: devices,
                        lastUpdateTime: new Date(),
                    });
                }
            } else {
                console.error("PyBridge.getDevices is not a function!");
            }

            // Check connection status
            if (typeof PyBridgeToUse.getConnectionStatus === 'function') {
                const status = await PyBridgeToUse.getConnectionStatus();
                if (status && status.connected) {
                    setState({
                        hubConnected: true,
                        hubDeviceName: status.device,
                    });
                }
            } else {
                console.error("PyBridge.getConnectionStatus is not a function!");
            }
        } catch (e) {
            console.log("Python data loading failed:", e);
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

            if (result.status === "sent") {
                console.log("Command sent to hub:", newMessage.command, "with threshold:", rssiThreshold);
            } else {
                console.error("Send failed:", result.error);
                showToast(`Failed to send command: ${result.error}`, "error");
            }
        } catch (e) {
            console.error("Send error:", e);
            showToast(`Error sending command: ${e.message}`, "error");
        }
    }

    async handleRefreshDevices() {
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
            console.log('Calling PyBridge.refreshDevices()...');
            const devices = await PyBridgeToUse.refreshDevices();
            console.log("Python returned:", devices);

            console.log("Updating allDevices in state...");
            setState({
                allDevices: devices || [],
                lastUpdateTime: new Date(),
            });
            console.log("State updated, new allDevices:", state.allDevices);
        } catch (e) {
            console.log("Python backend not ready, refresh command logged only:", e);
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
        setState({ hubConnecting: true });

        try {
            const result = await PyBridgeToUse.connectHub();

            if (result.status === "success") {
                console.log("Successfully connected to hub");
                // State will be updated by the BLE connected event
            } else if (result.status === "cancelled") {
                // User cancelled - this is normal, don't show error
                console.log("User cancelled BLE connection");
                setState({ hubConnecting: false });
            } else {
                // Actual error occurred - only show if it's a real error, not user cancellation
                const errorMsg = result.error || "Unknown error";
                if (!errorMsg.toLowerCase().includes("cancelled") && 
                    !errorMsg.toLowerCase().includes("user cancelled") &&
                    !errorMsg.toLowerCase().includes("notallowederror") &&
                    !errorMsg.toLowerCase().includes("aborterror")) {
                    console.error("BLE connection error:", errorMsg);
                    // Show a more user-friendly error message
                    showToast("Bluetooth connection failed. Please try again.", "error");
                } else {
                    console.log("User cancelled connection (no error to show)");
                }
                setState({ hubConnecting: false });
            }
        } catch (e) {
            // Only show error if it's not a user cancellation
            const errorMsg = e.message || e.toString();
            if (!errorMsg.toLowerCase().includes("cancelled") && 
                !errorMsg.toLowerCase().includes("user cancelled") &&
                !errorMsg.toLowerCase().includes("notallowederror") &&
                !errorMsg.toLowerCase().includes("aborterror")) {
                console.error("BLE connection exception:", errorMsg);
                showToast("Bluetooth connection failed. Please try again.", "error");
            } else {
                console.log("User cancelled connection (no error to show)");
            }
            setState({ hubConnecting: false });
        }
    }

    async handleHubDisconnect() {
        try {
            await PyBridgeToUse.disconnectHub();
            console.log("Disconnected from hub");
        } catch (e) {
            console.error("Disconnect error:", e);
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
console.log("About to create App instance...");
try {
    const app = new App();
    console.log("App created successfully:", app);
} catch (error) {
    console.error("Error creating App:", error);
}
