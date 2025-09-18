/* web_ble_uart.js
 * Minimal Web Bluetooth helper for Nordic UART (ESP32 "Yell")
 * Usage (from a user-gesture, e.g. a button click):
 *   const ble = new WebBLEUART();
 *   await ble.connect(); // or ble.connect({ namePrefix: 'Fred' })
 *   ble.onReceive = (data) => console.log('RX bytes:', data);
 *   await ble.writeString('hello\n');
 *   // ble.disconnect();
 */
(function () {
  const NUS_SERVICE = '6e400001-b5a3-f393-e0a9-e50e24dcca9e';
  const NUS_RX_CHAR = '6e400002-b5a3-f393-e0a9-e50e24dcca9e'; // write to ESP
  const NUS_TX_CHAR = '6e400003-b5a3-f393-e0a9-e50e24dcca9e'; // notify from ESP

  class WebBLEUART {
    constructor() {
      this.device = null;
      this.server = null;
      this.service = null;
      this._rx = null; // writeCharacteristic
      this._tx = null; // notifyCharacteristic
      this.onReceive = null; // (Uint8Array) => void
      this._handleNotify = this._handleNotify.bind(this);
      this._decoder = new TextDecoder();
      this._encoder = new TextEncoder();
    }

    /**
     * Connect to a device that advertises the Nordic UART Service.
     * options:
     *   - name: exact name to filter (e.g. 'Fred')
     *   - namePrefix: prefix to filter (e.g. 'Fred')
     *   - service: override service UUID (defaults to NUS)
     *   - rxChar / txChar: override characteristic UUIDs
     *
     * Must be called from a user gesture (click/tap).
     */
    async connect(options = {}) {
      if (!navigator.bluetooth) {
        throw new Error('Web Bluetooth not supported in this browser.');
      }

      const serviceUUID = (options.service || NUS_SERVICE).toLowerCase();
      const writeUUID = (options.rxChar || NUS_RX_CHAR).toLowerCase();
      const notifyUUID = (options.txChar || NUS_TX_CHAR).toLowerCase();

      // Build requestDevice filters
      const filters = [{ services: [serviceUUID] }];
      if (options.name) filters.push({ name: options.name });
      if (options.namePrefix) filters.push({ namePrefix: options.namePrefix });

      // Show chooser
      this.device = await navigator.bluetooth.requestDevice({
        filters,
        optionalServices: [serviceUUID], // some UAs require this too
      });

      // Auto-cleanup hook
      this.device.addEventListener('gattserverdisconnected', () => {
        // Note: reconnecting without a user gesture is limited by browser
        // policy
        console.log('BLE disconnected');
      });

      // GATT connect
      this.server = await this.device.gatt.connect();

      // Service + characteristics
      this.service = await this.server.getPrimaryService(serviceUUID);
      this._rx = await this.service.getCharacteristic(writeUUID);
      this._tx = await this.service.getCharacteristic(notifyUUID);

      // Notifications
      await this._tx.startNotifications();
      this._tx.addEventListener('characteristicvaluechanged',
                                this._handleNotify);

      return true;
    }

    /** Internal: notification handler */
    _handleNotify(event) {
      const dv = event.target.value; // DataView
      const data = new Uint8Array(dv.buffer);
      if (this.onReceive) {
        try { this.onReceive(data); } catch (e) { console.error(e); }
      } else {
        console.log('RX', data);
      }
    }

    /** Write raw bytes (Uint8Array or ArrayLike<number>) to ESP RX char */
    async writeBytes(data) {
      if (!this._rx) throw new Error('Not connected');
      const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
      // writeValue() works broadly; writeValueWithoutResponse() may be faster
      // if supported
      if ('writeValueWithoutResponse' in this._rx) {
        await this._rx.writeValueWithoutResponse(bytes);
      } else {
        await this._rx.writeValue(bytes);
      }
    }

    /** Convenience: write a UTF-8 string */
    async writeString(str) {
      await this.writeBytes(this._encoder.encode(str));
    }

    /** Convenience: decode bytes to string (UTF-8) */
    bytesToString(bytes) {
      return this._decoder.decode(bytes);
    }

    /** Disconnect if connected */
    disconnect() {
      try {
        if (this._tx) {
          this._tx.removeEventListener('characteristicvaluechanged',
                                        this._handleNotify);
        }
      } catch {}
      try {
        if (this.device && this.device.gatt.connected) {
          this.device.gatt.disconnect();
        }
      } catch {}
      this.server = null;
      this.service = null;
      this._rx = null;
      this._tx = null;
    }

    /** Simple connected state */
    get isConnected() {
      return !!(this.device && this.device.gatt && this.device.gatt.connected);
    }
  }

  // expose globally
  window.WebBLEUART = WebBLEUART;
})();
