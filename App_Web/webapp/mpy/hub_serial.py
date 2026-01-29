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

# Debug mode flag
_DEBUG_MODE = True

from pyscript import window
from pyodide.ffi import create_proxy
import asyncio
import json

print("✅ hub_serial.py LOADED")


class SerialConnection:
    """Manages Serial connection and JSON message protocol"""
    
    def __init__(self):
        """Initialize Serial connection manager"""
        self.on_data_callback = None
        self.on_connection_lost_callback = None
        self.read_loop_stop = None
        
        # Store proxies as instance variables to prevent garbage collection
        self._on_data_proxy = None
        self._on_error_proxy = None
        
        # Explicit proxy keepalive list (extra safety against garbage collection)
        self._proxy_keepalive = []
        
        # Line buffer for incomplete messages
        self._line_buffer = ""
        
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
        if _DEBUG_MODE:
            print("🔵 [hub_serial.py] _start_json_read_loop CALLED")
        
        if self.read_loop_stop:
            # Stop existing loop
            if _DEBUG_MODE:
                print("🔵 [hub_serial.py] Stopping existing loop")
            self.read_loop_stop()
        
        # Clear line buffer for fresh start
        self._line_buffer = ""
        
        if _DEBUG_MODE:
            print(f"🔵 [hub_serial.py] Adapter exists: {hasattr(self, 'adapter')}")
            print(f"🔵 [hub_serial.py] startReadLoop exists: {hasattr(self.adapter, 'startReadLoop')}")
        
        # Start read loop with JS adapter
        def on_data(data):
            """Handle incoming data from JS adapter with line buffering"""
            if _DEBUG_MODE:
                print(f"🔵 [hub_serial.py] on_data CALLED!")
                print(f"🔵 [hub_serial.py] data type: {type(data)}")
                print(f"🔵 [hub_serial.py] data length: {len(data) if data else 'None'}")
                print(f"🔵 [hub_serial.py] data repr: {repr(data[:200] if data else 'None')}")
            
            if not data:
                if _DEBUG_MODE:
                    print("🔵 [hub_serial.py] Data is empty, returning")
                return
            
            print(f"🔵 hub_serial.py: Received {len(data)} bytes")
            
            # Add data to line buffer
            self._line_buffer += data
            
            if _DEBUG_MODE:
                print(f"🔵 [hub_serial.py] Buffer now: {len(self._line_buffer)} bytes")
            
            # Process complete lines (delimited by \n)
            while '\n' in self._line_buffer:
                line, self._line_buffer = self._line_buffer.split('\n', 1)
                line = line.strip()
                
                if not line:
                    continue
                
                if _DEBUG_MODE:
                    print(f"🔵 [hub_serial.py] Complete line: {line[:100]}")
                    print(f"🔵 [hub_serial.py] Callback exists: {self.on_data_callback is not None}")
                
                # Pass raw line data to callback (let main.py handle JSON parsing)
                print(f"🔵 hub_serial.py: Passing line to callback: {line[:100]}")
                if self.on_data_callback:
                    if _DEBUG_MODE:
                        print(f"🔵 [hub_serial.py] Calling callback with line")
                    self.on_data_callback(line)
                    if _DEBUG_MODE:
                        print(f"🔵 [hub_serial.py] Callback returned")
            
            # Log if there's data remaining in buffer (incomplete line)
            if _DEBUG_MODE and self._line_buffer:
                print(f"🔵 [hub_serial.py] Buffering incomplete line: {repr(self._line_buffer[:50])}")
        
        def on_error(error):
            """Handle read errors"""
            print(f"🔵 [hub_serial.py] Serial read error: {error}")
            if self.on_connection_lost_callback:
                self.on_connection_lost_callback()
        
        # Wrap callbacks with create_proxy to prevent destruction
        # Store as instance variables to prevent garbage collection
        self._on_data_proxy = create_proxy(on_data)
        self._on_error_proxy = create_proxy(on_error)
        
        # Add to keepalive list for extra safety
        self._proxy_keepalive = [self._on_data_proxy, self._on_error_proxy]
        
        if _DEBUG_MODE:
            print(f"🔵 [hub_serial.py] Created proxies: {self._on_data_proxy}, {self._on_error_proxy}")
            print(f"🔵 [hub_serial.py] Keepalive list: {len(self._proxy_keepalive)} proxies")
        
        # Start loop and store stop function
        self.read_loop_stop = self.adapter.startReadLoop(self._on_data_proxy, self._on_error_proxy)
        
        if _DEBUG_MODE:
            print(f"🔵 [hub_serial.py] startReadLoop returned: {self.read_loop_stop}")
    
    async def _stop_json_read_loop(self):
        """Stop the JSON read loop and wait for cleanup to complete"""
        if self.read_loop_stop:
            print("🛑 Stopping JSON read loop...")
            self.read_loop_stop()
            self.read_loop_stop = None
            
            # Clear proxy references
            self._on_data_proxy = None
            self._on_error_proxy = None
            self._proxy_keepalive = []
            
            # Clear line buffer
            self._line_buffer = ""
            
            # Wait for async cleanup to complete (reader.cancel() is async)
            # Longer wait to ensure reader is fully released before REPL operations
            await asyncio.sleep(1.5)
            
            print("✅ JSON read loop stopped and cleaned up")

