# ESP32C6 Hub - BLE to ESP-NOW bridge for Smart Playground
# Uses Nordic UART Service for BLE communication with web app
# Coordinates ESP-NOW messages to/from playground modules

import network
import time
import json
import random
from machine import Pin, I2C
from ble_uart import Yell
from twist_iot import TwistIOT
import ssd1306
import espnow
from ucollections import deque

# === GLOBAL MESSAGE BUFFERS (Required for interrupt handlers) ===
espnow_msg_buffer = deque((), 50, 2)
ble_command_buffer = deque((), 10, 2)
_rxbuf = b""
MAX_BUFFER_SIZE = 1024

# === INTERRUPT HANDLERS (MUST be global functions) ===
def espnow_recv_cb(interface):
    """ESP-NOW receive interrupt - buffers incoming messages"""
    global espnow_msg_buffer
    while True:
        mac, msg = interface.irecv(0)
        if mac is None:
            return
        try:
            receivedMessage = json.loads(msg)
            print("Received from", mac.hex(), ":", receivedMessage)
            espnow_msg_buffer.append((bytes(mac), receivedMessage))
        except Exception as error:
            print("recv_cb error:", error)

def handle_cmd(chunk):
    """BLE UART receive interrupt - buffers incoming commands"""
    global _rxbuf, ble_command_buffer
    
    if not chunk:
        return
    
    if len(_rxbuf) + len(chunk) > MAX_BUFFER_SIZE:
        print("RX buffer overflow, clearing")
        _rxbuf = b""
    
    _rxbuf += chunk.replace(b"\r", b"\n")
    
    while b"\n" in _rxbuf:
        line, _, _rxbuf = _rxbuf.partition(b"\n")
        if line.strip():
            try:
                command = line.decode().strip()
                ble_command_buffer.append(command)
            except Exception as err:
                print("Decode error:", err)


# === HUB CLASS ===
class Hub:
    """Smart Playground Hub - manages BLE/ESP-NOW communication"""
    
    def __init__(self, name="SPHub"):
        self.name = name
        self.BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'
        self.WIFI_CHANNEL = 1
        
        # Hardware
        self.led = Pin(2, Pin.OUT)
        self.led.value(0)
        self.i2c = I2C(0, sda=Pin(6), scl=Pin(7), freq=100000)
        
        # Peripherals
        self.twist = self._setup_twist()
        self.display = self._setup_display()
        self.espnow_interface = self._setup_espnow()
        self.ble = self._setup_ble()
        
        # Scan state
        self.scan_in_progress = False
        self.scan_start_time = 0
        self.scan_rssi_threshold = "all"
        self.discovered_devices = []
        self.scan_ping_counter = 0
        self.last_ping_time = 0
        self.ble_paused = False
        
        # Scan configuration
        self.device_scan_timeout = 5.0
        self.scan_redundancy_count = 3  # Send multiple PINGs to overcome reception issues
        self.scan_redundancy_delay = 1.0
        
        # Command mappings
        self.COMMAND_MAP = {
            "Play": "updateGame",
            "Pause": "lightOff",
            "Win": "rainbow",
            "Color Game": "updateGame",
            "Number Game": "updateGame",
            "Off": "deepSleep",
            "PING": "pingCall",
        }
        
        self.GAME_VALUES = {
            "Play": 0,
            "Color Game": 1,
            "Number Game": 2,
        }
        
        # Function lookup table for ESP-NOW message routing
        self.functionLUT = {
            "deviceScan": self.handle_device_scan,
        }
    
    def _setup_twist(self):
        """Initialize Twist knob with LED modes"""
        twist = TwistIOT(i2c_driver=self.i2c)
        twist.setup_modes([
            ("Off", 0, 0, 0),
            ("Waiting", 255, 0, 255),
            ("Paired", 0, 255, 0),
            ("Devices", 0, 128, 255),
        ])
        return twist
    
    def _setup_display(self):
        """Initialize OLED display"""
        try:
            display = ssd1306.SSD1306_I2C(128, 64, self.i2c)
            display.fill(0)
            display.text("Hub Ready", 0, 0, 1)
            display.show()
            print("OLED display initialized")
            return display
        except Exception as err:
            print("OLED init failed:", err)
            return None
    
    def _setup_espnow(self):
        """Initialize ESP-NOW on specified WiFi channel"""
        print("Initializing ESP-NOW...")
        
        sta = network.WLAN(network.WLAN.IF_STA)
        sta.active(True)
        sta.disconnect()
        sta.config(channel=self.WIFI_CHANNEL)
        print("WiFi channel set to:", self.WIFI_CHANNEL)
        
        time.sleep_ms(100)
        
        e = espnow.ESPNow()
        e.active(True)
        e.add_peer(self.BROADCAST_MAC)
        
        print(f"ESP-NOW initialized, broadcast: {self.BROADCAST_MAC.hex()}")
        return e
    
    def _setup_ble(self):
        """Initialize BLE UART service"""
        print("Initializing BLE UART service...")
        ble = Yell(self.name, verbose=True)
        print(f"BLE advertising as '{self.name}'")
        return ble
    
    def show_display(self, line1="", line2="", line3="", line4=""):
        """Update OLED with up to 4 lines of text"""
        if self.display is None:
            return
        try:
            self.display.fill(0)
            if line1: self.display.text(line1[:16], 0, 0, 1)
            if line2: self.display.text(line2[:16], 0, 16, 1)
            if line3: self.display.text(line3[:16], 0, 32, 1)
            if line4: self.display.text(line4[:16], 0, 48, 1)
            self.display.show()
        except Exception as err:
            print("Display error:", err)
    
    def parse_web_command(self, command_str):
        """Parse command format: "command":"rssi_threshold" """
        try:
            command_str = command_str.strip()
            print(f"Parsing command: {repr(command_str)}")
            
            if command_str.startswith('"') and command_str.endswith('"'):
                inner = command_str[1:-1]
                if '":"' in inner:
                    command, threshold = inner.split('":"', 1)
                    return command, threshold
            elif '":"' in command_str:
                command, threshold = command_str.split('":"', 1)
                return command, threshold
            else:
                return command_str, "all"
                
        except Exception as e:
            print(f"Command parse error: {e}")
            return command_str, "all"
    
    def rssi_threshold_to_int(self, rssi_threshold):
        """Convert RSSI threshold to integer (-100 for 'all')"""
        if rssi_threshold == "all":
            return -100
        try:
            return int(rssi_threshold)
        except:
            print(f"Invalid RSSI threshold: {rssi_threshold}, defaulting to -100")
            return -100
    
    def send_espnow_command(self, command, rssi_threshold="all"):
        """Send command to modules via ESP-NOW broadcast"""
        if command not in self.COMMAND_MAP:
            print(f"Unknown command: {command}")
            return False
        
        espnow_command = self.COMMAND_MAP[command]
        rssi_value = self.rssi_threshold_to_int(rssi_threshold)
        
        # Determine command value
        if espnow_command == "updateGame":
            value = self.GAME_VALUES.get(command, 0)
        elif espnow_command == "pingCall":
            value = "app"
        else:
            value = 0
        
        # Build protocol message
        message = {
            espnow_command: {
                "RSSI": rssi_value,
                "value": value
            }
        }
        
        message_str = json.dumps(message)
        print(f"ESP-NOW: Sending {espnow_command} (RSSI: {rssi_value})")
        
        try:
            success = self.espnow_interface.send(self.BROADCAST_MAC, message_str)
            print(f"  Send() returned: {success}")
            
            if success:
                # Flash LED to indicate transmission
                self.led.value(1)
                time.sleep_ms(50)
                self.led.value(0)
            
            return success
            
        except Exception as e:
            print(f"ESP-NOW send error: {e}")
            return False
    
    def send_ble_framed(self, data_bytes, chunk_size=100):
        """Send data via BLE with message framing: MSG:<length>|<payload>"""
        if self.ble_paused:
            print("Cannot send: BLE paused during ESP-NOW scan")
            return False
        
        if not self.ble.is_connected:
            print("Cannot send: BLE not connected")
            return False
        
        payload_length = len(data_bytes)
        header = f"MSG:{payload_length}|".encode()
        
        # Send header
        try:
            self.ble.send(header)
            print(f"Sent header: {header.decode()} ({len(header)} bytes)")
            time.sleep_ms(20)
        except Exception as e:
            print(f"Error sending header: {e}")
            return False
        
        # Send payload in chunks
        num_chunks = (payload_length + chunk_size - 1) // chunk_size
        print(f"Sending payload: {payload_length} bytes in {num_chunks} chunks")
        
        for i in range(0, payload_length, chunk_size):
            chunk = data_bytes[i:i+chunk_size]
            chunk_num = i // chunk_size + 1
            
            try:
                self.ble.send(chunk)
                print(f"Sent chunk {chunk_num}/{num_chunks}: {len(chunk)} bytes")
                time.sleep_ms(20)
            except Exception as e:
                print(f"Error sending chunk {chunk_num}: {e}")
                return False
        
        print(f"Framed message sent: {len(header)}B header + {payload_length}B payload")
        return True
    
    def start_device_scan(self, rssi_threshold="all"):
        """Start device scan with redundant PINGs"""
        global espnow_msg_buffer
        
        # Prevent overlapping scans
        if self.scan_in_progress:
            print("WARNING: Scan already in progress! Ignoring duplicate request.")
            return
        
        # Force BLE resume if stuck from previous scan
        if self.ble_paused:
            print("WARNING: BLE was stuck paused! Forcing resume before new scan.")
            self.ble_paused = False
            time.sleep_ms(50)
        
        scan_start_timestamp = time.ticks_ms()
        print(f"[T+{scan_start_timestamp}ms] === STARTING REDUNDANT DEVICE SCAN ===")
        print("RSSI threshold:", rssi_threshold)
        print("Will send", self.scan_redundancy_count, "PINGs at", self.scan_redundancy_delay, "s intervals")
        
        # Stop BLE advertising to free radio for ESP-NOW
        try:
            print("Stopping BLE advertising to free radio for ESP-NOW...")
            self.ble.stop_advertising()
            time.sleep_ms(100)
            print("BLE advertising stopped")
        except Exception as e:
            print("Warning: Could not stop BLE advertising:", e)
        
        # Clear stale messages
        old_buffer_size = len(espnow_msg_buffer)
        if old_buffer_size > 0:
            print(f"Clearing {old_buffer_size} stale ESP-NOW messages from buffer")
            espnow_msg_buffer.clear()
        
        # Initialize scan state
        self.scan_in_progress = True
        self.scan_start_time = time.time()
        self.scan_rssi_threshold = rssi_threshold
        self.discovered_devices = []
        self.ble_paused = True
        self.scan_ping_counter = 0
        self.last_ping_time = 0
        
        self.show_display("REDUNDANT SCAN",
                         "RSSI: " + str(rssi_threshold),
                         "BLE stopped",
                         "ESP-NOW active")
        
        # Send first PING immediately
        self.send_espnow_command("PING", rssi_threshold)
        self.scan_ping_counter = 1
        self.last_ping_time = time.time()
        print(f"Sent PING 1/{self.scan_redundancy_count}")
        print("Waiting for module responses (ESP-NOW IRQ active)...")
    
    def handle_device_scan(self, mac, data):
        """Process deviceScan responses from modules"""
        if not self.scan_in_progress:
            print("deviceScan received but no scan active (ignored)")
            return
        
        try:
            # Get RSSI from peers table
            try:
                rssi = self.espnow_interface.peers_table[mac][0]
            except (KeyError, IndexError):
                rssi = -50
            
            mac_hex = mac.hex()
            
            # Deduplicate by MAC, keep strongest RSSI
            existing_device = None
            for device in self.discovered_devices:
                if device["mac"] == mac_hex:
                    existing_device = device
                    break
            
            if existing_device:
                # Update RSSI if stronger
                if rssi > existing_device["rssi"]:
                    print(f"Device {existing_device['id']} updated: RSSI {existing_device['rssi']} -> {rssi}")
                    existing_device["rssi"] = rssi
                else:
                    print(f"Device {existing_device['id']} duplicate response (RSSI {rssi}, keeping {existing_device['rssi']})")
            else:
                # New device
                device_info = {
                    "id": data.get("value", "M-" + mac_hex[:6]),
                    "rssi": rssi,
                    "battery": data.get("battery", -1),
                    "type": data.get("type", "Unknown"),
                    "mac": mac_hex
                }
                self.discovered_devices.append(device_info)
                print("NEW device found:", device_info["id"], "RSSI:", rssi)
            
            # Update display with unique device count
            unique_count = len(self.discovered_devices)
            self.show_display("Device Response",
                            str(unique_count) + " unique",
                            "RSSI: " + str(rssi),
                            "Ping: " + str(self.scan_ping_counter))
            
        except Exception as err:
            print("handle_device_scan error:", err)
    
    def finish_device_scan(self):
        """Complete scan and send results to app"""
        scan_finish_timestamp = time.ticks_ms()
        print(f"\n[T+{scan_finish_timestamp}ms] === SCAN COMPLETE - FINISHING ===")
        print(f"Sent {self.scan_ping_counter}/{self.scan_redundancy_count} redundant PINGs")
        print(f"Unique devices found: {len(self.discovered_devices)}")
        
        if len(self.discovered_devices) > 0:
            for d in self.discovered_devices:
                print(f"  - {d['id']} (MAC: {d['mac']}, RSSI: {d['rssi']})")
        
        self.scan_in_progress = False
        
        # Resume BLE advertising
        self.ble_paused = False
        print("Resuming BLE advertising...")
        try:
            self.ble.advertise()
            time.sleep_ms(100)
            print("BLE advertising resumed")
        except Exception as e:
            print("Warning: Could not resume BLE advertising:", e)
        
        # Apply RSSI filtering
        if self.scan_rssi_threshold != "all":
            try:
                threshold_val = int(self.scan_rssi_threshold)
                self.discovered_devices = [d for d in self.discovered_devices if d["rssi"] >= threshold_val]
                print("Filtered to", len(self.discovered_devices), "devices above", threshold_val, "dBm")
            except:
                pass
        
        # Send device list to app
        device_list_response = {
            "type": "devices",
            "list": self.discovered_devices
        }
        
        try:
            response_json = json.dumps(device_list_response)
            response_bytes = response_json.encode()
            
            print("Sending", len(response_bytes), "bytes to app via BLE")
            
            success = self.send_ble_framed(response_bytes, chunk_size=100)
            
            if success:
                print("Device list sent to app")
            else:
                print("Failed to send device list")
        except Exception as err:
            print("Error sending device list:", err)
    
    def process_ble_command(self, command_str):
        """Process BLE command from buffer"""
        print("BLE command:", command_str)
        
        command, threshold = self.parse_web_command(command_str)
        print("Parsed:", command, "threshold:", threshold)
        
        if command == "PING":
            self.start_device_scan(threshold)
            
        elif command in self.COMMAND_MAP:
            print("Sending:", command)
            success = self.send_espnow_command(command, threshold)
            
            if success:
                print("Command sent")
            else:
                print("Command failed")
            
            # Send acknowledgment to app
            try:
                ack_response = {
                    "type": "ack",
                    "command": command,
                    "status": "sent" if success else "failed",
                    "rssi": threshold
                }
                ack_json = json.dumps(ack_response)
                self.send_ble_framed(ack_json.encode(), chunk_size=100)
            except Exception as err:
                print("Ack failed:", err)
                
        else:
            print("Unknown command:", command)
            try:
                error_response = {
                    "type": "error",
                    "message": "Unknown command: " + command,
                    "available_commands": list(self.COMMAND_MAP.keys())
                }
                error_json = json.dumps(error_response)
                self.send_ble_framed(error_json.encode(), chunk_size=100)
            except Exception as err:
                print("Error response failed:", err)
    
    def check_scan_progress(self, current_time):
        """Check scan timeout and send redundant PINGs"""
        elapsed = current_time - self.scan_start_time
        
        # Send additional redundant PINGs
        if self.scan_ping_counter < self.scan_redundancy_count:
            time_since_last_ping = current_time - self.last_ping_time
            if time_since_last_ping >= self.scan_redundancy_delay:
                try:
                    self.send_espnow_command("PING", self.scan_rssi_threshold)
                    self.scan_ping_counter += 1
                    self.last_ping_time = current_time
                    print(f"Sent redundant PING {self.scan_ping_counter}/{self.scan_redundancy_count}")
                except Exception as err:
                    print("Redundant PING error:", err)
        
        # Watchdog: force reset if scan stuck >10s
        if elapsed > (self.device_scan_timeout * 2):
            print(f"!!! WATCHDOG: Scan stuck for {elapsed:.1f}s! Force resetting state...")
            self.scan_in_progress = False
            self.ble_paused = False
            espnow_msg_buffer.clear()
            try:
                self.ble.advertise()
                print("BLE advertising restarted after watchdog")
            except:
                pass
            print("State forcibly reset. System recovered.")
        elif elapsed > self.device_scan_timeout:
            # Normal timeout
            try:
                self.finish_device_scan()
            except Exception as err:
                print("Scan finish error:", err)
                self.scan_in_progress = False
                self.ble_paused = False
                try:
                    self.ble.advertise()
                except:
                    pass


# === INITIALIZATION ===
print("Hub initialization starting...")
hub = Hub("SPHub")

# Register interrupt handlers
hub.espnow_interface.irq(espnow_recv_cb)
hub.ble._write_callback = handle_cmd

print("Hub initialization complete!")
print("=" * 50)
print("SMART PLAYGROUND HUB - AUTONOMOUS MODE")
print("=" * 50)
print(f"ESP-NOW: Broadcast MAC {hub.BROADCAST_MAC.hex()}")
print(f"BLE: Device name '{hub.name}'")
print("=" * 50)

# Start BLE advertising
hub.twist.current_mode = 0
hub.twist.show_mode()
hub.twist.start_breathe((255, 0, 255), duration=4000)
hub.ble.advertise()

print("Starting reactive main loop...")


# === MAIN EVENT LOOP ===
last_connection_check = time.time()
last_status_time = time.time()
last_display_update = time.time()

while True:
    current_time = time.time()
    
    # 1. Process BLE commands from buffer
    if len(ble_command_buffer) > 0:
        command_str = ble_command_buffer.popleft()
        try:
            hub.process_ble_command(command_str)
        except Exception as err:
            print("BLE command error:", err)
    
    # 2. Process ESP-NOW messages from buffer
    if len(espnow_msg_buffer) > 0:
        mac, receivedMessage = espnow_msg_buffer.popleft()
        print("Processing buffered ESP-NOW message (buffer size:", len(espnow_msg_buffer), ")")
        
        for key in receivedMessage:
            try:
                # RSSI filtering
                try:
                    sender_rssi = hub.espnow_interface.peers_table[mac][0]
                    threshold = receivedMessage[key]["RSSI"]
                    passes = sender_rssi > threshold
                    print("Msg:", key, "| Sender RSSI:", sender_rssi, "| Threshold:", threshold, "| Pass:", passes)
                except (KeyError, IndexError):
                    sender_rssi = 0
                    threshold = receivedMessage[key].get("RSSI", -100)
                    passes = True
                    print("Msg:", key, "| Sender RSSI: unknown | Threshold:", threshold, "| Pass:", passes)
                
                if passes:
                    # Route to handler
                    if hub.functionLUT.get(key):
                        print("Calling", key, "handler")
                        hub.functionLUT[key](mac, receivedMessage[key])
                    else:
                        print("No handler for", key, "(ignored)")
            except Exception as err:
                print("Message processing error:", err)
    
    # 3. Check scan timeout and send redundant PINGs
    if hub.scan_in_progress:
        hub.check_scan_progress(current_time)
    
    # 4. Update animations
    try:
        hub.twist.update_animations()
    except Exception as err:
        print("Animation error:", err)
    
    # 5. Monitor BLE connection
    if not hub.ble.is_connected:
        if current_time - last_connection_check > 5.0:
            try:
                hub.twist.start_breathe((255, 0, 255), duration=4000)
                hub.ble.advertise()
            except Exception as err:
                print("Advertise error:", err)
            last_connection_check = current_time
    
    # 6. Update display periodically
    if not hub.scan_in_progress and (current_time - last_display_update) > 0.5:
        try:
            hub.show_display("Hub Status",
                           "Buf:" + str(len(espnow_msg_buffer)),
                           "BLE:" + ("Y" if hub.ble.is_connected else "N"),
                           "Scan:" + ("Y" if hub.scan_in_progress else "N"))
            last_display_update = current_time
        except Exception as err:
            print("Display update error:", err)
    
    # 7. Periodic status logging
    if current_time - last_status_time >= 60:
        if hub.ble.is_connected:
            print("Hub: BLE connected,", len(hub.discovered_devices), "devices")
        else:
            print("Hub: BLE disconnected, advertising")
        last_status_time = current_time
