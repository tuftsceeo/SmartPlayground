"""
Smart Playground Control - Python Backend

PyScript backend handling USB Serial communication with ESP32 hub devices
and ESP-NOW protocol for playground modules.
"""

from pyscript import document, window
from pyodide.ffi import create_proxy, to_js
from js import console, Object, Array
import json
import random
import time
import asyncio

_DEBUG_SERIAL = True

print("✅ main.py LOADED")
console.log("✅ main.py visible in browser console")

if not hasattr(window, 'serialAdapter'):
    console.error("❌ FATAL: serialAdapter not found!")
    console.error("Make sure js/adapters/serialAdapter.js is loaded before PyScript")
    raise Exception("JavaScript serial adapter not loaded properly")

console.log("✅ JavaScript serial adapter detected")

from mpy.hub_serial import SerialConnection
from mpy.repl_controller import ReplController
from mpy.firmware_manager import FirmwareManager

# Create component instances
serial = SerialConnection()
repl = ReplController(serial)
firmware = FirmwareManager(repl)

# Set up serial callbacks

# Connection state
serial_connected = False
hub_device_name = None
hub_connection_mode = None
devices = []

last_hub_ready_time = 0
last_device_list_time = 0
last_heartbeat_time = 0
pending_commands = {}  # {command_id: {command, timestamp, timeout_ms}}

# Message framing state for unused BLE transmission reassembly
# Protocol: MSG:<length>|<payload>
_frame_state = "waiting_header"  # States: "waiting_header", "receiving_payload"
_expected_payload_length = 0
_payload_buffer = ""
_frame_buffer = ""
_last_fragment_time = 0
_buffer_timeout = 2.0

def parse_hub_response(data):
    """Parse JSON from hub with single repair attempt for truncated data."""
    try:
        parsed = json.loads(data)
        return parsed
    except Exception as e:
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
    """Process message from hub (JSON or debug text)."""
    global devices
    
    message_data = message_data.strip()
    
    console.log(f"🔵 process_complete_message: stripped data = '{message_data[:100]}'")
    console.log(f"🔵 process_complete_message: starts with '{{' ? {message_data.startswith('{')}")
    
    if not message_data.startswith('{'):
        console.info(f"📡 Hub debug: {message_data}")
        return
    
    console.log("=== PROCESSING HUB JSON ===")
    console.log(f"Full JSON message: {message_data}")
    
    parsed = parse_hub_response(message_data)
    if not parsed:
        console.error(f"❌ Failed to parse hub JSON: {message_data}")
        return
    
    console.log(f"✅ JSON parsed successfully: type = '{parsed.get('type', 'MISSING')}'")
    
    if 'type' not in parsed:
        console.log("❌ Missing 'type' field in hub response")
        return
    
    if parsed.get("type") == "ready":
        # Hub startup handshake
        global last_hub_ready_time
        last_hub_ready_time = time.time()
        
        console.log("🟢 Hub ready handshake received")
        hub_version = parsed.get("version", "unknown")
        hub_mac = parsed.get("mac", "unknown")
        hub_timestamp = parsed.get("timestamp", 0)
        
        console.log(f"Hub Version: {hub_version}")
        console.log(f"Hub MAC: {hub_mac}")
        console.log(f"Hub Timestamp: {hub_timestamp}")
        
        # Notify JavaScript if handler exists
        if hasattr(window, 'onHubReady'):
            js_data = Object.new()
            js_data.version = hub_version
            js_data.mac = hub_mac
            js_data.timestamp = hub_timestamp
            window.onHubReady(js_data)
            console.log("✅ onHubReady() called")
        
    elif parsed.get("type") == "poll_started":
        console.log("Poll cycle started")
        if hasattr(window, 'onPollStarted'):
            js_data = Object.new()
            js_data.timestamp = parsed.get("timestamp", 0)
            window.onPollStarted(js_data)
            console.log("onPollStarted() called")

    elif parsed.get("type") == "device_report":
        console.log("Device report received")
        if hasattr(window, 'onDeviceReport'):
            report = Object.new()
            report.id = parsed.get("id", "")
            report.mac = parsed.get("mac", "")
            report.battery = parsed.get("battery")
            report.rssi = parsed.get("rssi")
            report.timestamp = parsed.get("timestamp", 0)
            window.onDeviceReport(report)
            console.log("onDeviceReport() called")

    elif parsed.get("type") == "devices":
        global last_device_list_time
        last_device_list_time = time.time()
        
        console.log("🎯 Found 'devices' type - processing device list")
        console.log(f"Device list length: {len(parsed.get('list', []))}")
        
        if 'list' not in parsed:
            console.log("Missing 'list' field in devices response")
            return
            
        device_list = parsed.get("list", [])
        if not isinstance(device_list, list):
            console.log("Device list is not an array")
            return
        
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
        
        # Log when receiving empty device list
        if len(unique_devices) == 0:
            console.log("📭 EMPTY device list received from hub (all devices removed/expired)")
        
        hub_timestamp = parsed.get("timestamp", 0)
        
        devices = []
        for dev in unique_devices:
            # Handle None/null values - do NOT invent fake data
            # If value is None, leave it as None to indicate "unknown"
            rssi = dev.get("rssi")
            if rssi is not None and isinstance(rssi, (int, float)):
                # Valid RSSI - calculate signal strength
                if rssi >= -50:
                    signal = 3
                elif rssi >= -70:
                    signal = 2
                elif rssi >= -85:
                    signal = 1
                else:
                    signal = 0
            else:
                # Unknown RSSI - mark signal as None for UI to display as unknown
                rssi = None
                signal = None
            
            battery_pct = dev.get("battery")
            if battery_pct is not None and isinstance(battery_pct, (int, float)):
                # Valid battery - calculate battery level
                if battery_pct >= 75:
                    battery = "full"
                elif battery_pct >= 50:
                    battery = "high"
                elif battery_pct >= 25:
                    battery = "medium"
                else:
                    battery = "low"
            else:
                # Unknown battery - mark as None for UI to display as unknown
                battery_pct = None
                battery = None
            
            device_name = dev.get("id", "Unknown")
            
            # Log malformed data warnings
            if rssi is None:
                console.warn(f"⚠️ Device {device_name}: Missing/invalid RSSI data")
            if battery_pct is None:
                console.warn(f"⚠️ Device {device_name}: Missing/invalid battery data")
            
            # Sanitize ID for DOM selectors
            sanitized_id = device_name.replace(" ", "-").replace("_", "-")
            sanitized_id = ''.join(c for c in sanitized_id if c.isalnum() or c == '-')
            
            console.log(f"DEBUG SANITIZATION: '{device_name}' -> '{sanitized_id}'")
            
            # Get staleness indicator from hub
            is_stale = dev.get("is_stale", False)
            
            devices.append({
                "id": sanitized_id,
                "name": device_name,
                "type": "module",
                "mac": dev.get("mac", ""),
                "rssi": rssi,
                "signal": signal,
                "battery": battery,
                "battery_pct": battery_pct,
                "last_seen": dev.get("last_seen", 0),
                "is_stale": is_stale
            })
        
        if hasattr(window, 'onDevicesUpdated'):
            console.log("🟢 Python: Calling window.onDevicesUpdated()")
            console.log(f"📋 Devices to send: {len(devices)} devices")
            for i, dev in enumerate(devices):
                console.log(f"  Device {i+1}: {dev.get('name')} (RSSI: {dev.get('rssi')}, Battery: {dev.get('battery_pct')}%)")
            console.log(f"⏰ Hub timestamp: {hub_timestamp}")
            
            js_devices = to_js(devices, dict_converter=Object.fromEntries)
            
            console.log(f"✅ Converted to JS: {len(devices)} devices")
            window.onDevicesUpdated(js_devices, hub_timestamp)
            console.log("✅ onDevicesUpdated() called successfully")
        else:
            console.log("❌ Python: window.onDevicesUpdated not available!")
        
        console.log(f"Updated {len(devices)} devices from hub")
    elif parsed.get("type") == "heartbeat":
        global last_heartbeat_time
        last_heartbeat_time = time.time()
        
        if _DEBUG_SERIAL:
            hub_timestamp = parsed.get("timestamp", 0)
            uptime = parsed.get("uptime", 0)
            console.log(f"💓 Heartbeat received (uptime: {uptime}ms)")
        
        if hasattr(window, 'onHubHeartbeat'):
            js_data = Object.new()
            js_data.timestamp = parsed.get("timestamp", 0)
            js_data.uptime = parsed.get("uptime", 0)
            window.onHubHeartbeat(js_data)
    
    elif parsed.get("type") == "ack":
        global pending_commands
        
        console.log("Received acknowledgment from hub")
        command = parsed.get("command", "unknown")
        status = parsed.get("status", "unknown")
        cleared_commands = []
        for cmd_id, cmd_info in list(pending_commands.items()):
            if cmd_info['command'] == command:
                cleared_commands.append(cmd_id)
                del pending_commands[cmd_id]
        
        if cleared_commands and _DEBUG_SERIAL:
            console.log(f"Cleared {len(cleared_commands)} pending command(s)")
        
        if status == "sent":
            console.log(f"✓ Command '{command}' sent successfully")
        else:
            console.log(f"✗ Command '{command}' failed to send (status: {status})")
    elif parsed.get("type") == "error":
        console.log("Received error from hub")
        error_msg = parsed.get("message", "Unknown error")
        console.log(f"Hub error: {error_msg}")
        
        if hasattr(window, 'showToast'):
            window.showToast(error_msg, "error")
    else:
        console.log(f"Unknown message type: {parsed.get('type')}")

# Unused BLE stubs
async def connect_hub():
    """Unused BLE stub."""
    console.error("❌ connect_hub() is deprecated - BLE not supported")
    console.error("Use connect_hub_serial() for USB Serial connection")
    js_result = Object.new()
    js_result.status = "error"
    js_result.error = "BLE not supported - use USB Serial connection"
    return js_result

async def disconnect_hub():
    """Unused BLE stub."""
    console.error("❌ disconnect_hub() is deprecated - BLE not supported")
    console.error("Use disconnect_hub_serial() for USB Serial disconnection")
    js_result = Object.new()
    js_result.status = "error"
    js_result.error = "BLE not supported - use USB Serial connection"
    return js_result

async def connect_hub_serial():
    """Connect to hub via USB Serial."""
    global serial_connected, hub_device_name, hub_connection_mode
    
    console.log("Attempting Serial connection...")
    
    try:
        serial.on_data_callback = create_proxy(on_serial_data)
        
        if _DEBUG_SERIAL:
            console.log(f"🟡 [main.py] Serial callback set to: {serial.on_data_callback}")
            console.log(f"🟡 [main.py] Callback is function: {callable(serial.on_data_callback)}")
        
        success = await serial.connect()
        
        if success:
            serial_connected = True
            hub_device_name = "USB Serial Hub"
            hub_connection_mode = "serial"
            
            console.log("Serial connected successfully")
            
            if hasattr(window, 'onHubConnected'):
                js_data = Object.new()
                js_data.deviceName = hub_device_name
                js_data.mode = "serial"
                window.onHubConnected(js_data)
            
            js_result = Object.new()
            js_result.status = "success"
            js_result.device = hub_device_name
            js_result.mode = "serial"
            return js_result
        else:
            console.log("Serial connection cancelled or failed - check console for details")
            js_result = Object.new()
            js_result.status = "error"
            js_result.error = "Connection failed - check browser console for details"
            return js_result
    
    except Exception as e:
        error_msg = str(e)
        console.log(f"Serial connection exception: {error_msg}")
        
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
    
    if hasattr(window, 'onHubDisconnected'):
        window.onHubDisconnected()
    
    js_result = Object.new()
    js_result.status = "disconnected"
    return js_result

def on_serial_data(data):
    """Handle incoming Serial data."""
    if _DEBUG_SERIAL:
        console.log("=" * 80)
        console.log("🟡 [main.py] on_serial_data() CALLED")
        console.log(f"🟡 [main.py] Serial data received ({len(data)} chars): {data[:200]}")
        console.log(f"🟡 [main.py] Data type: {type(data)}")
        console.log("=" * 80)
    else:
        console.log("🟡 on_serial_data() CALLED")
        console.log(f"📥 Serial data received ({len(data)} chars): {data[:200]}")
    
    process_complete_message(data)

def check_pending_commands():
    """Check for timed out commands."""
    global pending_commands
    
    current_time = time.time()
    timed_out = []
    
    for cmd_id, cmd_info in list(pending_commands.items()):
        age_ms = (current_time - cmd_info['timestamp']) * 1000
        if age_ms > cmd_info['timeout_ms']:
            timed_out.append({
                'id': cmd_id,
                'command': cmd_info['command'],
                'age_ms': int(age_ms)
            })
            del pending_commands[cmd_id]
    
    if timed_out:
        console.log(f"⚠️ {len(timed_out)} command(s) timed out without ACK")
        for cmd in timed_out:
            console.log(f"  - {cmd['command']} (waited {cmd['age_ms']}ms)")
    
    return to_js(timed_out, dict_converter=Object.fromEntries)

def check_connection_health():
    """Check connection health and return status info."""
    global last_hub_ready_time, last_device_list_time, last_heartbeat_time
    
    current_time = time.time()
    issues = []
    
    if hub_connection_mode != "serial" or not serial.is_connected():
        issues.append("Not connected to hub")
    
    if last_heartbeat_time > 0:
        heartbeat_age = current_time - last_heartbeat_time
        if heartbeat_age > 10:
            issues.append(f"No heartbeat for {int(heartbeat_age)}s")
    
    js_result = Object.new()
    js_result.healthy = len(issues) == 0
    js_result.issues = to_js(issues)
    js_result.last_heartbeat = (current_time - last_heartbeat_time) if last_heartbeat_time > 0 else -1
    
    return js_result

def on_serial_connection_lost():
    """Handle unexpected serial connection loss."""
    global serial_connected, hub_device_name, hub_connection_mode
    
    console.log("⚠️ Serial connection lost - updating backend state")
    console.log(f"BEFORE: serial_connected={serial_connected}, mode={hub_connection_mode}")
    
    serial_connected = False
    hub_device_name = None
    hub_connection_mode = None
    
    console.log(f"AFTER: serial_connected={serial_connected}, mode={hub_connection_mode}")
    console.log(f"serial.is_connected() = {serial.is_connected()}")
    
    if hasattr(window, 'onHubDisconnected'):
        console.log("🔔 Notifying UI of disconnection via onHubDisconnected()")
        window.onHubDisconnected()
    else:
        console.warn("⚠️ onHubDisconnected callback not found in window")

async def send_command_to_hub(command):
    """Send command to hub for ESP-NOW broadcast to all wands."""
    global pending_commands

    if hub_connection_mode != "serial" or not serial.is_connected():
        console.log("❌ Serial not connected - cannot send command")
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = "Not connected to hub"
        return js_result

    cmd_id = f"{command}_{int(time.time() * 1000)}"
    pending_commands[cmd_id] = {
        'command': command,
        'timestamp': time.time(),
        'timeout_ms': 2000
    }

    message = json.dumps({"cmd": command})
    success = await serial.send_json(message)

    js_result = Object.new()
    if success:
        console.log(f"Sent to hub (serial): {command}")
        js_result.status = "sent"
        js_result.command = command
    else:
        js_result.status = "error"
        js_result.error = "Send failed"
    return js_result

async def find_device(mac):
    """Ask the hub to ping one specific wand (targeted broadcast by MAC)."""
    if hub_connection_mode != "serial" or not serial.is_connected():
        console.log("❌ Serial not connected - cannot send find")
        js_result = Object.new()
        js_result.status = "error"
        js_result.error = "Not connected to hub"
        return js_result

    message = json.dumps({"cmd": "find", "mac": mac})
    success = await serial.send_json(message)

    js_result = Object.new()
    if success:
        console.log(f"Sent find to hub (serial): {mac}")
        js_result.status = "sent"
        js_result.mac = mac
    else:
        js_result.status = "error"
        js_result.error = "Send failed"
    return js_result

def get_connection_status():
    """Return hub connection status (connected bool, mode, device name)."""
    # Check actual connection status (USB Serial only)
    if hub_connection_mode == "serial":
        actual_connected = serial.is_connected()
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

def get_devices():
    """Return cached device list from the last Ask Device Status poll."""
    console.log("Python: get_devices called")
    return to_js(devices, dict_converter=Object.fromEntries)

def send_command(command, device_ids):
    """Send command to specific devices (legacy, use send_command_to_hub)."""
    console.log(f"Python: Sending '{command}' to {len(device_ids)} devices")
    
    if serial.is_connected():
        # Use Serial to send command to hub
        # Convert range slider to RSSI threshold (this will be done in JS)
        return send_command_to_hub(command)
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
window.find_device = create_proxy(find_device)
# Firmware upload and device management functions
window.upload_firmware = create_proxy(upload_firmware)
window.get_board_info = create_proxy(get_board_info)
window.query_device_info_for_setup = create_proxy(query_device_info_for_setup)
window.get_device_board_info = create_proxy(get_device_board_info)
window.execute_file_on_device = create_proxy(execute_file_on_device)
window.soft_reset_device = create_proxy(soft_reset_device)
window.hard_reset_device = create_proxy(hard_reset_device)

# Connection health and retry functions
window.check_connection_health = check_connection_health
window.check_pending_commands = check_pending_commands

# Set up serial connection lost callback (proxied for JS)
serial.on_connection_lost_callback = create_proxy(on_serial_connection_lost)

# Python backend is ready

console.log("✅ Python backend initialized [v2024.12.05]")