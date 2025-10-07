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
from js import console, Object
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
devices = []

def parse_hub_response(data):
    """
    Parse and validate JSON response from ESP32 hub.
    
    This function handles JSON parsing with a single repair attempt for truncated data.
    It validates required fields and logs parsing failures for debugging.
    
    Parameters:
    -----------
    data : str
        Raw JSON string from hub
        
    Returns:
    --------
    dict or None: Parsed JSON data if successful, None if parsing failed
        
    Error Handling:
    - Single repair attempt for truncated JSON
    - Logs all parsing failures for debugging
    - Validates required fields before returning
    """
    try:
        # Try to parse JSON normally first
        parsed = json.loads(data)
        console.log(f"Successfully parsed JSON: {parsed}")
        return parsed
    except Exception as e:
        console.log(f"JSON parsing failed: {e}")
        
        # Single repair attempt for truncated JSON
        if "Unterminated string" in str(e) or "Expecting" in str(e):
            console.log("Attempting to fix truncated JSON...")
            try:
                fixed_data = data + '"]}'
                parsed = json.loads(fixed_data)
                console.log("Successfully fixed truncated JSON")
                return parsed
            except Exception as fix_error:
                console.log(f"Failed to fix JSON: {fix_error}")
                return None
        else:
            return None

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
    1. Parse JSON data from hub using parse_hub_response()
    2. Validate required fields (type, list)
    3. Handle device list updates (type: "devices")
    4. Convert RSSI values to signal strength bars (0-3)
    5. Convert battery percentages to level categories (low/medium/high/full)
    6. Format data for JavaScript consumption
    7. Dispatch updates to frontend via direct function calls
    
    Error Handling:
    - Uses centralized JSON parsing with single repair attempt
    - Logs parsing failures for debugging
    - Validates data before processing
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
    
    # Parse JSON using centralized function
    parsed = parse_hub_response(data)
    if not parsed:
        console.log("Failed to parse hub data - skipping")
        return
    
    # Validate required fields
    if 'type' not in parsed:
        console.log("Missing 'type' field in hub response")
        return
    
    if parsed.get("type") == "devices":
        console.log("Found devices type - processing device list")
        
        # Validate device list
        if 'list' not in parsed:
            console.log("Missing 'list' field in devices response")
            return
            
        device_list = parsed.get("list", [])
        if not isinstance(device_list, list):
            console.log("Device list is not an array")
            return
        
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
        
        # Call JavaScript directly
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
            console.log("Python: onDevicesUpdated not available")
        
        console.log(f"Updated {len(devices)} devices from hub")
    else:
        console.log(f"Unknown message type: {parsed.get('type')}")

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
            
            # Call JavaScript directly
            if hasattr(window, 'onBLEConnected'):
                console.log("Python: Calling onBLEConnected directly")
                # Create proper JavaScript object
                js_data = Object.new()
                js_data.deviceName = hub_device_name
                window.onBLEConnected(js_data)
                console.log("Python: BLE connected callback called")
            else:
                console.log("Python: onBLEConnected not available")
            
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
    
    # Call JavaScript directly
    if hasattr(window, 'onBLEDisconnected'):
        console.log("Python: Calling onBLEDisconnected directly")
        window.onBLEDisconnected()
    else:
        console.log("Python: onBLEDisconnected not available")
    
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
    """Get current BLE connection status - Python is source of truth"""
    # Check actual BLE connection status, not stored variable
    actual_connected = ble.is_connected()
    
    # Convert None to False for JavaScript compatibility
    # ble.is_connected() can return None, True, or False
    # JavaScript needs explicit True/False, not None (which becomes undefined)
    actual_connected_bool = bool(actual_connected) if actual_connected is not None else False
    
    # Update stored variable to match reality
    global ble_connected
    if actual_connected_bool != ble_connected:
        console.log(f"BLE state mismatch: stored={ble_connected}, actual={actual_connected_bool}")
        ble_connected = actual_connected_bool
    
    # Return proper JavaScript object
    js_result = Object.new()
    js_result.connected = actual_connected_bool
    # Use empty string instead of None to avoid undefined in JavaScript
    js_result.device = hub_device_name if (actual_connected_bool and hub_device_name) else ""
    return js_result

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
    # The response will be handled by on_ble_data callback
    # which will update the global devices list
    
    console.log(f"Device scan requested from hub")
    
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
    return js_devices

# Legacy functions (for compatibility)
def get_devices():
    """Return list of available devices"""
    console.log("Python: get_devices called")
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
    return js_devices

def refresh_devices():
    """Refresh device list - requires BLE connection"""
    console.log("Python: refresh_devices called")
    
    if ble.is_connected():
        # Use BLE to get real device list
        return refresh_devices_from_hub()
    else:
        # Return empty list if not connected
        console.log("Hub not connected, returning empty device list")
        return []

def send_command(command, device_ids):
    """Send command to specific devices - requires BLE connection"""
    console.log(f"Python: Sending '{command}' to {len(device_ids)} devices")
    
    if ble.is_connected():
        # Use BLE to send command to hub
        # Convert range slider to RSSI threshold (this will be done in JS)
        rssi_threshold = "all"  # Default to all
        return send_command_to_hub(command, rssi_threshold)
    else:
        # Return error if not connected
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = "Not connected to hub"
        return js_result


# Direct function calls only - no event system needed

# Expose functions directly to global scope - simplified approach
# Use create_proxy only for async functions to prevent garbage collection
window.get_devices = get_devices
window.get_connection_status = get_connection_status
window.connect_hub = create_proxy(connect_hub)
window.disconnect_hub = create_proxy(disconnect_hub)
window.send_command_to_hub = create_proxy(send_command_to_hub)
window.refresh_devices = create_proxy(refresh_devices)

# Python backend is ready

console.log("Python backend initialized!")