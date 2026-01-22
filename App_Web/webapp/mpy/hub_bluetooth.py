"""
Hub Bluetooth Connection Manager

Manages BLE connection to ESP32 hub using Nordic UART Service.
Delegates browser API calls to JavaScript adapter (js/adapters/bluetoothAdapter.js).

Responsibilities:
- Connect/disconnect BLE device
- Send/receive messages
- Handle BLE notifications

BLE Service Details:
- Service UUID: 6e400001-b5a3-f393-e0a9-e50e24dcca9e (Nordic UART)
- TX Characteristic: 6e400003-b5a3-f393-e0a9-e50e24dcca9e (device→browser)
- RX Characteristic: 6e400002-b5a3-f393-e0a9-e50e24dcca9e (browser→device)

Communication Protocol:
- Text-based messaging with newline termination
- JSON format for structured data exchange
- UTF-8 encoding for all text transmission

Architecture:
- JavaScript adapter: Handles Web Bluetooth API calls (I/O only)
- This Python class: Handles connection orchestration and message formatting
"""

from pyscript import window
import json


class BluetoothConnection:
    """Manages BLE connection and message protocol"""
    
    def __init__(self):
        """Initialize Bluetooth connection manager"""
        self.on_data_callback = None
        print("📱 BluetoothConnection initialized")
        
        # Check if JS adapter is available
        if not hasattr(window, 'bluetoothAdapter'):
            raise Exception("bluetoothAdapter not found! Make sure js/adapters/bluetoothAdapter.js is loaded.")
        
        self.adapter = window.bluetoothAdapter
    
    def is_connected(self):
        """Check if bluetooth device is connected"""
        return self.adapter.isConnected()
    
    async def connect(self, name_prefix='ESP32'):
        """
        Connect to BLE device by name prefix.
        
        Args:
            name_prefix: Device name prefix to filter (default 'ESP32')
            
        Returns:
            bool: True if connected successfully
        """
        try:
            # Use JS adapter for connection
            success = await self.adapter.connect(name_prefix)
            
            if success:
                # Set up notification handler
                def on_notification(data):
                    """Handle incoming notifications"""
                    if not data:
                        return
                    
                    print(f"Received: {data}")
                    
                    # Parse JSON messages
                    try:
                        # Data may contain multiple newline-separated messages
                        lines = data.split('\n')
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                            
                            message = json.loads(line)
                            if self.on_data_callback:
                                self.on_data_callback(message)
                    except json.JSONDecodeError:
                        # Not valid JSON, pass raw data to callback
                        if self.on_data_callback:
                            self.on_data_callback(data)
                
                # Start notifications with our handler
                await self.adapter.startNotifications(on_notification)
                
                # Set up disconnection handler
                def on_disconnect():
                    print("Bluetooth device disconnected")
                
                self.adapter.onDisconnected(on_disconnect)
                
                print("Bluetooth connected successfully")
            
            return success
            
        except Exception as e:
            print(f"Bluetooth connection error: {e}")
            return False
    
    async def connect_by_service(self):
        """
        Connect to BLE device by service UUID.
        
        Finds any device with Nordic UART service.
        
        Returns:
            bool: True if connected successfully
        """
        # For now, just use the name-based connection
        # The JS adapter could be extended to support service-based filtering
        print("Note: connect_by_service() currently uses name-based connection")
        return await self.connect('ESP32')
    
    async def send(self, message):
        """
        Send message to device.
        
        Args:
            message: JSON string or dict to send
            
        Returns:
            bool: True if sent successfully
        """
        if not self.is_connected():
            print("Not connected!")
            return False
        
        try:
            # Convert dict to JSON string if needed
            if isinstance(message, dict):
                message = json.dumps(message)
            
            # Add newline terminator if not present
            if not message.endswith('\n'):
                message += '\n'
            
            # Send via JS adapter
            await self.adapter.write(message)
            print(f"Sent: {message.strip()}")
            return True
            
        except Exception as e:
            print(f"Bluetooth send error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from BLE device"""
        try:
            await self.adapter.disconnect()
            print("Bluetooth disconnected")
            return True
            
        except Exception as e:
            print(f"Disconnect error: {e}")
            return False
    
    def get_device_name(self):
        """
        Get connected device name.
        
        Returns:
            str: Device name or None if not connected
        """
        return self.adapter.getDeviceName()
    
    def get_device_id(self):
        """
        Get connected device ID.
        
        Returns:
            str: Device ID or None if not connected
        """
        return self.adapter.getDeviceId()

