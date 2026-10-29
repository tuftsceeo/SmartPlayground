"""
Splat Echo -- two-player Simon, wand half
==========================================
Tag / start_game name: splatecho. Runs with the Splat Companion's
splatecho.py (SplatCompanion/Companion/), which runs the game: joining,
turns, playback, checking and scores. See that file for the rules.

This wand:
  joins     sends echo_hello every HELLO_MS until the hub answers with
            echo_you (its player number); blinks dim white until then
  identity  the player number is logged; wand icons do not use player colors
  icons     each phase has its own icon on the wand whose turn it is; the
            other player's wand shows a dim hourglass in every phase:
              watch   hourglass, white, and a chirp (echo_turn)
              play    play arrow, green, and a beep (echo_repeat_now) --
                      press the Splats now; each correct press: a short beep
              add     plus (echo_add_now), see below
  add       when the hub asks (echo_add_now): the plus always shows one
            Splat's color, starting with Splat 0; tilt to pick another
            (forward = 0, right = 1, back = 2, left = 3; flat keeps the last
            pick) and press to add the one shown. A Splat press on the hub
            also adds a step; the hub's echo_added ends add mode either way. The hub
            resends echo_add_now (same "add" id) until it has the step; a
            resend for an id already answered sends the same echo_add again
  result    whoever won the round (a full repeat, or the other player's
            miss) gets a rainbow and a tune; a miss gets red and a low
            tune, then the score as lit pixels for SCORE_MS

Exits on ESP-NOW "stop"/"start_game" or a stop / other game tag.

After joining, echo_add goes to the hub by unicast (ESP-NOW ACKs and
retries it; SEND_TRIES attempts), and a hub message whose "q" repeats the
last one is a duplicate (its ACK was lost) and is dropped.

DIAGNOSTIC log: the wand runs off USB, so key moments are kept in RAM
(LOG_MAX lines) and written to LOG_PATH at start, on exit (stop, error)
and whenever nothing has happened for QUIET_MS (backing off, so a long
freeze keeps the history before it). The previous game's log is kept as
LOG_PREV. Read them with mpremote after the wand is plugged back in.

Entry point:
    play(nfc, leds, buz, accel, i2c, enow, batt=None)  -- called from main.py
"""

import json
import os
import time
from machine import Pin

from nfc_reader import read_tag_command
from game_tags import exit_tags_excluding
from leds import RED, BLUE, YELLOW, PURPLE, GREEN, WHITE_DIM, OFF
from leds import SHAPE_HOURGLASS, SHAPE_PLAY, SHAPE_PLUS

_EXIT_TAGS = exit_tags_excluding("splatecho")

NUM_LEDS = 25
BUTTON_PIN = 0
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 20
HELLO_MS = 1000
TILT_G = 0.5            # |x| or |y| above this picks a Splat
SCORE_MS = 2000
SEND_TRIES = 3          # unicast attempts to the hub before giving up

LOG_PATH = "/echo_log.txt"
LOG_PREV = "/echo_log_prev.txt"
LOG_MAX = 150           # lines kept in RAM
QUIET_MS = 10000        # first snapshot after this long with no event
SLOW_POLL_MS = 300      # log a gap between polls longer than this

# Splat unit -> wand color and buzzer tone; same unit order as the hub's.
UNIT_COLOR = (RED, BLUE, YELLOW, PURPLE)
UNIT_TONE = (392, 523, 659, 784)
# Icons not tied to a Splat are white, so every other color on the wand is
# a Splat's color, green (press now) or a result color.
PLAYER_COLOR = ((150, 150, 150), (150, 150, 150))
PLAYER_DIM = ((15, 15, 15), (15, 15, 15))


class _Log:
    """Timestamped ring of lines, printed live and written to LOG_PATH.
    Never raises into the game."""

    def __init__(self, name):
        self.name = name
        self.t0 = time.ticks_ms()
        self.lines = []
        self.last_event = self.t0
        self.gap = QUIET_MS
        self.next_snap = time.ticks_add(self.t0, QUIET_MS)
        try:
            os.rename(LOG_PATH, LOG_PREV)
        except OSError:
            pass

    def __call__(self, msg, event=True):
        now = time.ticks_ms()
        line = "%7d %s" % (time.ticks_diff(now, self.t0), msg)
        print("  [%s] %s" % (self.name, line))
        self.lines.append(line)
        if len(self.lines) > LOG_MAX:
            self.lines.pop(0)
        if event:
            self.last_event = now
            self.gap = QUIET_MS
            self.next_snap = time.ticks_add(now, QUIET_MS)

    def tick(self, snapshot):
        """Call every loop. While nothing is logged, snapshot() is logged
        and the file written after 10 s, then 20, 40, ... s."""
        now = time.ticks_ms()
        if time.ticks_diff(now, self.next_snap) < 0:
            return
        self.gap *= 2
        self.next_snap = time.ticks_add(now, self.gap)
        try:
            s = snapshot()
        except Exception as e:
            s = "snapshot failed: %r" % e
        self("QUIET %d ms: %s" % (time.ticks_diff(now, self.last_event), s),
             event=False)
        self.flush("quiet snapshot")

    def flush(self, why):
        try:
            with open(LOG_PATH, "w") as f:
                for line in self.lines:
                    f.write(line)
                    f.write("\n")
                f.write("== written at %d ms: %s\n"
                        % (time.ticks_diff(time.ticks_ms(), self.t0), why))
        except Exception as e:
            print("  [%s] log write failed: %r" % (self.name, e))


RAINBOW_MS = 900
RAINBOW_LEVEL = 150     # peak channel value, same as the white icons


def _wheel(pos):
    """0..255 -> (r, g, b) around the color wheel, peak RAINBOW_LEVEL."""
    pos &= 255
    if pos < 85:
        r, g, b = 255 - pos * 3, pos * 3, 0
    elif pos < 170:
        pos -= 85
        r, g, b = 0, 255 - pos * 3, pos * 3
    else:
        pos -= 170
        r, g, b = pos * 3, 0, 255 - pos * 3
    return (r * RAINBOW_LEVEL // 255, g * RAINBOW_LEVEL // 255,
            b * RAINBOW_LEVEL // 255)


def mac_bytes_str(b):
    return ":".join("%02X" % x for x in b)


def _pick(accel):
    """Splat unit chosen by tilt, or None when the wand is near flat."""
    x, y, z = accel.read()
    if abs(x) < TILT_G and abs(y) < TILT_G:
        return None
    if abs(y) >= abs(x):
        return 0 if y > 0 else 2
    return 1 if x > 0 else 3


class SplatEchoGame:
    def __init__(self, nfc, leds, buz, accel, enow, log):
        self.nfc = nfc
        self.np = leds.np
        self.buz = buz
        self.accel = accel
        self.enow = enow
        self.log = log
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self.frame = 0
        self.me = None           # player number from the hub
        self.hub = None          # hub MAC string, from echo_you
        self.added = None        # ("add" id, unit) of the last step sent
        # DIAGNOSTIC state
        self.state = "join"
        self.last_q = None       # last hub message "q" received
        self.missed = 0          # hub messages never received (q gaps)
        self.rx = {}             # kind -> count
        self.last_rx = None      # (ticks_ms, kind)
        self.adds = 0            # echo_add sent
        self.btn_was = self.btn.value() == 0
        self.last_poll = time.ticks_ms()
        self.max_gap = 0

    # ── DIAGNOSTIC helpers ──
    def _espnow_stats(self):
        """(tx_pkts, tx_responses, tx_failures, rx_packets, rx_dropped)
        from the ESP-NOW driver; rx_dropped counts receive-buffer overflow."""
        try:
            return self.enow.enow.stats()
        except Exception as e:
            return "err %r" % e

    def _snapshot(self):
        now = time.ticks_ms()
        if self.last_rx:
            last = "%s %d ms ago" % (self.last_rx[1],
                                     time.ticks_diff(now, self.last_rx[0]))
        else:
            last = "none"
        try:
            tilt = _pick(self.accel)
        except Exception as e:
            tilt = "err %r" % e
        return ("state=%s me=%s last_rx=%s rx=%s last_q=%s missed=%d adds=%d "
                "btn_down=%d tilt=%s max_poll_gap=%d espnow=%s" % (
                    self.state, self.me, last, self.rx, self.last_q, self.missed,
                    self.adds, int(self.btn.value() == 0), tilt, self.max_gap,
                    self._espnow_stats()))

    def _set_state(self, state):
        self.state = state
        self.log("STATE %s" % state)

    def _note_rx(self, kind, data):
        """Count and log a received echo_* message; check its q for gaps.
        Returns True for a duplicate (same q as the last one)."""
        self.rx[kind] = self.rx.get(kind, 0) + 1
        self.last_rx = (time.ticks_ms(), kind)
        q = data.get("q")
        gap = ""
        if isinstance(q, int):
            if q == self.last_q:
                self.log("DUP %s dropped (state=%s)" % (data, self.state))
                return True
            if self.last_q is not None and q != self.last_q + 1:
                if q > self.last_q:
                    self.missed += q - self.last_q - 1
                gap = " MISSED %d before this (total %d)" % (
                    q - self.last_q - 1, self.missed)
            self.last_q = q
        if kind == "echo_add_now" and self.state == "add":
            return False        # the hub's once-a-second resend; not logged
        self.log("RX %s (state=%s)%s" % (data, self.state, gap))
        return False

    def _send_hub(self, msg):
        """Unicast msg to the hub, retried until ACKed. Returns the attempt
        that was ACKed, or -attempts if none was."""
        mac = self.hub
        data = json.dumps(msg)
        n = 0
        while n < SEND_TRIES:
            n += 1
            try:
                if self.enow.enow.send(mac, data, True):
                    return n
            except OSError as e:
                self.log("TX to hub err %r" % e)
        return -n

    def _check_button(self):
        """Log wand button presses made outside add_step()."""
        down = self.btn.value() == 0
        if down and not self.btn_was:
            self.log("BUTTON pressed outside add (state=%s)" % self.state)
        self.btn_was = down

    def _icon(self, shape, color):
        for i in range(NUM_LEDS):
            self.np[i] = color if i in shape else OFF
        self.np.write()

    def _fill(self, color, n=NUM_LEDS):
        for i in range(NUM_LEDS):
            self.np[i] = color if i < n else OFF
        self.np.write()

    def _poll(self):
        """One ESP-NOW message and, every NFC_POLL_INTERVAL frames, one tag
        check. Returns ("exit", None), (kind, data) or (None, None)."""
        now = time.ticks_ms()
        gap = time.ticks_diff(now, self.last_poll)
        if gap > self.max_gap:
            self.max_gap = gap
        if gap > SLOW_POLL_MS:
            self.log("SLOW poll gap %d ms (state=%s)" % (gap, self.state),
                     event=False)
        self.log.tick(self._snapshot)
        mt, data, mac = self.enow.poll()
        if mt in ("stop", "start_game"):
            self.log("RX %s from %s: %s -- exiting (state=%s)"
                     % (mt, mac, data, self.state))
            return "exit", None
        self.frame += 1
        if self.frame % NFC_POLL_INTERVAL == 0:
            text, _ = read_tag_command(self.nfc, timeout=100)
            if text in _EXIT_TAGS:
                self.log("NFC exit tag %s (state=%s)" % (text, self.state))
                return "exit", None
        self.last_poll = time.ticks_ms()
        if isinstance(data, dict):
            kind = data.get("type")
            if isinstance(kind, str) and kind.startswith("echo_"):
                if self._note_rx(kind, data):
                    return None, None
                if kind == "echo_you" and mac:
                    self._set_hub(mac)
            return kind, data
        return None, None

    def _set_hub(self, mac_str):
        if mac_str != (self.hub and mac_bytes_str(self.hub)):
            self.enow.add_peer(mac_str)
            self.hub = bytes(int(b, 16) for b in mac_str.split(":"))
            self.log("HUB %s" % mac_str)

    def join(self):
        """Hello until the hub assigns a player number. False to exit."""
        next_hello = time.ticks_ms()
        blink = False
        hellos = 0
        while self.me is None:
            kind, data = self._poll()
            if kind == "exit":
                return False
            if kind == "echo_you":
                self.me = data.get("player")
                print("  splatecho: I am player %d" % self.me)
                self.log("JOINED as player %s after %d hello(s)" % (self.me, hellos))
                self.buz.beep(784, 80)
                break
            now = time.ticks_ms()
            if time.ticks_diff(now, next_hello) >= 0:
                ok = self.enow.broadcast({"type": "echo_hello"})
                hellos += 1
                if hellos <= 2 or not ok:
                    self.log("TX echo_hello #%d ok=%s" % (hellos, ok))
                blink = not blink
                self._fill(WHITE_DIM if blink else OFF)
                next_hello = time.ticks_add(now, HELLO_MS)
            time.sleep_ms(LOOP_DELAY_MS)
        self._icon(SHAPE_HOURGLASS, PLAYER_DIM[self.me])
        return True

    def add_step(self, add_id):
        """Tilt to pick, press to add a step for request add_id. False to
        exit."""
        print("  splatecho: your turn to add a step")
        self._set_state("add")
        t_add = time.ticks_ms()
        unit = 0
        self._icon(SHAPE_PLUS, UNIT_COLOR[unit])
        was_down = self.btn.value() == 0
        while True:
            kind, data = self._poll()
            if kind == "exit":
                return False
            if kind == "echo_added" and data.get("add") == add_id:
                # Added on the hub (a Splat press) before this wand sent one.
                self.added = (add_id, data.get("unit"))
                self._icon(SHAPE_HOURGLASS, PLAYER_DIM[self.me])
                self._set_state("added on hub, waiting")
                return True
            if kind is not None and kind != "echo_add_now":
                self.log("  %s ignored while adding" % kind)
            tilt = _pick(self.accel)
            if tilt is not None and tilt != unit:
                unit = tilt
                self._icon(SHAPE_PLUS, UNIT_COLOR[unit])
            down = self.btn.value() == 0
            if down and not was_down:
                self.adds += 1
                self.added = (add_id, unit)
                tries = self._send_hub({"type": "echo_add", "unit": unit, "add": add_id})
                print("  splatecho: added Splat %d" % unit)
                self.log("TX echo_add unit %d add %s tries=%d%s after %d ms"
                         % (unit, add_id, tries, "" if tries > 0 else " NOT ACKED",
                            time.ticks_diff(time.ticks_ms(), t_add)))
                self.buz.beep(UNIT_TONE[unit], 150)
                self._icon(SHAPE_HOURGLASS, PLAYER_DIM[self.me])
                self.btn_was = True
                self._set_state("added, waiting")
                return True
            was_down = down
            time.sleep_ms(LOOP_DELAY_MS)

    def _rainbow(self, ms=RAINBOW_MS):
        """Rainbow swirl across the matrix for ms (blocks)."""
        t0 = time.ticks_ms()
        k = 0
        while time.ticks_diff(time.ticks_ms(), t0) < ms:
            for i in range(NUM_LEDS):
                self.np[i] = _wheel(i * 10 + k * 16)
            self.np.write()
            k += 1
            time.sleep_ms(40)

    def show_result(self, data):
        """The round's winner gets a rainbow and a tune; the player who
        missed gets red and a low tune. A correct repeat is won by the
        repeater; a miss is won by the other player. Solo, this wand is
        always the repeater."""
        ok = data.get("ok")
        repeater = data.get("player") == self.me
        scores = data.get("scores") or [0, 0]
        t = time.ticks_ms()
        if ok and not repeater:
            outcome = "watched"         # the other player got it right
        elif ok == repeater:            # my full repeat, or the other's miss
            outcome = "won"
            self._rainbow(200)
            self.buz.celebrate()
            self._rainbow()
        else:
            outcome = "lost"
            self._fill(RED)
            self.buz.error()
            time.sleep_ms(400)
        mine = scores[self.me] if self.me < len(scores) else 0
        print("  splatecho: scores %s (me: player %d)" % (scores, self.me))
        if not ok:
            self._fill(PLAYER_COLOR[self.me], n=min(mine, NUM_LEDS))
            time.sleep_ms(SCORE_MS)
        self._icon(SHAPE_HOURGLASS, PLAYER_DIM[self.me])
        self.log("RESULT shown ok=%s %s, blocked %d ms"
                 % (ok, outcome, time.ticks_diff(time.ticks_ms(), t)))

    def run(self):
        self._set_state("join")
        if not self.join():
            return
        self._set_state("waiting")
        while True:
            kind, data = self._poll()
            if kind == "exit":
                return
            self._check_button()
            if kind == "echo_turn":
                if data.get("player") == self.me:
                    print("  splatecho: my turn (length %d)" % data.get("len", 0))
                    self._set_state("my turn len %s" % data.get("len"))
                    self._icon(SHAPE_HOURGLASS, PLAYER_COLOR[self.me])
                    self.buz.beep(1047, 80)
                    self.buz.beep(1319, 80)
                else:
                    self._set_state("other's turn")
                    self._icon(SHAPE_HOURGLASS, PLAYER_DIM[self.me])
            elif kind == "echo_repeat_now":
                if data.get("player") == self.me:
                    self._set_state("repeat")
                    self._icon(SHAPE_PLAY, GREEN)
                    self.buz.beep(1319, 60)
                else:
                    self._icon(SHAPE_HOURGLASS, PLAYER_DIM[self.me])
            elif kind == "echo_step" and data.get("player") == self.me:
                self.buz.beep(880, 50)
            elif kind == "echo_add_now" and data.get("player") != self.me:
                self._icon(SHAPE_HOURGLASS, PLAYER_DIM[self.me])
            elif kind == "echo_add_now":
                add_id = data.get("add")
                if self.added and self.added[0] == add_id:
                    # The hub asked again for a step already sent: it did
                    # not get the echo_add, so send the same one again.
                    unit = self.added[1]
                    tries = self._send_hub({"type": "echo_add", "unit": unit, "add": add_id})
                    self.log("RESEND echo_add unit %d add %s tries=%d" % (unit, add_id, tries))
                elif not self.add_step(add_id):
                    return
            elif kind == "echo_result":
                self._set_state("result")
                self.show_result(data)
                self._set_state("waiting")
            elif kind == "echo_you":
                self.me = data.get("player")
            time.sleep_ms(LOOP_DELAY_MS)


def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    buz.beep(523, 100)
    log = _Log("echo")
    game = SplatEchoGame(nfc, leds, buz, accel, enow, log)
    log("START espnow=%s" % (game._espnow_stats(),))
    log.flush("started (only this line later = wand reset or hard hang)")
    why = "exit"
    try:
        game.run()
    except Exception as e:
        why = "exception %r" % e
        log("EXCEPTION in state %s: %r" % (game.state, e))
        raise
    finally:
        try:
            log("END: %s" % game._snapshot())
        except Exception as e:
            log("END snapshot failed: %r" % e)
        log.flush(why)
        leds.off()
