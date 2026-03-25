"""
Freeze Dance — ESP-NOW Multiplayer Motion Game for Wand Module
================================================================
All wands run the same code. On entry, each player taps either
a CALLER or PLAYER tag to choose their role.

  Caller:  Scans GO / FREEZE tags to control all player wands.
           LED shows amber pulse. Not motion-checked.
  Player:  Dances during GO, must freeze during FREEZE.
           If caught moving → OUT for 30 seconds, then auto-rejoins.

ESP-NOW messages are plain byte strings (no JSON) for speed:
  FD_GO, FD_FREEZE, FD_RESET, stop

Tap STOP tag or receive "stop" via ESP-NOW to exit back to
programming mode.

Requires /lib/: pn532.py, nfc_reader.py, buzzer.py, lis2dw12.py

Entry point — called from main.py:
    from freeze_dance import play
    play(nfc, leds, buz, accel, i2c)
"""

import machine
import network
import espnow
import time
import math
from machine import Pin
from neopixel import NeoPixel

from pn532 import PN532
from nfc_reader import NfcReader, _decode_ndef_text, COMMON_KEYS
from pn532 import MIFARE_AUTH_A, MIFARE_AUTH_B
from buzzer import Buzzer

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
NUM_LEDS = 25
BROADCAST = b'\xFF\xFF\xFF\xFF\xFF\xFF'

# ESP-NOW message bytes
MSG_GO     = b"FD_GO"
MSG_FREEZE = b"FD_FREEZE"
MSG_RESET  = b"FD_RESET"
MSG_STOP   = b"stop"

# NFC commands recognized inside the game
GAME_COMMANDS = {"caller", "player", "go", "freeze", "stop"}

# Game states
STATE_ROLE_SELECT = 0
STATE_READY       = 1
STATE_GO          = 2
STATE_FREEZE      = 3
STATE_OUT         = 4

# Motion detection tuning
MOVE_THRESHOLD   = 0.70   # sum of axis deltas in g
MOVE_HITS_NEEDED = 2      # consecutive frames above threshold
FREEZE_GRACE_MS  = 1000   # grace period after FREEZE before checking
OUT_DURATION_MS  = 30_000 # time-out penalty

# Timing
LOOP_DELAY_MS         = 40
REPEAT_SCAN_GUARD_MS  = 1200

# 5x5 grid X pattern indices
X_INDICES = [0, 4, 6, 8, 12, 16, 18, 20, 24]


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
# ESP-NOW SETUP
# ─────────────────────────────────────────────
def _espnow_init():
    _configure_external_antenna()
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.disconnect()
    e = espnow.ESPNow()
    e.active(True)
    try:
        e.add_peer(BROADCAST)
    except Exception:
        pass
    return e


# ─────────────────────────────────────────────
# LED HELPERS (work on the raw NeoPixel object)
# ─────────────────────────────────────────────
def _fill(np, r, g, b):
    for i in range(NUM_LEDS):
        np[i] = (r, g, b)
    np.write()


def _off(np):
    _fill(np, 0, 0, 0)


def _flash(np, r, g, b, times=2, on_ms=120, off_ms=80):
    for _ in range(times):
        _fill(np, r, g, b)
        time.sleep_ms(on_ms)
        _off(np)
        time.sleep_ms(off_ms)


def _pulse(np, base_r, base_g, base_b, origin_ms,
           period_ms=1000, min_s=0.2, max_s=1.0):
    phase = (time.ticks_diff(time.ticks_ms(), origin_ms)
             % period_ms) / float(period_ms)
    wave = (math.sin(phase * 2 * math.pi) + 1.0) / 2.0
    s = min_s + (max_s - min_s) * wave
    _fill(np, int(base_r * s), int(base_g * s), int(base_b * s))


def _green_chase(np, origin_ms):
    t = time.ticks_ms()
    pos = (time.ticks_diff(t, origin_ms) // 90) % NUM_LEDS
    for i in range(NUM_LEDS):
        np[i] = (0, 2, 0)
    for trail in range(5):
        idx = (pos - trail) % NUM_LEDS
        brightness = max(0, 32 - trail * 6)
        np[idx] = (0, brightness, 0)
    np.write()


def _red_x(np):
    t = time.ticks_ms()
    on = ((t // 250) % 2) == 0
    bg = (1, 0, 0) if on else (0, 0, 0)
    fg = (28, 0, 0) if on else (8, 0, 0)
    for i in range(NUM_LEDS):
        np[i] = bg
    for idx in X_INDICES:
        np[idx] = fg
    np.write()


# ─────────────────────────────────────────────
# SOUND HELPERS
# ─────────────────────────────────────────────
def _join_sound(buz):
    buz.beep(700, 80)
    time.sleep_ms(40)
    buz.beep(980, 120)


def _go_sound(buz):
    buz.beep(900, 70)
    time.sleep_ms(30)
    buz.beep(1200, 90)


def _freeze_sound(buz):
    buz.beep(650, 120)


def _out_sound(buz):
    for _ in range(3):
        buz.beep(880, 120)
        time.sleep_ms(100)


def _role_confirm_sound(buz):
    buz.beep(600, 60)
    time.sleep_ms(30)
    buz.beep(900, 60)
    time.sleep_ms(30)
    buz.beep(1200, 80)


# ─────────────────────────────────────────────
# NFC READING (lightweight, no NfcReader object)
# ─────────────────────────────────────────────
def _read_tag_text(nfc):
    """Quick NDEF text read. Returns (text, uid_hex) or (None, None)."""
    tag = nfc.read_passive_target(timeout=80)
    if tag is None:
        return None, None

    uid_hex = tag['uid_hex']
    sak = tag['sak']

    if sak not in (0x08, 0x18):
        return None, uid_hex

    ndef_data = bytearray()
    for sector in (1, 2):
        first_block = sector * 4
        authed = False
        for key in COMMON_KEYS:
            for key_type in [MIFARE_AUTH_A, MIFARE_AUTH_B]:
                resel = nfc.read_passive_target(timeout=150)
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
    if text and text in GAME_COMMANDS:
        return text, uid_hex
    return None, uid_hex


# ─────────────────────────────────────────────
# MOTION DETECTION
# ─────────────────────────────────────────────
class MotionChecker:
    def __init__(self, accel):
        self.accel = accel
        self.last_xyz = None
        self.hit_count = 0

    def reset(self):
        self.hit_count = 0
        try:
            self.last_xyz = self.accel.read()
        except Exception:
            self.last_xyz = None

    def triggered(self):
        try:
            xyz = self.accel.read()
        except Exception:
            return False

        if self.last_xyz is None:
            self.last_xyz = xyz
            return False

        dx = abs(xyz[0] - self.last_xyz[0])
        dy = abs(xyz[1] - self.last_xyz[1])
        dz = abs(xyz[2] - self.last_xyz[2])
        movement = dx + dy + dz
        self.last_xyz = xyz

        if movement >= MOVE_THRESHOLD:
            self.hit_count += 1
        else:
            if self.hit_count > 0:
                self.hit_count -= 1

        return self.hit_count >= MOVE_HITS_NEEDED


# ─────────────────────────────────────────────
# GAME CLASS
# ─────────────────────────────────────────────
class FreezeDanceGame:
    def __init__(self, nfc, np, buz, accel, enow):
        self.nfc = nfc
        self.np = np
        self.buz = buz
        self.enow = enow
        self.motion = MotionChecker(accel)

        self.state = STATE_ROLE_SELECT
        self.state_ms = time.ticks_ms()
        self.is_caller = False
        self.out_until_ms = 0

        # NFC debounce
        self.last_uid = None
        self.last_scan_ms = 0

    # ── State transitions ────────────────────

    def _set_state(self, new_state):
        self.state = new_state
        self.state_ms = time.ticks_ms()
        self.motion.reset()

        if new_state == STATE_ROLE_SELECT:
            _off(self.np)

        elif new_state == STATE_READY:
            _flash(self.np, 0, 18, 18, times=2)
            _join_sound(self.buz)

        elif new_state == STATE_GO:
            _go_sound(self.buz)

        elif new_state == STATE_FREEZE:
            _freeze_sound(self.buz)

        elif new_state == STATE_OUT:
            self.out_until_ms = time.ticks_add(
                time.ticks_ms(), OUT_DURATION_MS)
            _out_sound(self.buz)

    # ── NFC polling ──────────────────────────

    def _poll_nfc(self):
        text, uid = _read_tag_text(self.nfc)

        if uid is None:
            return None

        now_ms = time.ticks_ms()
        if (uid == self.last_uid
                and time.ticks_diff(now_ms, self.last_scan_ms)
                < REPEAT_SCAN_GUARD_MS):
            return None

        self.last_uid = uid
        self.last_scan_ms = now_ms
        return text

    # ── ESP-NOW polling ──────────────────────

    def _poll_espnow(self):
        mac, msg = self.enow.irecv(0)
        if msg is None:
            return None
        return bytes(msg)

    # ── Rendering ────────────────────────────

    def _render(self):
        if self.state == STATE_ROLE_SELECT:
            # Gentle white breathing — waiting for role tag
            _pulse(self.np, 12, 8, 15, self.state_ms,
                   period_ms=1500, min_s=0.1, max_s=0.5)

        elif self.state == STATE_READY:
            if self.is_caller:
                # Amber pulse — caller waiting to send commands
                _pulse(self.np, 25, 12, 0, self.state_ms,
                       period_ms=900, min_s=0.2, max_s=0.9)
            else:
                # Yellow-green pulse — player waiting for GO
                _pulse(self.np, 10, 20, 0, self.state_ms,
                       period_ms=1200, min_s=0.15, max_s=0.75)

        elif self.state == STATE_GO:
            _green_chase(self.np, self.state_ms)

        elif self.state == STATE_FREEZE:
            # Blue freeze glow
            _pulse(self.np, 0, 0, 40, self.state_ms,
                   period_ms=1300, min_s=0.2, max_s=0.85)

        elif self.state == STATE_OUT:
            _red_x(self.np)

    # ── Main loop ────────────────────────────

    def run(self):
        """
        Run the game until stop is triggered.
        Returns when the player should exit back to programming mode.
        """
        print("\n  === FREEZE DANCE ===")
        print("  Tap CALLER or PLAYER tag to choose your role.")
        print("  Tap STOP tag to exit.\n")

        while True:
            # ── Check NFC (caller and role-select only) ──
            # Players skip NFC after choosing role to keep
            # the ESP-NOW receive window open
            cmd = None
            if self.is_caller or self.state == STATE_ROLE_SELECT:
                cmd = self._poll_nfc()

            if cmd == "stop":
                print("  STOP tag — exiting Freeze Dance")
                if self.is_caller:
                    for _ in range(3):
                        self.enow.send(BROADCAST, MSG_STOP)
                        time.sleep_ms(15)
                    print("  >> Broadcast: STOP (x3)")
                _off(self.np)
                return

            if cmd == "caller" and self.state in (
                    STATE_ROLE_SELECT, STATE_READY):
                self.is_caller = True
                _role_confirm_sound(self.buz)
                _flash(self.np, 25, 12, 0, times=3, on_ms=80, off_ms=60)
                self._set_state(STATE_READY)
                print("  Role: CALLER — scan GO / FREEZE to control")

            elif cmd == "player" and self.state in (
                    STATE_ROLE_SELECT, STATE_READY):
                self.is_caller = False
                _role_confirm_sound(self.buz)
                _flash(self.np, 0, 20, 10, times=3, on_ms=80, off_ms=60)
                self._set_state(STATE_READY)
                print("  Role: PLAYER — dance on GO, freeze on FREEZE")

            elif cmd == "go" and self.is_caller:
                for _ in range(3):
                    self.enow.send(BROADCAST, MSG_GO)
                    time.sleep_ms(15)
                self._set_state(STATE_GO)
                print("  >> Broadcast: GO (x3)")

            elif cmd == "freeze" and self.is_caller:
                for _ in range(3):
                    self.enow.send(BROADCAST, MSG_FREEZE)
                    time.sleep_ms(15)
                self._set_state(STATE_FREEZE)
                print("  >> Broadcast: FREEZE (x3)")

            # ── Check ESP-NOW ──
            msg = self._poll_espnow()

            if msg == MSG_STOP or msg == b'"stop"':
                print("  ESP-NOW stop — exiting Freeze Dance")
                _off(self.np)
                return

            if self.state != STATE_OUT:
                if msg == MSG_GO and not self.is_caller:
                    self._set_state(STATE_GO)
                    print("  Received: GO")

                elif msg == MSG_FREEZE and not self.is_caller:
                    self._set_state(STATE_FREEZE)
                    print("  Received: FREEZE")

                elif msg == MSG_RESET:
                    self._set_state(STATE_READY)
                    print("  Received: RESET")

            # ── Motion check during FREEZE (players only) ──
            if (self.state == STATE_FREEZE
                    and not self.is_caller):
                elapsed = time.ticks_diff(
                    time.ticks_ms(), self.state_ms)
                if elapsed >= FREEZE_GRACE_MS:
                    if self.motion.triggered():
                        self._set_state(STATE_OUT)
                        print("  CAUGHT MOVING — out for %d seconds"
                              % (OUT_DURATION_MS // 1000))

            # ── Out timer ──
            if self.state == STATE_OUT:
                if time.ticks_diff(
                        time.ticks_ms(), self.out_until_ms) >= 0:
                    self._set_state(STATE_READY)
                    print("  Back in! Waiting for next GO/FREEZE...")

            # ── Render + loop delay ──
            self._render()
            time.sleep_ms(LOOP_DELAY_MS)


# ─────────────────────────────────────────────
# ENTRY POINT (called from main.py)
# ─────────────────────────────────────────────
def play(nfc, leds, buz, accel, i2c):
    """
    Called from main.py when the "freezedance" tag is tapped.
    Runs the game until STOP is scanned or received via ESP-NOW.

    Args:
        nfc:   PN532 driver instance
        leds:  Leds instance (we use leds.np for raw NeoPixel access)
        buz:   Buzzer instance
        accel: LIS2DW12 instance
        i2c:   SoftI2C instance (unused, reserved for future)
    """
    enow = _espnow_init()

    try:
        game = FreezeDanceGame(nfc, leds.np, buz, accel, enow)
        game.run()
    finally:
        try:
            enow.active(False)
        except Exception:
            pass
        _off(leds.np)


# ─────────────────────────────────────────────
# STANDALONE MODE (run directly for testing)
# ─────────────────────────────────────────────
def main():
    print("\n" + "=" * 45)
    print("  Freeze Dance — Standalone Mode")
    print("=" * 45)

    i2c = machine.SoftI2C(
        sda=machine.Pin(22), scl=machine.Pin(23), freq=100_000)
    np = NeoPixel(machine.Pin(20), NUM_LEDS)
    buz = Buzzer(19)

    from lis2dw12 import LIS2DW12, RANGE_4G
    accel = LIS2DW12(i2c)
    accel.init(fs_range=RANGE_4G)

    nfc = PN532(i2c)
    nfc.begin()

    enow = _espnow_init()

    try:
        game = FreezeDanceGame(nfc, np, buz, accel, enow)
        game.run()
    except KeyboardInterrupt:
        print("\n  Exiting.")
    finally:
        _off(np)
        try:
            enow.active(False)
        except Exception:
            pass


if __name__ == "__main__":
    main()