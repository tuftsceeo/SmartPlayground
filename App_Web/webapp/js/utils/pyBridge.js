/**
 * PyBridge - Python-JavaScript Communication Bridge
 * 
 * Interface for JavaScript to call Python backend (PyScript).
 */

class PythonNotReadyError extends Error {
  constructor(functionName) {
    super(`Python function '${functionName}' not available. PyScript may still be initializing.`);
    this.name = 'PythonNotReadyError';
    this.functionName = functionName;
  }
}

async function callPython(fnName, ...args) {
  const fn = window[fnName];
  if (typeof fn !== 'function') {
    throw new PythonNotReadyError(fnName);
  }
  
  try {
    return await fn(...args);
  } catch (error) {
    error.pythonFunction = fnName;
    error.pythonArgs = args;
    console.error(`Python call failed: ${fnName}`, error);
    throw error;
  }
}

const PyBridge = {
  isPythonReady() {
    return typeof window.get_devices === 'function' && 
           typeof window.get_connection_status === 'function';
  },

  async waitForPython(timeout = 5000) {
    const start = Date.now();
    while (!this.isPythonReady() && (Date.now() - start) < timeout) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    return this.isPythonReady();
  },

  async getDevices() {
    return await callPython('get_devices');
  },

  async getConnectionStatus() {
    return await callPython('get_connection_status');
  },

  // Unused BLE stubs
  async connectHub() {
    console.error('❌ connectHub() is deprecated - use connectHubSerial()');
    throw new Error('BLE not supported - use connectHubSerial()');
  },

  async disconnectHub() {
    console.error('❌ disconnectHub() is deprecated - use disconnectHubSerial()');
    throw new Error('BLE not supported - use disconnectHubSerial()');
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

  async softResetDevice() {
    return await callPython('soft_reset_device');
  },

  async hardResetDevice() {
    return await callPython('hard_reset_device');
  },
};

window.PyBridge = PyBridge;
window.PythonNotReadyError = PythonNotReadyError;
export { PyBridge, PythonNotReadyError };