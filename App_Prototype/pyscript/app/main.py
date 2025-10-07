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
from pyodide.ffi import create_proxy, to_js
from js import console, Object, Array
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

# Message framing state for BLE transmission reassembly
# Protocol: MSG:<length>|<payload>
_frame_state = "waiting_header"  # States: "waiting_header", "receiving_payload"
_expected_payload_length = 0
_payload_buffer = ""
_frame_buffer = ""  # Buffer for header parsing
_last_fragment_time = 0
_buffer_timeout = 2.0  # 2 second timeout for message completion

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

def process_complete_message(message_data):
    """
    Process a complete message received from the hub.
    
    This is called once we've reassembled a complete framed message.
    It parses the JSON and updates the UI accordingly.
    """
    global devices
    
    console.log("=== PROCESSING COMPLETE MESSAGE ===")
    console.log(f"Message length: {len(message_data)}")
    console.log(f"Message: {message_data}")
    
    # Parse JSON using centralized function
    parsed = parse_hub_response(message_data)
    if not parsed:
        console.log("Failed to parse hub data - skipping")
        return
    
    # Validate required fields
    if 'type' not in parsed:
        console.log("Missing 'type' field in hub response")
        return
    
    # Handle different message types
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
        
        # Deduplicate devices by MAC address (keep first occurrence)
        seen_macs = set()
        unique_devices = []
        for dev in device_list:
            mac = dev.get("mac", "")
            if mac and mac not in seen_macs:
                seen_macs.add(mac)
                unique_devices.append(dev)
            elif mac in seen_macs:
                console.log(f"Skipping duplicate device with MAC: {mac}")
        
        console.log(f"Filtered {len(device_list)} devices to {len(unique_devices)} unique devices")
        
        # Convert to expected format
        devices = []
        for dev in unique_devices:
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
            
            # Get original device name
            device_name = dev.get("id", "Unknown")
            
            # Create sanitized ID for DOM selectors (remove spaces and special chars)
            # Replace spaces with hyphens and remove any characters that aren't alphanumeric or hyphens
            sanitized_id = device_name.replace(" ", "-").replace("_", "-")
            # Remove any remaining special characters
            sanitized_id = ''.join(c for c in sanitized_id if c.isalnum() or c == '-')
            
            console.log(f"DEBUG SANITIZATION: '{device_name}' -> '{sanitized_id}'")
            
            devices.append({
                "id": sanitized_id,  # Sanitized ID for DOM selectors
                "name": device_name,  # Original name for display
                "type": "module",
                "rssi": rssi,
                "signal": signal,
                "battery": battery
            })
        
        # Call JavaScript directly
        if hasattr(window, 'onDevicesUpdated'):
            console.log("Python: Calling onDevicesUpdated directly")
            console.log(f"Devices to send: {devices}")
            
            # Convert Python list to JavaScript array using to_js()
            # This creates proper JavaScript objects that won't be garbage collected
            js_devices = to_js(devices, dict_converter=Object.fromEntries)
            
            console.log(f"Converted to JS: {len(devices)} devices")
            window.onDevicesUpdated(js_devices)
            console.log("onDevicesUpdated called successfully")
        else:
            console.log("Python: onDevicesUpdated not available")
        
        console.log(f"Updated {len(devices)} devices from hub")
    elif parsed.get("type") == "ack":
        # Acknowledgment from hub that command was sent
        console.log("Received acknowledgment from hub")
        command = parsed.get("command", "unknown")
        status = parsed.get("status", "unknown")
        rssi = parsed.get("rssi", "all")
        
        if status == "sent":
            console.log(f"✓ Command '{command}' sent successfully (RSSI: {rssi})")
            # Optionally show toast for user feedback
            # showToast(f"Command '{command}' sent to modules", "success")
        else:
            console.log(f"✗ Command '{command}' failed to send (status: {status})")
            # Optionally show error toast
            # showToast(f"Command '{command}' failed", "error")
    elif parsed.get("type") == "error":
        # Error message from hub
        console.log("Received error from hub")
        error_msg = parsed.get("message", "Unknown error")
        console.log(f"Hub error: {error_msg}")
        
        # Show error to user
        if hasattr(window, 'showToast'):
            window.showToast(error_msg, "error")
    else:
        console.log(f"Unknown message type: {parsed.get('type')}")

def on_ble_data(data):
    """
    Handle incoming BLE data with message framing protocol.
    
    Message Framing Protocol:
    -------------------------
    Format: MSG:<length>|<payload>
    
    Example:
    - Fragment 1: "MSG:330|"  (header indicating 330 bytes follow)
    - Fragment 2-N: Payload chunks (100 bytes each typically)
    
    State Machine:
    1. waiting_header: Looking for "MSG:<length>|" header
    2. receiving_payload: Accumulating payload bytes until we have <length> bytes
    
    This approach is much more robust than trying to detect JSON completeness,
    as it explicitly tells us how many bytes to expect.
    
    Parameters:
    -----------
    data : str
        Raw string fragment from BLE notification
    """
    global _frame_state, _expected_payload_length, _payload_buffer, _frame_buffer, _last_fragment_time
    
    console.log(f"=== BLE FRAGMENT v2.0 (FRAMED) ===")
    console.log(f"State: {_frame_state}")
    console.log(f"Fragment: {data[:50]}{'...' if len(data) > 50 else ''}")
    console.log(f"Fragment length: {len(data)}")
    
    # Timeout handling
    current_time = time.time()
    if _frame_buffer or _payload_buffer:
        if (current_time - _last_fragment_time) > _buffer_timeout:
            console.log(f"TIMEOUT: Resetting frame state (no data for {_buffer_timeout}s)")
            _frame_state = "waiting_header"
            _frame_buffer = ""
            _payload_buffer = ""
            _expected_payload_length = 0
    
    _last_fragment_time = current_time
    
    # State machine for framed message reception
    # Track if we just transitioned states in this call
    state_changed = False
    
    if _frame_state == "waiting_header":
        # Accumulate data until we find the header
        _frame_buffer += data
        
        # Look for frame header: MSG:<length>|
        if "MSG:" in _frame_buffer and "|" in _frame_buffer:
            # Extract header
            header_start = _frame_buffer.index("MSG:")
            header_end = _frame_buffer.index("|", header_start)
            
            # Parse length from header
            try:
                length_str = _frame_buffer[header_start + 4:header_end]
                _expected_payload_length = int(length_str)
                console.log(f"HEADER RECEIVED: Expecting {_expected_payload_length} bytes of payload")
                
                # Any data after the "|" is the start of the payload
                payload_start = header_end + 1
                _payload_buffer = _frame_buffer[payload_start:]
                _frame_buffer = ""
                
                # Transition to receiving payload state
                _frame_state = "receiving_payload"
                state_changed = True  # Mark that we just transitioned
                console.log(f"State -> receiving_payload (already have {len(_payload_buffer)} bytes)")
                
                # Check if header fragment contained complete payload
                if len(_payload_buffer) >= _expected_payload_length:
                    # Complete message was in header fragment!
                    complete_payload = _payload_buffer[:_expected_payload_length]
                    console.log(f"PAYLOAD COMPLETE: {len(complete_payload)} bytes received (in header fragment)")
                    console.log(f"Processing complete framed message...")
                    
                    # Process the complete message
                    process_complete_message(complete_payload)
                    
                    # Reset state for next message
                    _frame_state = "waiting_header"
                    _payload_buffer = ""
                    _frame_buffer = ""
                    _expected_payload_length = 0
                    console.log("State -> waiting_header (ready for next message)")
                    return
                
            except (ValueError, IndexError) as e:
                console.log(f"ERROR: Failed to parse header: {e}")
                console.log(f"Header buffer: {_frame_buffer}")
                _frame_buffer = ""
                return
        else:
            console.log(f"Still waiting for header (buffer: {len(_frame_buffer)} bytes)")
            return
    
    # Only process payload if we're already in receiving_payload state 
    # (not if we just transitioned to it in this same call)
    if _frame_state == "receiving_payload" and not state_changed:
        # Add new fragment to payload buffer
        _payload_buffer += data
        
        console.log(f"Payload progress: {len(_payload_buffer)}/{_expected_payload_length} bytes")
        
        # Check if we have the complete payload
        if len(_payload_buffer) >= _expected_payload_length:
            # Extract exact payload (trim any extra data)
            complete_payload = _payload_buffer[:_expected_payload_length]
            
            console.log(f"PAYLOAD COMPLETE: {len(complete_payload)} bytes received")
            console.log(f"Processing complete framed message...")
            
            # Process the complete message
            process_complete_message(complete_payload)
            
            # Reset state for next message
            _frame_state = "waiting_header"
            _payload_buffer = ""
            _frame_buffer = ""
            _expected_payload_length = 0
            
            console.log("State -> waiting_header (ready for next message)")
        else:
            console.log(f"Waiting for more payload ({_expected_payload_length - len(_payload_buffer)} bytes remaining)")


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

async def refresh_devices_from_hub(rssi_threshold="all"):
    """
    Request device list from hub via BLE with RSSI filtering.
    
    Parameters:
    -----------
    rssi_threshold : str or int
        RSSI threshold for device filtering:
        - "all": Return all devices that respond (no filtering)
        - "-XX": Only devices with RSSI >= -XX dBm will respond
        
    The filtering happens at the module level - only modules that can
    receive the hub's broadcast at the specified RSSI will respond to the ping.
    """
    if not ble.is_connected():
        console.log("Cannot refresh: Hub not connected")
        return to_js([])
    
    global devices
    
    # Convert rssi_threshold to string for protocol
    threshold_str = str(rssi_threshold)
    
    # Send PING command to hub with RSSI threshold using real protocol
    # Hub will broadcast PING to modules and only those with strong enough
    # signal will respond
    ping_command = f'"PING":"{threshold_str}"'
    await ble.send(ping_command)
    
    # Wait for response (hub should send back device list)
    # The response will be handled by on_ble_data callback
    # which will update the global devices list
    
    console.log(f"Device scan requested from hub with RSSI threshold: {threshold_str}")
    
    # Convert Python list to JavaScript array using to_js()
    return to_js(devices, dict_converter=Object.fromEntries)

# Legacy functions (for compatibility)
def get_devices():
    """Return list of available devices"""
    console.log("Python: get_devices called")
    # Convert Python list to JavaScript array using to_js()
    return to_js(devices, dict_converter=Object.fromEntries)

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
window.refresh_devices_from_hub = create_proxy(refresh_devices_from_hub)

# Python backend is ready

console.log("Python backend initialized!")