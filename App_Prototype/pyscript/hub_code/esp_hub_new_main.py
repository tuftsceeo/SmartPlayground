# ESP32C6 Hub - Phase 1 Test Implementation (Isolated Mode)
# BLE UART service for web app integration with ESP-NOW placeholders
# Based on BLE_CEEO.py, esp_hub_ble_main.py, and BLE_Integration_Plan.md
#
# AUTONOMOUS OPERATION: This hub runs completely standalone
# - No USB serial input required
# - Automatically reconnects on BLE disconnection
# - Continuous operation without user intervention

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
    Examples:
    - "PING":"all" -> scan all devices
    - "COLOR BASED GROUP":"-60" -> send to devices with RSSI >= -60
    - "BATTERY CHECK":"all" -> check battery on all devices
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
        p.send(json.dumps(device_list_response))
        print("Sent device list to web app")
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
        # Send acknowledgment
        try:
            p.send('{"type":"ack","command":"BATTERY CHECK","status":"sent"}')
        except:
            pass
            
    elif command in ["COLOR BASED GROUP", "NUMBER BASED GROUP", "RAINBOW", "TURN OFF"]:
        print(f"Game command: {command} (PLACEHOLDER)")
        success = send_espnow_command(command, threshold)
        
        # Send acknowledgment
        try:
            ack_msg = '{"type":"ack","command":"' + command + '","status":"' + ("sent" if success else "failed") + '"}'
            p.send(ack_msg)
        except:
            pass
            
    else:
        print(f"Unknown command: {command}")
        # Send error response
        try:
            error_msg = '{"type":"error","message":"Unknown command: ' + command + '"}'
            p.send(error_msg)
        except:
            pass

def handle_cmd(chunk):
    """
    BLE UART command handler - processes incoming commands from web app
    """
    global _rxbuf
    print(f"DEBUG: handle_cmd called with chunk: {chunk}")
    print(f"DEBUG: p.is_connected: {p.is_connected}")
    print(f"DEBUG: p._write_callback: {p._write_callback}")
    
    if not chunk:
        return
    
    # Add to buffer
    _rxbuf += chunk.replace(b"\r", b"\n")
    
    # Process complete lines
    while b"\n" in _rxbuf:
        line, _, _rxbuf = _rxbuf.partition(b"\n")
        if line.strip():
            try:
                command = line.decode().strip()
                print(f"DEBUG: Processing command: {command}")
                handle_ble_command(command)
            except Exception as e:
                print(f"Command handler error: {e}")

# === INITIALIZATION ===
_rxbuf = b""

# Set up BLE command handler (using working pattern)
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

# Start advertising
p.advertise()

while True:
    time.sleep(0.1)  # Check more frequently
    
    current_time = time.time()
    
    # Check for BLE connection
    if p.is_connected:
        # Connection is active - process commands
        if current_time - last_connection_check > 1.0:  # Check every second
            last_connection_check = current_time
            # Connection is maintained, continue processing
            pass
    else:
        # No connection - restart advertising if needed
        if current_time - last_connection_check > connection_timeout:
            print("Waiting for BLE connection...")
            # Check if we need to restart advertising
            try:
                p.advertise()  # Restart advertising
                print("Advertising restarted")
            except Exception as e:
                print(f"Error restarting advertising: {e}")
            last_connection_check = current_time
    
    # Periodic status updates (every 60 seconds)
    if current_time - last_status_time >= 60:
        if p.is_connected:
            print(f"Hub status: BLE connected, {len(discovered_devices)} devices known (mock data)")
        else:
            print("Hub status: BLE disconnected, advertising for connections...")
        last_status_time = current_time
