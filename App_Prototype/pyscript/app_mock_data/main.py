"""
Smart Playground Control - Demo Mode Python Backend

This module serves as the PyScript backend for the Smart Playground Control DEMO application.
It provides mock data and simulated device responses for demonstration purposes.

Key Responsibilities:
- Mock device data management for demonstration
- Simulated command responses without real BLE connections
- Data parsing and format conversion between JSON and JavaScript objects
- Event dispatching to JavaScript frontend for real-time UI updates

Demo Mode Features:
- No BLE dependencies - works entirely with mock data
- Simulated device responses for all commands
- Realistic device behavior for demonstration purposes
- Shows "Demonstration" status instead of "Connected"

Dependencies:
- PyScript/Pyodide for browser Python execution
- JavaScript bridge for frontend communication

"""

from pyscript import document, window
from pyodide.ffi import create_proxy
from js import console, CustomEvent, Object, setTimeout
import json
import random
import time
import asyncio

# Demo mode state - no BLE dependencies
demo_mode = True
hub_device_name = "Demo Hub"

# Device data (mock data for demonstration)
devices = [
    {"id": "M-A3F821", "name": "M-A3F821", "type": "module", "rssi": -25, "signal": 3, "battery": "full"},
    {"id": "M-B4C932", "name": "M-B4C932", "type": "module", "rssi": -40, "signal": 3, "battery": "high"},
    {"id": "M-C5D043", "name": "M-C5D043", "type": "module", "rssi": -58, "signal": 2, "battery": "medium"},
    {"id": "E-D6E154", "name": "E-D6E154", "type": "extension", "rssi": -48, "signal": 2, "battery": "high"},
    {"id": "E-E7F265", "name": "E-E7F265", "type": "extension", "rssi": -78, "signal": 1, "battery": "low"},
    {"id": "B-F8G376", "name": "B-F8G376", "type": "button", "rssi": -85, "signal": 1, "battery": "medium"},
]

def simulate_device_response():
    """
    Simulate device responses for demo mode.
    
    This function provides realistic mock data for demonstration purposes.
    It simulates device discovery and status updates without requiring
    actual BLE connections.
    """
    global devices
    
    # Simulate some variation in device data
    for device in devices:
        # Randomly vary RSSI slightly for realism
        base_rssi = device["rssi"]
        variation = random.randint(-5, 5)
        device["rssi"] = max(-100, min(-10, base_rssi + variation))
        
        # Update signal strength based on new RSSI
        rssi = device["rssi"]
        if rssi >= -50:
            device["signal"] = 3
        elif rssi >= -70:
            device["signal"] = 2
        elif rssi >= -85:
            device["signal"] = 1
        else:
            device["signal"] = 0
    
    # Send updated devices to JavaScript
    if hasattr(window, 'onDevicesUpdated'):
        console.log("Demo: Calling onDevicesUpdated with simulated data")
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
        console.log("Demo: onDevicesUpdated called successfully")


# Demo Mode Connection Functions
async def connect_hub():
    """
    Simulate hub connection for demo mode.
    
    This function simulates a successful connection to a demo hub
    without requiring actual BLE hardware.
    """
    global hub_device_name
    
    console.log("Demo: Simulating hub connection...")
    
    # Simulate connection delay
    await asyncio.sleep(1)
    
    # Dispatch event to JavaScript
    if hasattr(window, 'onBLEConnected'):
        console.log("Demo: Calling onBLEConnected")
        js_data = Object.new()
        js_data.deviceName = hub_device_name
        window.onBLEConnected(js_data)
    else:
        console.log("Demo: onBLEConnected not available, using event dispatch")
        event = CustomEvent.new("py-ble-connected", {
            "detail": {"deviceName": hub_device_name}
        })
        window.dispatchEvent(event)
    
    # Return success result
    js_result = Object.new()
    js_result.status = "success"
    js_result.device = hub_device_name
    return js_result

async def disconnect_hub():
    """Simulate hub disconnection for demo mode"""
    console.log("Demo: Simulating hub disconnection...")
    
    # Dispatch event to JavaScript
    if hasattr(window, 'onBLEDisconnected'):
        console.log("Demo: Calling onBLEDisconnected")
        window.onBLEDisconnected()
    else:
        console.log("Demo: onBLEDisconnected not available, using event dispatch")
        event = CustomEvent.new("py-ble-disconnected", {"detail": {}})
        window.dispatchEvent(event)
    
    js_result = Object.new()
    js_result.status = "disconnected"
    return js_result

async def send_command_to_hub(command, rssi_threshold="all"):
    """
    Simulate command transmission for demo mode.
    
    This function simulates sending commands to playground modules
    without requiring actual BLE connections.
    """
    console.log(f"Demo: Simulating command '{command}' with threshold '{rssi_threshold}'")
    
    # Simulate command processing delay
    await asyncio.sleep(0.5)
    
    # Simulate device response variation
    simulate_device_response()
    
    # Return success result
    js_result = Object.new()
    js_result.status = "sent"
    js_result.command = command
    js_result.threshold = rssi_threshold
    return js_result

def get_connection_status():
    """Get current demo connection status"""
    return {
        "connected": True,  # Always connected in demo mode
        "device": hub_device_name
    }

async def refresh_devices_from_hub():
    """Simulate device refresh for demo mode"""
    console.log("Demo: Simulating device refresh...")
    
    # Simulate refresh delay
    await asyncio.sleep(1)
    
    # Simulate device response variation
    simulate_device_response()
    
    return devices

# Legacy functions (for compatibility)
def get_devices():
    """Return list of available devices"""
    console.log("Demo: get_devices called")
    return devices

def refresh_devices():
    """Refresh device list - demo mode simulation"""
    console.log("Demo: refresh_devices called")
    return refresh_devices_from_hub()

def send_command(command, device_ids):
    """Send command to specific devices - demo mode simulation"""
    console.log(f"Demo: Simulating '{command}' to {len(device_ids)} devices")
    
    # Simulate command processing
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
    console.log("===== Demo: Event handler triggered =====")
    detail = event.detail.to_py()  # Convert JS object to Python dict
    function_name = detail.get('function')
    args_json = detail.get('args', '[]')
    callback_name = detail.get('callback')
    
    # Parse JSON args
    args = json.loads(args_json) if isinstance(args_json, str) else args_json
    
    console.log(f"Demo: function={function_name}, callback={callback_name}, args={args}")
    
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
        console.log(f"Demo: ERROR - Unknown function: {function_name}")
    
    console.log(f"Demo: Result ready, type={type(result).__name__}, len={len(result) if isinstance(result, list) else 'N/A'}")
    
    # Call back to JavaScript with result
    if callback_name:
        console.log(f"Demo: Calling window['{callback_name}']...")
        callback = getattr(window, callback_name, None)
        if callback:
            callback(result)
            console.log(f"Demo: Callback invoked successfully")
        else:
            console.log(f"Demo: ERROR - Callback '{callback_name}' not found!")
    else:
        console.log("Demo: ERROR - No callback provided!")


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

# Initialize demo mode - simulate connection
console.log("Demo mode: Simulating initial connection...")

async def init_demo():
    """Initialize demo mode with simulated connection"""
    await asyncio.sleep(1)  # Simulate connection delay
    await connect_hub()

# Start demo initialization
asyncio.create_task(init_demo())

# Dispatch ready event to JavaScript
ready_event = CustomEvent.new("py-ready", {"detail": {}})
window.dispatchEvent(ready_event)

console.log("Demo mode Python backend initialized!")