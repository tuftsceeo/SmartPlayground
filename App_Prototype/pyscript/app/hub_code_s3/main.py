# ESP32S3-N32R16V Hub - BLE to ESP-NOW bridge for Smart Playground
# Uses Nordic UART Service for BLE communication with web app
# Coordinates ESP-NOW messages to/from playground modules

import network
import time
import json
import random
import struct
from machine import Pin
import neopixel
import bluetooth
import espnow
from ucollections import deque

# === GLOBAL MESSAGE BUFFERS (Required for interrupt handlers) ===
espnow_msg_buffer = deque((), 50, 2)
ble_command_buffer = deque((), 10, 2)
_rxbuf = b""
MAX_BUFFER_SIZE = 1024

# === BLE NORDIC UART SERVICE ===
# Nordic UART Service UUIDs
UART_SERVICE_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
UART_RX_CHAR_UUID = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
UART_TX_CHAR_UUID = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")

# BLE IRQ constants
IRQ_CENTRAL_CONNECT = 1
IRQ_CENTRAL_DISCONNECT = 2
IRQ_GATTS_WRITE = 3

# Characteristic flags
FLAG_READ = 0x0002
FLAG_WRITE_NO_RESPONSE = 0x0004
FLAG_WRITE = 0x0008
FLAG_NOTIFY = 0x0010

# Nordic UART Service definition
UART_TX = (UART_TX_CHAR_UUID, FLAG_READ | FLAG_NOTIFY,)
UART_RX = (UART_RX_CHAR_UUID, FLAG_WRITE | FLAG_WRITE_NO_RESPONSE,)
UART_SERVICE = (UART_SERVICE_UUID, (UART_TX, UART_RX),)

class BLEUART:
    """Nordic UART Service using standard MicroPython Bluetooth"""
    
    def __init__(self, name="SPHub", verbose=True):
        self.name = name
        self.verbose = verbose
        self.is_connected = False
        self._connections = set()
        self._write_callback = None
        
        # Initialize BLE
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(self._irq)
        
        # Register Nordic UART Service
        ((self._handle_tx, self._handle_rx),) = self._ble.gatts_register_services((UART_SERVICE,))
        
        if self.verbose:
            print(f"BLE UART initialized: {self.name}")
    
    def _irq(self, event, data):
        """BLE interrupt handler"""
        if event == IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            self.is_connected = True
            if self.verbose:
                print(f"BLE Connected: {conn_handle}")
                
        elif event == IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self._connections.discard(conn_handle)
            self.is_connected = len(self._connections) > 0
            if self.verbose:
                print(f"BLE Disconnected: {conn_handle}")
                
        elif event == IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if value_handle == self._handle_rx:
                value = self._ble.gatts_read(value_handle)
                if self._write_callback:
                    self._write_callback(value)
    
    def advertise(self, interval_us=100000):
        """Start advertising the BLE service"""
        name_bytes = self.name.encode()[:8]  # Limit to 8 bytes for short name
        payload = struct.pack("BB", len(name_bytes) + 1, 0x09) + name_bytes  # Complete local name
        
        # Add service UUID to advertising data
        service_bytes = bytes(UART_SERVICE_UUID)
        payload += struct.pack("BB", len(service_bytes) + 1, 0x07) + service_bytes  # Complete 128-bit UUID
        
        self._ble.gap_advertise(interval_us, adv_data=payload)
        if self.verbose:
            print(f"BLE advertising as '{self.name}'")
    
    def stop_advertising(self):
        """Stop advertising"""
        self._ble.gap_advertise(None)
        if self.verbose:
            print("BLE advertising stopped")
    
    def send(self, data):
        """Send data via BLE notifications"""
        if not self.is_connected:
            if self.verbose:
                print("Cannot send: BLE not connected")
            return False
        
        if isinstance(data, str):
            data = data.encode()
        
        for conn_handle in self._connections:
            try:
                self._ble.gatts_notify(conn_handle, self._handle_tx, data)
            except Exception as e:
                if self.verbose:
                    print(f"BLE send error: {e}")
                return False
        
        if self.verbose:
            print(f"BLE sent to {len(self._connections)} connection(s): {len(data)} bytes")
        return True
    
    def disconnect(self):
        """Disconnect all connections"""
        for conn_handle in list(self._connections):
            try:
                self._ble.gap_disconnect(conn_handle)
            except:
                pass
        self._connections.clear()
        self.is_connected = False
        if self.verbose:
            print("BLE disconnected from all clients")

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
        
        # RGB LED (built-in NeoPixel on ESP32S3-N32R16V)
        # GPIO38 is typical, but may be GPIO48 on some board versions
        self.RGB_LED_PIN = 38
        self.rgb_led = neopixel.NeoPixel(Pin(self.RGB_LED_PIN), 1)
        self.rgb_led[0] = (0, 0, 0)  # Start off
        self.rgb_led.write()
        
        # Animation state
        self.animation_start_time = 0
        self.animation_duration = 0
        self.animation_color = (0, 0, 0)
        self.current_status_color = (0, 0, 0)
        
        # Peripherals
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
    
    def set_rgb_status(self, r, g, b, brightness=1.0):
        """Set RGB LED to a solid color"""
        self.current_status_color = (
            int(r * brightness),
            int(g * brightness),
            int(b * brightness)
        )
        self.rgb_led[0] = self.current_status_color
        self.rgb_led.write()
    
    def start_breathe(self, color, duration=4000):
        """Start breathing animation with specified color"""
        self.animation_color = color
        self.animation_duration = duration
        self.animation_start_time = time.ticks_ms()
    
    def update_animations(self):
        """Update RGB LED animations (breathing effect)"""
        if self.animation_duration > 0:
            elapsed = time.ticks_ms() - self.animation_start_time
            if elapsed < self.animation_duration:
                # Breathing effect: triangle wave from 0.3 to 1.0 brightness
                # Using triangle wave instead of sine for simplicity (no math module needed)
                cycle_time = elapsed % 2000  # 2 second cycle
                if cycle_time < 1000:
                    # Rising: 0.3 to 1.0 over 1 second
                    brightness = 0.3 + 0.7 * (cycle_time / 1000.0)
                else:
                    # Falling: 1.0 to 0.3 over 1 second
                    brightness = 1.0 - 0.7 * ((cycle_time - 1000) / 1000.0)
                
                self.set_rgb_status(
                    self.animation_color[0],
                    self.animation_color[1],
                    self.animation_color[2],
                    brightness
                )
            else:
                # Animation complete, return to solid color
                self.animation_duration = 0
                self.set_rgb_status(
                    self.animation_color[0],
                    self.animation_color[1],
                    self.animation_color[2]
                )
    
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
        ble = BLEUART(self.name, verbose=True)
        print(f"BLE advertising as '{self.name}'")
        return ble
    
    def show_status(self, status_type):
        """Update RGB LED status based on hub state"""
        if status_type == "off":
            self.set_rgb_status(0, 0, 0)
        elif status_type == "waiting":
            # Purple/magenta for waiting for BLE connection
            self.set_rgb_status(255, 0, 255)
        elif status_type == "paired":
            # Green for BLE connected
            self.set_rgb_status(0, 255, 0)
        elif status_type == "scanning":
            # Blue for device scan in progress
            self.set_rgb_status(0, 128, 255)
        elif status_type == "devices_found":
            # Cyan for devices discovered
            self.set_rgb_status(0, 255, 255)
        elif status_type == "error":
            # Red for error state
            self.set_rgb_status(255, 0, 0)
    
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
        
        self.show_status("scanning")
        
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
            
            # Update status LED - flash briefly on new device
            unique_count = len(self.discovered_devices)
            if unique_count == 1 or unique_count % 3 == 0:  # Flash every 3rd device
                self.set_rgb_status(0, 255, 255)  # Cyan flash
                time.sleep_ms(100)
                self.show_status("scanning")
            
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
        
        # Update status LED
        if len(self.discovered_devices) > 0:
            self.show_status("devices_found")
        else:
            self.show_status("waiting")
        
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
hub.show_status("waiting")
hub.start_breathe((255, 0, 255), duration=4000)  # Purple breathing while waiting
hub.ble.advertise()

print("Starting reactive main loop...")


# === MAIN EVENT LOOP ===
last_connection_check = time.time()
last_status_time = time.time()

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
        hub.update_animations()
    except Exception as err:
        print("Animation error:", err)
    
    # 5. Monitor BLE connection and update status
    if hub.ble.is_connected:
        if not hub.scan_in_progress:
            # Connected and idle - show green
            if hub.current_status_color != (0, 255, 0):
                hub.show_status("paired")
    else:
        if current_time - last_connection_check > 5.0:
            try:
                hub.show_status("waiting")
                hub.start_breathe((255, 0, 255), duration=4000)
                hub.ble.advertise()
            except Exception as err:
                print("Advertise error:", err)
            last_connection_check = current_time
    
    # 6. Periodic status logging
    if current_time - last_status_time >= 60:
        if hub.ble.is_connected:
            print("Hub: BLE connected,", len(hub.discovered_devices), "devices")
        else:
            print("Hub: BLE disconnected, advertising")
        last_status_time = current_time
