"""
Smart Playground Control - Python Backend

This module serves as the PyScript backend for the Smart Playground Control application.
It handles Bluetooth Low Energy (BLE) communication with ESP32 hub devices and manages
the ESP-NOW protocol for communicating with playground modules.

Key Responsibilities:
- BLE connection management with ESP32C6 hub using Nordic UART Service
- Device discovery and RSSI-based filtering of playground modules
- Command transmission and response handling via ESP-NOW protocol
- Data parsing and format conversion between JSON and JavaScript objects
- Event dispatching to JavaScript frontend for real-time UI updates

Communication Flow:
1. Web app connects to ESP32 hub via BLE (Nordic UART Service)
2. Hub broadcasts commands to playground modules via ESP-NOW
3. Modules respond with status/sensor data back through hub
4. Hub forwards responses to web app via BLE notifications
5. Python backend parses responses and updates JavaScript frontend

Dependencies:
- PyScript/Pyodide for browser Python execution
- webBluetooth.py for Web Bluetooth API wrapper
- JavaScript bridge for frontend communication

"""

from pyscript import document, window
from pyodide.ffi import create_proxy
from js import console, CustomEvent, Object
import json
import random
import time

# Import WebBLE class
from mpy.webBluetooth import code
exec(code)  # This executes the code and creates the WebBLE class
ble = WebBLE()  # Create BLE instance

# BLE connection state
ble_connected = False
hub_device_name = None

# Device data (will be updated via BLE from hub)
devices = [
    {"id": "M-A3F821", "name": "M-A3F821", "type": "module", "rssi": -25, "signal": 3, "battery": "full"},
    {"id": "M-B4C932", "name": "M-B4C932", "type": "module", "rssi": -40, "signal": 3, "battery": "high"},
    {"id": "M-C5D043", "name": "M-C5D043", "type": "module", "rssi": -58, "signal": 2, "battery": "medium"},
]

def on_ble_data(data):
    """
    Handle incoming data from ESP32 hub via BLE notifications.
    
    This function processes JSON responses from the hub containing device lists,
    status updates, and other system information. It performs data parsing,
    format conversion, and state updates for the JavaScript frontend.
    
    Parameters:
    -----------
    data : str
        Raw string data received from BLE notification, typically JSON format
        Expected format: {"type": "devices", "list": [{"id": "...", "rssi": -50, "battery": 75}, ...]}
    
    Processing Steps:
    1. Parse JSON data from hub
    2. Handle device list updates (type: "devices")
    3. Convert RSSI values to signal strength bars (0-3)
    4. Convert battery percentages to level categories (low/medium/high/full)
    5. Format data for JavaScript consumption
    6. Dispatch updates to frontend via direct function calls or events
    
    Error Handling:
    - Handles truncated JSON by attempting to complete missing braces
    - Logs all parsing errors for debugging
    - Gracefully continues operation on parse failures
    
    Output:
    -------
    Updates global 'devices' list and notifies JavaScript frontend
    """
    global devices
    console.log(f"=== BLE DATA RECEIVED ===")
    console.log(f"BLE Data: {data}")
    console.log(f"Data type: {type(data)}")
    console.log(f"Data length: {len(data) if hasattr(data, '__len__') else 'N/A'}")
    
    try:
        # Parse JSON response from hub
        console.log(f"Attempting to parse JSON: {data}")
        parsed = json.loads(data)
        console.log(f"Parsed JSON: {parsed}")
        console.log(f"Type field: {parsed.get('type')}")
        
        if parsed.get("type") == "devices":
            console.log("Found devices type - processing device list")
            # Update device list from hub
            device_list = parsed.get("list", [])
            
            # Convert to expected format
            devices = []
            for dev in device_list:
                # Calculate signal bars from RSSI
                rssi = dev.get("rssi", -100)
                if rssi >= -50:
                    signal = 3
                elif rssi >= -70:
                    signal = 2
                elif rssi >= -85:
                    signal = 1
                else:
                    signal = 0
                
                # Convert battery percentage to level
                battery_pct = dev.get("battery", 50)
                if battery_pct >= 75:
                    battery = "full"
                elif battery_pct >= 50:
                    battery = "high"
                elif battery_pct >= 25:
                    battery = "medium"
                else:
                    battery = "low"
                
                devices.append({
                    "id": dev.get("id"),
                    "name": dev.get("id"),
                    "type": "module",
                    "rssi": rssi,
                    "signal": signal,
                    "battery": battery
                })
            
            # Dispatch event to JavaScript - try direct function call first
            if hasattr(window, 'onDevicesUpdated'):
                console.log("Python: Calling onDevicesUpdated directly")
                console.log(f"Devices to send: {devices}")
                # Convert Python list to JavaScript array
                js_devices = []
                for device in devices:
                    js_device = Object.new()
                    js_device.id = device.get("id")
                    js_device.name = device.get("name")
                    js_device.type = device.get("type")
                    js_device.rssi = device.get("rssi")
                    js_device.signal = device.get("signal")
                    js_device.battery = device.get("battery")
                    js_devices.append(js_device)
                console.log(f"Created {len(js_devices)} JS devices")
                window.onDevicesUpdated(js_devices)
                console.log("onDevicesUpdated called successfully")
            else:
                console.log("Python: onDevicesUpdated not available, using event dispatch")
                # Convert Python list to JavaScript array for event dispatch too
                js_devices = []
                for device in devices:
                    js_device = Object.new()
                    js_device.id = device.get("id")
                    js_device.name = device.get("name")
                    js_device.type = device.get("type")
                    js_device.rssi = device.get("rssi")
                    js_device.signal = device.get("signal")
                    js_device.battery = device.get("battery")
                    js_devices.append(js_device)
                event = CustomEvent.new("py-devices-updated", {
                    "detail": js_devices
                })
                window.dispatchEvent(event)
            
            console.log(f"Updated {len(devices)} devices from hub")
            
    except Exception as e:
        console.log(f"Error parsing BLE data: {e}")
        # Try to handle truncated JSON by adding missing closing braces
        if "Unterminated string" in str(e) or "Expecting" in str(e):
            console.log("Attempting to fix truncated JSON...")
            try:
                # Try to complete the JSON
                fixed_data = data + '"]}'
                parsed = json.loads(fixed_data)
                console.log("Successfully fixed truncated JSON")
                # Process the fixed data
                if parsed.get("type") == "devices":
                    # Process devices with fixed data
                    device_list = parsed.get("list", [])
                    devices = []
                    for dev in device_list:
                        rssi = dev.get("rssi", -100)
                        if rssi >= -50:
                            signal = 3
                        elif rssi >= -70:
                            signal = 2
                        elif rssi >= -85:
                            signal = 1
                        else:
                            signal = 0
                        
                        battery_pct = dev.get("battery", 50)
                        if battery_pct >= 75:
                            battery = "full"
                        elif battery_pct >= 50:
                            battery = "high"
                        elif battery_pct >= 25:
                            battery = "medium"
                        else:
                            battery = "low"
                        
                        devices.append({
                            "id": dev.get("id"),
                            "name": dev.get("id"),
                            "type": "module",
                            "rssi": rssi,
                            "signal": signal,
                            "battery": battery
                        })
                    
                    # Send to JavaScript
                    if hasattr(window, 'onDevicesUpdated'):
                        js_devices = []
                        for device in devices:
                            js_device = Object.new()
                            js_device.id = device.get("id")
                            js_device.name = device.get("name")
                            js_device.type = device.get("type")
                            js_device.rssi = device.get("rssi")
                            js_device.signal = device.get("signal")
                            js_device.battery = device.get("battery")
                            js_devices.append(js_device)
                        window.onDevicesUpdated(js_devices)
                        console.log("Fixed JSON processed successfully")
            except Exception as fix_error:
                console.log(f"Failed to fix JSON: {fix_error}")

# Set the callback for BLE data
ble.on_data_callback = on_ble_data


# BLE Connection Functions
async def connect_hub():
    """
    Connect to ESP32C6 hub via Bluetooth Low Energy.
    
    This function initiates a BLE connection to an ESP32 hub device using the
    Nordic UART Service. It handles device discovery, connection establishment,
    and error management including user cancellation scenarios.
    
    Connection Process:
    1. Use WebBLE to scan for devices with Nordic UART Service
    2. Present device selection dialog to user
    3. Establish GATT connection and service discovery
    4. Set up notification handlers for incoming data
    5. Update connection state and notify JavaScript frontend
    
    Returns:
    --------
    dict : JavaScript object with connection result
        - status: "success" | "cancelled" | "error"
        - device: Device name if successful
        - error: Error message if failed
    
    Error Handling:
    - User cancellation is treated as normal operation (not an error)
    - Connection failures are logged and reported to user
    - Graceful fallback for various BLE error conditions
    
    Side Effects:
    - Updates global ble_connected and hub_device_name variables
    - Dispatches BLE connection events to JavaScript frontend
    - Sets up data callback for ongoing communication
    """
    global ble_connected, hub_device_name
    
    try:
        # Connect by service UUID to find any Nordic UART device
        success = await ble.connect_by_service()
        
        if success:
            ble_connected = True
            hub_device_name = ble.device.name
            console.log(f"Connected to hub: {hub_device_name}")
            
            # Dispatch event to JavaScript - try direct function call first
            event_data = {"deviceName": hub_device_name}
            console.log(f"Python: Creating BLE connected event with data: {event_data}")
            
            # Try direct function call if available
            if hasattr(window, 'onBLEConnected'):
                console.log("Python: Calling onBLEConnected directly")
                # Create proper JavaScript object
                js_data = Object.new()
                js_data.deviceName = hub_device_name
                window.onBLEConnected(js_data)
            else:
                console.log("Python: onBLEConnected not available, using event dispatch")
                event = CustomEvent.new("py-ble-connected", {
                    "detail": event_data
                })
                window.dispatchEvent(event)
            console.log("Python: BLE connected event dispatched")
            
            # Return proper JavaScript object
            js_result = Object.new()
            js_result.status = "success"
            js_result.device = hub_device_name
            return js_result
        else:
            # User cancelled or no device found - this is normal, not an error
            console.log("BLE connection cancelled or no device found")
            # Return proper JavaScript object
            js_result = Object.new()
            js_result.status = "cancelled"
            js_result.error = "User cancelled or device not found"
            return js_result
            
    except Exception as e:
        error_msg = str(e)
        console.log(f"Connection error: {error_msg}")
        
        # Check if it's a user cancellation error
        if ("User cancelled" in error_msg or 
            "NotAllowedError" in error_msg or 
            "AbortError" in error_msg or
            "cancelled" in error_msg.lower()):
            console.log("User cancelled BLE connection - this is normal")
            js_result = Object.new()
            js_result.status = "cancelled"
            js_result.error = "User cancelled connection"
            return js_result
        else:
            console.log(f"Real BLE error: {error_msg}")
            js_result = Object.new()
            js_result.status = "error"
            js_result.error = error_msg
            return js_result

async def disconnect_hub():
    """Disconnect from hub"""
    global ble_connected, hub_device_name
    
    await ble.disconnect()
    ble_connected = False
    hub_device_name = None
    
    # Dispatch event to JavaScript - try direct function call first
    if hasattr(window, 'onBLEDisconnected'):
        console.log("Python: Calling onBLEDisconnected directly")
        window.onBLEDisconnected()
    else:
        console.log("Python: onBLEDisconnected not available, using event dispatch")
        event = CustomEvent.new("py-ble-disconnected", {"detail": {}})
        window.dispatchEvent(event)
    
    js_result = Object.new()
    js_result.status = "disconnected"
    return js_result

async def send_command_to_hub(command, rssi_threshold="all"):
    """
    Send command to hub for ESP-NOW broadcast to playground modules.
    
    This function formats and transmits commands to the ESP32 hub, which then
    broadcasts them to playground modules via ESP-NOW protocol. The hub uses
    RSSI thresholding to control which modules receive the command.
    
    Parameters:
    -----------
    command : str
        Command to send to modules (e.g., "play", "pause", "win", "off")
    rssi_threshold : str, optional
        RSSI filter for command broadcast:
        - "all": Send to all modules regardless of signal strength
        - "-XX": Send only to modules with RSSI >= -XX dBm
        
    Message Format:
    The hub expects commands in the format: "[command]":"[rssi_threshold]"
    Example: "play":"all" or "pause":"-50"
    
    Returns:
    --------
    dict : JavaScript object with transmission result
        - status: "sent" | "error"
        - command: Original command if successful
        - threshold: RSSI threshold used
        - error: Error message if failed
    
    Communication Flow:
    1. Format command according to hub protocol
    2. Send via BLE to hub
    3. Hub broadcasts via ESP-NOW to modules within RSSI range
    4. Modules execute command and may send responses back
    """
    if not ble.is_connected():
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = "Not connected to hub"
        return js_result
    
    # Format command for hub using real protocol
    # Hub expects: "[command]":"[rssi_threshold]"
    message = f'"{command}":"{rssi_threshold}"'
    
    success = await ble.send(message)
    
    js_result = Object.new()
    if success:
        console.log(f"Sent to hub: {message}")
        js_result.status = "sent"
        js_result.command = command
        js_result.threshold = rssi_threshold
    else:
        js_result.status = "error"
        js_result.error = "Send failed"
    return js_result

def get_connection_status():
    """Get current BLE connection status"""
    return {
        "connected": ble_connected,
        "device": hub_device_name
    }

async def refresh_devices_from_hub():
    """Request device list from hub via BLE"""
    if not ble.is_connected():
        console.log("Cannot refresh: Hub not connected")
        return []
    
    global devices
    
    # Send PING command to hub using real protocol
    # Hub will broadcast PING to modules and collect responses
    await ble.send('"PING":"all"')
    
    # Wait for response (hub should send back device list)
    # This requires implementing a response parser in on_ble_data callback
    # For now, keep mock data structure
    
    console.log(f"Device scan requested from hub")
    return devices  # Will be updated by incoming BLE data

# Legacy functions (for compatibility)
def get_devices():
    """Return list of available devices"""
    console.log("Python: get_devices called")
    return devices

def refresh_devices():
    """Refresh device list - now uses BLE if connected"""
    console.log("Python: refresh_devices called")
    
    if ble_connected:
        # Use BLE to get real device list
        return refresh_devices_from_hub()
    else:
        # Return mock data if not connected
        console.log("Hub not connected, returning mock data")
        return devices

def send_command(command, device_ids):
    """Send command to specific devices - now uses BLE if connected"""
    console.log(f"Python: Sending '{command}' to {len(device_ids)} devices")
    
    if ble_connected:
        # Use BLE to send command to hub
        # Convert range slider to RSSI threshold (this will be done in JS)
        rssi_threshold = "all"  # Default to all
        return send_command_to_hub(command, rssi_threshold)
    else:
        # Mock response if not connected
        event_data = {
            "command": command,
            "devices": device_ids,
            "status": "sent"
        }
        
        event = CustomEvent.new("py-message-sent", {"detail": event_data})
        window.dispatchEvent(event)
        
        return {"status": "success", "sent_to": len(device_ids)}


# Set up event listener for JS calls
async def handle_py_call(event):
    """Handle function calls from JavaScript"""
    console.log("===== Python: Event handler triggered =====")
    detail = event.detail.to_py()  # Convert JS object to Python dict
    function_name = detail.get('function')
    args_json = detail.get('args', '[]')
    callback_name = detail.get('callback')
    
    # Parse JSON args
    args = json.loads(args_json) if isinstance(args_json, str) else args_json
    
    console.log(f"Python: function={function_name}, callback={callback_name}, args={args}")
    
    # Call the appropriate function
    result = None
    if function_name == 'get_devices':
        result = get_devices()
    elif function_name == 'refresh_devices':
        result = refresh_devices()
    elif function_name == 'send_command':
        result = send_command(*args)
    elif function_name == 'connect_hub':
        result = await connect_hub()
    elif function_name == 'disconnect_hub':
        result = await disconnect_hub()
    elif function_name == 'send_command_to_hub':
        result = await send_command_to_hub(*args)
    elif function_name == 'get_connection_status':
        result = get_connection_status()
    else:
        console.log(f"Python: ERROR - Unknown function: {function_name}")
    
    console.log(f"Python: Result ready, type={type(result).__name__}, len={len(result) if isinstance(result, list) else 'N/A'}")
    
    # Call back to JavaScript with result
    if callback_name:
        console.log(f"Python: Calling window['{callback_name}']...")
        callback = getattr(window, callback_name, None)
        if callback:
            callback(result)
            console.log(f"Python: Callback invoked successfully")
        else:
            console.log(f"Python: ERROR - Callback '{callback_name}' not found!")
    else:
        console.log("Python: ERROR - No callback provided!")


# Register event listener with proxy to prevent garbage collection
# Store proxy globally to prevent garbage collection
global proxy_handler
proxy_handler = create_proxy(handle_py_call)
window.addEventListener('py-call', proxy_handler)

# Expose functions directly to global scope - simplified approach
# Use create_proxy only for async functions to prevent garbage collection
window.get_devices = get_devices
window.get_connection_status = get_connection_status
window.connect_hub = create_proxy(connect_hub)
window.disconnect_hub = create_proxy(disconnect_hub)
window.send_command_to_hub = create_proxy(send_command_to_hub)
window.refresh_devices = create_proxy(refresh_devices)

# Dispatch ready event to JavaScript
ready_event = CustomEvent.new("py-ready", {"detail": {}})
window.dispatchEvent(ready_event)

console.log("Python backend initialized!")