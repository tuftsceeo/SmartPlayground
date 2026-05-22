"""
Color Quest — ESP-NOW Receiver Game for Wand Module

Receives a color sequence via ESP-NOW from the 4-reader hub; player must
find & tap matching NFC tags in order.

5x5 Matrix: row 0 = targets, rows 1-3 = animation, row 4 = collected.
Rescan tag re-requests sequence from station (debounced per placement).
Button: ignored during play; triggers rainbow after a win.

Requires /lib/: pn532.py, nfc_reader.py, buzzer.py

Entry points:
    play(nfc, leds, buz, accel, i2c, enow)  — called from main.py
    main()                             — standalone testing
"""

import machine, time, math, json
from machine import Pin
from neopixel import NeoPixel

from espnow_manager import ESPNowManager
from pn532 import PN532
from nfc_reader import read_ndef_text as read_tag_text
from buzzer import Buzzer
from target import SCORE_MAC

# Hardware
I2C_SDA, I2C_SCL = 22, 23
NEOPIXEL_PIN, NUM_LEDS = 20, 25
BUZZER_PIN, SWITCH_PIN = 19, 0
PN532_ADDR = 0x24

# 5x5 grid: 0-4 targets, 5-19 animation, 20-24 collected
def rc(row, col): return row * 5 + col

def target_slots(n):
    if n <= 0: return []
    off = (5 - n) // 2
    return [rc(0, off + i) for i in range(n)]

def found_slots(n):
    if n <= 0: return []
    off = (5 - n) // 2
    return [rc(4, off + i) for i in range(n)]

CROSS_LEDS  = [6, 8, 16, 17, 18, 20, 24]
MIDDLE_LEDS = list(range(5, 20))
PERIMETER   = [0, 1, 2, 3, 4, 9, 14, 19, 24, 23, 22, 21, 20, 15, 10, 5]
SMILEY_LEDS = [6, 8, 15, 19, 21, 22, 23]

# Import library colors — auto-scale with ambient brightness via leds.np
from leds import (
    OFF, RED, GREEN, BLUE, PURPLE, PINK, YELLOW, WHITE,
    RED_DIM, GREEN_DIM, BLUE_DIM, YELLOW_DIM, WHITE_DIM, PINK_DIM, PURPLE_DIM, AMBER_DIM,
)

# Map action names to library colors
COLOR_BRIGHT = {
    "turnred":    RED,
    "turngreen":  GREEN,
    "turnblue":   BLUE,
    "turnpurple": PURPLE,
    "turnpink":   PINK,
    "turnyellow": YELLOW,
    "turnwhite":  WHITE,
    "turnoff":    OFF,
}
COLOR_DIM = {
    "turnred":    RED_DIM,
    "turngreen":  GREEN_DIM,
    "turnblue":   BLUE_DIM,
    "turnpurple": PURPLE_DIM,
    "turnpink":   PINK_DIM,
    "turnyellow": YELLOW_DIM,
    "turnwhite":  WHITE_DIM,
    "turnoff":    OFF,
}

RED_X          = RED_DIM
GREEN_WIN      = GREEN_DIM
SMILEY_DEFAULT = AMBER_DIM

RESCAN_TAG    = "color_quest_scan"

# Rescan state: debounce per placement + waiting-animation flag
_last_rescan_uid = None
_awaiting_scan_reply = False


def _rescan_seen(enow, uid):
    """Send scan_request once per physical placement."""
    global _last_rescan_uid, _awaiting_scan_reply
    if uid == _last_rescan_uid:
        return False
    _last_rescan_uid = uid
    try:
        enow.broadcast({"type": "scan_request"})
        _awaiting_scan_reply = True
        print("  RESCAN tag — scan_request sent (awaiting reply)")
        return True
    except Exception as ex:
        print("  scan_request send err: %s" % str(ex))
        return False


def _rescan_cleared():
    """Re-arm debounce; cancel waiting animation."""
    global _last_rescan_uid, _awaiting_scan_reply
    _last_rescan_uid = None
    _awaiting_scan_reply = False


def _rescan_reply_received():
    """Reply landed: stop waiting animation, keep debounce set."""
    global _awaiting_scan_reply
    _awaiting_scan_reply = False


def _beep_stop(buz):
    buz.beep(800, 80); time.sleep_ms(30); buz.beep(400, 200)


def _beep_new(buz):
    buz.beep(600, 50); time.sleep_ms(30); buz.beep(900, 50)


class GameDisplay:
    def __init__(self, np):
        self.np = np

    def clear(self):
        self.np.fill(OFF)
        self.np.write()

    def clear_middle(self):
        for i in MIDDLE_LEDS:
            self.np[i] = OFF
        self.np.write()

    def show_game_state(self, targets, found_count, pulse_frame=0):
        """Draw targets (row 0), glow (rows 1-3), collected (row 4)."""
        n = len(targets)
        t_slots = target_slots(n)
        f_slots = found_slots(n)

        for i in range(5):
            self.np[i] = OFF
            self.np[20 + i] = OFF

        for i, cmd in enumerate(targets):
            bright = COLOR_BRIGHT.get(cmd, OFF)
            dim    = COLOR_DIM.get(cmd, OFF)
            if i < found_count:
                self.np[t_slots[i]] = bright
                self.np[f_slots[i]] = bright
            elif i == found_count:
                pulse = (math.sin(pulse_frame * 0.15) + 1) / 2
                scale = 0.3 + 0.7 * pulse
                self.np[t_slots[i]] = (
                    int(bright[0] * scale),
                    int(bright[1] * scale),
                    int(bright[2] * scale),
                )
            else:
                self.np[t_slots[i]] = dim

        if found_count < n:
            current = COLOR_BRIGHT.get(targets[found_count], OFF)
            breath = (math.sin(pulse_frame * 0.08) + 1) / 2
            for i in MIDDLE_LEDS:
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
        """Animate middle rows during NFC scan; preserve game rows."""
        self.show_game_state(targets, found_count)
        ring = frame % 5
        for row in range(1, 4):
            for col in range(5):
                idx = rc(row, col)
                dist = abs(col - 2) + abs(row - 2)
                if dist == ring:
                    self.np[idx] = (15, 10, 20)
                elif dist == max(0, ring - 1):
                    self.np[idx] = (5, 3, 7)
                else:
                    self.np[idx] = OFF
        self.np.write()

    def show_smiley(self, cmd=None, hold_ms=1000):
        """Smiley face in given color, blocking for hold_ms."""
        color = COLOR_BRIGHT.get(cmd, SMILEY_DEFAULT)
        self.np.fill(OFF)
        for idx in SMILEY_LEDS:
            self.np[idx] = color
        self.np.write()
        time.sleep_ms(hold_ms)

    def show_wrong(self):
        for _ in range(3):
            for i in range(NUM_LEDS):
                self.np[i] = RED_X if i in CROSS_LEDS else OFF
            self.np.write()
            time.sleep_ms(200)
            self.clear()
            time.sleep_ms(120)

    def show_win_green(self):
        for step in range(15):
            self.np.fill((0, min(step * 4, 50), 0))
            self.np.write()
            time.sleep_ms(40)
        time.sleep_ms(500)

    def solid_green(self):
        self.np.fill(GREEN_WIN)
        self.np.write()

    def rainbow_dance(self, duration_ms=3000):
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < duration_ms:
            t = time.ticks_diff(time.ticks_ms(), start)
            for i in range(NUM_LEDS):
                hue = ((i * 255 // NUM_LEDS) + t // 4) % 255
                self.np[i] = self._hsv(hue, 255, 35)
            self.np.write()
            time.sleep_ms(20)

    def show_waiting(self, frame):
        """Breathing blue while waiting for ESP-NOW broadcast."""
        brightness = int((math.sin(frame * 0.08) + 1) * 12)
        self.np.fill((0, 0, brightness))
        self.np.write()

    def show_scan_waiting(self):
        """Time-based purple spinner on perimeter (~1.28s/rotation)."""
        pos = (time.ticks_ms() // 80) % len(PERIMETER)
        self.np.fill(OFF)
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


def send_score(enow, targets, elapsed_ms):
    mac_str = ':'.join('%02X' % b for b in SCORE_MAC)
    ok = enow.send_to(mac_str, {
        "type": "score",
        "colors": targets,
        "time_ms": elapsed_ms,
        "time_s": round(elapsed_ms / 1000, 2),
    })
    if ok:
        print("  Score sent: %.2fs -> %s" % (elapsed_ms / 1000, mac_str))
    else:
        print("  Score send error")


def _colors_from_data(data):
    if not isinstance(data, list):
        return None
    colors = [c for c in data if c in COLOR_BRIGHT]
    return colors if colors else None


def wait_for_commands(enow, display, nfc, last_espnow=None):
    """Block until commands arrive. Returns (targets, from_espnow) or ('stop', False)."""
    if last_espnow:
        print("Waiting for new sequence (button = replay last)...")
    else:
        print("Waiting for color sequence (button = random quest)...")
    print("  Tap STOP tag or send \"stop\" via ESP-NOW to exit")
    print("  Tap %s tag to request a new sequence from the station\n" % RESCAN_TAG)
    btn = Pin(SWITCH_PIN, Pin.IN, Pin.PULL_UP)
    frame = 0

    while True:
        if _awaiting_scan_reply:
            display.show_scan_waiting()
        else:
            display.show_waiting(frame)
        frame += 1

        msg_type, data, _ = enow.poll(50)
        if msg_type == "stop":
            print("  ESP-NOW: stop received")
            _rescan_reply_received()
            return "stop", False
        if msg_type == "colors":
            colors = _colors_from_data(data)
            if colors:
                print("Received: %s" % str(colors))
                _rescan_reply_received()
                return colors, True

        if frame % 10 == 0:
            text, uid = read_tag_text(nfc)
            if uid is None:
                _rescan_cleared()
            elif text == RESCAN_TAG:
                _rescan_seen(enow, uid)
            elif text == "stop":
                print("  STOP tag detected")
                return "stop", False
            else:
                _rescan_cleared()

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


def _post_win_wait(enow, display, nfc, buz):
    """Hold victory state. Button=rainbow, stop=exit, new colors=next round."""
    print("\n  Victory! Press button for rainbow, tap %s for next round, stop to exit\n" % RESCAN_TAG)

    btn = Pin(SWITCH_PIN, Pin.IN, Pin.PULL_UP)
    last_btn = btn.value()
    last_uid = None
    frame = 0
    prev_awaiting = False
    _rescan_cleared()

    while True:
        # Spinner needs every-frame redraw; green is static — only redraw on transition out.
        awaiting_now = _awaiting_scan_reply
        if awaiting_now:
            display.show_scan_waiting()
        elif prev_awaiting:
            display.solid_green()
        prev_awaiting = awaiting_now

        cur = btn.value()
        if last_btn == 1 and cur == 0:
            time.sleep_ms(30)
            if btn.value() == 0:
                while btn.value() == 0:
                    time.sleep_ms(10)
                print("  Button pressed — rainbow!")
                display.rainbow_dance(5000)
                if not _awaiting_scan_reply:
                    display.solid_green()
        last_btn = cur

        msg_type, data, _ = enow.poll(0)
        if msg_type == "stop":
            print("  ESP-NOW: stop received")
            _beep_stop(buz)
            _rescan_reply_received()
            display.clear()
            return "stop"
        if msg_type == "colors":
            colors = _colors_from_data(data)
            if colors:
                print("  NEW SEQUENCE received: %s" % str(colors))
                _beep_new(buz)
                _rescan_reply_received()
                display.clear()
                return colors

        # NDEF read is slow — don't do it every frame
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
                    _rescan_seen(enow, tag['uid_hex'])
                elif text == "stop":
                    print("  STOP tag — exiting")
                    _beep_stop(buz)
                    display.clear()
                    return "stop"

        frame += 1
        time.sleep_ms(20)


def run_game(nfc, buz, display, targets, enow, start_ticks=None):
    """Main game loop. Returns 'stop' or new targets list."""
    n = len(targets)
    found = 0
    last_uid = None
    frame = 0

    if start_ticks is None:
        start_ticks = time.ticks_ms()

    print("\n  === COLOR QUEST ===")
    print("  Find these colors in order:")
    for i, t in enumerate(targets):
        print("    %d. %s" % (i + 1, t))
    print()

    # Opening fanfare
    buz.beep(523, 80); time.sleep_ms(40)
    buz.beep(659, 80); time.sleep_ms(40)
    buz.beep(784, 120); time.sleep_ms(200)

    display.clear()

    while found < n:
        msg_type, data, _ = enow.poll(0)
        if msg_type == "stop":
            print("  ESP-NOW: stop received")
            _beep_stop(buz)
            _rescan_reply_received()
            display.clear()
            return "stop"
        if msg_type == "colors":
            colors = _colors_from_data(data)
            if colors:
                print("  NEW SEQUENCE received: %s" % str(colors))
                _beep_new(buz)
                _rescan_reply_received()
                return colors

        if _awaiting_scan_reply:
            display.show_scan_waiting()
        else:
            display.show_game_state(targets, found, frame)
        frame += 1

        tag = nfc.read_passive_target(timeout=150)

        if tag is None:
            if last_uid is not None:
                last_uid = None
            _rescan_cleared()
            time.sleep_ms(30)
            continue

        if tag['uid_hex'] == last_uid:
            time.sleep_ms(30 if _awaiting_scan_reply else 100)
            continue

        last_uid = tag['uid_hex']

        print("  Tag detected: %s" % tag['uid_hex'])
        buz.beep(800, 30)

        for f in range(12):
            display.scan_animate(f, targets, found)
            time.sleep_ms(60)

        text, uid = read_tag_text(nfc)

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

        # Rescan tag — request new sequence; spinner is the ack
        if text == RESCAN_TAG:
            _rescan_seen(enow, tag['uid_hex'])
            continue

        _rescan_cleared()

        if text == "stop":
            print("  STOP tag — exiting game")
            _beep_stop(buz)
            display.clear()
            return "stop"

        expected = targets[found]

        if text == expected:
            found += 1
            print("  CORRECT! (%d/%d)" % (found, n))
            buz.beep(880, 60); time.sleep_ms(30); buz.beep(1100, 80)
            display.show_smiley(text)
            display.show_game_state(targets, found)
        else:
            print("  WRONG! Expected '%s', got '%s'" % (expected, text))
            buz.beep(400, 150); time.sleep_ms(60); buz.beep(250, 250)
            display.show_wrong()
            display.show_game_state(targets, found)
            time.sleep_ms(300)

    # WIN
    elapsed_ms = time.ticks_diff(time.ticks_ms(), start_ticks)
    print("\n  ALL COLORS FOUND!")
    print("  Time: %.2f seconds" % (elapsed_ms / 1000))

    send_score(enow, targets, elapsed_ms)

    # Victory fanfare
    buz.beep(523, 100); time.sleep_ms(50)
    buz.beep(659, 100); time.sleep_ms(50)
    buz.beep(784, 100); time.sleep_ms(50)
    buz.beep(1047, 300)

    display.rainbow_dance(5000)
    display.show_win_green()
    return _post_win_wait(enow, display, nfc, buz)


def play(nfc, leds, buz, accel, i2c, enow):
    """Called from main.py when 'colorquest' tag is tapped."""
    np = leds.np
    display = GameDisplay(np)
    display.clear()
    espnow_targets = None
    _rescan_cleared()

    print("\n  === ENTERING COLOR QUEST MODE ===")
    print("  Tap STOP tag to return to programming\n")
    buz.beep(523, 80); time.sleep_ms(40)
    buz.beep(784, 80); time.sleep_ms(40)
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


def main():
    print("\n" + "=" * 45)
    print("  Color Quest — NFC Tag Scavenger Hunt")
    print("  Tap colors in the right order to win!")
    print("=" * 45)

    i2c = machine.SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100_000)
    
    # Calibrate brightness from ambient light sensor
    import brightness
    try:
        from opt3002 import OPT3002
        light = OPT3002(i2c)
        light.init()
        m, lux = brightness.calibrate(light)
        if lux is not None:
            print("  Light: %.0f lux -> brightness x%.2f" % (lux, m))
    except Exception as e:
        print("  [WARN] OPT3002: %s — brightness x1.00" % e)
    
    from leds import Leds
    leds = Leds()
    np = leds.np
    buz = Buzzer(BUZZER_PIN)
    display = GameDisplay(np)
    display.clear()

    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d — NFC ready" % (ic, ver, rev))
    except Exception as e:
        print("  NFC init failed: %s" % str(e))
        return

    enow = ESPNowManager()
    enow.init()
    _beep_new(buz)

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
