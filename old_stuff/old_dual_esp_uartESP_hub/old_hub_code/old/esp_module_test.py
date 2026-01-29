# ESP32C6 Module Test - Simulates playground equipment modules
# Responds to ESP-NOW commands from the hub

import network
import espnow
import time
import json
import random
from machine import Pin

# === MODULE CONFIGURATION ===
MODULE_ID = f"M-{random.randint(100000, 999999)}"  # Random module ID
WIFI_CHANNEL = 1
HUB_MAC = b'\xff\xff\xff\xff\xff\xff'  # Broadcast MAC for hub

# Status LED
led = Pin(2, Pin.OUT)
led.value(0)

# === ESP-NOW SETUP ===
print(f"Initializing module {MODULE_ID}...")
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(channel=WIFI_CHANNEL)
try:
    wlan.disconnect()
except:
    pass

espnow_interface = espnow.ESPNow()
espnow_interface.active(True)
espnow_interface.add_peer(HUB_MAC)
print(f"Module {MODULE_ID} ready")

# === MODULE STATE ===
battery_level = random.randint(60, 100)  # Random battery level
current_rssi = random.randint(-80, -40)  # Simulated RSSI
is_active = False

def send_response(response_data):
    """Send response back to hub"""
    try:
        response_str = json.dumps(response_data)
        success = espnow_interface.send(HUB_MAC, response_str.encode())
        print(f"Sent response: {response_data} (success: {success})")
        
        # Flash LED to indicate transmission
        led.value(1)
        time.sleep_ms(20)
        led.value(0)
        
        return success
    except Exception as e:
        print(f"Response send error: {e}")
        return False

def handle_ping_command(rssi_threshold):
    """Handle PING command from hub"""
    print(f"PING received with threshold: {rssi_threshold}")
    
    # Check if we should respond based on RSSI threshold
    if rssi_threshold is None or current_rssi >= rssi_threshold:
        response = {
            "id": MODULE_ID,
            "rssi": current_rssi,
            "battery": battery_level,
            "type": "module",
            "status": "ready"
        }
        send_response(response)
        print(f"Responded to PING with RSSI {current_rssi}")
    else:
        print(f"Ignoring PING - RSSI {current_rssi} below threshold {rssi_threshold}")

def handle_battery_check():
    """Handle battery check command"""
    print("Battery check requested")
    response = {
        "id": MODULE_ID,
        "battery": battery_level,
        "type": "battery_response"
    }
    send_response(response)
    print(f"Battery level: {battery_level}%")

def handle_game_command(command):
    """Handle game commands"""
    print(f"Game command received: {command}")
    
    if command == "COLOR BASED GROUP":
        print("Starting color-based game")
        # Simulate game activity
        for i in range(3):
            led.value(1)
            time.sleep_ms(200)
            led.value(0)
            time.sleep_ms(200)
        is_active = True
        
    elif command == "NUMBER BASED GROUP":
        print("Starting number-based game")
        # Simulate game activity
        for i in range(5):
            led.value(1)
            time.sleep_ms(100)
            led.value(0)
            time.sleep_ms(100)
        is_active = True
        
    elif command == "RAINBOW":
        print("Starting rainbow effect")
        # Simulate rainbow
        for i in range(10):
            led.value(1)
            time.sleep_ms(50)
            led.value(0)
            time.sleep_ms(50)
        is_active = True
        
    elif command == "TURN OFF":
        print("Turning off")
        led.value(0)
        is_active = False
        
    # Send acknowledgment
    ack_response = {
        "id": MODULE_ID,
        "command": command,
        "status": "executed",
        "type": "ack"
    }
    send_response(ack_response)

def process_command(command_data):
    """Process incoming command from hub"""
    try:
        command = command_data.get("command")
        rssi_threshold = command_data.get("rssi_threshold")
        
        print(f"Processing command: {command} (threshold: {rssi_threshold})")
        
        if command == "PING":
            handle_ping_command(rssi_threshold)
        elif command == "BATTERY CHECK":
            handle_battery_check()
        elif command in ["COLOR BASED GROUP", "NUMBER BASED GROUP", "RAINBOW", "TURN OFF"]:
            handle_game_command(command)
        else:
            print(f"Unknown command: {command}")
            
    except Exception as e:
        print(f"Command processing error: {e}")

# === MAIN LOOP ===
print(f"Module {MODULE_ID} starting main loop...")
print("Waiting for commands from hub...")

try:
    while True:
        # Check for incoming ESP-NOW messages
        try:
            mac, msg = espnow_interface.irecv(0)  # Non-blocking
            if mac is not None:
                try:
                    command_data = json.loads(msg.decode())
                    print(f"Received command from {mac.hex()}: {command_data}")
                    process_command(command_data)
                except Exception as e:
                    print(f"Message parse error: {e}")
        except:
            pass
        
        # Simulate battery drain over time
        if time.time() % 60 == 0:  # Every minute
            battery_level = max(10, battery_level - random.randint(0, 2))
            current_rssi = random.randint(-80, -40)  # Simulate RSSI variation
            print(f"Module {MODULE_ID}: Battery {battery_level}%, RSSI {current_rssi}")
        
        time.sleep_ms(100)
        
except KeyboardInterrupt:
    print(f"Module {MODULE_ID} shutting down...")
    espnow_interface.active(False)
    wlan.active(False)
    print("Module stopped")
except Exception as e:
    print(f"Module error: {e}")
    import traceback
    traceback.print_exc()
