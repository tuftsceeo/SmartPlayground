"""
Smart Playground Control - Python Backend
Handles ESP-NOW communication with ESP32 devices
"""

from pyscript import document, window
from pyodide.ffi import create_proxy
from js import console, CustomEvent
import json
import random
import time

# Mock device data (replace with actual ESP-NOW communication)
devices = [
    {"id": "M-A3F821", "name": "M-A3F821", "type": "module", "rssi": -25, "signal": 3, "battery": "full"},
    {"id": "M-B4C932", "name": "M-B4C932", "type": "module", "rssi": -40, "signal": 3, "battery": "high"},
    {"id": "M-C5D043", "name": "M-C5D043", "type": "module", "rssi": -58, "signal": 2, "battery": "medium"},
    {"id": "E-D6E154", "name": "E-D6E154", "type": "extension", "rssi": -48, "signal": 2, "battery": "high"},
    {"id": "E-E7F265", "name": "E-E7F265", "type": "extension", "rssi": -78, "signal": 1, "battery": "low"},
    {"id": "B-F8G376", "name": "B-F8G376", "type": "button", "rssi": -85, "signal": 1, "battery": "medium"},
]


def get_devices():
    """Return list of available devices"""
    console.log("Python: get_devices called")
    return devices


def refresh_devices():
    """Refresh device list (simulate scanning for ESP32 devices with RSSI variation)"""
    console.log("Python: refresh_devices called - simulating ping/pong")
    

    # # Simulate RSSI fluctuation (devices move or signal varies)
    # for device in devices:
    #     # Add random variation to RSSI (-5 to +5 dBm)
    #     variation = random.randint(-5, 5)
    #     new_rssi = device["rssi"] + variation
        
    #     # Keep RSSI in realistic bounds (-20 to -95 dBm)
    #     device["rssi"] = max(-95, min(-20, new_rssi))
        
    #     # Update signal bars based on RSSI
    #     if device["rssi"] >= -50:
    #         device["signal"] = 3
    #     elif device["rssi"] >= -70:
    #         device["signal"] = 2
    #     elif device["rssi"] >= -85:
    #         device["signal"] = 1
    #     else:
    #         device["signal"] = 0

       
    # Ping-pong simulation is instant for prototype

    console.log(f"Python: {len(devices)} devices responded to ping")
    return devices


def send_command(command, device_ids):
    """Send command to specific devices via ESP-NOW"""
    console.log(f"Python: Sending '{command}' to {len(device_ids)} devices")
    
    for device_id in device_ids:
        console.log(f"  -> Sending to {device_id}")
    
    # Dispatch event back to JavaScript
    event_data = {
        "command": command,
        "devices": device_ids,
        "status": "sent"
    }
    
    event = CustomEvent.new("py-message-sent", {"detail": event_data})
    window.dispatchEvent(event)
    
    return {"status": "success", "sent_to": len(device_ids)}


# Set up event listener for JS calls
def handle_py_call(event):
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
proxy_handler = create_proxy(handle_py_call)
window.addEventListener('py-call', proxy_handler)

console.log("Python backend initialized!")