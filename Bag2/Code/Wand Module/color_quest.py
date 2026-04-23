"""
Color Quest — ESP-NOW Receiver Game for Wand Module
=====================================================
Receives a color sequence via ESP-NOW from the 4-reader hub,
then the player must find & tap matching NFC tags in order.

5x5 LED Matrix Layout:
  Row 0 (top):    Target color sequence (dim = upcoming, bright = done)
  Rows 1-3:       Scan animation / effects area
  Row 4 (bottom): Colors collected so far (bright)

Rescan support: tapping the "color_quest_scan" tag sends an ESP-NOW
scan_request to the Programming Station. While the card is held the
wand shows a rotating spinner on the matrix perimeter. The
scan_request is only sent once per physical placement — the wand must
be lifted and replaced to resend. When the station's reply arrives,
the usual "new sequence" beeps fire and the new round starts.

Button behavior:
  During active play      — ignored
  After a successful win  — triggers a 5-second rainbow dance (repeatable)

Requires /lib/: pn532.py, nfc_reader.py, buzzer.py
"""

import machine
import network
import espnow
import time
import math
import json
import random
from machine import Pin
from neopixel import NeoPixel

from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
from nfc_reader import _decode_ndef_text, COMMON_KEYS
from buzzer import Buzzer
from target import SCORE_MAC

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

# Perimeter LEDs, clockwise from top-left — used by the scan-wait spinner
PERIMETER = [0, 1, 2, 3, 4, 9, 14, 19, 24, 23, 22, 21, 20, 15, 10, 5]

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
# RESCAN TAG — triggers a fresh scan request to the station
# ─────────────────────────────────────────────
RESCAN_TAG = "color_quest_scan"
BROADCAST_MAC = b'\xFF\xFF\xFF\xFF\xFF\xFF'

# Module-level state:
#
# _last_rescan_uid — debounce. Set to the rescan tag's UID when a request
#   is sent; cleared on card removal or non-rescan tag read. Prevents
#   duplicate sends while the card is held across round transitions.
#
# _awaiting_scan_reply — True while the wand has sent a scan_request and
#   is waiting for the station's colors reply. Controls the waiting
#   animation on the matrix. Cleared when the reply arrives OR when the
#   card is removed (user canceled).

_last_rescan_uid = None
_awaiting_scan_reply = False


def _rescan_seen(enow, uid):
    """
    Called when the rescan tag is read. Sends a scan_request exactly once
    per physical placement. Returns True if a request was sent this call,
    False if suppressed because the same placement was already processed
    or because the send itself failed.
    """
    global _last_rescan_uid, _awaiting_scan_reply
    if uid == _last_rescan_uid:
        return False  # already sent for this placement; waiting for lift
    _last_rescan_uid = uid
    try:
        enow.send(BROADCAST_MAC, json.dumps({"type": "scan_request"}))
        _awaiting_scan_reply = True
        print("  RESCAN tag — scan_request sent (awaiting reply)")
        return True
    except Exception as ex:
        print("  scan_request send err: %s" % str(ex))
        return False


def _rescan_cleared():
    """Arm the debounce for a new placement. Called when the reader
    reports no tag, when a non-rescan tag is read, or at session start.
    Also cancels any in-flight waiting animation — the player lifted
    the card without a reply arriving."""
    global _last_rescan_uid, _awaiting_scan_reply
    _last_rescan_uid = None
    _awaiting_scan_reply = False


def _rescan_reply_received():
    """The station's reply landed. Clear the waiting animation flag but
    leave the debounce set — if the player is still holding the rescan
    card into the new round, we don't want to immediately resend."""
    global _awaiting_scan_reply
    _awaiting_scan_reply = False


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

    def solid_green(self):
        """Static green hold — used between rainbow bursts in victory state."""
        for i in range(NUM_LEDS):
            self.np[i] = GREEN_WIN
        self.np.write()

    def rainbow_dance(self, duration_ms=3000):
        """Rainbow cycle across all 25 LEDs for a fixed duration."""
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
        """Breathing blue while waiting for ESP-NOW (operator broadcast)."""
        brightness = int((math.sin(frame * 0.08) + 1) * 12)
        for i in range(NUM_LEDS):
            self.np[i] = (0, 0, brightness)
        self.np.write()

    def show_scan_waiting(self):
        """Rotating spinner on the matrix perimeter with a fading tail —
        shown while a scan_request is in flight to the Programming Station.

        Time-based (uses time.ticks_ms()) so the animation speed is
        independent of the calling loop's frame rate. The NFC polling
        path can drop frame rate to ~7fps and this still looks like
        an active animation.
        """
        # 80ms per LED step × 16 LEDs = 1.28 sec per full rotation
        pos = (time.ticks_ms() // 80) % len(PERIMETER)
        for i in range(NUM_LEDS):
            self.np[i] = OFF
        # Head + 3-LED fading tail — purple (red + blue)
        for offset, level in enumerate((40, 24, 12, 5)):
            led_idx = PERIMETER[(pos - offset) % len(PERIMETER)]
            self.np[led_idx] = (level // 2, 0, level)
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
# EXTERNAL ANTENNA CONFIG
# ─────────────────────────────────────────────
def _configure_external_antenna():
    """Switch to external antenna before WiFi activation."""
    wifi_en = Pin(3, Pin.OUT)
    ant_cfg = Pin(14, Pin.OUT)
    wifi_en.value(0)
    time.sleep_ms(100)
    ant_cfg.value(1)  # External antenna


# ─────────────────────────────────────────────
# ESP-NOW RECEIVER
# ─────────────────────────────────────────────
def espnow_init():
    _configure_external_antenna()
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.disconnect()
    e = espnow.ESPNow()
    e.active(True)
    # Add score target peer
    try:
        e.add_peer(SCORE_MAC)
    except Exception:
        pass
    # Also add broadcast — needed both to receive station broadcasts and
    # to send the scan_request.
    if SCORE_MAC != BROADCAST_MAC:
        try:
            e.add_peer(BROADCAST_MAC)
        except Exception:
            pass
    print("ESP-NOW listening...")
    return e


def send_score(enow, targets, elapsed_ms):
    """Send timing result to the scoreboard."""
    result = {
        "type": "score",
        "colors": targets,
        "time_ms": elapsed_ms,
        "time_s": round(elapsed_ms / 1000, 2),
    }
    msg = json.dumps(result)
    try:
        enow.send(SCORE_MAC, msg)
        print("  Score sent: %.2fs -> %s" % (
            elapsed_ms / 1000,
            ':'.join('%02X' % b for b in SCORE_MAC)))
    except Exception as ex:
        print("  Score send error: %s" % str(ex))


# ─────────────────────────────────────────────
# SHARED ESP-NOW PARSING
# ─────────────────────────────────────────────
def _parse_incoming(msg):
    """Decode an ESP-NOW message payload. Returns one of:
      ("stop", None), ("colors", [list]), (None, None)
    """
    try:
        raw = msg.decode('utf-8').strip()
    except Exception:
        return None, None
    if raw.lower() in ('"stop"', 'stop'):
        return "stop", None
    try:
        commands = json.loads(raw)
    except Exception:
        return None, None
    if isinstance(commands, list) and len(commands) > 0:
        if "stop" in commands:
            return "stop", None
        colors = [c for c in commands if c in COLOR_BRIGHT]
        if colors:
            return "colors", colors
    return None, None


def wait_for_commands(enow, display, nfc, last_espnow=None):
    """
    Block until we receive a command source.
    Returns (targets_list, from_espnow_bool) or ("stop", False) to exit.
    """
    if last_espnow:
        print("Waiting for new sequence (button = replay last)...")
    else:
        print("Waiting for color sequence (button = random quest)...")
    print("  Tap STOP tag or send \"stop\" via ESP-NOW to exit")
    print("  Tap %s tag to request a new sequence from the station\n" % RESCAN_TAG)
    btn = machine.Pin(SWITCH_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    frame = 0

    while True:
        # Spinner while the wand has a scan_request pending; breathing
        # blue otherwise (the general "waiting for any sequence" state).
        if _awaiting_scan_reply:
            display.show_scan_waiting()
        else:
            display.show_waiting(frame)
        frame += 1

        # Check ESP-NOW
        host, msg = enow.irecv(50)
        if msg:
            kind, payload = _parse_incoming(msg)
            if kind == "stop":
                print("  ESP-NOW: stop received")
                _rescan_reply_received()
                return "stop", False
            if kind == "colors":
                print("Received: %s" % str(payload))
                _rescan_reply_received()
                return payload, True

        # Check NFC every ~0.5s for stop or rescan
        if frame % 10 == 0:
            text, uid = read_tag_text(nfc)
            if uid is None:
                # Tag lifted — re-arm the rescan debounce
                _rescan_cleared()
            elif text == RESCAN_TAG:
                _rescan_seen(enow, uid)
                # Reply will arrive as a colors list on a subsequent ESP-NOW
                # poll above and return from this function.
            elif text == "stop":
                print("  STOP tag detected")
                return "stop", False
            else:
                # Some other tag — re-arm so a later rescan tap fires fresh
                _rescan_cleared()

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
                    print("  Button pressed — no sequence received yet, waiting...")


# ─────────────────────────────────────────────
# POST-WIN WAIT — button triggers rainbow, rescan/stop/new colors exit
# ─────────────────────────────────────────────
def _post_win_wait(enow, display, nfc, buz):
    """Holds the victory green state after a win. Returns to caller on:
      - Stop tag / ESP-NOW stop         -> "stop"
      - ESP-NOW new colors list         -> that list
    Button press plays a 5-second rainbow dance and returns to holding
    green. The rescan tag sends a scan_request (debounced) and switches
    to the scan-waiting spinner until the reply arrives or the card is lifted.
    """
    print("\n  Victory! Press button for rainbow, tap %s for next round, stop to exit\n" % RESCAN_TAG)

    btn = machine.Pin(SWITCH_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    # Initialize to current state so a button still held from the last
    # color tap (unlikely but possible) doesn't trigger a rainbow.
    last_btn = btn.value()
    last_uid = None
    frame = 0
    prev_awaiting = False

    # Clear stale rescan state so the first post-win tap fires.
    _rescan_cleared()

    while True:
        # ── Render: spinner when scan reply pending, else solid green.
        # Green is static — only redraw on the transition out of waiting.
        # Spinner needs to be redrawn every frame.
        awaiting_now = _awaiting_scan_reply
        if awaiting_now:
            display.show_scan_waiting()
        elif prev_awaiting:
            display.solid_green()
        prev_awaiting = awaiting_now

        # ── Button: trigger 5s rainbow on rising edge of press ──
        cur = btn.value()
        if last_btn == 1 and cur == 0:
            time.sleep_ms(30)  # debounce
            if btn.value() == 0:
                while btn.value() == 0:
                    time.sleep_ms(10)
                print("  Button pressed — rainbow!")
                display.rainbow_dance(5000)
                # After the rainbow, restore whichever state we're in.
                if not _awaiting_scan_reply:
                    display.solid_green()
                # If awaiting, the next loop iter's render will redraw the
                # spinner on top of the rainbow's final frame.
        last_btn = cur

        # ── ESP-NOW: new colors or stop ──
        host, msg = enow.irecv(0)
        if msg:
            kind, payload = _parse_incoming(msg)
            if kind == "stop":
                print("  ESP-NOW: stop received")
                buz.beep(800, 80); time.sleep_ms(30); buz.beep(400, 200)
                _rescan_reply_received()
                display.clear()
                return "stop"
            if kind == "colors":
                print("  NEW SEQUENCE received: %s" % str(payload))
                buz.beep(600, 50); time.sleep_ms(30); buz.beep(900, 50)
                _rescan_reply_received()
                display.clear()
                return payload

        # ── NFC: rescan or stop (checked periodically) ──
        # Full NDEF read takes ~500ms+ — don't do it every frame or the
        # loop stalls and the button feels sluggish.
        if frame % 15 == 0:
            tag = nfc.read_passive_target(timeout=100)
            if tag is None:
                if last_uid is not None:
                    last_uid = None
                _rescan_cleared()
            elif tag['uid_hex'] != last_uid:
                last_uid = tag['uid_hex']
                text, _uid = read_tag_text(nfc)
                if text == RESCAN_TAG:
                    # Send quietly — the spinner taking over is the ack.
                    _rescan_seen(enow, tag['uid_hex'])
                elif text == "stop":
                    print("  STOP tag — exiting")
                    buz.beep(800, 80); time.sleep_ms(30); buz.beep(400, 200)
                    display.clear()
                    return "stop"
                # Any other tag is ignored during victory

        frame += 1
        time.sleep_ms(20)


# ─────────────────────────────────────────────
# GAME LOOP
# ─────────────────────────────────────────────
def run_game(nfc, buz, display, targets, enow, start_ticks=None):
    """
    Main game: find and tap NFC tags in the correct color order.

    start_ticks: time.ticks_ms() when sequence was received (for timing).
    Returns:
      "stop"  — stop tag tapped (during game or during post-win wait)
      list    — new ESP-NOW sequence received (during game or after win)

    Button presses during active play are ignored. After a win, the button
    triggers a 5-second rainbow dance in the post-win wait state. While a
    rescan card is held on the wand, the matrix shows a rotating spinner
    instead of the game state.
    """
    n = len(targets)
    found = 0
    last_uid = None
    frame = 0

    # Start timer if not already running
    if start_ticks is None:
        start_ticks = time.ticks_ms()

    print("\n  === COLOR QUEST ===")
    print("  Find these colors in order:")
    for i, t in enumerate(targets):
        print("    %d. %s" % (i + 1, t))
    print()

    # Opening fanfare
    buz.beep(523, 80)
    time.sleep_ms(40)
    buz.beep(659, 80)
    time.sleep_ms(40)
    buz.beep(784, 120)
    time.sleep_ms(200)

    display.clear()

    while found < n:
        # ── Check for new ESP-NOW sequence or stop ──
        host, msg = enow.irecv(0)
        if msg:
            kind, payload = _parse_incoming(msg)
            if kind == "stop":
                print("  ESP-NOW: stop received")
                buz.beep(800, 80); time.sleep_ms(30); buz.beep(400, 200)
                _rescan_reply_received()
                display.clear()
                return "stop"
            if kind == "colors":
                print("  NEW SEQUENCE received: %s" % str(payload))
                buz.beep(600, 50); time.sleep_ms(30); buz.beep(900, 50)
                _rescan_reply_received()
                return payload

        # ── Render: scan-waiting spinner when a scan_request is pending,
        # otherwise the normal game state. ──
        if _awaiting_scan_reply:
            display.show_scan_waiting()
        else:
            display.show_game_state(targets, found, frame)
        frame += 1

        # Quick tag detection
        tag = nfc.read_passive_target(timeout=150)

        if tag is None:
            if last_uid is not None:
                last_uid = None
            # Lifted — re-arm debounce and cancel any waiting animation
            _rescan_cleared()
            time.sleep_ms(30)
            continue

        # Same tag still on reader — skip
        if tag['uid_hex'] == last_uid:
            # Shorter sleep while the spinner is animating so the motion
            # stays smooth; longer sleep otherwise to keep CPU low.
            time.sleep_ms(30 if _awaiting_scan_reply else 100)
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

        # ── Rescan tag — request a new sequence from the station ──
        # Debounced: only fires on fresh placement. The next loop iteration
        # will render the spinner because _awaiting_scan_reply is now set.
        # No confirmation beep — the spinner is the ack.
        if text == RESCAN_TAG:
            _rescan_seen(enow, tag['uid_hex'])
            continue

        # Any other successful read — re-arm so a later rescan tap fires fresh
        _rescan_cleared()

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
    elapsed_ms = time.ticks_diff(time.ticks_ms(), start_ticks)
    elapsed_s = elapsed_ms / 1000

    print("\n  ALL COLORS FOUND!")
    print("  Time: %.2f seconds" % elapsed_s)

    # Send score
    send_score(enow, targets, elapsed_ms)

    # Victory fanfare
    buz.beep(523, 100)
    time.sleep_ms(50)
    buz.beep(659, 100)
    time.sleep_ms(50)
    buz.beep(784, 100)
    time.sleep_ms(50)
    buz.beep(1047, 300)

    # Fade-in to solid green victory display, then enter the post-win wait.
    display.show_win_green()
    return _post_win_wait(enow, display, nfc, buz)


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

    # Clear any stale rescan debounce from a previous session
    _rescan_cleared()

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
            start_ticks = time.ticks_ms()

            while True:
                result = run_game(nfc, buz, display, targets, enow, start_ticks)

                if result == "stop":
                    display.clear()
                    print("\n  === RETURNING TO PROGRAMMING MODE ===\n")
                    return

                elif isinstance(result, list):
                    espnow_targets = list(result)
                    targets = result
                    start_ticks = time.ticks_ms()
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
                display.clear()
                print("\n  Stopped. Waiting for next round...\n")
                time.sleep_ms(500)
                continue

            if from_espnow:
                espnow_targets = list(targets)

            display.clear()
            time.sleep_ms(200)
            start_ticks = time.ticks_ms()

            while True:
                result = run_game(nfc, buz, display, targets, enow, start_ticks)

                if result == "stop":
                    display.clear()
                    print("\n  Stopped. Waiting for next round...\n")
                    time.sleep_ms(500)
                    break

                elif isinstance(result, list):
                    espnow_targets = list(result)
                    targets = result
                    start_ticks = time.ticks_ms()
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