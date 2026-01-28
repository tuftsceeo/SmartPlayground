"""
Smart Playground Control - Python Backend

PyScript backend for Smart Playground Control. Handles BLE/Serial communication
with ESP32 hub devices and manages ESP-NOW protocol for playground modules.

Key Responsibilities:
- Connection management (Serial USB primary, BLE legacy)
- Device discovery and RSSI-based filtering
- Command transmission and response handling
- JSON/JavaScript data conversion
- Event dispatching to frontend

Communication Flow:
1. Connect to ESP32 hub via Serial (USB) or BLE (Nordic UART)
2. Hub broadcasts commands to modules via ESP-NOW
3. Modules respond through hub
4. Backend parses and updates frontend

Dependencies:
- PyScript 2024.1.1 (browser Python execution)
- mpy/hub_serial.py, hub_bluetooth.py, repl_controller.py, firmware_manager.py
- js/adapters/serialAdapter.js, bluetoothAdapter.js (browser APIs)
- js/utils/pyBridge.js (JavaScript-Python bridge)
"""

from pyscript import document, window
from pyodide.ffi import create_proxy, to_js
from js import console, Object, Array
import json
import random
import time
import asyncio

# Check if JavaScript adapters are loaded (hybrid architecture)
if not hasattr(window, 'serialAdapter'):
    console.error("❌ FATAL: serialAdapter not found!")
    console.error("Make sure js/adapters/serialAdapter.js is loaded before PyScript")
    raise Exception("JavaScript adapters not loaded properly")

if not hasattr(window, 'bluetoothAdapter'):
    console.error("❌ FATAL: bluetoothAdapter not found!")
    console.error("Make sure js/adapters/bluetoothAdapter.js is loaded before PyScript")
    raise Exception("JavaScript adapters not loaded properly")

console.log("✅ JavaScript adapters detected")

# Import new refactored modules
from mpy.hub_bluetooth import BluetoothConnection
from mpy.hub_serial import SerialConnection
from mpy.repl_controller import ReplController
from mpy.firmware_manager import FirmwareManager

# Create component instances
ble = BluetoothConnection()
serial = SerialConnection()
repl = ReplController(serial)
firmware = FirmwareManager(repl)

# Set up serial callbacks (will be properly assigned after functions are defined)
# These are forward-declared here and assigned at the bottom of the file

# Connection state
ble_connected = False
serial_connected = False
hub_device_name = None
hub_connection_mode = None  # "ble" or "serial"

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
        Raw JSON string from hub (should already be filtered to only JSON messages)
        
    Returns:
    --------
    dict or None: Parsed JSON data if successful, None if parsing failed
        
    Error Handling:
    - Single repair attempt for truncated JSON
    - Minimal logging (detailed errors handled by caller)
    """
    try:
        # Try to parse JSON normally first
        parsed = json.loads(data)
        return parsed
    except Exception as e:
        # Single repair attempt for truncated JSON
        if "Unterminated string" in str(e) or "Expecting" in str(e):
            try:
                fixed_data = data + '"]}'
                parsed = json.loads(fixed_data)
                console.log("⚠️ Fixed truncated JSON from hub")
                return parsed
            except:
                return None
        else:
            return None

def process_complete_message(message_data):
    """
    Process a complete message received from the hub.
    
    This is called once we've reassembled a complete framed message.
    It parses the JSON and updates the UI accordingly.
    
    The hub sends two types of messages:
    1. JSON data (starts with '{') - commands, acks, device lists
    2. Plain text debug messages - hub's internal logging
    """
    global devices
    
    # Quick check: Is this JSON or a debug message?
    message_data = message_data.strip()
    
    console.log(f"🔵 process_complete_message: stripped data = '{message_data[:100]}'")
    console.log(f"🔵 process_complete_message: starts with '{{' ? {message_data.startswith('{')}")
    
    if not message_data.startswith('{'):
        # Not JSON - this is a debug/print statement from the hub
        console.info(f"📡 Hub debug: {message_data}")
        return
    
    # It's JSON - try to parse it
    console.log("=== PROCESSING HUB JSON ===")
    console.log(f"Full JSON message: {message_data}")
    
    # Parse JSON using centralized function
    parsed = parse_hub_response(message_data)
    if not parsed:
        console.error(f"❌ Failed to parse hub JSON: {message_data}")
        return
    
    console.log(f"✅ JSON parsed successfully: type = '{parsed.get('type', 'MISSING')}'")
    
    # Validate required fields
    if 'type' not in parsed:
        console.log("❌ Missing 'type' field in hub response")
        return
    
    # Handle different message types
    if parsed.get("type") == "devices":
        console.log("🎯 Found 'devices' type - processing device list")
        console.log(f"Device list length: {len(parsed.get('list', []))}")
        
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
        
        # Extract hub timestamp for client-side age calculation
        hub_timestamp = parsed.get("timestamp", 0)
        
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
            
            # Get battery percentage and convert to level string
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
                "battery": battery,
                "battery_pct": battery_pct,  # Percentage for display
                "last_seen": dev.get("last_seen", 0)  # Hub timestamp (ticks_ms)
            })
        
        # Call JavaScript directly with hub timestamp
        if hasattr(window, 'onDevicesUpdated'):
            console.log("🟢 Python: Calling window.onDevicesUpdated()")
            console.log(f"📋 Devices to send: {len(devices)} devices")
            for i, dev in enumerate(devices):
                console.log(f"  Device {i+1}: {dev.get('name')} (RSSI: {dev.get('rssi')}, Battery: {dev.get('battery_pct')}%)")
            console.log(f"⏰ Hub timestamp: {hub_timestamp}")
            
            # Convert Python list to JavaScript array using to_js()
            # This creates proper JavaScript objects that won't be garbage collected
            js_devices = to_js(devices, dict_converter=Object.fromEntries)
            
            console.log(f"✅ Converted to JS: {len(devices)} devices")
            window.onDevicesUpdated(js_devices, hub_timestamp)
            console.log("✅ onDevicesUpdated() called successfully")
        else:
            console.log("❌ Python: window.onDevicesUpdated not available!")
        
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


# Set the callback for BLE data (proxied for JS)
ble.on_data_callback = create_proxy(on_ble_data)


# BLE Connection Functions
async def connect_hub():
    """Connect to hub via BLE using Nordic UART Service (deprecated, use connect_hub_serial).
    
    Returns:
        JavaScript object with status: "success"|"cancelled"|"error"
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
    """Disconnect from BLE hub (legacy, use disconnect_hub_serial)."""
    global ble_connected, hub_device_name, hub_connection_mode
    
    await ble.disconnect()
    ble_connected = False
    hub_device_name = None
    hub_connection_mode = None
    
    # Call JavaScript directly
    if hasattr(window, 'onBLEDisconnected'):
        console.log("Python: Calling onBLEDisconnected directly")
        window.onBLEDisconnected()
    else:
        console.log("Python: onBLEDisconnected not available")
    
    js_result = Object.new()
    js_result.status = "disconnected"
    return js_result

async def connect_hub_serial():
    """Connect to hub via USB Serial (primary connection method)."""
    global serial_connected, hub_device_name, hub_connection_mode
    
    console.log("Attempting Serial connection...")
    
    try:
        success = await serial.connect()
        
        if success:
            serial_connected = True
            hub_device_name = "USB Serial Hub"
            hub_connection_mode = "serial"
            
            # Set up data callback to reuse BLE data processing (proxied for JS)
            serial.on_data_callback = create_proxy(on_serial_data)
            
            console.log("Serial connected successfully")
            
            # Notify JavaScript
            if hasattr(window, 'onHubConnected'):
                js_data = Object.new()
                js_data.deviceName = hub_device_name
                js_data.mode = "serial"
                window.onHubConnected(js_data)
            
            # Return success
            js_result = Object.new()
            js_result.status = "success"
            js_result.device = hub_device_name
            js_result.mode = "serial"
            return js_result
        else:
            # Connection failed - check console output for specific error
            console.log("Serial connection cancelled or failed - check console for details")
            js_result = Object.new()
            js_result.status = "error"
            js_result.error = "Connection failed - check browser console for details"
            return js_result
    
    except Exception as e:
        error_msg = str(e)
        console.log(f"Serial connection exception: {error_msg}")
        
        # Check for specific error types
        if "cancelled" in error_msg.lower() or "aborted" in error_msg.lower():
            js_result = Object.new()
            js_result.status = "cancelled"
            return js_result
        elif "in use" in error_msg.lower() or "busy" in error_msg.lower():
            js_result = Object.new()
            js_result.status = "error"
            js_result.error = "Port in use - close Thonny/Arduino IDE and try again"
            return js_result
        else:
            js_result = Object.new()
            js_result.status = "error"
            js_result.error = error_msg
            return js_result

async def disconnect_hub_serial():
    """Disconnect from Serial hub."""
    global serial_connected, hub_device_name, hub_connection_mode
    
    console.log("Disconnecting Serial...")
    await serial.disconnect()
    serial_connected = False
    hub_device_name = None
    hub_connection_mode = None
    
    # Notify JavaScript
    if hasattr(window, 'onHubDisconnected'):
        window.onHubDisconnected()
    
    js_result = Object.new()
    js_result.status = "disconnected"
    return js_result

def on_serial_data(data):
    """Handle incoming Serial data (line-delimited JSON or debug output)."""
    console.log("=" * 80)
    console.log("🟢 on_serial_data() CALLED")
    console.log(f"📥 Serial data received ({len(data)} chars): {data[:200]}")
    console.log(f"Data type: {type(data)}")
    console.log("=" * 80)
    # Process the message (it will handle JSON vs debug message filtering)
    process_complete_message(data)

def on_serial_connection_lost():
    """
    Handle unexpected serial connection loss.
    
    This is called by hub_serial.py when the serial connection is lost
    unexpectedly (not from user-initiated disconnect).
    """
    global serial_connected, hub_device_name, hub_connection_mode
    
    console.log("⚠️ Serial connection lost - updating backend state")
    console.log(f"BEFORE: serial_connected={serial_connected}, mode={hub_connection_mode}")
    
    # Update Python backend state immediately
    serial_connected = False
    hub_device_name = None
    hub_connection_mode = None
    
    console.log(f"AFTER: serial_connected={serial_connected}, mode={hub_connection_mode}")
    console.log(f"serial.is_connected() = {serial.is_connected()}")

async def send_command_to_hub(command, rssi_threshold="all"):
    """Send command to hub for ESP-NOW broadcast to modules.
    
    Args:
        command: Command name (e.g., "play", "pause", "win")
        rssi_threshold: "all" or "-XX" for RSSI >= -XX dBm
    
    Returns:
        JavaScript object with status: "sent"|"error"
    """
    # Check connection based on mode
    if hub_connection_mode == "serial":
        if not serial.is_connected():
            console.log("❌ Serial not connected - cannot send command")
            js_result = Object.new()
            js_result.status = "error"
            js_result.error = "Not connected to hub"
            return js_result
        
        # Format for Serial (JSON)
        cmd_obj = {"cmd": command, "rssi": rssi_threshold}
        message = json.dumps(cmd_obj)
        success = await serial.send_json(message)
        
    elif hub_connection_mode == "ble":
        if not ble.is_connected():
            js_result = Object.new()
            js_result.status = "error"
            js_result.error = "Not connected to hub"
            return js_result
        
        # Format for BLE (legacy format)
        message = f'"{command}":"{rssi_threshold}"'
        success = await ble.send(message)
    
    else:
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = "Not connected to hub"
        return js_result
    
    js_result = Object.new()
    if success:
        console.log(f"Sent to hub ({hub_connection_mode}): {command}")
        js_result.status = "sent"
        js_result.command = command
        js_result.threshold = rssi_threshold
    else:
        js_result.status = "error"
        js_result.error = "Send failed"
    return js_result

def get_connection_status():
    """Return hub connection status (connected bool, mode, device name)."""
    # Check actual connection status based on mode
    if hub_connection_mode == "serial":
        actual_connected = serial.is_connected()
    elif hub_connection_mode == "ble":
        actual_connected = ble.is_connected()
    else:
        actual_connected = False
    
    # Convert to bool for JavaScript compatibility
    actual_connected_bool = bool(actual_connected) if actual_connected is not None else False
    
    console.log(f"Connection status: mode={hub_connection_mode}, connected={actual_connected_bool}")
    
    # Return proper JavaScript object
    js_result = Object.new()
    js_result.connected = actual_connected_bool
    js_result.mode = hub_connection_mode if hub_connection_mode else ""
    # Use empty string instead of None to avoid undefined in JavaScript
    js_result.device = hub_device_name if (actual_connected_bool and hub_device_name) else ""
    return js_result

async def refresh_devices_from_hub(rssi_threshold="all"):
    """Request device list from hub with RSSI filtering.
    
    Args:
        rssi_threshold: "all" for no filter, or "-XX" for RSSI >= -XX dBm
    
    Returns:
        JavaScript array of device objects
    """
    global devices
    
    # Convert rssi_threshold to string for protocol
    threshold_str = str(rssi_threshold)
    
    # Send PING command based on connection mode
    if hub_connection_mode == "serial":
        if not serial.is_connected():
            console.log("Cannot refresh: Hub not connected")
            return to_js([])
        
        # Format for Serial (JSON)
        ping_obj = {"cmd": "PING", "rssi": threshold_str}
        ping_command = json.dumps(ping_obj)
        await serial.send_json(ping_command)
        
    elif hub_connection_mode == "ble":
        if not ble.is_connected():
            console.log("Cannot refresh: Hub not connected")
            return to_js([])
        
        # Format for BLE (legacy format)
        ping_command = f'"PING":"{threshold_str}"'
        await ble.send(ping_command)
    
    else:
        console.log("Cannot refresh: Hub not connected")
        return to_js([])
    
    # Wait for response (hub should send back device list)
    # The response will be handled by on_ble_data or on_serial_data callback
    # which will update the global devices list
    
    console.log(f"Device scan requested from hub ({hub_connection_mode}) with RSSI threshold: {threshold_str}")
    
    # Convert Python list to JavaScript array using to_js()
    return to_js(devices, dict_converter=Object.fromEntries)

def get_devices():
    """Return list of available devices (legacy, use refresh_devices_from_hub)."""
    console.log("Python: get_devices called")
    # Convert Python list to JavaScript array using to_js()
    return to_js(devices, dict_converter=Object.fromEntries)

def refresh_devices():
    """Refresh device list (deprecated, use refresh_devices_from_hub)."""
    console.log("Python: refresh_devices called (deprecated)")
    
    if ble.is_connected():
        # Use BLE to get real device list
        return refresh_devices_from_hub()
    else:
        # Return empty list if not connected
        console.log("Hub not connected, returning empty device list")
        return []

def send_command(command, device_ids):
    """Send command to specific devices (legacy, use send_command_to_hub)."""
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
# ============================================================================
# Firmware Upload Functions
# ============================================================================

async def upload_firmware(files_json):
    """Upload hub firmware files to ESP32.
    
    Args:
        files_json: List of {"path": str, "content": str} dicts
    
    Returns:
        JavaScript object with status and files_uploaded count
    """
    global serial_connected
    
    # Check if serial is connected
    if not serial.is_connected():
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = "Not connected to serial port"
        return js_result
    
    try:
        # Enter normal REPL mode (interrupt running code)
        console.log("Entering REPL mode...")
        await repl.enter_repl_mode()
        
        # Enter raw REPL mode (needed for file upload operations)
        console.log("Entering raw REPL mode for file upload...")
        await repl.enter_raw_repl_mode()
        
        # Convert JS array to Python list
        files = []
        for i in range(len(files_json)):
            file_obj = files_json[i]
            files.append({
                "path": file_obj.path,
                "content": file_obj.content
            })
        
        total_files = len(files)
        console.log(f"Uploading {total_files} files...")
        
        # Upload each file with progress callback
        for idx, file_info in enumerate(files):
            file_path = file_info["path"]
            content = file_info["content"]
            
            # Notify JavaScript of progress
            if hasattr(window, 'onUploadProgress'):
                progress = Object.new()
                progress.current = idx + 1
                progress.total = total_files
                progress.file = file_path
                progress.status = "uploading"
                window.onUploadProgress(progress)
            
            console.log(f"Uploading {idx + 1}/{total_files}: {file_path}...")
            
            # Create directory if needed
            dir_parts = file_path.split("/")
            if len(dir_parts) > 1:
                dir_path = "/".join(dir_parts[:-1])
                if dir_path:
                    await firmware.ensure_directory(dir_path)
            
            # Upload file
            await firmware.upload_single_file(file_path, content)
            
            # Notify upload complete for this file
            if hasattr(window, 'onUploadProgress'):
                progress = Object.new()
                progress.current = idx + 1
                progress.total = total_files
                progress.file = file_path
                progress.status = "uploaded"
                window.onUploadProgress(progress)
        
        # Exit raw REPL mode back to normal REPL
        console.log("Exiting REPL mode...")
        await repl.exit_raw_repl_mode()
        
        # Start the uploaded main.py
        console.log("Starting hub firmware...")
        await repl.execute_command("import main", timeout_ms=2000)
        
        console.log(f"✅ Upload complete: {total_files} files")
        console.log("Hub firmware is now running...")
        
        # Return success
        js_result = Object.new()
        js_result.status = "success"
        js_result.files_uploaded = total_files
        return js_result
        
    except Exception as e:
        console.error(f"Upload failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to exit REPL mode on error
        try:
            await repl.exit_raw_repl_mode()
        except:
            pass
        
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = str(e)
        return js_result

async def get_board_info():
    """Get MicroPython board info (enters REPL, queries, returns to JSON mode)."""
    if not serial.is_connected():
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = "Not connected"
        return js_result
    
    try:
        # Enter normal REPL mode (stops JSON read loop, interrupts running code)
        await repl.enter_repl_mode()
        
        # Get board info from normal REPL (no need for raw REPL)
        info = await repl.get_board_info()
        
        # Exit raw REPL if we entered it
        await repl.exit_raw_repl_mode()
        
        # Restart JSON read loop to return to normal operation
        serial._start_json_read_loop()
        
        js_result = Object.new()
        js_result.status = "success"
        js_result.info = info
        return js_result
        
    except Exception as e:
        console.error(f"Failed to get board info: {e}")
        
        # Try to recover to JSON mode
        try:
            await repl.exit_raw_repl_mode()
            serial._start_json_read_loop()
        except:
            pass
        
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = str(e)
        return js_result

async def query_device_info_for_setup():
    """Stop JSON read loop to prepare for board info query (setup workflow only)."""
    console.log("🔍 [query_device_info_for_setup] Starting device query...")
    
    if not serial.is_connected():
        console.log("❌ [query_device_info_for_setup] Serial not connected")
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = "Not connected to serial port"
        return js_result
    
    console.log("✅ [query_device_info_for_setup] Serial is connected")
    
    try:
        # Stop any JSON read loop if it exists (but don't fail if it doesn't)
        console.log("🛑 [query_device_info_for_setup] Stopping JSON read loop...")
        try:
            await serial._stop_json_read_loop()
            console.log("✅ [query_device_info_for_setup] JSON read loop stopped and cleaned up")
        except Exception as e:
            console.log(f"⚠️ [query_device_info_for_setup] No JSON read loop to stop: {e}")
            pass
        
        js_result = Object.new()
        js_result.status = "loop_stopped"
        js_result.message = "JSON read loop stopped, ready for board info query"
        return js_result
        
    except Exception as e:
        console.error(f"❌ [query_device_info_for_setup] Failed: {e}")
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = str(e)
        return js_result

def get_device_board_info():
    """Get board info after read loop stopped (call after query_device_info_for_setup)."""
    console.log("📡 [get_device_board_info] Getting board info...")
    
    if not serial.is_connected():
        console.log("❌ [get_device_board_info] Serial not connected")
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = "Not connected to serial port"
        return js_result
    
    # Return a promise-like object that JavaScript can await
    # This allows the async repl.get_board_info() to work properly
    async def _get_info():
        try:
            info = await repl.get_board_info()
            console.log(f"✅ [get_device_board_info] Got board info: {info}")
            
            js_result = Object.new()
            js_result.status = "success"
            js_result.info = info
            return js_result
        except Exception as e:
            console.error(f"❌ [get_device_board_info] Failed: {e}")
            js_result = Object.new()
            js_result.status = "error"
            js_result.error = str(e)
            return js_result
    
    # Return the coroutine for JavaScript to await
    return _get_info()

async def execute_file_on_device(file_path):
    """Execute Python file on device (enters REPL, runs file, returns to JSON mode)."""
    if not serial.is_connected():
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = "Not connected"
        return js_result
    
    try:
        # Enter normal REPL mode (interrupt running code)
        await repl.enter_repl_mode()
        
        # Enter raw REPL mode (needed for file execution)
        await repl.enter_raw_repl_mode()
        
        # Execute the file
        output = await firmware.execute_file(file_path)
        
        # Exit raw REPL mode
        await repl.exit_raw_repl_mode()
        
        # Restart JSON read loop to return to normal operation
        serial._start_json_read_loop()
        
        js_result = Object.new()
        js_result.status = "success"
        js_result.output = output
        return js_result
        
    except Exception as e:
        console.error(f"File execution failed: {e}")
        
        # Try to recover to JSON mode
        try:
            await repl.exit_raw_repl_mode()
            serial._start_json_read_loop()
        except:
            pass
        
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = str(e)
        return js_result

async def soft_reset_device():
    """Soft reset device (MicroPython re-init, no hardware reboot)."""
    if not serial.is_connected():
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = "Not connected"
        return js_result
    
    try:
        # Enter normal REPL mode (interrupt running code)
        await repl.enter_repl_mode()
        
        # Perform soft reset (Ctrl-D from normal REPL)
        await firmware.soft_reset()
        
        # Device is now at normal REPL prompt (>>>)
        # Don't restart JSON mode - user may want to interact with REPL
        
        js_result = Object.new()
        js_result.status = "success"
        js_result.message = "Device soft reset (at REPL prompt)"
        return js_result
        
    except Exception as e:
        console.error(f"Soft reset failed: {e}")
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = str(e)
        return js_result

async def hard_reset_device():
    """Hard reset device (full hardware reboot, runs main.py on restart)."""
    if not serial.is_connected():
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = "Not connected"
        return js_result
    
    try:
        # Enter normal REPL mode (interrupt running code)
        await repl.enter_repl_mode()
        
        # Enter raw REPL mode (needed to execute machine.reset())
        await repl.enter_raw_repl_mode()
        
        # Perform hard reset (device will reboot)
        await firmware.hard_reset()
        
        # Device has rebooted and is running main.py
        # Restart JSON read loop to reconnect
        serial._start_json_read_loop()
        
        js_result = Object.new()
        js_result.status = "success"
        js_result.message = "Device rebooted (running main.py)"
        return js_result
        
    except Exception as e:
        console.error(f"Hard reset failed: {e}")
        
        # Try to recover to JSON mode
        try:
            serial._start_json_read_loop()
        except:
            pass
        
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = str(e)
        return js_result

# ============================================================================
# Expose Python functions to JavaScript
# ============================================================================

# Use create_proxy only for async functions to prevent garbage collection
window.get_devices = get_devices
window.get_connection_status = get_connection_status
window.connect_hub = create_proxy(connect_hub)
window.disconnect_hub = create_proxy(disconnect_hub)
window.connect_hub_serial = create_proxy(connect_hub_serial)
window.disconnect_hub_serial = create_proxy(disconnect_hub_serial)
window.send_command_to_hub = create_proxy(send_command_to_hub)
window.refresh_devices = create_proxy(refresh_devices)
window.refresh_devices_from_hub = create_proxy(refresh_devices_from_hub)

# Firmware upload and device management functions
window.upload_firmware = create_proxy(upload_firmware)
window.get_board_info = create_proxy(get_board_info)
window.query_device_info_for_setup = create_proxy(query_device_info_for_setup)
window.get_device_board_info = create_proxy(get_device_board_info)
window.execute_file_on_device = create_proxy(execute_file_on_device)
window.soft_reset_device = create_proxy(soft_reset_device)
window.hard_reset_device = create_proxy(hard_reset_device)

# Set up serial connection lost callback (proxied for JS)
serial.on_connection_lost_callback = create_proxy(on_serial_connection_lost)

# Python backend is ready

console.log("✅ Python backend initialized [v2024.12.05]")