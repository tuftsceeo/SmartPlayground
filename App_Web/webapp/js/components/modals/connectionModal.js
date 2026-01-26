/**
 * Connection Modal Component
 * 
 * Provides UI for selecting connection type to hub:
 * - BLE (Bluetooth) - Wireless, requires Web Bluetooth API
 * - Serial (USB) - Wired, requires Web Serial API (Chrome/Edge only)
 */

import { setState } from "../../state/store.js";
import { PyBridge } from "../../utils/pyBridge.js";

export function createConnectionModal() {
    const modal = document.createElement('div');
    modal.id = 'connectionModal';
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4';
    
    modal.innerHTML = `
        <div class="bg-white rounded-2xl p-8 max-w-md w-full shadow-2xl" onclick="event.stopPropagation()">
            <div class="flex flex-col items-center">
                <!-- Title -->
                <div class="text-2xl font-bold text-gray-900 mb-2 text-center">Connect to Hub</div>
                <div class="text-sm text-gray-500 mb-6 text-center">Choose your connection method</div>
                
                <!-- BLE Connection Button -->
                <button class="w-full px-6 py-4 bg-blue-600 hover:bg-blue-700 text-white text-base font-medium rounded-xl transition-colors flex items-center justify-between mb-3 group" id="bleBtn">
                    <div class="flex items-center gap-3">
                        <i data-lucide="bluetooth" class="w-5 h-5"></i>
                        <div class="text-left">
                            <div class="font-semibold">Bluetooth Hub</div>
                            <div class="text-xs text-blue-100 opacity-90">Wireless connection</div>
                        </div>
                    </div>
                    <i data-lucide="chevron-right" class="w-5 h-5 opacity-50 group-hover:opacity-100 transition-opacity"></i>
                </button>
                
                <!-- Serial Connection Button -->
                <button class="w-full px-6 py-4 bg-green-600 hover:bg-green-700 text-white text-base font-medium rounded-xl transition-colors flex items-center justify-between mb-4 group" id="serialBtn">
                    <div class="flex items-center gap-3">
                        <i data-lucide="usb" class="w-5 h-5"></i>
                        <div class="text-left">
                            <div class="font-semibold">USB Serial Hub</div>
                            <div class="text-xs text-green-100 opacity-90">Wired connection (cable required)</div>
                        </div>
                    </div>
                    <i data-lucide="chevron-right" class="w-5 h-5 opacity-50 group-hover:opacity-100 transition-opacity"></i>
                </button>
                
                <!-- Info Box -->
                <div class="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 w-full">
                    <div class="flex items-start gap-2">
                        <i data-lucide="info" class="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0"></i>
                        <div class="text-xs text-blue-800">
                            <strong>USB Serial:</strong> Chrome/Edge only. Requires HTTPS or localhost.
                        </div>
                    </div>
                </div>
                
                <!-- Cancel Button -->
                <button class="text-sm text-gray-500 hover:text-gray-700 transition-colors font-medium" id="cancelBtn">
                    Cancel
                </button>
            </div>
        </div>
    `;
    
    // Close modal on background click
    modal.onclick = (e) => {
        if (e.target === modal) {
            closeModal();
        }
    };
    
    // BLE connection handler
    modal.querySelector('#bleBtn').onclick = async (e) => {
        e.stopPropagation();
        await handleBLEConnection();
    };
    
    // Serial connection handler
    modal.querySelector('#serialBtn').onclick = async (e) => {
        e.stopPropagation();
        await handleSerialConnection();
    };
    
    // Cancel handler
    modal.querySelector('#cancelBtn').onclick = (e) => {
        e.stopPropagation();
        closeModal();
    };
    
    function closeModal() {
        modal.remove();
        setState({ hubConnecting: false });
    }
    
    async function handleBLEConnection() {
        console.log("🔵 BLE connection selected");
        closeModal();
        
        setState({ hubConnecting: true });
        
        try {
            const result = await PyBridge.connectHub();
            
            if (result.status === "success") {
                console.log("✅ BLE connected:", result.device);
                setState({
                    hubConnected: true,
                    hubDeviceName: result.device,
                    hubConnectionMode: "ble",
                    hubConnecting: false
                });
            } else if (result.status === "cancelled") {
                console.log("❌ BLE connection cancelled by user");
                setState({ hubConnecting: false });
            } else {
                console.error("❌ BLE connection failed:", result.error);
                setState({ hubConnecting: false });
                alert(`Connection failed: ${result.error || "Unknown error"}`);
            }
        } catch (error) {
            console.error("❌ BLE connection error:", error);
            setState({ hubConnecting: false });
            alert(`Connection error: ${error.message}`);
        }
    }
    
    async function handleSerialConnection() {
        console.log("🟢 Serial connection selected");
        closeModal();
        
        setState({ hubConnecting: true });
        
        try {
            const result = await PyBridge.connectHubSerial();
            
            if (result.status === "success") {
                console.log("✅ Serial connected:", result.device);
                setState({
                    hubConnected: true,
                    hubDeviceName: result.device,
                    hubConnectionMode: "serial",
                    hubConnecting: false
                });
            } else if (result.status === "cancelled") {
                console.log("❌ Serial connection cancelled by user");
                setState({ hubConnecting: false });
            } else {
                console.error("❌ Serial connection failed:", result.error);
                setState({ hubConnecting: false });
                
                // Provide helpful error messages
                const error = result.error || "";
                
                if (error.includes("not available") || error.includes("serial")) {
                    alert("❌ Web Serial API Not Available\n\n" +
                          "Please use Chrome or Edge browser.\n" +
                          "Note: HTTPS or localhost required.");
                } else if (error.includes("in use") || error.includes("busy")) {
                    alert("⚠️  Port Already In Use\n\n" +
                          "The serial port is being used by another application.\n\n" +
                          "Common causes:\n" +
                          "• Thonny IDE is connected\n" +
                          "• Arduino IDE has the port open\n" +
                          "• Another browser tab is using it\n" +
                          "• Serial monitor is running\n\n" +
                          "Solution:\n" +
                          "1. Close Thonny/Arduino IDE\n" +
                          "2. Disconnect serial monitors\n" +
                          "3. Try connecting again");
                } else {
                    alert(`Connection failed: ${error || "Unknown error"}\n\n` +
                          "Check browser console for details.");
                }
            }
        } catch (error) {
            console.error("❌ Serial connection error:", error);
            setState({ hubConnecting: false });
            alert(`Connection error: ${error.message}`);
        }
    }
    
    // Initialize Lucide icons after adding to DOM
    setTimeout(() => {
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }, 0);
    
    return modal;
}

export function showConnectionModal() {
    // Remove existing modal if present
    const existing = document.getElementById('connectionModal');
    if (existing) {
        existing.remove();
    }
    
    // Create and show new modal
    const modal = createConnectionModal();
    document.body.appendChild(modal);
}

