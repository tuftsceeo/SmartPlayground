"""
Smart Playground Control - Python Backend
Handles ESP-NOW communication with ESP32 devices
"""

from pyscript import document, window, when
from js import console, CustomEvent
import json

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
    """Refresh device list (simulate scanning for ESP32 devices)"""
    console.log("Python: refresh_devices called")
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


@when("py-call", "window")
def handle_py_call(event):
    """Handle function calls from JavaScript"""
    detail = event.detail
    function_name = detail.get('function')
    args = detail.get('args', [])
    callback_name = detail.get('callback')
    
    console.log(f"Python: Received call to {function_name}")
    
    # Call the appropriate function
    result = None
    if function_name == 'get_devices':
        result = get_devices()
    elif function_name == 'refresh_devices':
        result = refresh_devices()
    elif function_name == 'send_command':
        result = send_command(*args)
    
    # Call back to JavaScript with result
    if callback_name:
        window[callback_name](result)


console.log("Python backend initialized!")