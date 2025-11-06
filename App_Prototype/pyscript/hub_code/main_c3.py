# ESP32C6 Hub/Modem for BLE communication with Web App 
#
# Nordic UART Service (NUS):
# - Standard BLE service that emulates a serial/UART connection
# - Service UUID: 6E400001-B5A3-F393-E0A9-E50E24DCCA9E
# - Two characteristics:
#   * RX (6E400002...): Central writes commands → Peripheral reads (web → ESP32)
#   * TX (6E400003...): Peripheral sends data → Central reads (ESP32 → web)
#
# Data Flow in this application:
# 1. ESP32 advertises "SPHub" name with Nordic UART service
# 2. Web browser scans for devices and connects to ESP32
# 3. Browser writes commands to RX characteristic (e.g., "PING":"all")
# 4. ESP32's handle_cmd() processes the command
# 5. ESP32 sends responses via TX characteristic using p.send()
# 6. Browser receives notifications and updates UI
#
# CRITICAL: All data sent via BLE UART must be BYTES, not strings!
# - Use .encode() to convert strings: "hello".encode() → b"hello"
# - Use b'...' for literals: b'{"status":"ok"}'
# =============================================================================

import network
import time
import json
import random
from machine import Pin
from ble_uart import Yell
from twist_iot import TwistIOT

twist = TwistIOT()
twist.setup_modes([
    ("Off", 0, 0, 0),
    ("Waiting", 255, 0, 255),
    ("Paired", 0, 255, 0),
    ("Devices", 0, 128, 255),
])
    

# === CONFIGURATION ===
HUB_NAME = "SPHub"

BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'  # Broadcast to all modules

# Status LED for visual feedback
led = Pin(2, Pin.OUT)  # Built-in LED
led.value(0)

# === ESP-NOW SETUP ===
print("Initializing ESP-NOW...")
import espnow

# A WLAN interface must be active to send()/recv()
sta = network.WLAN(network.WLAN.IF_STA)
sta.active(True)
sta.disconnect()

# ESP32-C3 uses external antenna by default?
# EXTERNAL_ANT = False
# if EXTERNAL_ANT:
#     # Define pins
#     WIFI_ENABLE = Pin(3, Pin.OUT)
#     WIFI_ANT_CONFIG = Pin(14, Pin.OUT)
#     # Activate RF switch control
#     WIFI_ENABLE.value(0) #Low
#     # Wait for 100 milliseconds
#     time.sleep_ms(100)
#     # Use external antenna
#     WIFI_ANT_CONFIG.value(1) #High

# Wait for 100 milliseconds
time.sleep_ms(100)

espnow_interface = espnow.ESPNow()
espnow_interface.active(True)

peer = b'\xff\xff\xff\xff\xff\xff'   # MAC address of peer's wifi interface
espnow_interface.add_peer(peer)
BROADCAST_MAC = peer

print(f"ESP-NOW initialized")
print(f"Broadcast peer added: {BROADCAST_MAC.hex()}")

# ESP-NOW message buffer for interrupt handler
from ucollections import deque
espnow_msg_buffer = deque((), 50, 2)  # Max 50 messages

def espnow_recv_cb(interface):
    """
    ESP-NOW interrupt callback - buffers incoming messages
    This prevents messages from being dropped during polling delays
    """
    global espnow_msg_buffer
    while True:
        mac, msg = interface.irecv(0)
        if mac is None:
            return
        try:
            espnow_msg_buffer.append((bytes(mac), msg))
            print("ESP-NOW RX:", mac.hex()[:12], "buffered")
        except Exception as err:
            print("ESP-NOW recv error:", err)

# Set up interrupt handler for ESP-NOW
espnow_interface.irq(espnow_recv_cb)
print("ESP-NOW interrupt handler registered")

# === BLE UART SETUP ===
# Yell is a BLE Peripheral (server) class from ble_uart.py
# It creates a GATT server with Nordic UART Service
# - Automatically registers the service and characteristics
# - Sets up interrupt handlers for connection events
# - Provides send() method to transmit data to connected central device
print("Initializing BLE UART service...")
p = Yell(HUB_NAME, verbose=True)
print(f"BLE advertising as '{HUB_NAME}'")

# === DEVICE DISCOVERY STATE ===
discovered_devices = []
device_scan_timeout = 5.0  # seconds to wait for device responses
scan_in_progress = False

# === MOCK DEVICE DATA (for testing without modules) ===
"""
mock_devices = [
    {"id": "M-001", "rssi": -45, "battery": 85, "type": "module", "mac": "aa:bb:cc:dd:ee:01"},
    {"id": "M-002", "rssi": -60, "battery": 92, "type": "module", "mac": "aa:bb:cc:dd:ee:02"},
    {"id": "M-003", "rssi": -75, "battery": 78, "type": "module", "mac": "aa:bb:cc:dd:ee:03"}
]
"""

# === WEB APP TO ESP-NOW COMMAND MAPPING ===
# Maps web app commands (as sent by main.js) to ESP-NOW protocol format
# Format: {"espnowCommand": {"RSSI": threshold, "value": value}}
#
# Web app sends command.label from COMMANDS array in constants.js:
#  * Command Types:
#  * - play: Start playground activity
#  * - pause: Pause current activity
#  * - win: Trigger win/success state
#  * - color_game: Start color-based game
#  * - number_game: Start number-based game
#  * - off: Turn off/reset modules
COMMAND_MAP = {
    # Main commands from web app
    "Play": "updateGame",           # Start game - uses game value
    "Pause": "lightOff",             # Pause/turn off modules
    "Win": "rainbow",                # Winning animation
    "Color Game": "updateGame",      # Color-based grouping game (value: 1)
    "Number Game": "updateGame",     # Number-based grouping game (value: 2)
    "Off": "deepSleep", # Deep sleep mode
    "PING": "pingCall",
}

# Game values for updateGame command
GAME_VALUES = {
    "Play": 0,              # Generic play (no specific game)
    "Color Game": 1,        # Color-based grouping
    "Number Game": 2,       # Number-based grouping
}

# === COMMAND PROTOCOL IMPLEMENTATION ===
def parse_web_command(command_str):
    """
    Parse commands from web app in format: "command":"rssi_threshold"
    
    BLE UART receives data as bytes, but we work with strings after decoding.
    The web app sends commands in a simple JSON-like format without outer braces.
    
    Examples:
    - "PING":"all" -> scan all devices
    - "COLOR BASED GROUP":"-60" -> send to devices with RSSI >= -60
    - "BATTERY CHECK":"all" -> check battery on all devices
    
    RSSI (Received Signal Strength Indicator):
    - Measured in dBm (negative numbers)
    - -30 dBm = very close (excellent signal)
    - -60 dBm = moderate distance (good signal)
    - -90 dBm = far away (weak signal)
    - "all" = no filtering, send to all devices
    """
    try:
        # Remove any whitespace and newlines
        command_str = command_str.strip()
        print(f"Parsing command: {repr(command_str)}")
        
        # Try to parse as JSON
        if command_str.startswith('"') and command_str.endswith('"'):
            # Remove outer quotes and parse
            inner = command_str[1:-1]
            if '":"' in inner:
                command, threshold = inner.split('":"', 1)
                return command, threshold
            
        elif '":"' in command_str:
            # Direct format without outer quotes
            command, threshold = command_str.split('":"', 1)
            return command, threshold
        
        else:
            # Fallback: treat as simple command
            return command_str, "all"
            
    except Exception as e:
        print(f"Command parse error: {e}")
        return command_str, "all"

def rssi_threshold_to_int(rssi_threshold):
    """
    Convert RSSI threshold string to integer value.
    
    Handles special cases:
    - "all" -> -100 (weakest threshold, includes all devices)
    - Numeric string -> convert to int
    - Invalid -> default to -100
    
    RSSI approximates:
        RSSI < -90 dBm: this signal is extremely weak, at the edge of what a receiver can receive.
        RSSI -67dBm: this is a fairly strong signal.
        RSSI > -55dBm: this is a very strong signal.
        RSSI > -30dBm: your sniffer is sitting right next to the transmitter.
    """
    if rssi_threshold == "all":
        return -100
    try:
        return int(rssi_threshold)
    except:
        print(f"Invalid RSSI threshold: {rssi_threshold}, defaulting to -90")
        return -100

def send_espnow_command(command, rssi_threshold="all"):
    """
    Send command to ESP-NOW modules using the proper protocol format.
    
    Protocol Format (from espnow_protocol_hub_to_controller.md):
    {"commandName": {"RSSI": <threshold>, "value": <value>}}
    
    Examples:
    - {"batteryCheck": {"RSSI": -40, "value": 0}}
    - {"rainbow": {"RSSI": -40, "value": 0}}
    - {"lightOff": {"RSSI": -90, "value": 0}}
    - {"updateGame": {"RSSI": -40, "value": 1}}
    - {"pingCall": {"RSSI": self.THRESHOLD_RSSI, "value": "app"}} <--- Hub sends
        - {"deviceScan": {"RSSI": self.THRESHOLD_RSSI, "value": self.name}} <-- MODULE REPLIES
    
    Parameters:
    -----------
    command : str
        Web app command (e.g., "BATTERY CHECK", "COLOR BASED GROUP")
    rssi_threshold : str
        RSSI filter ("all" or numeric string like "-60")
    
    Returns:
    --------
    bool : True if transmission successful, False otherwise
    """
    # Map web app command to ESP-NOW protocol command
    if command not in COMMAND_MAP:
        print(f"Unknown command: {command}")
        return False
    
    espnow_command = COMMAND_MAP[command]
    rssi_value = rssi_threshold_to_int(rssi_threshold)
    
    # Determine command value
    if espnow_command == "updateGame":
        # Game commands need specific game values
        value = GAME_VALUES.get(command, 0)
        
    elif espnow_command == "pingCall":
        value = "app"
    else:
        # Other commands use value: 0
        value = 0
    
    # Create ESP-NOW protocol message
    message = {
        espnow_command: {
            "RSSI": rssi_value,
            "value": value
        }
    }
    
    message_str = json.dumps(message)  # Convert dict to string for ESP-NOW transmission
    print(f"ESP-NOW: Sending")
    print(message)
    print(f"  Target RSSI: {rssi_value} dBm (modules stronger than this will respond)")
    
    try:
        # Send via ESP-NOW broadcast
        # IMPORTANT: ESP-NOW send() expects a STRING, not bytes!
        # MicroPython's espnow.send() will handle the encoding internally
        success = espnow_interface.send(BROADCAST_MAC, message_str)
        
        if success:
            print(f"ESP-NOW: Transmission successful")
            # Flash LED to indicate successful transmission
            led.value(1)
            time.sleep_ms(50)
            led.value(0)
        else:
            print(f"ESP-NOW: Transmission failed")
        
        return success
        
    except Exception as e:
        print(f"ESP-NOW send error: {e}")
        return False

def send_ble_framed(data_bytes, chunk_size=100):
    """
    Send large data over BLE with message framing protocol.
    
    Message Framing Protocol:
    -------------------------
    Each message is sent with a header indicating the total payload size:
    
    Format: MSG:<length>|<payload_chunk_1><payload_chunk_2>...<payload_chunk_n>
    
    Example:
    - Header: "MSG:330|"  (indicates 330 bytes of payload will follow)
    - Payload: Sent in 100-byte chunks after the header
    
    Why Message Framing?
    --------------------
    - Receiver knows exactly how many bytes to expect
    - No need to guess when message is complete (JSON brace counting is fragile)
    - Handles any data format, not just JSON
    - More robust than timeout-based buffering
    
    BLE MTU (Maximum Transmission Unit) limits:
    - BLE 4.0: 20 bytes default
    - BLE 4.2+: 23-244 bytes (negotiated)
    - Web Bluetooth API: Often 512 bytes, but not guaranteed
    
    We use 100 bytes as a safe chunk size that works across all versions.
    
    Parameters:
    -----------
    data_bytes : bytes
        The complete message payload to send (must be bytes, not string)
    chunk_size : int
        Maximum bytes per BLE notification (default: 100 bytes)
    """
    if not p.is_connected:
        print("Cannot send: BLE not connected")
        return False
    
    payload_length = len(data_bytes)
    
    # Create framing header: MSG:<length>|
    header = f"MSG:{payload_length}|".encode()
    
    # Send header first
    try:
        p.send(header)
        print(f"Sent message header: {header.decode()} ({len(header)} bytes)")
        time.sleep_ms(20)  # Small delay after header
    except Exception as e:
        print(f"Error sending header: {e}")
        return False
    
    # Send payload in chunks
    num_chunks = (payload_length + chunk_size - 1) // chunk_size  # Ceiling division
    print(f"Sending payload: {payload_length} bytes in {num_chunks} chunks")
    
    for i in range(0, payload_length, chunk_size):
        chunk = data_bytes[i:i+chunk_size]
        chunk_num = i // chunk_size + 1
        
        try:
            p.send(chunk)
            print(f"Sent payload chunk {chunk_num}/{num_chunks}: {len(chunk)} bytes")
            # Small delay between chunks to prevent buffer overflow
            time.sleep_ms(20)
        except Exception as e:
            print(f"Error sending payload chunk {chunk_num}: {e}")
            return False
    
    print(f"Successfully sent framed message: {len(header)} byte header + {payload_length} byte payload")
    return True

def handle_ping_command(rssi_threshold="all"):
    """
    Handle PING command - scan for nearby modules
    """
    global scan_in_progress, discovered_devices, espnow_msg_buffer
    
    print("Starting device scan ...")
    scan_in_progress = True
    discovered_devices = []
    
    # Clear any old messages from buffer
    while len(espnow_msg_buffer) > 0:
        espnow_msg_buffer.popleft()
    print("Cleared ESP-NOW buffer")
    
    # Send PING command to modules
    send_espnow_command("PING", rssi_threshold)
    
    # Wait for responses from buffer
    start_time = time.time()
    while time.time() - start_time < device_scan_timeout:
        # Check for buffered ESP-NOW responses
        if len(espnow_msg_buffer) > 0:
            mac, msg = espnow_msg_buffer.popleft()
            try:
                response = json.loads(msg.decode())
                print("Device response from", mac.hex(), ":", response)
                
                device_scan_data = response.get("deviceScan", None)
                if device_scan_data is None:
                    print("Not a deviceScan response, ignoring")
                    continue
                
                # Add to discovered devices
                try:
                    rssi = espnow_interface.peers_table[mac][0]
                except (KeyError, IndexError):
                    rssi = -50  # Default if not in peers table
                    
                device_info = {
                    "id": device_scan_data.get("value", "M-" + mac.hex()[:6]),
                    "rssi": rssi,
                    "battery": device_scan_data.get("battery", -1),
                    "type": device_scan_data.get("type", "Unknown"),
                    "mac": mac.hex()
                }
                discovered_devices.append(device_info)
                print("Added device:", device_info)
                
            except Exception as err:
                print("Response parse error:", err)
        else:
            # No messages in buffer, wait a bit
            time.sleep_ms(100)
    
    # PLACEHOLDER: Use mock devices for testing ===
    # print("ESP-NOW PLACEHOLDER: Using mock device data")
    # discovered_devices = mock_devices.copy()
    # ======
    print(f"Device scan complete. Found {len(discovered_devices)} devices")
    # Apply RSSI filtering if specified
    if rssi_threshold != "all":
        try:
            threshold_val = int(rssi_threshold)
            discovered_devices = [d for d in discovered_devices if d["rssi"] >= threshold_val]
            print(f"ESP-NOW: Filtered to {len(discovered_devices)} devices above {threshold_val} dBm")
        except:
            pass
    
    scan_in_progress = False

    # Send device list back to web app
    device_list_response = {
        "type": "devices",
        "list": discovered_devices
    }
    
    try:
        print(f"DEBUG: Sending device list, p.is_connected: {p.is_connected}")
        
        # Split large messages into chunks and send separately
        # 
        # Steps:
        # 1. Convert Python dict to JSON string with json.dumps()
        # 2. Encode the string to bytes with .encode()
        # 3. Split bytes into chunks of 100 bytes (safe for all BLE versions)
        # 4. Send each chunk with small delay to prevent buffer overflow
        # 5. Web app buffers chunks and reassembles complete JSON message
        response_json = json.dumps(device_list_response)
        response_bytes = response_json.encode()
        
        print(f"Response size: {len(response_bytes)} bytes")
        print(f"Response preview: {response_json[:100]}...")
        
        # Use framed sending with header for reliable transmission
        success = send_ble_framed(response_bytes, chunk_size=100)
        
        if success:
            print("Device list sent successfully to web app")
        else:
            print("Failed to send device list")
    except Exception as e:
        print(f"Error sending device list: {e}")

def handle_ble_command(command_str):
    """
    Main command handler for BLE UART commands from web app.
    
    Processes commands from web app and translates them to ESP-NOW messages
    for the playground modules.
    
    Command Flow:
    1. Parse command string from web app ("COMMAND":"RSSI")
    2. Map to ESP-NOW protocol format
    3. Broadcast via ESP-NOW to modules
    4. Send acknowledgment back to web app via BLE
    """
    print(f"BLE command received: {repr(command_str)}")
    
    # Parse command
    command, threshold = parse_web_command(command_str)
    print(f"Parsed: command='{command}', threshold='{threshold}'")
    
    # Handle different commands
    if command == "PING":
        handle_ping_command(threshold)
        
    elif command in COMMAND_MAP:
        # Known ESP-NOW command - send it
        print(f"Processing command: {command}")
        success = send_espnow_command(command, threshold)
        
        if success:
            print(f"✓ Command '{command}' sent successfully")
        else:
            print(f"✗ Command '{command}' failed to send")
        
        # Send acknowledgment back to web app via BLE
        try:
            ack_response = {
                "type": "ack",
                "command": command,
                "status": "sent" if success else "failed",
                "rssi": threshold
            }
            ack_json = json.dumps(ack_response)
            
            # Use framed sending for reliability
            send_ble_framed(ack_json.encode(), chunk_size=100)
            print(f"Sent acknowledgment to web app")
        except Exception as e:
            print(f"Failed to send acknowledgment: {e}")
            
    else:
        # Unknown command
        print(f"Unknown command: {command}")
        try:
            error_response = {
                "type": "error",
                "message": f"Unknown command: {command}",
                "available_commands": list(COMMAND_MAP.keys())
            }
            error_json = json.dumps(error_response)
            send_ble_framed(error_json.encode(), chunk_size=100)
        except Exception as e:
            print(f"Failed to send error response: {e}")

def handle_cmd(chunk):
    """
    BLE UART command handler - processes incoming commands from web app.
    
    HOW THIS WORKS (BLE Peripheral perspective):
    1. Web browser writes data to RX characteristic (6E400002...)
    2. BLE stack triggers IRQ_GATTS_WRITE interrupt
    3. ble_uart.py's _irq() handler calls this callback function
    4. This function receives the raw bytes written by the browser
    
    IMPORTANT PATTERNS:
    - Data arrives as bytes (chunk parameter)
    - Data may arrive in fragments (partial messages)
    - We buffer incomplete messages until newline (\n) received
    - Must decode bytes to string before processing
    
    COMMON ISSUES:
    - If chunk is None/empty, ignore it (connection event, not data)
    - Always check if data is complete before processing
    - Handle decode errors gracefully (invalid UTF-8)
    """
    global _rxbuf
    print(f"DEBUG: handle_cmd called with chunk: {chunk}")
    print(f"DEBUG: p.is_connected: {p.is_connected}")
    print(f"DEBUG: p._write_callback: {p._write_callback}")
    
    if not chunk:
        return
    
    # Buffer overflow protection - prevent memory exhaustion from malformed data
    # If buffer would exceed limit, clear it and start fresh
    # Normal commands should be < 100 bytes, 1KB is very generous
    if len(_rxbuf) + len(chunk) > MAX_BUFFER_SIZE:
        print(f"WARNING: RX buffer overflow ({len(_rxbuf)} + {len(chunk)} > {MAX_BUFFER_SIZE}), clearing")
        _rxbuf = b""
    
    # Buffer incoming data - commands may arrive in multiple chunks
    # Replace \r with \n to normalize line endings (cross-platform compatibility)
    _rxbuf += chunk.replace(b"\r", b"\n")
    
    # Process complete lines (delimited by \n)
    # Commands from web app are terminated with newline
    while b"\n" in _rxbuf:
        line, _, _rxbuf = _rxbuf.partition(b"\n")
        if line.strip():
            try:
                # Decode bytes to string for processing
                command = line.decode().strip()
                print(f"DEBUG: Processing command: {command}")
                handle_ble_command(command)
            except Exception as e:
                print(f"Command handler error: {e}")

# === INITIALIZATION ===
# Buffer for incoming BLE data - commands may arrive fragmented
# MUST be bytes (b""), not string ("")
_rxbuf = b""
MAX_BUFFER_SIZE = 1024  # Max 1KB for command buffer (prevents memory exhaustion)

# Set up BLE command handler (using working pattern)
# This registers our handle_cmd function to be called when data arrives
# The ble_uart.Yell class calls this callback from its IRQ handler
# when the central device (browser) writes to the RX characteristic
p._write_callback = handle_cmd

print("Hub initialization complete!")
print("Waiting for BLE connection...")
print("")
print("=" * 50)
print("SMART PLAYGROUND HUB - AUTONOMOUS MODE")
print("=" * 50)
print("Hub is running standalone - no USB serial required")
print("Connect via BLE from web application")
print("=" * 50)

# === MAIN LOOP (Continuous operation) ===
print("Hub ready for BLE connections and ESP-NOW communication.")
print("")
print("=== ESP-NOW STATUS ===")
print(f"  Broadcast MAC: {BROADCAST_MAC.hex()}")
print(f"  Commands will be sent to modules via ESP-NOW")
print("")
print("=== BLE STATUS ===")
print(f"  Device Name: {HUB_NAME}")
print(f"  Advertising: Active")
print(f"  Waiting for web app connection...")
print("")

# Continuous operational loop
last_status_time = time.time()
last_connection_check = time.time()
connection_timeout = 5.0  # seconds to wait for initial connection

print("Starting continuous operation loop...")
print(f"BLE advertising status: Active")
print(f"Hub name: {HUB_NAME}")
print(f"BLE object: {p}")
print("Hub should now be visible in Bluetooth scan...")

twist.current_mode = 0
twist.show_mode()
twist.start_breathe((255, 0, 255), duration=4000)

# Start advertising - makes this device visible to BLE scanners
# The ble_uart.Yell class handles:
# - Building advertisement packet with device name and service UUIDs
# - Starting GATT server with Nordic UART service
# - Setting up interrupt handlers for connection events
p.advertise()


# === MAIN EVENT LOOP ===
# BLE operates on an interrupt-driven model:
# - Connection events trigger IRQ handlers in ble_uart.py
# - Data writes trigger our handle_cmd() callback
# - This loop handles housekeeping and connection recovery
#
# IMPORTANT: Do NOT block or use long delays here!
# - Blocking prevents BLE interrupts from being processed
# - Keep delays short (100ms max) to maintain responsiveness
# - Heavy processing should be done in callbacks, not here

while True:
    time.sleep(0.05)  # Short sleep to prevent CPU spinning
    twist.update_animations()
    current_time = time.time()
    
    # Monitor BLE connection state
    # p.is_connected is updated by ble_uart.py IRQ handlers:
    # - Set to True on IRQ_CENTRAL_CONNECT
    # - Set to False on IRQ_CENTRAL_DISCONNECT
    if p.is_connected:
        # Connection is active - commands are processed via handle_cmd() callback
        # No action needed here, just update timestamp
        if current_time - last_connection_check > 1.0:
            last_connection_check = current_time
            # Connection maintained - callbacks handle all data processing
            pass
    else:
        # No connection - ensure we're advertising for new connections
        # BLE peripheral should auto-restart advertising after disconnect,
        # but we explicitly restart it here for reliability
        if current_time - last_connection_check > connection_timeout:
            print("Waiting for BLE connection...")
            try:
                twist.start_breathe((255, 0, 255), duration=4000)
                p.advertise()  # Make device discoverable again
                print("Advertising restarted")
            except Exception as e:
                print(f"Error restarting advertising: {e}")
            last_connection_check = current_time
    
    # Periodic status logging (every 60 seconds)
    # Helps with debugging and monitoring hub health
    if current_time - last_status_time >= 60:
        if p.is_connected:
            print(f"Hub status: BLE connected, {len(discovered_devices)} devices known")
        else:
            print("Hub status: BLE disconnected, advertising for connections...")
        last_status_time = current_time




