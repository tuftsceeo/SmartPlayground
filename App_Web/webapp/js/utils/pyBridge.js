/**
 * PyBridge - Python-JavaScript Communication Bridge
 * 
 * Interface for JavaScript to call Python backend (PyScript).
 * Handles async calls, readiness detection, and error propagation.
 * Python functions exposed via window object.
 */

/**
 * Custom error for Python readiness issues
 */
class PythonNotReadyError extends Error {
  constructor(functionName) {
    super(`Python function '${functionName}' not available. PyScript may still be initializing.`);
    this.name = 'PythonNotReadyError';
    this.functionName = functionName;
  }
}

/**
 * Call Python function with better error context
 * @param {string} fnName - Name of the Python function on window object
 * @param  {...any} args - Arguments to pass to the function
 * @returns {Promise<any>} Result from Python function
 * @throws {PythonNotReadyError} If function not available
 * @throws {Error} If function call fails
 */
async function callPython(fnName, ...args) {
  const fn = window[fnName];
  if (typeof fn !== 'function') {
    throw new PythonNotReadyError(fnName);
  }
  
  try {
    return await fn(...args);
  } catch (error) {
    // Add context to error for better debugging
    error.pythonFunction = fnName;
    error.pythonArgs = args;
    console.error(`Python call failed: ${fnName}`, error);
    throw error;
  }
}

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

  // Direct function calls with simplified error handling
  async getDevices() {
    return await callPython('get_devices');
  },

  async getConnectionStatus() {
    return await callPython('get_connection_status');
  },

  async connectHub() {
    return await callPython('connect_hub');
  },

  async disconnectHub() {
    return await callPython('disconnect_hub');
  },

  async connectHubSerial() {
    return await callPython('connect_hub_serial');
  },

  async disconnectHubSerial() {
    return await callPython('disconnect_hub_serial');
  },

  async sendCommandToHub(command, rssiThreshold) {
    return await callPython('send_command_to_hub', command, rssiThreshold);
  },

  // Firmware upload functions
  async uploadFirmware(files) {
    return await callPython('upload_firmware', files);
  },

  async getBoardInfo() {
    return await callPython('get_board_info');
  },

  async queryDeviceInfoForSetup() {
    return await callPython('query_device_info_for_setup');
  },

  async getDeviceBoardInfo() {
    return await callPython('get_device_board_info');
  },

  async executeFileOnDevice(filePath) {
    return await callPython('execute_file_on_device', filePath);
  },

  /**
   * Soft reset the connected device (MicroPython re-initialization)
   * @returns {Promise<{status: string, message?: string, error?: string}>}
   */
  async softResetDevice() {
    return await callPython('soft_reset_device');
  },

  /**
   * Hard reset the connected device (full hardware reboot)
   * @returns {Promise<{status: string, message?: string, error?: string}>}
   */
  async hardResetDevice() {
    return await callPython('hard_reset_device');
  },

  // Direct function calls only - no event system needed
};

// Make PyBridge and error class available globally and as exports
window.PyBridge = PyBridge;
window.PythonNotReadyError = PythonNotReadyError;
export { PyBridge, PythonNotReadyError };