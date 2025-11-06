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
from machine import Pin, I2C
from ble_uart import Yell
from twist_iot import TwistIOT
import ssd1306

# Shared I2C bus for Twist and OLED display
i2c = I2C(0, sda=Pin(6), scl=Pin(7), freq=100000)

twist = TwistIOT(i2c)
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

# CRITICAL: Set WiFi channel for ESP-NOW reliability
# Both hub and modules MUST be on the same channel
WIFI_CHANNEL = 1
sta.config(channel=WIFI_CHANNEL)
print("WiFi channel set to:", WIFI_CHANNEL)

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

# === OLED DISPLAY SETUP FOR DEBUGGING ===
try:
    # Use shared I2C bus (already initialized above)
    display = ssd1306.SSD1306_I2C(128, 64, i2c)
    display.fill(0)
    display.text("Hub Ready", 0, 0, 1)
    display.show()
    print("OLED display initialized")
except Exception as err:
    print("OLED init failed:", err)
    display = None

def show_display(line1="", line2="", line3="", line4=""):
    """Update OLED display with up to 4 lines of text"""
    if display is None:
        return
    try:
        display.fill(0)
        if line1: display.text(line1[:16], 0, 0, 1)
        if line2: display.text(line2[:16], 0, 16, 1)
        if line3: display.text(line3[:16], 0, 32, 1)
        if line4: display.text(line4[:16], 0, 48, 1)
        display.show()
    except Exception as err:
        print("Display error:", err)

# === MESSAGE BUFFERS FOR INTERRUPT HANDLERS ===
from ucollections import deque
espnow_msg_buffer = deque((), 50, 2)  # Buffer for ESP-NOW messages
ble_command_buffer = deque((), 10, 2)  # Buffer for BLE commands

# Counters for display (updated in interrupts, displayed in main loop)
espnow_rx_count = 0
espnow_tx_count = 0
last_rx_mac = "none"

def espnow_recv_cb(interface):
    """
    ESP-NOW interrupt callback - buffers incoming messages.
    FAST, NON-BLOCKING: Just buffer and increment counter.
    """
    global espnow_msg_buffer, espnow_rx_count, last_rx_mac
    while True:
        mac, msg = interface.irecv(0)
        if mac is None:
            return
        try:
            espnow_msg_buffer.append((bytes(mac), msg))
            espnow_rx_count += 1
            last_rx_mac = mac.hex()[:12]
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
scan_start_time = 0
scan_rssi_threshold = "all"  # Store current scan threshold

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
        global espnow_tx_count
        # Send via ESP-NOW broadcast
        # IMPORTANT: ESP-NOW send() expects a STRING, not bytes!
        # MicroPython's espnow.send() will handle the encoding internally
        success = espnow_interface.send(BROADCAST_MAC, message_str)
        
        if success:
            espnow_tx_count += 1
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

def start_device_scan(rssi_threshold="all"):
    """
    Initiate device scan - NON-BLOCKING.
    Just sends the ping and sets up state for collecting responses.
    """
    global scan_in_progress, scan_start_time, scan_rssi_threshold, discovered_devices
    
    print("Starting device scan, RSSI:", rssi_threshold)
    scan_in_progress = True
    scan_start_time = time.time()
    scan_rssi_threshold = rssi_threshold
    discovered_devices = []
    
    # Show on display
    show_display("SCAN STARTED",
                "RSSI: " + str(rssi_threshold),
                "Waiting...",
                "")
    
    # Send PING command to modules
    send_espnow_command("PING", rssi_threshold)

def process_espnow_message(mac, msg):
    """
    Process a single ESP-NOW message - NON-BLOCKING.
    Called from main loop for each buffered message.
    """
    global discovered_devices
    
    print("=== PROCESS ESP-NOW MSG ===")
    print("From:", mac.hex())
    print("Scan active:", scan_in_progress)
    
    # Only process deviceScan responses when scan is active
    if not scan_in_progress:
        print("IGNORED: scan not active")
        show_display("MSG IGNORED",
                    "No scan active",
                    "From:" + mac.hex()[:12],
                    "")
        return
    
    try:
        response = json.loads(msg.decode())
        print("Decoded JSON:", response)
        device_scan_data = response.get("deviceScan", None)
        
        if device_scan_data is None:
            print("IGNORED: not deviceScan")
            show_display("MSG IGNORED",
                        "Not deviceScan",
                        str(list(response.keys())[:16]),
                        "")
            return  # Not a deviceScan response, ignore
        
        # Get RSSI from peers table or use default
        try:
            rssi = espnow_interface.peers_table[mac][0]
        except (KeyError, IndexError):
            rssi = -50  # Default if not in peers table
        
        # Build device info
        device_info = {
            "id": device_scan_data.get("value", "M-" + mac.hex()[:6]),
            "rssi": rssi,
            "battery": device_scan_data.get("battery", -1),
            "type": device_scan_data.get("type", "Unknown"),
            "mac": mac.hex()
        }
        
        discovered_devices.append(device_info)
        print("Device found:", device_info["id"], "RSSI:", rssi)
        
        # Update display to show device was found
        show_display("Device Found!",
                    device_info["id"][:16],
                    "RSSI: " + str(rssi),
                    "Count: " + str(len(discovered_devices)))
        
    except Exception as err:
        print("Parse error:", err)

def finish_device_scan():
    """
    Complete device scan and send results - NON-BLOCKING.
    Called from main loop when scan timeout expires.
    """
    global scan_in_progress, discovered_devices
    
    print("=== SCAN TIMEOUT - FINISHING ===")
    print("Devices found:", len(discovered_devices))
    scan_in_progress = False
    
    # Apply RSSI filtering if specified
    if scan_rssi_threshold != "all":
        try:
            threshold_val = int(scan_rssi_threshold)
            discovered_devices = [d for d in discovered_devices if d["rssi"] >= threshold_val]
            print("Filtered to", len(discovered_devices), "devices above", threshold_val, "dBm")
        except:
            pass
    
    # Send device list back to web app
    device_list_response = {
        "type": "devices",
        "list": discovered_devices
    }
    
    try:
        response_json = json.dumps(device_list_response)
        response_bytes = response_json.encode()
        
        print("Sending", len(response_bytes), "bytes to app")
        
        # Use framed sending for reliable transmission
        success = send_ble_framed(response_bytes, chunk_size=100)
        
        if success:
            print("Device list sent to app")
        else:
            print("Failed to send device list")
    except Exception as err:
        print("Error sending device list:", err)

def process_ble_command(command_str):
    """
    Process BLE command - NON-BLOCKING dispatcher.
    Called from main loop, just initiates actions.
    """
    print("BLE command:", command_str)
    
    # Parse command
    command, threshold = parse_web_command(command_str)
    print("Parsed:", command, "threshold:", threshold)
    
    # Handle different commands
    if command == "PING":
        # Initiate device scan (non-blocking)
        start_device_scan(threshold)
        
    elif command in COMMAND_MAP:
        # Send ESP-NOW command (fast, non-blocking)
        print("Sending:", command)
        success = send_espnow_command(command, threshold)
        
        if success:
            print("Command sent")
        else:
            print("Command failed")
        
        # Send quick acknowledgment to web app
        try:
            ack_response = {
                "type": "ack",
                "command": command,
                "status": "sent" if success else "failed",
                "rssi": threshold
            }
            ack_json = json.dumps(ack_response)
            send_ble_framed(ack_json.encode(), chunk_size=100)
        except Exception as err:
            print("Ack failed:", err)
            
    else:
        # Unknown command
        print("Unknown command:", command)
        try:
            error_response = {
                "type": "error",
                "message": "Unknown command: " + command,
                "available_commands": list(COMMAND_MAP.keys())
            }
            error_json = json.dumps(error_response)
            send_ble_framed(error_json.encode(), chunk_size=100)
        except Exception as err:
            print("Error response failed:", err)

def handle_cmd(chunk):
    """
    BLE UART interrupt handler - FAST, NON-BLOCKING.
    Just buffers commands for processing in main loop.
    """
    global _rxbuf, ble_command_buffer
    
    if not chunk:
        return
    
    # Buffer overflow protection
    if len(_rxbuf) + len(chunk) > MAX_BUFFER_SIZE:
        print("RX buffer overflow, clearing")
        _rxbuf = b""
    
    # Buffer incoming data
    _rxbuf += chunk.replace(b"\r", b"\n")
    
    # Extract complete lines and buffer them
    while b"\n" in _rxbuf:
        line, _, _rxbuf = _rxbuf.partition(b"\n")
        if line.strip():
            try:
                command = line.decode().strip()
                ble_command_buffer.append(command)
            except Exception as err:
                print("Decode error:", err)

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


# === MAIN EVENT LOOP (FULLY REACTIVE, NON-BLOCKING) ===
# Following the proven module pattern:
# - Interrupt handlers buffer messages
# - Main loop processes buffers reactively
# - NO blocking operations or long delays
# - System always responsive to interrupts

print("Starting reactive main loop...")
last_connection_check = time.time()
last_status_time = time.time()
last_display_update = time.time()

while True:
    current_time = time.time()
    
    # 1. Process BLE commands from buffer (highest priority)
    if len(ble_command_buffer) > 0:
        command_str = ble_command_buffer.popleft()
        try:
            process_ble_command(command_str)
        except Exception as err:
            print("BLE command error:", err)
    
    # 2. Process ESP-NOW messages from buffer
    if len(espnow_msg_buffer) > 0:
        mac, msg = espnow_msg_buffer.popleft()
        try:
            process_espnow_message(mac, msg)
        except Exception as err:
            print("ESP-NOW message error:", err)
    
    # 3. Check scan timeout (non-blocking state check)
    if scan_in_progress:
        if (current_time - scan_start_time) > device_scan_timeout:
            try:
                finish_device_scan()
            except Exception as err:
                print("Scan finish error:", err)
                scan_in_progress = False
    
    # 4. Update animations (fast, non-blocking)
    try:
        twist.update_animations()
    except Exception as err:
        print("Animation error:", err)
    
    # 5. Monitor BLE connection periodically
    if not p.is_connected:
        if current_time - last_connection_check > 5.0:
            try:
                twist.start_breathe((255, 0, 255), duration=4000)
                p.advertise()
            except Exception as err:
                print("Advertise error:", err)
            last_connection_check = current_time
    
    # 6. Update display periodically (every 0.5 seconds) if not scanning
    if not scan_in_progress and (current_time - last_display_update) > 0.5:
        try:
            show_display("Hub Status",
                        "RX:" + str(espnow_rx_count) + " TX:" + str(espnow_tx_count),
                        "Buf:" + str(len(espnow_msg_buffer)),
                        "BLE:" + ("Y" if p.is_connected else "N"))
            last_display_update = current_time
        except Exception as err:
            print("Display update error:", err)
    
    # 7. Periodic status logging (every 60 seconds)
    if current_time - last_status_time >= 60:
        if p.is_connected:
            print("Hub: BLE connected,", len(discovered_devices), "devices")
        else:
            print("Hub: BLE disconnected, advertising")
        last_status_time = current_time
    
    # NO SLEEP - loop immediately for maximum responsiveness
    # Interrupts will fill buffers, main loop processes them as fast as possible




