"""
Simple Hub - USB Serial to ESP-NOW Bridge
==========================================

This hub connects the webapp (via USB Serial/WebUSB) to playground modules (via ESP-NOW).
Based on the headless_controller.py pattern with added Serial communication.

Hardware: ESP32-C6 with external antenna
"""

# Debug mode flag
DEBUG_MODE = True

# Hub firmware version
HUB_VERSION = "v2.1.0"

import sys
import select
import json
import time
import asyncio
import utilities.now as now
from controller import Control

print("✅ Hub main.py LOADED", file=sys.stderr)

# Try to import display support
ROW_HEIGHT = 10  # Pixels per line on 128x64 display (can fit 6 lines)
MAX_DISPLAY_LINES = 6

try:
    from machine import I2C, SoftI2C, Pin
    import ssd1306
    DISPLAY_AVAILABLE = True
except ImportError:
    DISPLAY_AVAILABLE = False

# Game command mapping - synchronized with Plushie_Module/config.py
# Last synced: 2026-01-26
# IMPORTANT: Keep in sync with plushie games list (0-10) plus stop command (-1)
GAME_MAP = {
    # Core games (indices 0-10 from config.py)
    "Notes": 0,           # Music/sound notes
    "Shake": 1,           # Motion detection / shake counter
    "Hot_cold": 2,        # Proximity finding game
    "Jump": 3,            # Jump counter
    "Clap": 4,            # Range/connectivity test
    "Rainbow": 5,         # Battery check + celebration
    "Hibernate": 6,       # Sleep mode with button warning
    "Pattern_btn": 7,     # Button pattern matching
    "Pattern_plush": 8,   # Plushie pattern matching
    "Color_Press": 9,     # Single color selection
    "Color_Press_Mult": 10,  # Multi-color stacking
    
    # Command aliases (backwards compatibility & user convenience)
    "Off": 6,             # Alias for Hibernate
    "Stop": -1,           # Stop current game, return to idle
    "Pause": -1,          # Alias for Stop
}

class SerialBridge:
    """Handle USB Serial communication with webapp"""
    
    def __init__(self, command_callback, debug_callback):
        """
        Initialize serial bridge
        
        Args:
            command_callback: Function to call with (cmd_type, cmd_data)
            debug_callback: Function to call for debug messages
        """
        self.command_callback = command_callback
        self.debug = debug_callback
        self.buffer = ""
    
    def send(self, data):
        """Send JSON message to webapp via Serial"""
        try:
            if DEBUG_MODE:
                print(f"🔴 [Hub] About to send data: {data}", file=sys.stderr)
            
            msg = json.dumps(data)
            
            if DEBUG_MODE:
                print(f"🔴 [Hub] JSON serialized, length: {len(msg)} bytes", file=sys.stderr)
            
            # Print to stdout (MicroPython automatically flushes on newline)
            print(msg)
            # Note: sys.stdout.flush() not supported on all ESP32 MicroPython builds
            
            if DEBUG_MODE:
                print(f"🔴 [Hub] Successfully sent {len(msg)} bytes", file=sys.stderr)
            else:
                print(f"DEBUG: Successfully sent {len(msg)} bytes", file=sys.stderr)
        except Exception as e:
            self.debug("Ser TX Err")
            print(f"🔴 ERROR: Serial send failed: {e}", file=sys.stderr)
    
    def check_input(self):
        """Check for incoming Serial data (non-blocking with select() fallback)"""
        try:
            # Try using select to check if stdin has data
            rlist, _, _ = select.select([sys.stdin], [], [], 0)
            has_data = bool(rlist)
        except (OSError, ValueError, NotImplementedError) as e:
            # Fallback for platforms where select() doesn't work
            # Some ESP32 MicroPython builds don't support select on stdin
            if DEBUG_MODE:
                print(f"🔴 [Hub] select() not supported, using fallback: {e}", file=sys.stderr)
            # Use a simple try-read approach as fallback
            has_data = True  # Assume data might be available, try reading
        
        if has_data:
            try:
                # Read available data (non-blocking, 1 byte at a time)
                chunk = sys.stdin.read(1)
                if chunk:
                    if DEBUG_MODE:
                        print(f"🔴 [Hub] stdin has data available", file=sys.stderr)
                        print(f"🔴 [Hub] Read chunk: {repr(chunk)}", file=sys.stderr)
                    self.buffer += chunk
                    if DEBUG_MODE:
                        print(f"🔴 [Hub] Buffer now: {repr(self.buffer)}", file=sys.stderr)
                    
                    # Check for complete lines
                    while '\n' in self.buffer:
                        line, self.buffer = self.buffer.split('\n', 1)
                        line = line.strip()
                        
                        if line:
                            if DEBUG_MODE:
                                print(f"🔴 [Hub] Complete line received: {line}", file=sys.stderr)
                            self._process_command(line)
            except Exception as e:
                self.debug("Ser RX Err")
                print(f"🔴 [Hub] ERROR in check_input: {e}", file=sys.stderr)
    
    def _process_command(self, line):
        """Parse JSON command and call callback"""
        try:
            # Echo received command for debugging
            if DEBUG_MODE:
                print(f"🔴 [Hub] Processing command: {line}", file=sys.stderr)
            
            cmd = json.loads(line)
            cmd_type = cmd.get("cmd")
            
            if DEBUG_MODE:
                print(f"🔴 [Hub] Parsed command type: {cmd_type}", file=sys.stderr)
            
            self.command_callback(cmd_type, cmd)
        except json.JSONDecodeError as e:
            self.debug("JSON Err")
            print(f"🔴 [Hub] JSON parse error: {e}", file=sys.stderr)
            print(f"🔴 [Hub] Failed to parse: {repr(line)}", file=sys.stderr)
        except Exception as e:
            self.debug("CMD Err")
            print(f"🔴 [Hub] Command processing error: {e}", file=sys.stderr)

class HubDisplay:
    """Simple rolling display for hub debug messages"""
    
    def __init__(self):
        """Initialize SSD1306 display if available"""
        self.display = None
        self.lines = []
        
        if not DISPLAY_AVAILABLE:
            return
        
        try:
            # Initialize I2C and display
            # C6: I2C on pins 23 (SCL), 22 (SDA)
            # C3: SoftI2C on pins 7 (SCL), 6 (SDA)
            i2c = I2C(scl=Pin(23), sda=Pin(22))  # __DISPLAY_CONFIG_C6__
            # i2c = SoftI2C(scl=Pin(7), sda=Pin(6))  # __DISPLAY_CONFIG_C3__
            self.display = ssd1306.SSD1306_I2C(128, 64, i2c)
            self.display.fill(0)
            self.display.text("Hub Starting...", 2, 2, 1)
            self.display.show()
            print("Display initialized successfully", file=sys.stderr)
        except Exception as e:
            self.display = None
            print(f"Display not available: {e}", file=sys.stderr)
    
    def update(self, msg):
        """Update display with new message (rolling buffer)"""
        if not self.display:
            return
        
        try:
            # Truncate message to fit display width (~20 chars at 6x8 font)
            if len(msg) > 20:
                msg = msg[:17] + "..."
            
            # Add to rolling buffer
            self.lines.append(msg)
            if len(self.lines) > MAX_DISPLAY_LINES:
                self.lines = self.lines[-MAX_DISPLAY_LINES:]
            
            # Clear and redraw all lines
            self.display.fill(0)
            y = 2
            for line in self.lines:
                self.display.text(line, 2, y, 1)
                y += ROW_HEIGHT
            
            self.display.show()
        except Exception as e:
            # If display update fails, disable it
            print(f"Display update error: {e}", file=sys.stderr)
            self.display = None
    
    def close(self):
        """Display shutdown message"""
        if self.display:
            try:
                self.display.fill(0)
                self.display.text("Hub Stopped", 2, 28, 1)
                self.display.show()
            except:
                pass

class SimpleHub(Control):
    """Simple USB Serial to ESP-NOW bridge hub - inherits ESP-NOW methods from Control"""
    
    def __init__(self):
        """Initialize simple hub - passive device tracking via battery messages"""
        self.running = False
        
        # Device tracking (passive via battery messages)
        self.recent_devices = {}  # {mac_hex: {mac, rssi, battery, last_seen}}
        
        # Display for debug messages
        self.display = HubDisplay()
        
        # Serial bridge for webapp communication
        self.serial = SerialBridge(
            command_callback=self._handle_command,
            debug_callback=self._debug
        )
        
        self._debug("Hub Init")
    
    def _debug(self, msg):
        """Print debug message to stderr and update display"""
        print(msg, file=sys.stderr)
        self.display.update(msg)
    
    def connect(self):
        """Initialize ESP-NOW with custom callback for passive device tracking"""
        self._debug("Connecting")
        
        # Custom ESP-NOW callback to track battery messages (passive, no responses)
        def battery_callback(msg, mac, rssi):
            try:
                payload = json.loads(msg)
                topic = payload.get('topic', '')
                
                # Only track battery messages (sent by modules every 60s)
                if '/battery/' in topic:
                    # Convert MAC bytes to hex string for dictionary key
                    mac_hex = ''.join(f'{b:02x}' for b in mac)
                    
                    # Extract RSSI value from neighbor dict
                    # rssi is a dict: {mac_bytes: [rssi_value, timestamp], ...}
                    rssi_value = -100  # Default fallback
                    if isinstance(rssi, dict):
                        # Look up this sender's MAC in the neighbor table
                        if mac in rssi:
                            rssi_data = rssi[mac]
                            if isinstance(rssi_data, list) and len(rssi_data) > 0:
                                rssi_value = rssi_data[0]  # First element is RSSI
                    elif isinstance(rssi, int):
                        rssi_value = rssi
                    
                    # Update device tracking
                    self.recent_devices[mac_hex] = {
                        'mac': mac_hex,
                        'rssi': rssi_value,
                        'battery': payload.get('value', 0),
                        'last_seen': time.ticks_ms()
                    }
                    
                    # Show on display and stderr
                    battery_val = payload.get('value', 0)
                    self._debug(f"Dev:{len(self.recent_devices)} {mac_hex[-6:]}")
                    print(f"Battery: {mac_hex[-6:]} RSSI={rssi_value}dBm Batt={battery_val}%", file=sys.stderr)
            except Exception as e:
                print(f"Callback error: {e}", file=sys.stderr)
        
        # Initialize ESP-NOW with our custom callback
        # __ANTENNA_CONFIG_START__
        antenna_enabled = True  # C6 external antenna (set to False for internal)
        # __ANTENNA_CONFIG_END__
        self.n = now.Now(antenna_enabled, battery_callback)
        self.n.connect()
        self.mac = self.n.wifi.config('mac')
        
        mac_str = ':'.join(f'{b:02x}' for b in self.mac)
        self._debug(f"MAC:{mac_str[-8:]}")
        self._debug("NOW Ready")
        
        # Send ready message to webapp via Serial
        self.serial.send({
            "type": "ready",
            "mac": mac_str,
            "version": HUB_VERSION,
            "timestamp": time.ticks_ms()
        })
    
    def _handle_command(self, cmd_type, cmd):
        """Handle command from webapp (callback from SerialBridge)"""
        if cmd_type in GAME_MAP:
            # Send game command using inherited choose() method
            # choose() handles all game numbers including -1 (stop)
            game_num = GAME_MAP[cmd_type]
            
            # Show game name on display (truncate to fit 12 char limit: "Gm:" + 9 chars)
            game_display = cmd_type[:9] if len(cmd_type) <= 9 else cmd_type[:8] + "."
            self._debug(f"Gm:{game_display}")
            
            # Send game command via ESP-NOW
            # For games 0-10: starts that game
            # For game -1 (Stop/Pause): stops current game, returns to idle
            self.choose(game_num)
            
            # Send acknowledgment to webapp
            self.serial.send({
                "type": "ack",
                "command": cmd_type,
                "status": "sent"
            })
        
        else:
            # Show unknown command (truncate to fit)
            unk_display = str(cmd_type)[:8] if cmd_type else "None"
            self._debug(f"Unk:{unk_display}")
    
    def _send_device_list(self):
        """Send device list to webapp with stale device expiry (5 min)"""
        current_time = time.ticks_ms()
        
        # Remove devices not seen for 5 minutes
        stale_macs = []
        for mac, data in self.recent_devices.items():
            if time.ticks_diff(current_time, data['last_seen']) > 300000:  # 5 min
                stale_macs.append(mac)
        
        for mac in stale_macs:
            del self.recent_devices[mac]
            print(f"Expired device: {mac[-6:]}", file=sys.stderr)
        
        # Build device list
        device_list = []
        for mac, data in self.recent_devices.items():
            device_list.append({
                'id': f"M-{mac[-6:]}",  # Module with last 6 chars of MAC
                'mac': mac,
                'rssi': data['rssi'],
                'battery': data['battery'],
                'last_seen': data['last_seen']
            })
        
        # Send to webapp
        self.serial.send({
            'type': 'devices',
            'list': device_list,
            'timestamp': current_time
        })
        
        # Debug: Confirm send (to stderr so it doesn't interfere with JSON)
        print(f"DEBUG: Sent device list JSON to stdout", file=sys.stderr)
        
        # Show on display (update count)
        if device_list:
            self._debug(f"Sent:{len(device_list)} devs")
        else:
            self._debug("Sent:0 devs")
    
    async def run(self):
        """Main event loop with 30-second device list updates"""
        self.connect()
        self.running = True
        
        self._debug("Running")
        self._debug("Wait CMD")
        
        # Timer for device list updates (every 30 seconds)
        last_device_update = time.ticks_ms()
        
        # Timer for heartbeat (every 5 seconds)
        last_heartbeat = time.ticks_ms()
        
        # Heartbeat counter for debug logging
        loop_counter = 0
        
        try:
            while self.running:
                # Heartbeat logging (every 1000 iterations)
                loop_counter += 1
                if DEBUG_MODE and loop_counter % 1000 == 0:
                    print(f"🔴 [Hub] Loop iteration {loop_counter}", file=sys.stderr)
                
                # Check for Serial commands
                self.serial.check_input()
                
                # Get current time for periodic tasks
                current_time = time.ticks_ms()
                
                # Send heartbeat every 5 seconds
                if time.ticks_diff(current_time, last_heartbeat) > 5000:  # 5s
                    self.serial.send({
                        "type": "heartbeat",
                        "timestamp": current_time,
                        "uptime": time.ticks_diff(current_time, last_device_update)
                    })
                    last_heartbeat = current_time
                
                # Send device list every 30 seconds
                if time.ticks_diff(current_time, last_device_update) > 30000:  # 30s
                    self._send_device_list()
                    last_device_update = current_time
                
                # Small delay for responsiveness
                await asyncio.sleep(0.01)
        
        except KeyboardInterrupt:
            self._debug("Stopping")
        
        finally:
            self.close()
    
    def close(self):
        """Cleanup resources"""
        if self.n:
            self.n.close()
        self._debug("Stopped")
        self.display.close()

# Run simple hub (transmit-only, no device scanning)
hub = SimpleHub()
asyncio.run(hub.run())