/**
 * Playground Control App - Main Application
 */

console.log("main.js loading...");

import { state, setState, getAvailableDevices, onStateChange } from "./state/store.js";
import { PyBridge } from "./utils/pyBridge.js";
import { formatDisplayTime } from "./utils/helpers.js";
import { createRecipientBar } from "./components/recipientBar.js";
import { createMessageHistory } from "./components/messageHistory.js";
import { createMessageInput } from "./components/messageInput.js";
import { createDeviceListOverlay } from "./components/deviceListOverlay.js";
import { createMessageDetailsOverlay } from "./components/messageDetailsOverlay.js";
import { createHubConnectionBar } from "./components/hubConnectionBar.js";

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

        // Try Python in background (optional) - with retry logic
        this.retryPythonCall("get_devices", 3)
            .then((devices) => {
                if (devices) {
                    console.log("Real devices from Python:", devices);
                    setState({
                        allDevices: devices,
                        lastUpdateTime: new Date(),
                    });
                }
            })
            .catch((e) => console.log("Python call failed after retries:", e));

        // Listen for device updates
        PyBridge.on("devices-updated", (devices) =>
            setState({
                allDevices: devices,
                lastUpdateTime: new Date(),
            }),
        );
        PyBridge.on("message-sent", (data) => console.log("Message sent:", data));

        // Listen for BLE connection events
        PyBridge.on("ble-connected", (data) => {
            console.log("Hub connected:", data.deviceName);
            setState({
                hubConnected: true,
                hubDeviceName: data.deviceName,
                hubConnecting: false,
            });
        });

        PyBridge.on("ble-disconnected", () => {
            console.log("Hub disconnected");
            setState({
                hubConnected: false,
                hubDeviceName: null,
                hubConnecting: false,
            });
        });

        // Check connection status on load - with retry logic
        this.retryPythonCall("get_connection_status", 3)
            .then((status) => {
                if (status && status.connected) {
                    setState({
                        hubConnected: true,
                        hubDeviceName: status.device,
                    });
                }
            })
            .catch((e) => console.log("Could not get connection status:", e));

        // Register for state changes
        onStateChange(() => this.render());
        console.log("Registered state change listener");

        // Initial render
        console.log("Calling initial render...");
        this.render();
        console.log("init() complete");
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
        this.container.className = "flex flex-col h-screen max-w-2xl mx-auto bg-white relative";
        console.log("Container cleared and styled");

        // Create hub connection bar
        const hubConnectionBar = createHubConnectionBar(
            state.hubConnected,
            state.hubDeviceName,
            () => this.handleHubConnect(),
            () => this.handleHubDisconnect(),
        );

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
            () => setState({ currentMessage: "", showCommandPalette: false }),
            () => this.handleSendMessage(),
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
        console.log("Hub connection bar:", hubConnectionBar);
        console.log("Recipient bar:", recipientBar);
        console.log("Message history:", messageHistory);
        console.log("Message input:", messageInput);

        this.container.appendChild(hubConnectionBar);
        this.container.appendChild(recipientBar);
        this.container.appendChild(messageHistory);
        this.container.appendChild(messageInput);
        this.container.appendChild(this.components.deviceListOverlay);
        this.container.appendChild(this.components.messageDetailsOverlay);

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
        const devicesBefore = getAvailableDevices();
        if (!state.currentMessage || devicesBefore.length === 0) return;

        // Check hub connection
        if (!state.hubConnected) {
            alert("Please connect to the hub first!");
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

            const result = await PyBridge.call("send_command_to_hub", newMessage.command, rssiThreshold);

            if (result.status === "sent") {
                console.log("Command sent to hub:", newMessage.command, "with threshold:", rssiThreshold);
            } else {
                console.error("Send failed:", result.error);
                alert(`Failed to send command: ${result.error}`);
            }
        } catch (e) {
            console.error("Send error:", e);
            alert(`Error sending command: ${e.message}`);
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
            console.log('Calling PyBridge.call("refresh_devices")...');
            const devices = await PyBridge.call("refresh_devices");
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
            const result = await PyBridge.call("connect_hub");

            if (result.status === "success") {
                console.log("Successfully connected to hub");
            } else {
                alert(`Connection failed: ${result.error || "Unknown error"}`);
                setState({ hubConnecting: false });
            }
        } catch (e) {
            alert(`Connection error: ${e.message}`);
            setState({ hubConnecting: false });
        }
    }

    async handleHubDisconnect() {
        try {
            await PyBridge.call("disconnect_hub");
            console.log("Disconnected from hub");
        } catch (e) {
            console.error("Disconnect error:", e);
        }
    }

    async retryPythonCall(functionName, maxRetries = 3, delay = 1000) {
        for (let i = 0; i < maxRetries; i++) {
            try {
                console.log(`Attempting Python call: ${functionName} (attempt ${i + 1}/${maxRetries})`);
                const result = await PyBridge.call(functionName);
                console.log(`Python call successful: ${functionName}`);
                return result;
            } catch (error) {
                console.log(`Python call failed (attempt ${i + 1}/${maxRetries}):`, error.message);
                if (i === maxRetries - 1) {
                    throw error;
                }
                // Wait before retrying
                await new Promise((resolve) => setTimeout(resolve, delay));
            }
        }
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
