"""
Color Quest — ESP-NOW Receiver Game for Wand Module
=====================================================
Receives a color sequence via ESP-NOW from the 4-reader hub,
then the player must find & tap matching NFC tags in order.

5x5 LED Matrix Layout:
  Row 0 (top):    Target color sequence (dim = upcoming, bright = done)
  Rows 1-3:       Scan animation / effects area
  Row 4 (bottom): Colors collected so far (bright)

Requires /lib/: pn532.py, nfc_reader.py, buzzer.py
"""

import machine
import network
import espnow
import time
import math
import json
import random
from neopixel import NeoPixel

from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
from nfc_reader import _decode_ndef_text, COMMON_KEYS
from buzzer import Buzzer

# ─────────────────────────────────────────────
# HARDWARE
# ─────────────────────────────────────────────
I2C_SDA      = 22
I2C_SCL      = 23
NEOPIXEL_PIN = 20
NUM_LEDS     = 25
BUZZER_PIN   = 19
SWITCH_PIN   = 0
PN532_ADDR   = 0x24

# ─────────────────────────────────────────────
# 5x5 GRID HELPERS
# ─────────────────────────────────────────────
#  0  1  2  3  4    row 0 — targets
#  5  6  7  8  9    row 1 ┐
# 10 11 12 13 14    row 2 ├ animation area
# 15 16 17 18 19    row 3 ┘
# 20 21 22 23 24    row 4 — collected

def rc(row, col):
    return row * 5 + col

# Target slots: centered for 1-4 items
def target_slots(n):
    if n <= 0: return []
    offset = (5 - n) // 2
    return [rc(0, offset + i) for i in range(n)]

def found_slots(n):
    if n <= 0: return []
    offset = (5 - n) // 2
    return [rc(4, offset + i) for i in range(n)]

# Cross pattern (X shape)
CROSS_LEDS = [0, 4, 6, 8, 12, 16, 18, 20, 24]

# Middle area LEDs (rows 1-3) for scan animation
MIDDLE_LEDS = list(range(5, 20))

# ─────────────────────────────────────────────
# COLOR MAP — GRB tuples for SK6812
# ─────────────────────────────────────────────
#  NeoPixel byte order is (G, R, B)

# Tuples are (R, G, B) — matching leds.solid() / actions.py convention
COLOR_BRIGHT = {
    "turnred":    (50, 0, 0),
    "turngreen":  (0, 50, 0),
    "turnblue":   (0, 0, 50),
    "turnpurple": (50, 0, 50),
    "turnyellow": (50, 35, 0),
    "turnwhite":  (30, 30, 30),
    "turnoff":    (0, 0, 0),
}

COLOR_DIM = {}
for k, v in COLOR_BRIGHT.items():
    COLOR_DIM[k] = (v[0] // 6, v[1] // 6, v[2] // 6)

OFF = (0, 0, 0)
RED_X = (50, 0, 0)
GREEN_WIN = (0, 50, 0)

# ─────────────────────────────────────────────
# NFC TAG READING (proven patterns from nfc_reader.py)
# ─────────────────────────────────────────────
def read_tag_text(nfc):
    """Detect tag, auth, read NDEF sectors 1-2, decode text."""
    tag = nfc.read_passive_target(timeout=500)
    if tag is None:
        return None, None
    if tag['sak'] not in (0x08, 0x18):
        return None, tag['uid_hex']

    ndef_data = bytearray()
    for sector in (1, 2):
        first_block = sector * 4
        authed = False
        for key in COMMON_KEYS:
            for key_type in [MIFARE_AUTH_A, MIFARE_AUTH_B]:
                resel = nfc.read_passive_target(timeout=200)
                if resel is None:
                    continue
                if nfc.mifare_auth_block(resel['uid'], first_block, key, key_type):
                    for blk in range(first_block, first_block + 3):
                        try:
                            ndef_data.extend(nfc.mifare_read_block(blk))
                        except Exception:
                            ndef_data.extend(b'\x00' * 16)
                    authed = True
                    break
            if authed:
                break
        if not authed:
            ndef_data.extend(b'\x00' * 48)

    text = _decode_ndef_text(ndef_data)
    return text, tag['uid_hex']


# ─────────────────────────────────────────────
# DISPLAY CLASS
# ─────────────────────────────────────────────
class GameDisplay:
    def __init__(self, np):
        self.np = np

    def clear(self):
        for i in range(NUM_LEDS):
            self.np[i] = OFF
        self.np.write()

    def clear_middle(self):
        for i in MIDDLE_LEDS:
            self.np[i] = OFF
        self.np.write()

    def show_game_state(self, targets, found_count, pulse_frame=0):
        """
        Draw the persistent game state:
          Row 0: target colors (dim=upcoming, bright=done, pulse=current)
          Rows 1-3: gentle glow of current target color
          Row 4: collected colors (bright)
        """
        n = len(targets)
        t_slots = target_slots(n)
        f_slots = found_slots(n)

        # Clear rows 0 and 4
        for i in range(5):
            self.np[i] = OFF
            self.np[20 + i] = OFF

        # Target row
        for i, cmd in enumerate(targets):
            bright = COLOR_BRIGHT.get(cmd, OFF)
            dim = COLOR_DIM.get(cmd, OFF)

            if i < found_count:
                # Already found — bright on both rows
                self.np[t_slots[i]] = bright
                self.np[f_slots[i]] = bright
            elif i == found_count:
                # Current target — pulse on top row
                pulse = (math.sin(pulse_frame * 0.15) + 1) / 2
                scale = 0.3 + 0.7 * pulse
                pulsed = (
                    int(bright[0] * scale),
                    int(bright[1] * scale),
                    int(bright[2] * scale),
                )
                self.np[t_slots[i]] = pulsed
            else:
                # Upcoming — dim
                self.np[t_slots[i]] = dim

        # Middle rows: soft breathing glow of current target color
        if found_count < n:
            current = COLOR_BRIGHT.get(targets[found_count], OFF)
            breath = (math.sin(pulse_frame * 0.08) + 1) / 2
            for i in MIDDLE_LEDS:
                # Gentle glow, brighter at center (row 2)
                row = i // 5
                center_fade = 1.0 - abs(row - 2) * 0.3
                level = 0.05 + 0.15 * breath * center_fade
                self.np[i] = (
                    int(current[0] * level),
                    int(current[1] * level),
                    int(current[2] * level),
                )
        else:
            for i in MIDDLE_LEDS:
                self.np[i] = OFF

        self.np.write()

    def scan_animate(self, frame, targets, found_count):
        """Animate middle rows during NFC scan, preserve game rows."""
        self.show_game_state(targets, found_count)
        center = 2  # middle of middle area (row 2, col 2 = LED 12)
        for row in range(1, 4):
            for col in range(5):
                idx = rc(row, col)
                dist = abs(col - 2) + abs(row - 2)
                ring = frame % 5
                if dist == ring:
                    self.np[idx] = (15, 10, 20)
                elif dist == max(0, ring - 1):
                    self.np[idx] = (5, 3, 7)
                else:
                    self.np[idx] = OFF
        self.np.write()

    def show_correct(self, cmd):
        """Flash the correct color across middle area."""
        color = COLOR_BRIGHT.get(cmd, GREEN_WIN)
        for _ in range(3):
            for i in MIDDLE_LEDS:
                self.np[i] = color
            self.np.write()
            time.sleep_ms(80)
            self.clear_middle()
            time.sleep_ms(60)

    def show_wrong(self):
        """Red X cross pattern on entire grid."""
        for _ in range(3):
            for i in range(NUM_LEDS):
                self.np[i] = RED_X if i in CROSS_LEDS else OFF
            self.np.write()
            time.sleep_ms(200)
            self.clear()
            time.sleep_ms(120)

    def show_win_green(self):
        """All LEDs turn green."""
        for step in range(15):
            brightness = min(step * 4, 50)
            color = (0, brightness, 0)  # RGB green
            for i in range(NUM_LEDS):
                self.np[i] = color
            self.np.write()
            time.sleep_ms(40)
        time.sleep_ms(500)

    def rainbow_dance(self, duration_ms=3000):
        """Rainbow cycle across all 25 LEDs."""
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < duration_ms:
            t = time.ticks_diff(time.ticks_ms(), start)
            for i in range(NUM_LEDS):
                hue = ((i * 255 // NUM_LEDS) + t // 4) % 255
                r, g, b = self._hsv(hue, 255, 35)
                self.np[i] = (r, g, b)
            self.np.write()
            time.sleep_ms(20)

    def show_waiting(self, frame):
        """Breathing blue while waiting for ESP-NOW."""
        brightness = int((math.sin(frame * 0.08) + 1) * 12)
        for i in range(NUM_LEDS):
            self.np[i] = (0, 0, brightness)
        self.np.write()

    @staticmethod
    def _hsv(h, s, v):
        if s == 0:
            return v, v, v
        region = h // 43
        rem = (h - region * 43) * 6
        p = (v * (255 - s)) >> 8
        q = (v * (255 - ((s * rem) >> 8))) >> 8
        t = (v * (255 - ((s * (255 - rem)) >> 8))) >> 8
        if region == 0: return v, t, p
        if region == 1: return q, v, p
        if region == 2: return p, v, t
        if region == 3: return p, q, v
        if region == 4: return t, p, v
        return v, p, q


# ─────────────────────────────────────────────
# ESP-NOW RECEIVER
# ─────────────────────────────────────────────
def espnow_init():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.disconnect()
    e = espnow.ESPNow()
    e.active(True)
    print("ESP-NOW listening...")
    return e

def wait_for_commands(enow, display, nfc, last_espnow=None):
    """
    Block until we receive a command source.
    Returns (targets_list, from_espnow_bool) or ("stop", False) to exit.
    """
    if last_espnow:
        print("Waiting for new sequence (button = replay last)...")
    else:
        print("Waiting for color sequence (button = random quest)...")
    print("  Tap STOP tag or send \"stop\" via ESP-NOW to exit\n")
    btn = machine.Pin(SWITCH_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    frame = 0

    while True:
        display.show_waiting(frame)
        frame += 1

        # Check ESP-NOW
        host, msg = enow.irecv(50)
        if msg:
            try:
                raw = msg.decode('utf-8').strip()
                # Check for bare "stop" string
                if raw.lower() == '"stop"' or raw.lower() == 'stop':
                    print("  ESP-NOW: stop received")
                    return "stop", False
                commands = json.loads(raw)
                if isinstance(commands, list) and len(commands) > 0:
                    # Check if sequence contains "stop"
                    if "stop" in commands:
                        print("  ESP-NOW: stop received")
                        return "stop", False
                    colors = [c for c in commands if c in COLOR_BRIGHT]
                    if colors:
                        print("Received: %s" % str(colors))
                        return colors, True
            except Exception as ex:
                print("  Parse error: %s" % str(ex))

        # Check NFC for stop tag
        if frame % 10 == 0:  # every ~0.5s to avoid slowing the animation
            text, uid = read_tag_text(nfc)
            if text == "stop":
                print("  STOP tag detected")
                return "stop", False

        # Button: replay last ESP-NOW sequence, or random if none
        if btn.value() == 0:
            time.sleep_ms(30)
            if btn.value() == 0:
                while btn.value() == 0:
                    time.sleep_ms(10)
                if last_espnow:
                    print("Replaying: %s" % str(last_espnow))
                    return list(last_espnow), False
                else:
                    quest = random_quest()
                    print("Random quest: %s" % str(quest))
                    return quest, False


# ─────────────────────────────────────────────
# GAME LOOP
# ─────────────────────────────────────────────
def run_game(nfc, buz, display, targets, enow):
    """
    Main game: find and tap NFC tags in the correct color order.
    Returns:
      "win"   — completed successfully
      "reset" — button pressed, restart same sequence
      "stop"  — stop tag tapped, exit game
      list    — new ESP-NOW sequence received
    """
    btn = machine.Pin(SWITCH_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    n = len(targets)
    found = 0
    last_uid = None
    frame = 0

    print("\n  === COLOR QUEST ===")
    print("  Find these colors in order:")
    for i, t in enumerate(targets):
        print("    %d. %s" % (i + 1, t))
    print("  (Press button to reset)\n")

    # Opening fanfare
    buz.beep(523, 80)
    time.sleep_ms(40)
    buz.beep(659, 80)
    time.sleep_ms(40)
    buz.beep(784, 120)
    time.sleep_ms(200)

    display.clear()

    while found < n:
        # ── Check button for reset ──
        if btn.value() == 0:
            time.sleep_ms(30)
            if btn.value() == 0:
                print("  RESET — starting over!")
                buz.beep(400, 80)
                time.sleep_ms(30)
                buz.beep(300, 120)
                while btn.value() == 0:
                    time.sleep_ms(10)
                return "reset"

        # ── Check for new ESP-NOW sequence or stop ──
        host, msg = enow.irecv(0)
        if msg:
            try:
                raw = msg.decode('utf-8').strip()
                if raw.lower() == '"stop"' or raw.lower() == 'stop':
                    print("  ESP-NOW: stop received")
                    buz.beep(800, 80)
                    time.sleep_ms(30)
                    buz.beep(400, 200)
                    display.clear()
                    return "stop"
                commands = json.loads(raw)
                if isinstance(commands, list) and len(commands) > 0:
                    if "stop" in commands:
                        print("  ESP-NOW: stop received")
                        buz.beep(800, 80)
                        time.sleep_ms(30)
                        buz.beep(400, 200)
                        display.clear()
                        return "stop"
                    colors = [c for c in commands if c in COLOR_BRIGHT]
                    if colors:
                        print("  NEW SEQUENCE received: %s" % str(colors))
                        buz.beep(600, 50)
                        time.sleep_ms(30)
                        buz.beep(900, 50)
                        return colors
            except Exception:
                pass

        # Draw game state with pulsing current target
        display.show_game_state(targets, found, frame)
        frame += 1

        # Quick tag detection
        tag = nfc.read_passive_target(timeout=150)

        if tag is None:
            if last_uid is not None:
                last_uid = None
            time.sleep_ms(30)
            continue

        # Same tag still on reader — skip
        if tag['uid_hex'] == last_uid:
            time.sleep_ms(100)
            continue

        last_uid = tag['uid_hex']

        # Tag detected — animate scan on middle rows
        print("  Tag detected: %s" % tag['uid_hex'])
        buz.beep(800, 30)

        for f in range(12):
            display.scan_animate(f, targets, found)
            time.sleep_ms(60)

        # Now do the full NDEF read
        text, uid = read_tag_text(nfc)

        # Scan complete flash
        for i in MIDDLE_LEDS:
            display.np[i] = (15, 15, 20)
        display.np.write()
        time.sleep_ms(80)
        display.clear_middle()

        if text is None:
            print("  Could not read tag")
            buz.beep(300, 100)
            continue

        print("  Read: \"%s\"" % text)

        # Stop tag exits the game
        if text == "stop":
            print("  STOP tag — exiting game")
            buz.beep(800, 80)
            time.sleep_ms(30)
            buz.beep(400, 200)
            display.clear()
            return "stop"

        expected = targets[found]

        if text == expected:
            # CORRECT!
            found += 1
            print("  CORRECT! (%d/%d)" % (found, n))
            buz.beep(880, 60)
            time.sleep_ms(30)
            buz.beep(1100, 80)
            display.show_correct(text)
            display.show_game_state(targets, found)
            time.sleep_ms(300)
        else:
            # WRONG — uh oh!
            print("  WRONG! Expected '%s', got '%s'" % (expected, text))
            buz.beep(400, 150)
            time.sleep_ms(60)
            buz.beep(250, 250)
            display.show_wrong()
            display.show_game_state(targets, found)
            time.sleep_ms(300)

    # ── WIN! ──
    print("\n  ALL COLORS FOUND!")
    buz.beep(523, 100)
    time.sleep_ms(50)
    buz.beep(659, 100)
    time.sleep_ms(50)
    buz.beep(784, 100)
    time.sleep_ms(50)
    buz.beep(1047, 300)

    display.show_win_green()
    display.rainbow_dance(5000)
    display.clear()
    return "win"


# ─────────────────────────────────────────────
# ENTRY POINT FOR main.py
# ─────────────────────────────────────────────
def play(nfc, np, buz, enow=None):
    """
    Called from main.py when "colorquest" tag is tapped.
    Runs game rounds until "stop" tag is scanned.
    If enow is None, creates its own ESP-NOW instance.
    """
    own_enow = False
    if enow is None:
        enow = espnow_init()
        own_enow = True

    display = GameDisplay(np)
    display.clear()
    espnow_targets = None

    print("\n  === ENTERING COLOR QUEST MODE ===")
    print("  Tap STOP tag to return to programming\n")
    buz.beep(523, 80)
    time.sleep_ms(40)
    buz.beep(784, 80)
    time.sleep_ms(40)
    buz.beep(1047, 120)

    try:
        while True:
            targets, from_espnow = wait_for_commands(enow, display, nfc, espnow_targets)

            if targets == "stop":
                display.clear()
                print("\n  === RETURNING TO PROGRAMMING MODE ===\n")
                return

            if from_espnow:
                espnow_targets = list(targets)

            display.clear()
            time.sleep_ms(200)

            while True:
                result = run_game(nfc, buz, display, targets, enow)

                if result == "reset":
                    display.clear()
                    time.sleep_ms(300)
                    continue

                elif result == "stop":
                    display.clear()
                    print("\n  === RETURNING TO PROGRAMMING MODE ===\n")
                    return

                elif result == "win":
                    print("\n  Waiting for next round...\n")
                    time.sleep_ms(1000)
                    break

                elif isinstance(result, list):
                    espnow_targets = list(result)
                    targets = result
                    display.clear()
                    time.sleep_ms(200)
                    continue
    finally:
        display.clear()
        if own_enow:
            try:
                enow.active(False)
            except Exception:
                pass


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "=" * 45)
    print("  Color Quest — NFC Tag Scavenger Hunt")
    print("  Tap colors in the right order to win!")
    print("=" * 45)

    # Hardware init
    i2c = machine.SoftI2C(
        sda=machine.Pin(I2C_SDA),
        scl=machine.Pin(I2C_SCL),
        freq=100_000,
    )
    np = NeoPixel(machine.Pin(NEOPIXEL_PIN), NUM_LEDS)
    buz = Buzzer(BUZZER_PIN)
    display = GameDisplay(np)
    display.clear()

    # NFC init
    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d — NFC ready" % (ic, ver, rev))
    except Exception as e:
        print("  NFC init failed: %s" % str(e))
        return

    # ESP-NOW init
    enow = espnow_init()
    buz.beep(600, 50)
    time.sleep_ms(30)
    buz.beep(900, 50)

    # Game loop — play rounds until power off
    espnow_targets = None

    while True:
        try:
            targets, from_espnow = wait_for_commands(enow, display, nfc, espnow_targets)

            if targets == "stop":
                # In standalone mode, stop just goes back to waiting
                display.clear()
                print("\n  Stopped. Waiting for next round...\n")
                time.sleep_ms(500)
                continue

            if from_espnow:
                espnow_targets = list(targets)

            display.clear()
            time.sleep_ms(200)

            while True:
                result = run_game(nfc, buz, display, targets, enow)

                if result == "reset":
                    display.clear()
                    time.sleep_ms(300)
                    continue

                elif result == "stop":
                    # In standalone mode, stop just goes back to waiting
                    display.clear()
                    print("\n  Stopped. Waiting for next round...\n")
                    time.sleep_ms(500)
                    break

                elif result == "win":
                    print("\n  Waiting for next round...\n")
                    time.sleep_ms(1000)
                    break

                elif isinstance(result, list):
                    espnow_targets = list(result)
                    targets = result
                    display.clear()
                    time.sleep_ms(200)
                    continue

        except KeyboardInterrupt:
            display.clear()
            print("\n  Exiting.")
            break
        except Exception as e:
            print("  [ERR]: %s" % str(e))
            time.sleep_ms(1000)

if __name__ == "__main__":
    main()