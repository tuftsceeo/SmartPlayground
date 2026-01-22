/**
 * Bluetooth Adapter - Web Bluetooth API wrapper
 *
 * Native JavaScript layer for Web Bluetooth API (Nordic UART Service).
 * Handles BLE connect/disconnect, notifications, and GATT services.
 * 
 * Used by: mpy/hub_bluetooth.py
 */

export const BluetoothAdapter = {
  // Nordic UART Service UUIDs (lowercase for Web Bluetooth API)
  SERVICE_UUID: '6e400001-b5a3-f393-e0a9-e50e24dcca9e',
  TX_UUID: '6e400003-b5a3-f393-e0a9-e50e24dcca9e', // RX from device perspective (notifications)
  RX_UUID: '6e400002-b5a3-f393-e0a9-e50e24dcca9e', // TX from device perspective (write)

  device: null,
  server: null,
  service: null,
  txCharacteristic: null, // For receiving notifications from device
  rxCharacteristic: null, // For writing to device
  notificationCallback: null,

  /**
   * Check if bluetooth device is connected
   * @returns {boolean}
   */
  isConnected() {
    return this.device !== null && this.server !== null && this.server.connected;
  },

  /**
   * Connect to BLE device by name prefix
   * @param {string} namePrefix - Device name prefix (default 'ESP32')
   * @returns {Promise<boolean>} True if connected successfully
   */
  async connect(namePrefix = 'ESP32') {
    try {
      // Check API availability
      if (!navigator.bluetooth) {
        console.error('ERROR: Web Bluetooth API not available!');
        console.error('Make sure you are using Chrome/Edge and the page is HTTPS or localhost');
        return false;
      }

      console.log('Requesting Bluetooth device...');
      console.log(`Looking for devices with name prefix: ${namePrefix}`);

      // Request device with filters
      this.device = await navigator.bluetooth.requestDevice({
        filters: [{ namePrefix: namePrefix }],
        optionalServices: [this.SERVICE_UUID]
      });

      if (!this.device) {
        console.log('No device selected');
        return false;
      }

      console.log(`Selected device: ${this.device.name}`);

      // Connect to GATT server
      console.log('Connecting to GATT server...');
      this.server = await this.device.gatt.connect();
      console.log('Connected to GATT server');

      // Get Nordic UART service
      console.log(`Getting service ${this.SERVICE_UUID}...`);
      this.service = await this.server.getPrimaryService(this.SERVICE_UUID);
      console.log('Got service');

      // Get characteristics
      console.log('Getting characteristics...');
      this.txCharacteristic = await this.service.getCharacteristic(this.TX_UUID);
      this.rxCharacteristic = await this.service.getCharacteristic(this.RX_UUID);
      console.log('Got characteristics');

      console.log('Bluetooth connected successfully');
      return true;

    } catch (error) {
      const errorMsg = error.toString().toLowerCase();

      // User cancelled
      if (errorMsg.includes('cancelled') || errorMsg.includes('aborted')) {
        console.log('User cancelled Bluetooth device selection');
        return false;
      }

      // Device not found
      if (errorMsg.includes('no devices found') || errorMsg.includes('not found')) {
        console.error('ERROR: No Bluetooth devices found with that name');
        return false;
      }

      // Generic error
      console.error('Bluetooth connection error:', error);
      return false;
    }
  },

  /**
   * Disconnect from BLE device
   * @returns {Promise<boolean>}
   */
  async disconnect() {
    try {
      // Stop notifications
      await this.stopNotifications();

      // Disconnect GATT
      if (this.server && this.server.connected) {
        this.server.disconnect();
        console.log('Bluetooth disconnected');
      }

      // Clear references
      this.device = null;
      this.server = null;
      this.service = null;
      this.txCharacteristic = null;
      this.rxCharacteristic = null;

      return true;

    } catch (error) {
      console.error('Disconnect error:', error);
      return false;
    }
  },

  /**
   * Write data to BLE device
   * @param {string|Uint8Array} data - Data to write
   * @returns {Promise<void>}
   */
  async write(data) {
    if (!this.isConnected() || !this.rxCharacteristic) {
      throw new Error('Not connected to Bluetooth device');
    }

    try {
      // Convert string to Uint8Array if needed
      const bytes = typeof data === 'string'
        ? new TextEncoder().encode(data)
        : data;

      await this.rxCharacteristic.writeValue(bytes);

    } catch (error) {
      console.error('Bluetooth write error:', error);
      throw error;
    }
  },

  /**
   * Start notifications from device
   * @param {Function} callback - Callback function(data: string)
   * @returns {Promise<boolean>}
   */
  async startNotifications(callback) {
    if (!this.isConnected() || !this.txCharacteristic) {
      throw new Error('Not connected to Bluetooth device');
    }

    try {
      this.notificationCallback = callback;

      // Set up notification handler
      this.txCharacteristic.addEventListener('characteristicvaluechanged', (event) => {
        const value = event.target.value; // DataView
        const text = new TextDecoder().decode(value);
        
        if (this.notificationCallback) {
          this.notificationCallback(text);
        }
      });

      // Start notifications
      console.log('Starting notifications...');
      await this.txCharacteristic.startNotifications();
      console.log('Notifications started');

      return true;

    } catch (error) {
      console.error('Start notifications error:', error);
      throw error;
    }
  },

  /**
   * Stop notifications from device
   * @returns {Promise<boolean>}
   */
  async stopNotifications() {
    if (this.txCharacteristic) {
      try {
        await this.txCharacteristic.stopNotifications();
        this.notificationCallback = null;
        console.log('Notifications stopped');
        return true;
      } catch (error) {
        // Ignore errors - may already be stopped
        return false;
      }
    }
    return false;
  },

  /**
   * Get device name
   * @returns {string|null}
   */
  getDeviceName() {
    return this.device ? this.device.name : null;
  },

  /**
   * Get device ID
   * @returns {string|null}
   */
  getDeviceId() {
    return this.device ? this.device.id : null;
  },

  /**
   * Handle disconnection events
   * @param {Function} callback - Called when device disconnects
   */
  onDisconnected(callback) {
    if (this.device) {
      this.device.addEventListener('gattserverdisconnected', () => {
        console.log('Bluetooth device disconnected');
        
        // Clear state
        this.server = null;
        this.service = null;
        this.txCharacteristic = null;
        this.rxCharacteristic = null;
        this.notificationCallback = null;

        // Call callback
        if (callback) {
          callback();
        }
      });
    }
  }
};

// Make it available globally for Python
window.bluetoothAdapter = BluetoothAdapter;

export default BluetoothAdapter;

