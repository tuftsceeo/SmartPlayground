"""
MINIMAL ESP-NOW TEST HUB
Tests ONLY ESP-NOW communication (no BLE)
Matches module's proven pattern exactly
"""

import network
import espnow
import time
import json
from ucollections import deque
from machine import Pin

print("=" * 50)
print("MINIMAL ESP-NOW TEST HUB")
print("=" * 50)

# LED for visual feedback
led = Pin(2, Pin.OUT)
led.value(0)

# === WIFI SETUP ===
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()

# Set WiFi channel explicitly (CRITICAL!)
WIFI_CHANNEL = 1
sta.config(channel=WIFI_CHANNEL)
print("WiFi channel set to:", WIFI_CHANNEL)
print("WiFi MAC:", sta.config('mac').hex())

time.sleep_ms(100)

# === ESP-NOW SETUP ===
e = espnow.ESPNow()
e.active(True)

# Add broadcast peer
BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'
e.add_peer(BROADCAST_MAC)
print("Broadcast peer added:", BROADCAST_MAC.hex())

# === MESSAGE BUFFER (like module) ===
msg_buffer = deque((), 50, 2)

# === ESP-NOW IRQ CALLBACK (matches module exactly) ===
def recv_cb(interface):
    global msg_buffer
    while True:
        mac, msg = interface.irecv(0)
        if mac is None:
            return
        try:
            receivedMessage = json.loads(msg)
            print("Received from", mac.hex(), ":", receivedMessage)
            msg_buffer.append((bytes(mac), receivedMessage))
        except Exception as error:
            print("recv_cb error:", error)

e.irq(recv_cb)
print("ESP-NOW IRQ registered")

# === FUNCTION LOOKUP TABLE ===
def handle_device_scan(mac, data):
    """Handle deviceScan responses from modules"""
    print(">>> DEVICE FOUND!")
    print("    MAC:", mac.hex())
    print("    Name:", data.get("value", "Unknown"))
    
    try:
        rssi = e.peers_table[mac][0]
        print("    RSSI:", rssi, "dBm")
    except:
        print("    RSSI: Unknown")
    
    # Flash LED to show we got a response
    led.value(1)
    time.sleep_ms(100)
    led.value(0)

functionLUT = {
    "deviceScan": handle_device_scan,
}

# === HELPER: SEND PING ===
def send_ping(rssi_threshold=-100):
    """Send a ping to all modules"""
    message = {"pingCall": {"RSSI": rssi_threshold, "value": "app"}}
    message_str = json.dumps(message)
    
    print("\n>>> SENDING PING")
    print("    Message:", message)
    print("    Threshold:", rssi_threshold, "dBm")
    
    success = e.send(BROADCAST_MAC, message_str)
    
    if success:
        print("    Result: SUCCESS")
        led.value(1)
        time.sleep_ms(50)
        led.value(0)
    else:
        print("    Result: FAILED")
    
    return success

# === MAIN LOOP (matches module pattern) ===
print("\n" + "=" * 50)
print("STARTING MAIN LOOP")
print("Will send PING every 10 seconds")
print("=" * 50)
print()

last_ping_time = 0
ping_interval = 10.0  # Send ping every 10 seconds

while True:
    time.sleep(0.1)  # 100ms loop interval (like module)
    current_time = time.time()
    
    # Process any buffered messages (like module does)
    if len(msg_buffer) > 0:
        mac, receivedMessage = msg_buffer.popleft()
        
        print(">>> PROCESSING MESSAGE FROM BUFFER")
        
        for key in receivedMessage:
            try:
                # RSSI filtering (like module does)
                try:
                    sender_rssi = e.peers_table[mac][0]
                except (KeyError, IndexError):
                    sender_rssi = -1
                
                threshold = receivedMessage[key]["RSSI"]
                passes = sender_rssi > threshold
                
                print("Msg:", key, "| Sender RSSI:", sender_rssi, 
                      "| Threshold:", threshold, "| Pass:", passes)
                
                if passes:
                    if functionLUT.get(key):
                        print("Calling", key, "handler")
                        functionLUT[key](mac, receivedMessage[key])
                    else:
                        print("No handler for", key)
            except Exception as err:
                print("Processing error:", err)
    
    # Send ping periodically
    if (current_time - last_ping_time) > ping_interval:
        send_ping(rssi_threshold=-100)  # Accept all (strongest filter)
        last_ping_time = current_time
        print("Waiting for responses...")
        print("Buffer size:", len(msg_buffer))
        print()

