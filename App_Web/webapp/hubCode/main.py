"""
Simple Hub - USB Serial to ESP-NOW Bridge
==========================================

This hub connects the webapp (via USB Serial/WebUSB) to playground modules (via ESP-NOW).
Based on the headless_controller.py pattern with added Serial communication.

Hardware: ESP32-C6 with external antenna
"""

import sys
import select
import json
import time
import asyncio
import utilities.now as now
from controller import Control

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
            msg = json.dumps(data)
            print(msg)  # Print to stdout (USB Serial) - JSON only!
        except Exception as e:
            self.debug("Ser TX Err")
    
    def check_input(self):
        """Check for incoming Serial data (non-blocking)"""
        # Use select to check if stdin has data
        rlist, _, _ = select.select([sys.stdin], [], [], 0)
        
        if rlist:
            try:
                # Read available data
                chunk = sys.stdin.read(1)
                if chunk:
                    self.buffer += chunk
                    
                    # Check for complete lines
                    while '\n' in self.buffer:
                        line, self.buffer = self.buffer.split('\n', 1)
                        line = line.strip()
                        
                        if line:
                            self._process_command(line)
            except Exception as e:
                self.debug("Ser RX Err")
    
    def _process_command(self, line):
        """Parse JSON command and call callback"""
        try:
            cmd = json.loads(line)
            cmd_type = cmd.get("cmd")
            self.command_callback(cmd_type, cmd)
        except Exception as e:
            self.debug("CMD Err")

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
        """Initialize simple hub - transmit-only, no device scanning"""
        self.running = False
        
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
        """Initialize ESP-NOW using Control.connect() with C6 external antenna"""
        self._debug("Connecting")
        
        # Call parent's connect() to set up ESP-NOW
        # __ANTENNA_CONFIG_START__
        antenna_enabled = True  # C6 external antenna (set to False for internal)
        # __ANTENNA_CONFIG_END__
        super().connect(antenna_enabled)
        
        mac_str = ':'.join(f'{b:02x}' for b in self.mac)
        self._debug(f"MAC:{mac_str[-8:]}")
        self._debug("NOW Ready")
        
        # Send ready message to webapp via Serial
        self.serial.send({
            "type": "ready",
            "mac": mac_str
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
    
    async def run(self):
        """Main event loop"""
        self.connect()
        self.running = True
        
        self._debug("Running")
        self._debug("Wait CMD")
        
        try:
            while self.running:
                # Check for Serial commands
                self.serial.check_input()
                
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