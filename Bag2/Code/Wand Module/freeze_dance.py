"""
Freeze Dance — ESP-NOW multiplayer motion game for the wand.

Caller:  button press = GO (green), release = FREEZE (red),
         shake (button up) = DANCE (purple).
Player:  GO -> dance, FREEZE -> hold still, DANCE -> keep moving.
         Get caught -> blue sad face. Tap REJOIN, press button to come back.

All colors and shapes come from leds.py (RED, GREEN, SHAPE_SAD_FACE etc.).
LED writes go through the wrapped NeoPixel inside Leds, so colors auto-adapt
to ambient light via the brightness module — tune base RGB values once in
leds.py and every game uses them.

Tags: caller, player, go, freeze, stop, rejoin, freezedance.
ESP-NOW msgs: FD_GO, FD_FREEZE, FD_DANCE, FD_RESET, stop.

Entry points:
    play(nfc, leds, buz, accel, i2c, enow)  — called from main.py
    main()                             — standalone testing

Template Pattern:
    1. FreezeDanceGame class with __init__() and run()
    2. play() for wand integration (hardware passed in)
    3. main() for standalone testing (initializes hardware)
    4. CRITICAL: Stop tag polled via _poll_nfc() in game loop
"""

import machine, time
from machine import Pin

from espnow_manager import BROADCAST_MAC, ESPNowManager
from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
from nfc_reader import _decode_ndef_text, COMMON_KEYS
import brightness
from leds import (
    RED, GREEN, BLUE, YELLOW, AMBER, PURPLE, WHITE, TEAL, OFF,
    SHAPE_SAD_FACE, SHAPE_PLAY, SHAPE_DANCER,
)

# -- Hardware Config ----------------------------------------
I2C_SDA, I2C_SCL = 22, 23
BUZZER_PIN = 19
PN532_ADDR = 0x24

# -- Constants ----------------------------------------------
NUM_LEDS = 25
SWITCH_PIN = 0
MSG_GO     = b"FD_GO"
MSG_FREEZE = b"FD_FREEZE"
MSG_DANCE  = b"FD_DANCE"
MSG_RESET  = b"FD_RESET"
MSG_STOP   = b"stop"

GAME_COMMANDS = {"caller", "player", "go", "freeze", "stop", "rejoin"}

(STATE_ROLE_SELECT, STATE_READY, STATE_GO, STATE_FREEZE,
 STATE_OUT, STATE_DANCE, STATE_REJOIN_ARMED) = range(7)

# Motion tuning
MOVE_THRESHOLD,  MOVE_HITS_NEEDED,  FREEZE_GRACE_MS = 0.70, 2,  1000
STILL_THRESHOLD, STILL_HITS_NEEDED, DANCE_GRACE_MS  = 0.18, 30, 1500
SHAKE_THRESHOLD, SHAKE_HITS_NEEDED                  = 1.5,  2

# Loop / IO
LOOP_DELAY_MS        = 40
REPEAT_SCAN_GUARD_MS = 1200
NFC_POLL_INTERVAL    = 5
BTN_DEBOUNCE_MS      = 30
BTN_SEND_REPEATS     = 5
BTN_SEND_DELAY_MS    = 1

# state -> color (from leds module palette).
# READY, GO, DANCE, OUT, ROLE_SELECT are special-cased in _render
# (they use shapes or multi-color patterns instead of a flat fill).
STATE_COLORS = {
    STATE_FREEZE:       RED,
    STATE_REJOIN_ARMED: WHITE,
}
READY_CALLER = AMBER
READY_PLAYER = YELLOW
OUT_COLOR    = BLUE

# Multi-color icon shown after the freezedance tag is tapped — corners
# (red/green) plus center (yellow) using all three game-state colors,
# signaling "you're in freeze dance, choose your role".
ROLE_SELECT_PATTERN = {
    RED:    (0, 4),
    YELLOW: (12,),
    GREEN:  (20, 24),
}

# Sound sequences: list of (freq, dur_ms, gap_after_ms)
SOUNDS = {
    'join':   [(700, 80, 40),   (980, 120, 0)],
    'go':     [(900, 70, 30),   (1200, 90, 0)],
    'freeze': [(650, 120, 0)],
    'dance':  [(700, 60, 30),   (900, 60, 30), (1100, 80, 0)],
    'out':    [(880, 120, 100), (880, 120, 100), (880, 120, 0)],
    'rejoin': [(1100, 60, 30),  (1300, 80, 0)],
    'role':   [(600, 60, 30),   (900, 60, 30), (1200, 80, 0)],
}

# state -> sound name to play on entry (None = silent)
STATE_ENTRY_SOUND = {
    STATE_READY:        'join',
    STATE_GO:           'go',
    STATE_FREEZE:       'freeze',
    STATE_DANCE:        'dance',
    STATE_OUT:          'out',
    STATE_REJOIN_ARMED: 'rejoin',
}

# name -> (msg, state) for caller broadcasts
BROADCASTS = {
    'go':     (MSG_GO,     STATE_GO),
    'freeze': (MSG_FREEZE, STATE_FREEZE),
    'dance':  (MSG_DANCE,  STATE_DANCE),
}


# -- Sound helper -------------------------------------------
def _play(buz, name):
    seq = SOUNDS.get(name)
    if not seq: return
    for f, d, gap in seq:
        buz.beep(f, d)
        if gap: time.sleep_ms(gap)


# -- NFC tag read -------------------------------------------
def _read_tag_text(nfc):
    """Returns (text, uid_hex) or (None, None). Text is None if the
    tag's NDEF payload isn't one of GAME_COMMANDS."""
    tag = nfc.read_passive_target(timeout=80)
    if tag is None:
        return None, None
    uid_hex = tag['uid_hex']
    if tag['sak'] not in (0x08, 0x18):
        return None, uid_hex

    ndef = bytearray()
    for sector in (1, 2):
        first = sector * 4
        authed = False
        for key in COMMON_KEYS:
            for kt in (MIFARE_AUTH_A, MIFARE_AUTH_B):
                resel = nfc.read_passive_target(timeout=150)
                if resel is None: continue
                if nfc.mifare_auth_block(resel['uid'], first, key, kt):
                    for blk in range(first, first + 3):
                        try: ndef.extend(nfc.mifare_read_block(blk))
                        except Exception: ndef.extend(b'\x00' * 16)
                    authed = True
                    break
            if authed: break
        if not authed:
            ndef.extend(b'\x00' * 48)

    text = _decode_ndef_text(ndef)
    if text and text in GAME_COMMANDS:
        return text, uid_hex
    return None, uid_hex


# -- Motion: triggered (FREEZE), too_still (DANCE), shake (caller) --
class MotionChecker:
    def __init__(self, accel):
        self.accel = accel
        self.last_xyz = None
        self.move_hits = self.still_hits = self.shake_hits = 0

    def reset(self):
        self.move_hits = self.still_hits = self.shake_hits = 0
        try: self.last_xyz = self.accel.read()
        except Exception: self.last_xyz = None

    def _delta(self):
        try: xyz = self.accel.read()
        except Exception: return None
        if self.last_xyz is None:
            self.last_xyz = xyz
            return None
        dx = abs(xyz[0] - self.last_xyz[0])
        dy = abs(xyz[1] - self.last_xyz[1])
        dz = abs(xyz[2] - self.last_xyz[2])
        self.last_xyz = xyz
        return dx + dy + dz

    def triggered(self):
        m = self._delta()
        if m is None: return False
        if m >= MOVE_THRESHOLD: self.move_hits += 1
        elif self.move_hits > 0: self.move_hits -= 1
        return self.move_hits >= MOVE_HITS_NEEDED

    def too_still(self):
        m = self._delta()
        if m is None: return False
        if m < STILL_THRESHOLD: self.still_hits += 1
        else:                   self.still_hits = 0
        return self.still_hits >= STILL_HITS_NEEDED

    def shake_detected(self):
        m = self._delta()
        if m is None: return False
        if m >= SHAKE_THRESHOLD: self.shake_hits += 1
        elif self.shake_hits > 0: self.shake_hits -= 1
        if self.shake_hits >= SHAKE_HITS_NEEDED:
            self.shake_hits = 0   # consume so we don't refire on decel
            return True
        return False


# -- Game ---------------------------------------------------
class FreezeDanceGame:
    def __init__(self, nfc, leds, buz, accel, enow):
        self.nfc, self.leds, self.buz, self.enow = nfc, leds, buz, enow
        self.motion = MotionChecker(accel)
        self.btn = machine.Pin(SWITCH_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

        self.state = STATE_ROLE_SELECT
        self.state_ms = time.ticks_ms()
        self.is_caller = False

        self.last_uid = None
        self.last_scan_ms = 0
        self._nfc_poll_count = 0
        # Read button state at startup so a button held during freezedance tap
        # doesn't get interpreted as an immediate join.
        self._btn_was_down = (self.btn.value() == 0)

    def _set_state(self, new_state):
        self.state = new_state
        self.state_ms = time.ticks_ms()
        self.motion.reset()
        if new_state == STATE_ROLE_SELECT:
            self.leds.off()
        elif new_state == STATE_READY:
            self.leds.flash_color(TEAL, times=2)
        snd = STATE_ENTRY_SOUND.get(new_state)
        if snd: _play(self.buz, snd)

    def _broadcast(self, name):
        msg, state = BROADCASTS[name]
        for _ in range(BTN_SEND_REPEATS):
            self.enow.send_raw(BROADCAST_MAC, msg)
            time.sleep_ms(BTN_SEND_DELAY_MS)
        self._set_state(state)
        print("  >> %s" % name.upper())

    def _poll_caller_button(self):
        """Press = GO, release = FREEZE."""
        down = (self.btn.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(BTN_DEBOUNCE_MS)
            if self.btn.value() == 0:
                self._btn_was_down = True
                self._broadcast('go')
        elif not down and self._btn_was_down:
            time.sleep_ms(BTN_DEBOUNCE_MS)
            if self.btn.value() == 1:
                self._btn_was_down = False
                self._broadcast('freeze')

    def _poll_player_join_button(self):
        """Button press: join as player from ROLE_SELECT, or rejoin from REJOIN_ARMED."""
        down = (self.btn.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(BTN_DEBOUNCE_MS)
            if self.btn.value() == 0:
                self._btn_was_down = True
                joining = (self.state == STATE_ROLE_SELECT)
                self._set_state(STATE_READY)
                print("  Joined as PLAYER!" if joining else "  Rejoined!")
        elif not down and self._btn_was_down:
            self._btn_was_down = False

    def _poll_nfc(self):
        text, uid = _read_tag_text(self.nfc)
        if uid is None: return None
        now = time.ticks_ms()
        if uid == self.last_uid and time.ticks_diff(now, self.last_scan_ms) < REPEAT_SCAN_GUARD_MS:
            return None
        self.last_uid = uid
        self.last_scan_ms = now
        return text

    def _render(self):
        s = self.state
        if s == STATE_OUT:
            self.leds.show_shape(SHAPE_SAD_FACE, OUT_COLOR)
        elif s == STATE_READY:
            self.leds.fill(READY_CALLER if self.is_caller else READY_PLAYER)
        elif s == STATE_GO:
            self.leds.show_shape(SHAPE_PLAY, GREEN)
        elif s == STATE_DANCE:
            self.leds.show_shape(SHAPE_DANCER, PURPLE)
        elif s == STATE_ROLE_SELECT:
            self.leds.show_pattern(ROLE_SELECT_PATTERN)
        else:
            c = STATE_COLORS.get(s)
            if c: self.leds.fill(c)

    def run(self):
        print("\n  === FREEZE DANCE ===")
        print("  Press button to join as PLAYER.")
        print("  Tap CALLER tag to call. STOP tag to exit.")
        lux = brightness.get_lux()
        print("  Brightness x%.2f (lux=%s)" % (
            brightness.get_multiplier(),
            ("%.0f" % lux) if lux is not None else "n/a"))
        print()

        while True:
            # Caller button: press=GO, release=FREEZE (works from any active state).
            if self.is_caller and self.state in (STATE_READY, STATE_GO, STATE_FREEZE, STATE_DANCE):
                self._poll_caller_button()

            # Caller shake -> DANCE (only with button up, from READY or FREEZE).
            if (self.is_caller and not self._btn_was_down
                    and self.state in (STATE_READY, STATE_FREEZE)
                    and self.motion.shake_detected()):
                self._broadcast('dance')

            # Player join (ROLE_SELECT) or rejoin (REJOIN_ARMED) — button press.
            if (not self.is_caller
                    and self.state in (STATE_ROLE_SELECT, STATE_REJOIN_ARMED)):
                self._poll_player_join_button()

            # NFC: role select, caller idle, or OUT players (for rejoin tag).
            cmd = None
            poll_nfc = (self.state == STATE_ROLE_SELECT
                        or (self.is_caller and not self._btn_was_down)
                        or (not self.is_caller and self.state == STATE_OUT))
            if poll_nfc:
                self._nfc_poll_count += 1
                if self._nfc_poll_count >= NFC_POLL_INTERVAL:
                    self._nfc_poll_count = 0
                    try: cmd = self._poll_nfc()
                    except OSError as e: print("  [NFC: %s]" % str(e))

            if cmd == "stop":
                print("  STOP — exiting")
                if self.is_caller:
                    for _ in range(BTN_SEND_REPEATS):
                        self.enow.send_raw(BROADCAST_MAC, MSG_STOP)
                        time.sleep_ms(BTN_SEND_DELAY_MS)
                self.leds.off()
                return

            if cmd == "caller" and self.state in (STATE_ROLE_SELECT, STATE_READY):
                self.is_caller = True
                self._btn_was_down = False
                _play(self.buz, 'role')
                self.leds.flash_color(AMBER, times=3, on_ms=80, off_ms=60)
                self._set_state(STATE_READY)
                print("  Role: CALLER")

            elif cmd == "player" and self.state in (STATE_ROLE_SELECT, STATE_READY):
                self.is_caller = False
                _play(self.buz, 'role')
                self.leds.flash_color(YELLOW, times=3, on_ms=80, off_ms=60)
                self._set_state(STATE_READY)
                print("  Role: PLAYER")

            elif cmd == "go"     and self.is_caller: self._broadcast('go')
            elif cmd == "freeze" and self.is_caller: self._broadcast('freeze')

            elif cmd == "rejoin" and not self.is_caller and self.state == STATE_OUT:
                self._set_state(STATE_REJOIN_ARMED)
                self._btn_was_down = (self.btn.value() == 0)  # avoid stale-press
                print("  REJOIN — press button")

            # ESP-NOW. State guards dedupe the burst of 5 repeats and only beep
            # on the first message that actually changes state.
            msg_type, data, _ = self.enow.poll()
            if msg_type == "stop":
                print("  ESP-NOW stop"); self.leds.off(); return

            # Players in OUT, REJOIN_ARMED, or ROLE_SELECT ignore game-state
            # messages. ROLE_SELECT means they haven't joined yet — they must
            # press the button (or tap a role tag) before the wand reacts to
            # the caller's commands. The state guards below also dedupe the
            # burst of 5 repeats and only fire on a real state change.
            if msg_type == "raw" and self.state not in (STATE_OUT, STATE_REJOIN_ARMED, STATE_ROLE_SELECT) and not self.is_caller:
                if   data == MSG_GO     and self.state != STATE_GO:     self._set_state(STATE_GO);     print("  GO")
                elif data == MSG_FREEZE and self.state != STATE_FREEZE: self._set_state(STATE_FREEZE); print("  FREEZE")
                elif data == MSG_DANCE  and self.state != STATE_DANCE:  self._set_state(STATE_DANCE);  print("  DANCE")
                elif data == MSG_RESET  and self.state != STATE_READY:  self._set_state(STATE_READY);  print("  RESET")

            # Player motion checks: FREEZE catches movement, DANCE catches stillness.
            if not self.is_caller:
                if self.state == STATE_FREEZE:
                    if (time.ticks_diff(time.ticks_ms(), self.state_ms) >= FREEZE_GRACE_MS
                            and self.motion.triggered()):
                        self._set_state(STATE_OUT); print("  CAUGHT — out!")
                elif self.state == STATE_DANCE:
                    if (time.ticks_diff(time.ticks_ms(), self.state_ms) >= DANCE_GRACE_MS
                            and self.motion.too_still()):
                        self._set_state(STATE_OUT); print("  STOPPED — out!")

            self._render()
            time.sleep_ms(LOOP_DELAY_MS)



# -- Entry Point: Wand Integration --------------------------
def play(nfc, leds, buz, accel, i2c, enow):
    """
    Called from main.py when the freezedance tag is tapped.
    Hardware is already initialized by the caller.
    """
    try:
        FreezeDanceGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()


# -- Entry Point: Standalone Testing ------------------------
def main():
    """
    Standalone entry point for testing without main.py.
    Run directly: import freeze_dance; freeze_dance.main()
    """
    print("\n" + "=" * 45)
    print("  Freeze Dance — ESP-NOW Multiplayer Game")
    print("=" * 45)
    
    i2c = machine.SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100_000)
    
    # Calibrate brightness from ambient light
    try:
        from opt3002 import OPT3002
        light = OPT3002(i2c)
        light.init()
        mult, lux = brightness.calibrate(light)
        if lux is not None:
            print("  Light: %.0f lux -> brightness x%.2f" % (lux, mult))
    except Exception as e:
        print("  [WARN] OPT3002: %s — brightness x1.00" % e)
    
    # Initialize LEDs
    from leds import Leds
    leds = Leds()
    
    # Initialize buzzer
    from buzzer import Buzzer
    buz = Buzzer(BUZZER_PIN)
    
    # Initialize NFC
    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d — NFC ready" % (ic, ver, rev))
    except Exception as e:
        print("  NFC init failed: %s" % e)
        return
    
    # Initialize accelerometer
    try:
        from mpu6050 import MPU6050
        accel = MPU6050(i2c)
        print("  MPU6050 — accelerometer ready")
    except Exception as e:
        print("  [WARN] MPU6050: %s — motion disabled" % e)
        accel = None
    
    enow = ESPNowManager()
    enow.init()

    print()
    
    # Run the game
    play(nfc, leds, buz, accel, i2c, enow)


if __name__ == "__main__":
    main()