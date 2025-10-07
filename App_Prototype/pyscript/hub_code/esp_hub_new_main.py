# ESP32C6 Hub - Phase 1 Test Implementation (Isolated Mode)
# BLE UART service for web app integration with ESP-NOW placeholders
# Based on BLE_CEEO.py, esp_hub_ble_main.py, and BLE_Integration_Plan.md
#
# AUTONOMOUS OPERATION: This hub runs completely standalone
# - No USB serial input required
# - Automatically reconnects on BLE disconnection
# - Continuous operation without user intervention
#
# =============================================================================
# BLE & GATT CONCEPTS FOR BEGINNERS:
# =============================================================================
# 
# BLE (Bluetooth Low Energy):
# - Wireless protocol designed for low power consumption
# - Devices advertise their presence and services
# - Central device (web browser) connects to Peripheral device (this ESP32)
#
# GATT (Generic Attribute Profile):
# - Defines how BLE devices exchange data
# - Organizes data into Services → Characteristics → Values
# - Like a file system: Service = folder, Characteristic = file
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

# === CONFIGURATION ===
HUB_NAME = "SPHub"
WIFI_CHANNEL = 1
BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'  # Broadcast to all modules

# Status LED for visual feedback
led = Pin(2, Pin.OUT)  # Built-in LED
led.value(0)

# === ESP-NOW SETUP (PLACEHOLDER) ===
print("ESP-NOW setup (placeholder - no modules connected)")
# TODO: Uncomment when ESP-NOW modules are available
# import espnow
# wlan = network.WLAN(network.STA_IF)
# wlan.active(True)
# wlan.config(channel=WIFI_CHANNEL)
# try:
#     wlan.disconnect()
# except:
#     pass
# espnow_interface = espnow.ESPNow()
# espnow_interface.active(True)
# espnow_interface.add_peer(BROADCAST_MAC)
# print("ESP-NOW initialized with broadcast peer")

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
mock_devices = [
    {"id": "M-001", "rssi": -45, "battery": 85, "type": "module", "mac": "aa:bb:cc:dd:ee:01"},
    {"id": "M-002", "rssi": -60, "battery": 92, "type": "module", "mac": "aa:bb:cc:dd:ee:02"},
    {"id": "M-003", "rssi": -75, "battery": 78, "type": "module", "mac": "aa:bb:cc:dd:ee:03"}
]

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

def send_espnow_command(command, rssi_threshold="all"):
    """
    Send command to ESP-NOW modules with RSSI filtering (PLACEHOLDER)
    """
    global scan_in_progress, discovered_devices
    
    print(f"ESP-NOW PLACEHOLDER: Would send command '{command}' with threshold: {rssi_threshold}")
    
    # Create command message
    if rssi_threshold == "all":
        message = {"command": command, "rssi_threshold": None}
    else:
        try:
            rssi_val = int(rssi_threshold)
            message = {"command": command, "rssi_threshold": rssi_val}
        except:
            message = {"command": command, "rssi_threshold": None}
    
    message_str = json.dumps(message)
    print(f"ESP-NOW PLACEHOLDER: Message would be: {message_str}")
    
    # TODO: Uncomment when ESP-NOW modules are available
    # try:
    #     success = espnow_interface.send(BROADCAST_MAC, message_str.encode())
    #     print(f"ESP-NOW send result: {success}")
    #     
    #     # Flash LED to indicate transmission
    #     led.value(1)
    #     time.sleep_ms(50)
    #     led.value(0)
    #     
    #     return success
    # except Exception as e:
    #     print(f"ESP-NOW send error: {e}")
    #     return False
    
    # Flash LED to simulate transmission
    led.value(1)
    time.sleep_ms(50)
    led.value(0)
    
    print("ESP-NOW PLACEHOLDER: Simulating successful transmission")
    return True

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
    Handle PING command - scan for nearby modules (PLACEHOLDER)
    """
    global scan_in_progress, discovered_devices
    
    print("Starting device scan (PLACEHOLDER)...")
    scan_in_progress = True
    discovered_devices = []
    
    # Send PING command to modules (placeholder)
    send_espnow_command("PING", rssi_threshold)
    
    # TODO: Uncomment when ESP-NOW modules are available
    # # Wait for responses
    # start_time = time.time()
    # while time.time() - start_time < device_scan_timeout:
    #     # Check for ESP-NOW responses
    #     try:
    #         mac, msg = espnow_interface.irecv(0)  # Non-blocking
    #         if mac is not None:
    #             try:
    #                 response = json.loads(msg.decode())
    #                 print(f"Device response from {mac.hex()}: {response}")
    #                 
    #                 # Add to discovered devices
    #                 device_info = {
    #                     "id": response.get("id", f"M-{mac.hex()[:6]}"),
    #                     "rssi": response.get("rssi", -100),
    #                     "battery": response.get("battery", 50),
    #                     "type": response.get("type", "module"),
    #                     "mac": mac.hex()
    #                 }
    #                 discovered_devices.append(device_info)
    #                 print(f"Added device: {device_info}")
    #                 
    #             except Exception as e:
    #                 print(f"Response parse error: {e}")
    #     except:
    #         pass
    #     
    #     time.sleep_ms(100)
    
    # PLACEHOLDER: Use mock devices for testing
    print("ESP-NOW PLACEHOLDER: Using mock device data")
    discovered_devices = mock_devices.copy()
    
    # Apply RSSI filtering if specified
    if rssi_threshold != "all":
        try:
            threshold_val = int(rssi_threshold)
            discovered_devices = [d for d in discovered_devices if d["rssi"] >= threshold_val]
            print(f"ESP-NOW PLACEHOLDER: Filtered to {len(discovered_devices)} devices above {threshold_val} dBm")
        except:
            pass
    
    scan_in_progress = False
    print(f"Device scan complete. Found {len(discovered_devices)} devices")
    
    # Send device list back to web app
    device_list_response = {
        "type": "devices",
        "list": discovered_devices
    }
    
    try:
        print(f"DEBUG: Sending device list, p.is_connected: {p.is_connected}")
        
        # CRITICAL: BLE UART transmission with chunking for large messages
        # 
        # Problem: BLE MTU limits (20-244 bytes) cause large messages to be truncated
        # Solution: Split message into chunks and send separately
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
    Main command handler for BLE UART commands from web app
    """
    print(f"BLE command received: {repr(command_str)}")
    
    # Parse command
    command, threshold = parse_web_command(command_str)
    print(f"Parsed: command='{command}', threshold='{threshold}'")
    
    # Handle different commands
    if command == "PING":
        handle_ping_command(threshold)
        
    elif command == "BATTERY CHECK":
        print("Battery check requested (PLACEHOLDER)")
        send_espnow_command("BATTERY CHECK", threshold)
        # Send acknowledgment - must encode to bytes for BLE UART
        try:
            p.send(b'{"type":"ack","command":"BATTERY CHECK","status":"sent"}')
        except:
            pass
            
    elif command in ["COLOR BASED GROUP", "NUMBER BASED GROUP", "RAINBOW", "TURN OFF"]:
        print(f"Game command: {command} (PLACEHOLDER)")
        success = send_espnow_command(command, threshold)
        
        # Send acknowledgment - must encode to bytes for BLE UART
        try:
            ack_msg = '{"type":"ack","command":"' + command + '","status":"' + ("sent" if success else "failed") + '"}'
            p.send(ack_msg.encode())
        except:
            pass
            
    else:
        print(f"Unknown command: {command}")
        # Send error response - must encode to bytes for BLE UART
        try:
            error_msg = '{"type":"error","message":"Unknown command: ' + command + '"}'
            p.send(error_msg.encode())
        except:
            pass

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
print("Hub ready for BLE connections (ISOLATED MODE).")
print("Supported commands:")
print("  - PING: Scan for nearby modules (returns mock data)")
print("  - BATTERY CHECK: Check module batteries (placeholder)")
print("  - COLOR BASED GROUP: Start color-based game (placeholder)")
print("  - NUMBER BASED GROUP: Start number-based game (placeholder)")
print("  - RAINBOW: Rainbow effect (placeholder)")
print("  - TURN OFF: Turn off modules (placeholder)")
print("")
print("NOTE: ESP-NOW communication is disabled (no modules connected)")
print("All commands will be simulated with LED feedback")
print("Hub running autonomously - no USB serial input required")
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
    time.sleep(0.1)  # Short sleep to prevent CPU spinning
    
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
                p.advertise()  # Make device discoverable again
                print("Advertising restarted")
            except Exception as e:
                print(f"Error restarting advertising: {e}")
            last_connection_check = current_time
    
    # Periodic status logging (every 60 seconds)
    # Helps with debugging and monitoring hub health
    if current_time - last_status_time >= 60:
        if p.is_connected:
            print(f"Hub status: BLE connected, {len(discovered_devices)} devices known (mock data)")
        else:
            print("Hub status: BLE disconnected, advertising for connections...")
        last_status_time = current_time
