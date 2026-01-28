"""
Hub Serial Connection Manager

Manages USB Serial connection to ESP32 hub using JSON protocol.
Delegates browser API calls to JavaScript adapter (js/adapters/serialAdapter.js).

Responsibilities:
- Connect/disconnect serial port
- Send/receive JSON messages
- Manage JSON read loop
- Handle connection loss

Architecture:
- JavaScript adapter: Handles Web Serial API calls (I/O only)
- This Python class: Handles connection orchestration and JSON protocol
"""

from pyscript import window
from pyodide.ffi import create_proxy
import asyncio
import json


class SerialConnection:
    """Manages Serial connection and JSON message protocol"""
    
    def __init__(self):
        """Initialize Serial connection manager"""
        self.on_data_callback = None
        self.on_connection_lost_callback = None
        self.read_loop_stop = None
        print("🔌 SerialConnection initialized")
        
        # Check if JS adapter is available
        if not hasattr(window, 'serialAdapter'):
            raise Exception("serialAdapter not found! Make sure js/adapters/serialAdapter.js is loaded.")
        
        self.adapter = window.serialAdapter
    
    def is_connected(self):
        """Check if serial port is connected"""
        return self.adapter.isConnected()
    
    async def connect(self):
        """
        Connect to serial port and start JSON read loop.
        
        Returns:
            bool: True if connected successfully, False otherwise
        """
        try:
            # Use JS adapter for connection
            success = await self.adapter.connect()
            
            if success:
                # Start read loop for JSON messages
                self._start_json_read_loop()
                print("Serial connected successfully")
            
            return success
            
        except Exception as e:
            print(f"Serial connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from serial port and stop read loop"""
        try:
            # Stop read loop
            await self._stop_json_read_loop()
            
            # Disconnect via JS adapter
            await self.adapter.disconnect()
            
            print("Serial disconnected")
            return True
            
        except Exception as e:
            print(f"Disconnect error: {e}")
            return False
    
    async def send_json(self, message):
        """
        Send JSON message to hub.
        
        Args:
            message: JSON string or dict to send
            
        Returns:
            bool: True if sent successfully
        """
        try:
            # Convert dict to JSON string if needed
            if isinstance(message, dict):
                message = json.dumps(message)
            
            # Add newline terminator
            if not message.endswith('\n'):
                message += '\n'
            
            # Send via JS adapter
            await self.adapter.write(message)
            return True
            
        except Exception as e:
            print(f"Serial send error: {e}")
            return False
    
    async def send_raw(self, data):
        """
        Send raw bytes without adding newline (for REPL commands).
        
        Args:
            data: Raw string to send (may contain control characters)
        """
        # Debug logging
        printable = data.replace('\x03', '<CTRL-C>').replace('\x04', '<CTRL-D>').replace('\x01', '<CTRL-A>').replace('\x02', '<CTRL-B>')
        print(f"📤 Sending: {repr(printable)}")
        await self.adapter.write(data)
    
    async def read_raw(self, timeout_ms=2000):
        """
        Read raw data with timeout.
        
        Args:
            timeout_ms: Timeout in milliseconds
            
        Returns:
            str: Received data or empty string
        """
        result = await self.adapter.read(timeout_ms)
        if result:
            # Debug logging
            printable = result.replace('\x03', '<CTRL-C>').replace('\x04', '<CTRL-D>').replace('\x01', '<CTRL-A>').replace('\x02', '<CTRL-B>')
            print(f"📥 Received ({len(result)} bytes): {repr(printable[:200])}")
        return result
    
    def _start_json_read_loop(self):
        """Start background read loop for JSON messages using JS adapter"""
        if self.read_loop_stop:
            # Stop existing loop
            self.read_loop_stop()
        
        # Start read loop with JS adapter
        def on_data(data):
            """Handle incoming data from JS adapter"""
            if not data:
                return
            
            print(f"🔵 hub_serial.py: Received {len(data)} bytes")
                
            # Pass line-delimited messages (both JSON and debug text)
            lines = data.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Pass raw line data to callback (let main.py handle JSON parsing)
                print(f"🔵 hub_serial.py: Passing line to callback: {line[:100]}")
                if self.on_data_callback:
                    self.on_data_callback(line)
        
        def on_error(error):
            """Handle read errors"""
            print(f"Serial read error: {error}")
            if self.on_connection_lost_callback:
                self.on_connection_lost_callback()
        
        # Wrap callbacks with create_proxy to prevent destruction
        on_data_proxy = create_proxy(on_data)
        on_error_proxy = create_proxy(on_error)
        
        # Start loop and store stop function
        self.read_loop_stop = self.adapter.startReadLoop(on_data_proxy, on_error_proxy)
    
    async def _stop_json_read_loop(self):
        """Stop the JSON read loop and wait for cleanup to complete"""
        if self.read_loop_stop:
            print("🛑 Stopping JSON read loop...")
            self.read_loop_stop()
            self.read_loop_stop = None
            
            # Wait for async cleanup to complete (reader.cancel() is async)
            await asyncio.sleep(0.5)
            
            print("✅ JSON read loop stopped and cleaned up")

