/**
 * Simplified Python Bridge for PyScript
 * Direct function calls with proper initialization handling
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