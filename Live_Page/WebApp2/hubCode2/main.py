"""
Hub2 - USB Serial to ESP-NOW Bridge (Wand Protocol)

Connects LivePage2 webapp (USB Serial) to Bag2 wands (ESP-NOW).
Hardware: ESP32-C6 with external antenna
"""

DEBUG_MODE = False
HUB_VERSION = "v1.0.0"

import sys
import select
import json
import time
import asyncio
from espnow_manager import ESPNowManager, get_own_mac
from game_tags import GAME_TAGS

ROW_HEIGHT = 10
MAX_DISPLAY_LINES = 6

try:
    from machine import I2C, Pin
    import ssd1306
    DISPLAY_AVAILABLE = True
except ImportError:
    DISPLAY_AVAILABLE = False

CONTROL_CMDS = {"stop", "battery"}


class SerialBridge:
    """Handle USB Serial communication with webapp."""

    def __init__(self, command_callback, debug_callback):
        self.command_callback = command_callback
        self.debug = debug_callback
        self.buffer = ""

    def send(self, data):
        """Send JSON message to webapp via Serial."""
        try:
            if DEBUG_MODE:
                print(f"🔴 [Hub] About to send data: {data}", file=sys.stderr)

            msg = json.dumps(data)

            if DEBUG_MODE:
                print(f"🔴 [Hub] JSON serialized, length: {len(msg)} bytes", file=sys.stderr)

            print(msg)
            time.sleep_ms(10)

            if DEBUG_MODE:
                print(f"🔴 [Hub] Successfully sent {len(msg)} bytes", file=sys.stderr)
        except Exception as e:
            self.debug("Ser TX Err")
            if DEBUG_MODE:
                print(f"🔴 ERROR: Serial send failed: {e}", file=sys.stderr)

    def check_input(self):
        """Check for incoming Serial data (non-blocking)."""
        try:
            rlist, _, _ = select.select([sys.stdin], [], [], 0)
            has_data = bool(rlist)
        except (OSError, ValueError, NotImplementedError) as e:
            if DEBUG_MODE:
                print(f"🔴 [Hub] select() not supported, using fallback: {e}", file=sys.stderr)
            has_data = True

        if has_data:
            try:
                chunk = sys.stdin.read(1)
                if chunk:
                    if DEBUG_MODE:
                        print(f"🔴 [Hub] stdin has data available", file=sys.stderr)
                        print(f"🔴 [Hub] Read chunk: {repr(chunk)}", file=sys.stderr)
                    self.buffer += chunk
                    if DEBUG_MODE:
                        print(f"🔴 [Hub] Buffer now: {repr(self.buffer)}", file=sys.stderr)

                    while '\n' in self.buffer:
                        line, self.buffer = self.buffer.split('\n', 1)
                        line = line.strip()

                        if line:
                            if DEBUG_MODE:
                                print(f"🔴 [Hub] Complete line received: {line}", file=sys.stderr)
                            self._process_command(line)
            except Exception as e:
                self.debug("Ser RX Err")
                if DEBUG_MODE:
                    print(f"🔴 [Hub] ERROR in check_input: {e}", file=sys.stderr)

    def _process_command(self, line):
        """Parse JSON command and call callback."""
        try:
            if DEBUG_MODE:
                print(f"🔴 [Hub] Processing command: {line}", file=sys.stderr)

            cmd = json.loads(line)
            cmd_type = cmd.get("cmd")

            if DEBUG_MODE:
                print(f"🔴 [Hub] Parsed command type: {cmd_type}", file=sys.stderr)

            self.command_callback(cmd_type, cmd)
        except json.JSONDecodeError as e:
            self.debug("JSON Err")
            if DEBUG_MODE:
                print(f"🔴 [Hub] JSON parse error: {e}", file=sys.stderr)
                print(f"🔴 [Hub] Failed to parse: {repr(line)}", file=sys.stderr)
        except Exception as e:
            self.debug("CMD Err")
            if DEBUG_MODE:
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
            i2c = I2C(scl=Pin(23), sda=Pin(22))  # __DISPLAY_CONFIG_C6__
            self.display = ssd1306.SSD1306_I2C(128, 64, i2c)
            self.display.fill(0)
            self.display.text("Hub2 Starting", 2, 2, 1)
            self.display.show()
            if DEBUG_MODE:
                print("Display initialized successfully", file=sys.stderr)
        except Exception as e:
            self.display = None
            if DEBUG_MODE:
                print(f"Display not available: {e}", file=sys.stderr)

    def update(self, msg):
        """Update display with new message (rolling buffer)"""
        if not self.display:
            return

        try:
            if len(msg) > 20:
                msg = msg[:17] + "..."

            self.lines.append(msg)
            if len(self.lines) > MAX_DISPLAY_LINES:
                self.lines = self.lines[-MAX_DISPLAY_LINES:]

            self.display.fill(0)
            y = 2
            for line in self.lines:
                self.display.text(line, 2, y, 1)
                y += ROW_HEIGHT

            self.display.show()
        except Exception as e:
            if DEBUG_MODE:
                print(f"Display update error: {e}", file=sys.stderr)
            self.display = None

    def close(self):
        """Display shutdown message"""
        if self.display:
            try:
                self.display.fill(0)
                self.display.text("Hub2 Stopped", 2, 28, 1)
                self.display.show()
            except:
                pass


class SimpleHub:
    """USB Serial to ESP-NOW bridge for Bag2 wand protocol."""

    def __init__(self):
        self.running = False
        self.enow = None
        self.display = HubDisplay()
        self.serial = SerialBridge(
            command_callback=self._handle_command,
            debug_callback=self._debug
        )
        self._debug("Hub2 Init")

    def _debug(self, msg):
        """Print debug message to stderr and update display."""
        if DEBUG_MODE:
            print(msg, file=sys.stderr)
        self.display.update(msg)

    def connect(self):
        """Initialize ESP-NOW for wand broadcast commands."""
        self._debug("Connecting")

        self.enow = ESPNowManager()
        self.enow.init()
        mac_str = get_own_mac()

        self._debug(f"MAC:{mac_str[-8:]}")
        self._debug("NOW Ready")

        self.serial.send({
            "type": "ready",
            "mac": mac_str,
            "version": HUB_VERSION,
            "timestamp": time.ticks_ms()
        })

        time.sleep_ms(50)

    def _broadcast_twice(self, send_fn):
        """Send an ESP-NOW command twice for reliability (unacknowledged broadcast)."""
        send_fn()
        time.sleep_ms(100)
        send_fn()

    def _handle_command(self, cmd_type, cmd):
        """Handle command from webapp (callback from SerialBridge)."""
        if cmd_type == "stop":
            game_display = "stop"
            self._debug(f"Gm:{game_display}")
            self._broadcast_twice(self.enow.broadcast_stop)
        elif cmd_type == "battery":
            self._debug("Gm:battery")
            self._broadcast_twice(lambda: self.enow.broadcast(["battery"]))
        elif cmd_type in GAME_TAGS:
            game_display = cmd_type[:9] if len(cmd_type) <= 9 else cmd_type[:8] + "."
            self._debug(f"Gm:{game_display}")
            self._broadcast_twice(lambda: self.enow.broadcast_start_game(cmd_type))
        else:
            unk_display = str(cmd_type)[:8] if cmd_type else "None"
            self._debug(f"Unk:{unk_display}")
            return

        self.serial.send({
            "type": "ack",
            "command": cmd_type,
            "status": "sent"
        })

    async def run(self):
        """Main event loop with heartbeat."""
        self.connect()
        self.running = True

        self._debug("Running")
        self._debug("Wait CMD")

        last_heartbeat = time.ticks_ms()
        boot_time = last_heartbeat
        loop_counter = 0

        try:
            while self.running:
                loop_counter += 1
                if DEBUG_MODE and loop_counter % 1000 == 0:
                    print(f"🔴 [Hub] Loop iteration {loop_counter}", file=sys.stderr)

                self.serial.check_input()

                current_time = time.ticks_ms()

                if time.ticks_diff(current_time, last_heartbeat) > 5000:
                    self.serial.send({
                        "type": "heartbeat",
                        "timestamp": current_time,
                        "uptime": time.ticks_diff(current_time, boot_time)
                    })
                    last_heartbeat = current_time

                await asyncio.sleep(0.01)

        except KeyboardInterrupt:
            self._debug("Stopping")

        finally:
            self.close()

    def close(self):
        """Cleanup resources."""
        if self.enow:
            self.enow.shutdown()
        self._debug("Stopped")
        self.display.close()


hub = SimpleHub()
asyncio.run(hub.run())
