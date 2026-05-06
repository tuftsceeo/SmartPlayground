"""
Freeze Dance — ESP-NOW multiplayer motion game for the wand.

Caller:  button press = GO (green), release = FREEZE (red),
         shake (button up) = DANCE (purple).
Player:  GO → dance, FREEZE → hold still, DANCE → keep moving.
         Get caught → blue sad face. Tap REJOIN, press button to come back.

Tags: caller, player, go, freeze, stop, rejoin, freezedance.
ESP-NOW msgs: FD_GO, FD_FREEZE, FD_DANCE, FD_RESET, stop.

Entry point:
    from freeze_dance import play
    play(nfc, leds, buz, accel, i2c)
"""

import machine, network, espnow, time
from machine import Pin
from neopixel import NeoPixel

from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
from nfc_reader import _decode_ndef_text, COMMON_KEYS
from buzzer import Buzzer

# ── Constants ──────────────────────────────────────────────
NUM_LEDS = 25
SWITCH_PIN = 0
BROADCAST = b'\xFF\xFF\xFF\xFF\xFF\xFF'

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

# 5x5 sad face: eyes (6,8), frown top (16,17,18), corners (20,24)
SAD_FACE_INDICES = (6, 8, 16, 17, 18, 20, 24)

# state -> (r, g, b). READY and OUT are special-cased in _render.
STATE_COLORS = {
    STATE_ROLE_SELECT:  (200, 200, 0),
    STATE_GO:           (0,   200, 0),
    STATE_FREEZE:       (200, 0,   0),
    STATE_DANCE:        (180, 0,   180),
    STATE_REJOIN_ARMED: (140, 140, 140),
}
READY_CALLER = (200, 100, 0)
READY_PLAYER = (200, 200, 0)
SAD_BLUE     = (0,   0,   200)

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


# ── Hardware setup ─────────────────────────────────────────
def _configure_external_antenna():
    Pin(3,  Pin.OUT).value(0)
    time.sleep_ms(100)
    Pin(14, Pin.OUT).value(1)


def _espnow_init():
    _configure_external_antenna()
    sta = network.WLAN(network.STA_IF)
    sta.active(True); sta.disconnect()
    e = espnow.ESPNow(); e.active(True)
    try: e.add_peer(BROADCAST)
    except Exception: pass
    return e


# ── LED + sound helpers ────────────────────────────────────
def _fill(np, r, g, b):
    for i in range(NUM_LEDS):
        np[i] = (r, g, b)
    np.write()


def _off(np):
    _fill(np, 0, 0, 0)


def _flash(np, r, g, b, times=2, on_ms=120, off_ms=80):
    for _ in range(times):
        _fill(np, r, g, b); time.sleep_ms(on_ms)
        _off(np);            time.sleep_ms(off_ms)


def _sad_face(np):
    for i in range(NUM_LEDS):
        np[i] = (0, 0, 0)
    for idx in SAD_FACE_INDICES:
        np[idx] = SAD_BLUE
    np.write()


def _play(buz, name):
    seq = SOUNDS.get(name)
    if not seq: return
    for f, d, gap in seq:
        buz.beep(f, d)
        if gap: time.sleep_ms(gap)


# ── NFC tag read ───────────────────────────────────────────
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


# ── Motion: triggered (FREEZE), too_still (DANCE), shake (caller) ──
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


# ── Game ───────────────────────────────────────────────────
class FreezeDanceGame:
    def __init__(self, nfc, np, buz, accel, enow):
        self.nfc, self.np, self.buz, self.enow = nfc, np, buz, enow
        self.motion = MotionChecker(accel)
        self.btn = machine.Pin(SWITCH_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

        self.state = STATE_ROLE_SELECT
        self.state_ms = time.ticks_ms()
        self.is_caller = False

        self.last_uid = None
        self.last_scan_ms = 0
        self._nfc_poll_count = 0
        self._btn_was_down = False

    def _set_state(self, new_state):
        self.state = new_state
        self.state_ms = time.ticks_ms()
        self.motion.reset()
        if new_state == STATE_ROLE_SELECT:
            _off(self.np)
        elif new_state == STATE_READY:
            _flash(self.np, 0, 150, 150, times=2)
        snd = STATE_ENTRY_SOUND.get(new_state)
        if snd: _play(self.buz, snd)

    def _broadcast(self, name):
        msg, state = BROADCASTS[name]
        for _ in range(BTN_SEND_REPEATS):
            self.enow.send(BROADCAST, msg)
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

    def _poll_player_rejoin_button(self):
        down = (self.btn.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(BTN_DEBOUNCE_MS)
            if self.btn.value() == 0:
                self._btn_was_down = True
                self._set_state(STATE_READY)
                print("  Rejoined!")
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

    def _poll_espnow(self):
        _, msg = self.enow.irecv(0)
        return bytes(msg) if msg is not None else None

    def _render(self):
        s = self.state
        if s == STATE_OUT:
            _sad_face(self.np)
        elif s == STATE_READY:
            _fill(self.np, *(READY_CALLER if self.is_caller else READY_PLAYER))
        else:
            c = STATE_COLORS.get(s)
            if c: _fill(self.np, *c)

    def run(self):
        print("\n  === FREEZE DANCE ===")
        print("  Tap CALLER or PLAYER. STOP to exit.\n")

        while True:
            # Caller button: press=GO, release=FREEZE (works from any active state).
            if self.is_caller and self.state in (STATE_READY, STATE_GO, STATE_FREEZE, STATE_DANCE):
                self._poll_caller_button()

            # Caller shake → DANCE (only with button up, from READY or FREEZE).
            if (self.is_caller and not self._btn_was_down
                    and self.state in (STATE_READY, STATE_FREEZE)
                    and self.motion.shake_detected()):
                self._broadcast('dance')

            # Player rejoin button.
            if not self.is_caller and self.state == STATE_REJOIN_ARMED:
                self._poll_player_rejoin_button()

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
                        self.enow.send(BROADCAST, MSG_STOP)
                        time.sleep_ms(BTN_SEND_DELAY_MS)
                _off(self.np)
                return

            if cmd == "caller" and self.state in (STATE_ROLE_SELECT, STATE_READY):
                self.is_caller = True
                self._btn_was_down = False
                _play(self.buz, 'role')
                _flash(self.np, 200, 100, 0, times=3, on_ms=80, off_ms=60)
                self._set_state(STATE_READY)
                print("  Role: CALLER")

            elif cmd == "player" and self.state in (STATE_ROLE_SELECT, STATE_READY):
                self.is_caller = False
                _play(self.buz, 'role')
                _flash(self.np, 200, 200, 0, times=3, on_ms=80, off_ms=60)
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
            msg = self._poll_espnow()
            if msg == MSG_STOP or msg == b'"stop"':
                print("  ESP-NOW stop"); _off(self.np); return

            if self.state not in (STATE_OUT, STATE_REJOIN_ARMED) and not self.is_caller:
                if   msg == MSG_GO     and self.state != STATE_GO:     self._set_state(STATE_GO);     print("  GO")
                elif msg == MSG_FREEZE and self.state != STATE_FREEZE: self._set_state(STATE_FREEZE); print("  FREEZE")
                elif msg == MSG_DANCE  and self.state != STATE_DANCE:  self._set_state(STATE_DANCE);  print("  DANCE")
                elif msg == MSG_RESET  and self.state != STATE_READY:  self._set_state(STATE_READY);  print("  RESET")

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


# ── Entry points ───────────────────────────────────────────
def play(nfc, leds, buz, accel, i2c):
    """Called from main.py when the freezedance tag is tapped."""
    enow = _espnow_init()
    try:
        FreezeDanceGame(nfc, leds.np, buz, accel, enow).run()
    finally:
        try: enow.active(False)
        except Exception: pass
        _off(leds.np)


def main():
    """Standalone test mode."""
    print("\n  Freeze Dance — Standalone\n")
    i2c = machine.SoftI2C(sda=machine.Pin(22), scl=machine.Pin(23), freq=100_000)
    np  = NeoPixel(machine.Pin(20), NUM_LEDS)
    buz = Buzzer(19)
    from lis2dw12 import LIS2DW12, RANGE_4G
    accel = LIS2DW12(i2c); accel.init(fs_range=RANGE_4G)
    nfc = PN532(i2c); nfc.begin()
    enow = _espnow_init()
    try:
        FreezeDanceGame(nfc, np, buz, accel, enow).run()
    except KeyboardInterrupt:
        print("\n  Exiting.")
    finally:
        _off(np)
        try: enow.active(False)
        except Exception: pass


if __name__ == "__main__":
    main()
