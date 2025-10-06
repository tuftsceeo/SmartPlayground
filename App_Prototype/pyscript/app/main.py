"""
Smart Playground Control - Python Backend
Handles BLE communication with ESP32 hub and ESP-NOW with modules
"""

from pyscript import document, window
from pyodide.ffi import create_proxy
from js import console, CustomEvent
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
    """Handle incoming data from hub"""
    console.log(f"BLE Data: {data}")
    
    try:
        # Parse JSON response from hub
        parsed = json.loads(data)
        
        if parsed.get("type") == "devices":
            # Update device list from hub
            global devices
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
            
            # Dispatch event to JavaScript
            event = CustomEvent.new("py-devices-updated", {
                "detail": devices
            })
            window.dispatchEvent(event)
            
            console.log(f"Updated {len(devices)} devices from hub")
            
    except Exception as e:
        console.log(f"Error parsing BLE data: {e}")

# Set the callback for BLE data
ble.on_data_callback = on_ble_data


# BLE Connection Functions
async def connect_hub():
    """Connect to ESP32C6 hub via BLE"""
    global ble_connected, hub_device_name
    
    try:
        # Connect by service UUID to find any Nordic UART device
        success = await ble.connect_by_service()
        
        if success:
            ble_connected = True
            hub_device_name = ble.device.name
            console.log(f"Connected to hub: {hub_device_name}")
            
            # Dispatch event to JavaScript
            event = CustomEvent.new("py-ble-connected", {
                "detail": {"deviceName": hub_device_name}
            })
            window.dispatchEvent(event)
            
            return {"status": "success", "device": hub_device_name}
        else:
            # User cancelled or no device found - this is normal, not an error
            console.log("BLE connection cancelled or no device found")
            return {"status": "cancelled", "error": "User cancelled or device not found"}
            
    except Exception as e:
        error_msg = str(e)
        console.log(f"Connection error: {error_msg}")
        
        # Check if it's a user cancellation error
        if ("User cancelled" in error_msg or 
            "NotAllowedError" in error_msg or 
            "AbortError" in error_msg or
            "cancelled" in error_msg.lower()):
            console.log("User cancelled BLE connection - this is normal")
            return {"status": "cancelled", "error": "User cancelled connection"}
        else:
            console.log(f"Real BLE error: {error_msg}")
            return {"status": "error", "error": error_msg}

async def disconnect_hub():
    """Disconnect from hub"""
    global ble_connected, hub_device_name
    
    await ble.disconnect()
    ble_connected = False
    hub_device_name = None
    
    # Dispatch event to JavaScript
    event = CustomEvent.new("py-ble-disconnected", {"detail": {}})
    window.dispatchEvent(event)
    
    return {"status": "disconnected"}

async def send_command_to_hub(command, rssi_threshold="all"):
    """Send command to hub for ESP-NOW broadcast"""
    if not ble.is_connected():
        return {"status": "error", "error": "Not connected to hub"}
    
    # Format command for hub using real protocol
    # Hub expects: "[command]":"[rssi_threshold]"
    message = f'"{command}":"{rssi_threshold}"'
    
    success = await ble.send(message)
    
    if success:
        console.log(f"Sent to hub: {message}")
        return {"status": "sent", "command": command, "threshold": rssi_threshold}
    else:
        return {"status": "error", "error": "Send failed"}

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