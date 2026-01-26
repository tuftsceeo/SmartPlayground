/**
 * Serial Adapter - Web Serial API wrapper
 *
 * Native JavaScript layer for Web Serial API (avoids Pyodide async issues).
 * Handles connect/disconnect, read/write, timeouts, and reader/writer locks.
 * 
 * Used by: mpy/hub_serial.py
 */

export const SerialAdapter = {
  port: null,
  reader: null,
  writer: null,

  /**
   * Check if serial port is connected
   * @returns {boolean}
   */
  isConnected() {
    return this.port !== null && this.port.readable !== null;
  },

  /**
   * Request and connect to a serial port
   * @returns {Promise<boolean>} True if connected successfully
   */
  async connect() {
    try {
      // Check API availability
      if (!navigator.serial) {
        console.error('ERROR: Web Serial API not available!');
        console.error('Please use Chrome or Edge browser');
        return false;
      }

      // Request port from user
      console.log('Requesting serial port...');
      this.port = await navigator.serial.requestPort();

      if (!this.port) {
        console.log('No port selected');
        return false;
      }

      console.log('Port selected');

      // Open port with 115200 baud (standard for ESP32)
      await this.port.open({ baudRate: 115200 });
      console.log('Port opened at 115200 baud');

      console.log('Serial connected successfully');
      return true;

    } catch (error) {
      const errorMsg = error.toString().toLowerCase();

      // User cancelled port selection
      if (errorMsg.includes('cancelled') || errorMsg.includes('aborted')) {
        console.log('User cancelled serial port selection');
        return false;
      }

      // Port is already in use
      if (errorMsg.includes('in use') || errorMsg.includes('busy')) {
        console.error('ERROR: Serial port is already in use!');
        return false;
      }

      // Generic error
      console.error('Serial connection error:', error);
      return false;
    }
  },

  /**
   * Disconnect from serial port
   * @returns {Promise<boolean>}
   */
  async disconnect() {
    try {
      // Release locks first
      await this.releaseReader();
      await this.releaseWriter();

      // Close port
      if (this.port) {
        await this.port.close();
        this.port = null;
        console.log('Serial port closed');
      }

      return true;

    } catch (error) {
      console.error('Disconnect error:', error);
      return false;
    }
  },

  /**
   * Get a reader lock for the serial port
   * @returns {Promise<ReadableStreamDefaultReader>}
   */
  async getReader() {
    if (!this.port || !this.port.readable) {
      console.error('❌ [SerialAdapter] getReader() failed: Port not available or not readable');
      console.log('  Port exists:', !!this.port);
      console.log('  Port readable:', this.port ? !!this.port.readable : 'N/A');
      throw new Error('Port not available or not open');
    }

    console.log('🔒 [SerialAdapter] Acquiring reader lock');
    this.reader = this.port.readable.getReader();
    return this.reader;
  },

  /**
   * Release the reader lock
   * @returns {Promise<void>}
   */
  async releaseReader() {
    if (this.reader) {
      try {
        console.log('🔓 [SerialAdapter] Releasing reader lock');
        await this.reader.cancel();
        this.reader.releaseLock();
      } catch (error) {
        console.warn('⚠️ [SerialAdapter] Error releasing reader:', error);
        // Ignore errors - may already be released
      }
      this.reader = null;
    }
  },

  /**
   * Get a writer lock for the serial port
   * @returns {Promise<WritableStreamDefaultWriter>}
   */
  async getWriter() {
    if (!this.port || !this.port.writable) {
      throw new Error('Port not available or not open');
    }

    this.writer = this.port.writable.getWriter();
    return this.writer;
  },

  /**
   * Release the writer lock
   * @returns {Promise<void>}
   */
  async releaseWriter() {
    if (this.writer) {
      try {
        this.writer.releaseLock();
      } catch (error) {
        // Ignore errors - may already be released
      }
      this.writer = null;
    }
  },

  /**
   * Write data to serial port
   * @param {string|Uint8Array} data - Data to write
   * @returns {Promise<void>}
   */
  async write(data) {
    if (!this.isConnected()) {
      console.error('❌ [SerialAdapter] write() failed: Not connected');
      throw new Error('Not connected to serial port');
    }

    const writer = await this.getWriter();
    
    try {
      // Convert string to Uint8Array if needed
      const bytes = typeof data === 'string' 
        ? new TextEncoder().encode(data)
        : data;

      // Debug logging
      if (typeof data === 'string') {
        const printable = data
          .replace(/\x03/g, '<CTRL-C>')
          .replace(/\x04/g, '<CTRL-D>')
          .replace(/\x01/g, '<CTRL-A>')
          .replace(/\x02/g, '<CTRL-B>');
        console.log(`📤 [SerialAdapter] Writing ${bytes.length} bytes:`, printable.substring(0, 100));
      } else {
        console.log(`📤 [SerialAdapter] Writing ${bytes.length} bytes (binary)`);
      }

      await writer.write(bytes);
      
    } finally {
      await this.releaseWriter();
    }
  },

  /**
   * Read data from serial port with timeout
   * @param {number} timeoutMs - Timeout in milliseconds (default 2000)
   * @returns {Promise<string>} Decoded text data, or empty string on timeout
   */
  async read(timeoutMs = 2000) {
    if (!this.isConnected()) {
      console.error('❌ [SerialAdapter] read() failed: Not connected');
      throw new Error('Not connected to serial port');
    }

    const reader = await this.getReader();

    try {
      // Use Promise.race for native timeout handling
      const result = await Promise.race([
        reader.read(),
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('timeout')), timeoutMs)
        )
      ]);

      // Check if stream is done
      if (result.done) {
        console.log('⚠️ [SerialAdapter] Stream done (closed)');
        return '';
      }

      // Decode and return
      const text = new TextDecoder().decode(result.value);
      if (text) {
        console.log(`📥 [SerialAdapter] Read ${text.length} bytes:`, text.substring(0, 100));
      }
      return text;

    } catch (error) {
      // Timeout is expected, return empty string
      if (error.message === 'timeout') {
        console.log(`⏱️ [SerialAdapter] Read timeout after ${timeoutMs}ms`);
        return '';
      }
      console.error('❌ [SerialAdapter] Read error:', error);
      throw error;

    } finally {
      await this.releaseReader();
    }
  },

  /**
   * Read continuously until a specific string is found or timeout
   * @param {string} expected - String to wait for
   * @param {number} timeoutMs - Total timeout in milliseconds
   * @returns {Promise<{found: boolean, buffer: string}>}
   */
  async readUntil(expected, timeoutMs = 5000) {
    const startTime = Date.now();
    let buffer = '';

    while ((Date.now() - startTime) < timeoutMs) {
      try {
        const chunk = await this.read(500);
        buffer += chunk;

        if (buffer.includes(expected)) {
          return { found: true, buffer };
        }

        // No data and approaching timeout
        if (!chunk && (Date.now() - startTime) > (timeoutMs * 0.8)) {
          console.log('⚠️ No data received, approaching timeout...');
        }

      } catch (error) {
        console.error('Read error:', error);
        break;
      }
    }

    return { found: false, buffer };
  },

  /**
   * Start a continuous read loop with callback
   * Handles reader lifecycle internally
   * @param {Function} onData - Callback function(data: string)
   * @param {Function} onError - Error callback
   * @returns {Function} Stop function to cancel the loop
   */
  startReadLoop(onData, onError) {
    let running = true;
    let currentReader = null;

    const loop = async () => {
      try {
        // Get fresh reader for this loop
        if (!this.port || !this.port.readable) {
          console.error('❌ [SerialAdapter] startReadLoop: Port not available');
          throw new Error('Port not available');
        }

        console.log('🔁 [SerialAdapter] Starting read loop');
        currentReader = this.port.readable.getReader();

        while (running) {
          const { value, done } = await currentReader.read();

          if (done) {
            console.log('🛑 [SerialAdapter] Serial stream closed');
            break;
          }

          if (value) {
            const text = new TextDecoder().decode(value);
            onData(text);
          }
        }

      } catch (error) {
        console.error('❌ [SerialAdapter] Read loop error:', error);
        if (running && onError) {
          onError(error);
        }
      } finally {
        // Clean up reader
        if (currentReader) {
          try {
            console.log('🧹 [SerialAdapter] Cleaning up read loop reader');
            await currentReader.cancel();
            currentReader.releaseLock();
          } catch (e) {
            console.warn('⚠️ [SerialAdapter] Cleanup error:', e);
            // Ignore cleanup errors
          }
        }
      }
    };

    // Start the loop
    loop();

    // Return stop function
    return () => {
      console.log('⏹️ [SerialAdapter] Stopping read loop');
      running = false;
      if (currentReader) {
        currentReader.cancel().catch(() => {});
      }
    };
  }
};

// Make it available globally for Python
window.serialAdapter = SerialAdapter;

export default SerialAdapter;

