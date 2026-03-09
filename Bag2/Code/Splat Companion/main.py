"""
Splat Companion — ESP-NOW ↔ BLE Bridge for Splat Devices
==========================================================
Board: Seeed XIAO ESP32-C6
LEDs: 3× NeoPixel on GPIO20

Receives action configurations from the Wand via ESP-NOW,
then controls a Splat device over BLE based on Splat button
presses and releases.

ESP-NOW messages (JSON):
  Wand → Companion:
    {"type": "splat_config", "actions": [["turnblue", "notec"]]}
    {"type": "stop"}

BLE: Connects to Splat, subscribes to button notifications,
     sends LED/note commands on press/release.

Antenna sharing: ESP32-C6 supports WiFi + BLE coexistence.
  - BLE connects to Splat first (slow, ~5-10s)
  - ESP-NOW activates after BLE is established
  - keepAlive() sent periodically to prevent Splat timeout
"""

import machine
import network
import espnow
import time
import math
import json
from neopixel import NeoPixel

from ble_splat import OpenSplat

# ─────────────────────────────────────────────
# HARDWARE
# ─────────────────────────────────────────────
NEOPIXEL_PIN = 20
NUM_LEDS     = 3

np = NeoPixel(machine.Pin(NEOPIXEL_PIN), NUM_LEDS)

# ─────────────────────────────────────────────
# COLOR MAP — same as wand
# ─────────────────────────────────────────────
COLOR_RGB = {
    "turnred":    (255, 0, 0),
    "turngreen":  (0, 255, 0),
    "turnblue":   (0, 0, 255),
    "turnpurple": (160, 0, 200),
    "turnyellow": (255, 180, 0),
    "turnwhite":  (200, 200, 200),
    "turnoff":    (0, 0, 0),
}

# Dimmed versions for companion status LEDs
COLOR_DIM = {}
for k, v in COLOR_RGB.items():
    COLOR_DIM[k] = (v[0] // 8, v[1] // 8, v[2] // 8)

# ─────────────────────────────────────────────
# NOTE MAP — MIDI note numbers for noteOn/noteOff
# Using octave 4, instrument 17
# ─────────────────────────────────────────────
NOTE_MIDI = {
    "notec": 0,   # C
    "noted": 2,   # D
    "notee": 4,   # E
    "notef": 5,   # F
    "noteg": 7,   # G
    "notea": 9,   # A
    "noteb": 11,  # B
    "playnote": 0,  # default to C for melody
}

DEFAULT_OCTAVE     = 4
DEFAULT_VELOCITY   = 127
DEFAULT_INSTRUMENT = 17

# ─────────────────────────────────────────────
# LED HELPERS (3 LEDs on companion board)
# ─────────────────────────────────────────────
def leds_off():
    for i in range(NUM_LEDS):
        np[i] = (0, 0, 0)
    np.write()

def leds_solid(r, g, b):
    for i in range(NUM_LEDS):
        np[i] = (r, g, b)
    np.write()

def leds_single(idx, r, g, b):
    np[idx] = (r, g, b)
    np.write()

def leds_breathe(r, g, b, frame):
    brightness = (math.sin(frame * 0.08) + 1) / 2
    leds_solid(
        int(r * brightness),
        int(g * brightness),
        int(b * brightness),
    )

def leds_flash(r, g, b, times=3, on_ms=80, off_ms=60):
    for _ in range(times):
        leds_solid(r, g, b)
        time.sleep_ms(on_ms)
        leds_off()
        time.sleep_ms(off_ms)

# Status colors (dim, for companion LEDs)
STATUS_BLE_CONNECTING = (0, 0, 15)     # dim blue — connecting BLE
STATUS_BLE_CONNECTED  = (0, 15, 0)     # dim green — BLE ready
STATUS_ESPNOW_READY   = (0, 15, 15)    # dim cyan — BLE + ESP-NOW ready
STATUS_CONFIGURED     = (15, 0, 15)    # dim purple — has config, listening
STATUS_ERROR          = (15, 0, 0)     # dim red — error

# ─────────────────────────────────────────────
# ACTION PARSER
# ─────────────────────────────────────────────
def parse_actions(action_chain):
    """
    Parse an action chain into color and note lists.
    action_chain is a list of groups: [["turnblue", "notec"], ["turnred"]]

    Returns:
        colors: list of color command strings (one per group)
        notes:  list of note command strings (one per group, None if no note)
    """
    colors = []
    notes = []
    for group in action_chain:
        group_color = None
        group_note = None
        for action in group:
            if action in COLOR_RGB:
                group_color = action
            elif action in NOTE_MIDI:
                group_note = action
        colors.append(group_color)
        notes.append(group_note)
    return colors, notes


# ─────────────────────────────────────────────
# SPLAT CONTROLLER
# ─────────────────────────────────────────────
class SplatController:
    """
    Manages BLE connection to Splat and executes actions
    based on Splat button press/release.
    """

    def __init__(self, splat):
        self.splat = splat
        self.action_chain = None
        self.colors = []
        self.notes = []
        self.configured = False
        self.active_notes = []  # track notes to turn off on release

    def set_config(self, action_chain):
        """Store action config from wand."""
        self.action_chain = action_chain
        self.colors, self.notes = parse_actions(action_chain)
        self.configured = True
        self.active_notes = []
        print("  Config set: %d groups" % len(action_chain))
        for i, group in enumerate(action_chain):
            print("    Group %d: %s" % (i, " & ".join(group)))

    def clear_config(self):
        """Clear config and stop all outputs on Splat."""
        self.action_chain = None
        self.colors = []
        self.notes = []
        self.configured = False
        self._stop_all()
        print("  Config cleared")

    def on_press(self):
        """Called when Splat button is pressed."""
        if not self.configured or not self.splat.connected:
            return

        print("  Splat PRESSED")
        self.active_notes = []

        # Execute all groups sequentially (THEN chains)
        for i in range(len(self.colors)):
            color = self.colors[i]
            note = self.notes[i]

            # Set LEDs on Splat
            if color and color in COLOR_RGB:
                rgb = COLOR_RGB[color]
                try:
                    self.splat.setLEDsON(rgb)
                    print("    LED: %s -> (%d,%d,%d)" % (color, rgb[0], rgb[1], rgb[2]))
                except Exception as e:
                    print("    LED error: %s" % str(e))

            # Play note on Splat
            if note and note in NOTE_MIDI:
                midi_note = NOTE_MIDI[note]
                try:
                    self.splat.noteOn(
                        midi_note,
                        DEFAULT_VELOCITY,
                        DEFAULT_OCTAVE,
                        DEFAULT_INSTRUMENT,
                    )
                    self.active_notes.append(midi_note)
                    print("    Note ON: %s -> MIDI %d" % (note, midi_note))
                except Exception as e:
                    print("    Note error: %s" % str(e))

            # If there are sequential groups (THEN), add a delay
            if i < len(self.colors) - 1:
                time.sleep_ms(400)

    def on_release(self):
        """Called when Splat button is released."""
        if not self.configured or not self.splat.connected:
            return

        print("  Splat RELEASED")
        self._stop_all()

    def _stop_all(self):
        """Turn off all LEDs and notes on the Splat."""
        if not self.splat.connected:
            return

        # Turn off all active notes
        for midi_note in self.active_notes:
            try:
                self.splat.noteOff(
                    midi_note,
                    DEFAULT_VELOCITY,
                    DEFAULT_OCTAVE,
                    DEFAULT_INSTRUMENT,
                )
            except Exception:
                pass
        self.active_notes = []

        # Turn off LEDs
        try:
            self.splat.allLEDsOff()
        except Exception:
            pass


# ─────────────────────────────────────────────
# ESP-NOW SETUP
# ─────────────────────────────────────────────
def espnow_init():
    """Initialize ESP-NOW for receiving wand messages."""
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.disconnect()
    e = espnow.ESPNow()
    e.active(True)
    print("  ESP-NOW active")
    return e


# ─────────────────────────────────────────────
# MESSAGE HANDLER
# ─────────────────────────────────────────────
def handle_message(msg_bytes, controller):
    """
    Parse and handle an ESP-NOW message from the wand.

    Messages:
      {"type": "splat_config", "actions": [["turnblue", "notec"]]}
      {"type": "stop"}

    Returns:
      "configured" — new config loaded
      "stopped"    — config cleared
      None         — unrecognized message
    """
    try:
        data = json.loads(msg_bytes)
    except ValueError:
        print("  [WARN] Bad JSON: %s" % str(msg_bytes[:40]))
        return None

    if not isinstance(data, dict):
        print("  [WARN] Expected dict, got %s" % type(data).__name__)
        return None

    msg_type = data.get("type")

    if msg_type == "splat_config":
        actions = data.get("actions")
        if actions and isinstance(actions, list):
            controller.set_config(actions)
            return "configured"
        else:
            print("  [WARN] splat_config missing 'actions'")
            return None

    elif msg_type == "stop":
        controller.clear_config()
        return "stopped"

    else:
        print("  [WARN] Unknown message type: %s" % msg_type)
        return None


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "=" * 50)
    print("  Splat Companion — BLE/ESP-NOW Bridge")
    print("=" * 50)

    # ── Phase 1: Connect to Splat via BLE ──
    print("\n  Phase 1: Connecting to Splat via BLE...")
    leds_solid(*STATUS_BLE_CONNECTING)

    splat = OpenSplat(verbose=False)
    controller = SplatController(splat)

    # Set up button callbacks on the Splat
    splat.on_splat_pressed = controller.on_press
    splat.on_splat_released = controller.on_release

    # Scan and connect
    print("  Scanning for Splat...")
    mac = splat.scanSplat(timeout=10)
    if mac:
        print("  Found Splat: %s" % mac)
    else:
        print("  [WARN] No Splat found during scan, will retry on connect")

    connected = splat.connect(timeout=30)

    if not connected:
        print("  [FAIL] Could not connect to Splat")
        leds_flash(*STATUS_ERROR, times=5)
        print("  Retrying in 5 seconds...")
        time.sleep(5)
        # Try once more
        connected = splat.connect(timeout=30)
        if not connected:
            print("  [FAIL] BLE connection failed. Reboot to retry.")
            leds_solid(*STATUS_ERROR)
            while True:
                time.sleep(1)

    print("  BLE connected to Splat!")
    leds_flash(*STATUS_BLE_CONNECTED, times=3)

    # Quick identify to confirm connection
    try:
        splat.identifySplat()
    except Exception:
        pass

    # ── Phase 2: Activate ESP-NOW ──
    print("\n  Phase 2: Activating ESP-NOW...")
    enow = espnow_init()
    leds_solid(*STATUS_ESPNOW_READY)
    print("  Ready — waiting for wand commands\n")

    # ── Phase 3: Main loop ──
    last_keepalive = time.ticks_ms()
    keepalive_interval = 2500  # ms — Splat has 3s timeout
    frame = 0

    while True:
        try:
            # ── Send keepalive to Splat ──
            now = time.ticks_ms()
            if time.ticks_diff(now, last_keepalive) >= keepalive_interval:
                if splat.connected:
                    try:
                        splat.keepAlive()
                    except Exception:
                        pass
                last_keepalive = now

            # ── Check for BLE disconnection ──
            if not splat.connected:
                print("  [WARN] Splat BLE disconnected — reconnecting...")
                leds_solid(*STATUS_BLE_CONNECTING)
                controller.clear_config()

                reconnected = splat.connect(timeout=15)
                if reconnected:
                    print("  Reconnected!")
                    if controller.configured:
                        leds_solid(*STATUS_CONFIGURED)
                    else:
                        leds_solid(*STATUS_ESPNOW_READY)
                else:
                    print("  Reconnect failed, will retry...")
                    leds_flash(*STATUS_ERROR, times=2)
                    time.sleep(2)
                    continue

            # ── Check ESP-NOW messages ──
            mac, msg = enow.irecv(50)  # 50ms timeout — non-blocking-ish
            if msg:
                mac_str = ':'.join('%02X' % b for b in mac)
                print("  [ESP-NOW] From %s: %s" % (mac_str, msg[:60]))

                result = handle_message(msg, controller)

                if result == "configured":
                    leds_flash(0, 15, 15, times=2, on_ms=100, off_ms=60)
                    leds_solid(*STATUS_CONFIGURED)
                    print("  Listening for Splat button presses...\n")

                elif result == "stopped":
                    leds_flash(15, 8, 0, times=2, on_ms=100, off_ms=60)
                    leds_solid(*STATUS_ESPNOW_READY)
                    print("  Stopped — waiting for new config...\n")

            # ── Status LED animation ──
            if controller.configured:
                # Gentle purple breathe when configured
                leds_breathe(15, 0, 15, frame)
            elif not msg:
                # Gentle cyan breathe when idle
                if frame % 5 == 0:
                    leds_breathe(0, 10, 10, frame)

            frame += 1

        except KeyboardInterrupt:
            print("\n  Shutting down...")
            controller.clear_config()
            splat.disconnect()
            leds_off()
            try:
                enow.active(False)
            except Exception:
                pass
            break

        except Exception as e:
            print("  [ERR] %s" % str(e))
            time.sleep_ms(500)


if __name__ == "__main__":
    main()