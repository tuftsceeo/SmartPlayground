/**
 * Smart Playground Control - Python-JavaScript Communication Bridge
 * 
 * This module provides a clean interface for JavaScript to communicate with the
 * Python backend running in PyScript. It handles async function calls, error
 * handling, initialization checks, and event listening for Python callbacks.
 * 
 * Key Features:
 * - Direct function calls to Python backend via window object
 * - Async/await support for Python function calls
 * - Automatic Python readiness detection and waiting
 * - Comprehensive error handling with fallback values
 * - Event system for Python-initiated callbacks
 * - Timeout handling for initialization
 * 
 * Python Integration:
 * - Python functions are exposed to JavaScript via window object
 * - PyBridge provides a consistent interface regardless of Python readiness
 * - Handles connection between JavaScript frontend and Python BLE backend
 * - Manages device data flow and command transmission
 * 
 * Available Functions:
 * - getDevices(): Retrieve current device list
 * - getConnectionStatus(): Check BLE hub connection status
 * - connectHub(): Initiate BLE connection to ESP32 hub
 * - disconnectHub(): Disconnect from BLE hub
 * - sendCommandToHub(): Send command via BLE to hub for ESP-NOW broadcast
 * - refreshDevices(): Request fresh device scan from hub
 * 
 * Error Handling:
 * - Graceful degradation when Python backend unavailable
 * - Consistent return values for failed operations
 * - Logging of all errors for debugging
 * - Fallback to empty/default values when appropriate
 * 
 */

const PyBridge = {
  // Check if Python is ready
  isPythonReady() {
    return typeof window.get_devices === 'function' && 
           typeof window.get_connection_status === 'function';
  },

  // Wait for Python to be ready
  async waitForPython(timeout = 5000) {
    const start = Date.now();
    while (!this.isPythonReady() && (Date.now() - start) < timeout) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    return this.isPythonReady();
  },

  // Direct function calls with error handling
  async getDevices() {
    if (!this.isPythonReady()) {
      console.warn("Python not ready, returning empty array");
      return [];
    }
    try {
      return await window.get_devices();
    } catch (e) {
      console.error("get_devices failed:", e);
      return [];
    }
  },

  async getConnectionStatus() {
    if (!this.isPythonReady()) {
      return { connected: false, device: null };
    }
    try {
      return await window.get_connection_status();
    } catch (e) {
      console.error("get_connection_status failed:", e);
      return { connected: false, device: null };
    }
  },

  async connectHub() {
    if (!this.isPythonReady()) {
      return { status: "error", error: "Python not ready" };
    }
    try {
      return await window.connect_hub();
    } catch (e) {
      console.error("connect_hub failed:", e);
      return { status: "error", error: e.message };
    }
  },

  async disconnectHub() {
    if (!this.isPythonReady()) {
      return { status: "error", error: "Python not ready" };
    }
    try {
      return await window.disconnect_hub();
    } catch (e) {
      console.error("disconnect_hub failed:", e);
      return { status: "error", error: e.message };
    }
  },

  async sendCommandToHub(command, rssiThreshold) {
    if (!this.isPythonReady()) {
      return { status: "error", error: "Python not ready" };
    }
    try {
      return await window.send_command_to_hub(command, rssiThreshold);
    } catch (e) {
      console.error("send_command_to_hub failed:", e);
      return { status: "error", error: e.message };
    }
  },

  async refreshDevices() {
    if (!this.isPythonReady()) {
      console.warn("Python not ready, returning empty array");
      return [];
    }
    try {
      return await window.refresh_devices();
    } catch (e) {
      console.error("refresh_devices failed:", e);
      return [];
    }
  },

  // Event listeners for Python events
  on(eventName, callback) {
    window.addEventListener(`py-${eventName}`, (e) => callback(e.detail));
  }
};

// Make PyBridge available globally and as export
window.PyBridge = PyBridge;
export { PyBridge };