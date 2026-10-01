"""
Splat Echo -- two-player Simon, Splat Companion half (game master)
===================================================================
Tag / start_game name: splatecho (lib/splat_tags.py GAME_TAGS). Runs with
the wand's splatecho.py (MockWand/), a separate program for the same game.

Rules:
  Players take turns on one shared pattern. On a turn the hub plays the
  whole pattern on the Splats; the player repeats it on the Splats, with
  feedback on every press; after a full repeat the player adds one step
  with their wand (tilt + press) and the turn passes. A wrong Splat or a
  STEP_MS timeout ends the round: the other player scores and the pattern
  starts again from empty.

This half runs the game: joining, turns, playback, checking, scores.
Each wand sends echo_hello until it is given a player number by a unicast
echo_you. With one wand after LOBBY_MS the game runs solo.

Unit colors and sounds are fixed by unit index (UNITS) so they match the
wand's tilt colors. With fewer than 4 Splats a unit index wraps onto the
Splats present (index % splat.count).

Messages (dicts; "type" names not used elsewhere):
  from a wand  {"type": "echo_hello"}                          (broadcast)
               {"type": "echo_add", "unit": i, "add": a}      (unicast)
  to one wand  {"type": "echo_you", "player": p}              (p = 0 or 1)
  to players   {"type": "echo_turn", "player": p, "len": n}
               {"type": "echo_add_now", "player": p, "len": n, "add": a}
               {"type": "echo_repeat_now", "player": p, "len": n}
               {"type": "echo_step", "player": p, "idx": k}
               {"type": "echo_result", "ok": bool, "player": p,
                "len": n, "scores": [s0, s1]}
  Everything after joining is unicast to each player, which ESP-NOW ACKs
  and retries (broadcasts are not ACKed). A send not ACKed is retried
  SEND_TRIES times. Messages to players carry "q", a count the wand uses to drop
  duplicates (an ACK lost after delivery makes the hub send again).

Adding a step: each request has its own id, "add" (a counter starting
from a clock-derived value, so a restarted hub does not reuse ids). The
request is resent every ADD_RESEND_MS with the same id until an echo_add
carrying that id arrives; an echo_add with any other id is ignored.

Exits on ESP-NOW "stop" or "start_game" (cards arrive the same way; see
main.py's _GameEnow).

DIAGNOSTIC log: key moments are printed and kept in RAM (LOG_MAX lines),
then written to LOG_PATH at start, on exit (stop, error) and whenever
nothing has happened for QUIET_MS (backing off, so a long freeze keeps the
history before it). The previous game's log is kept as LOG_PREV.
"""

import os
import time

# unit index -> (Splat color, ring RGB, sound); same order as the wand's.
UNITS = (
    ("turnred", (60, 0, 0), "cat"),
    ("turnblue", (0, 0, 60), "dog"),
    ("turnyellow", (60, 40, 0), "cow"),
    ("turnpurple", (36, 0, 45), "duck"),
)
PLAYER_RGB = ((0, 40, 40), (50, 20, 0))    # player 0 cyan, player 1 orange
LOBBY_MS = 8000        # wait this long for a second wand, then play solo
SHOW_MS = 450          # one playback step lit
GAP_MS = 250           # dark gap between playback steps
PRESS_MS = 300         # a correct press stays lit
STEP_MS = 4000         # time allowed for each press while repeating
OK_MS = 1200           # Splats green after a full repeat
ADD_PAUSE_MS = 1200    # after a step is added, before the next turn starts
FAIL_MS = 1500         # red when a round ends
MAX_LEN = 12           # ring pixels; the pattern stops growing here

LOG_PATH = "/echo_log.txt"
LOG_PREV = "/echo_log_prev.txt"
LOG_MAX = 150          # lines kept in RAM
QUIET_MS = 10000       # first snapshot after this long with no event
SEND_TRIES = 3         # unicast attempts per player before giving up
ADD_RESEND_MS = 1000   # echo_add_now resend interval while waiting


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


def _light(splat, i):
    cname, rgb, sound = UNITS[i % len(UNITS)]
    u = splat.unit(i % splat.count)
    u.color(cname)
    u.sound(sound)
    return rgb


def _ring_count(leds, n, rgb):
    """First n ring pixels in rgb, the rest dark (n capped at leds.n)."""
    n = min(n, leds.n)
    leds.show_each([rgb] * n + [(0, 0, 0)] * (leds.n - n))


class _Game:
    def __init__(self, splat, leds, enow, log):
        self.splat = splat
        self.leds = leds
        self.enow = enow
        self.log = log
        self.players = []            # wand MAC strings, index = player number
        self.scores = [0, 0]
        self.pattern = []
        # DIAGNOSTIC state
        self.phase = "start"
        self.q = 0                   # messages sent to players
        self.rx = {}                 # kind -> count, every message received
        self.last_rx = None          # (ticks_ms, kind, mac)
        self.ignored = 0             # Splat presses discarded outside repeat()
        self.you_sent = {}           # mac -> echo_you sends
        self.resends = 0             # echo_add_now resends
        self.add_id = time.ticks_ms() & 0xFFFF

    # ── DIAGNOSTIC helpers ──
    def _units(self):
        """Per Splat: link state, accepted/IRQ-raw/loop-raw pressed,
        drops, raw events dropped, write failures."""
        out = []
        for i, u in enumerate(self.splat.units):
            l = u.link
            out.append("u%d:%s p=%d/%d/%d drops=%d evdrop=%d wfail=%d" % (
                i, l.state_name(), int(l.splat_pressed), int(l._irq_raw),
                int(l._raw), l.drops, l.events_dropped, u.write_failures))
        return " | ".join(out)

    def _snapshot(self):
        now = time.ticks_ms()
        if self.last_rx:
            t, kind, mac = self.last_rx
            last = "%s from %s %d ms ago" % (kind, mac, time.ticks_diff(now, t))
        else:
            last = "none"
        try:
            st = self.enow.link_stats()
            modem = ("rx=%s rx_overflow=%s tx_fail=%s host_timeouts=%s"
                     % (st["modem_rx"], st["modem_rx_overflow"],
                        st["modem_tx_fail"], st["host_timeouts"])
                     if st else "no reply")
        except Exception as e:
            modem = "err %r" % e
        return ("phase=%s pattern=%s players=%s last_rx=%s rx=%s ignored_presses=%d "
                "q=%d resends=%d modem[%s] splats[%s]" % (
                    self.phase, self.pattern, self.players, last, self.rx,
                    self.ignored, self.q, self.resends, modem, self._units()))

    def send(self, msg, quiet=False):
        """Unicast msg to every player, each retried until ACKed (up to
        SEND_TRIES), and log it (quiet: only if not ACKed). Returns True if
        every player ACKed."""
        self.q += 1
        msg["q"] = self.q
        tries = []
        for mac in self.players:
            acked = False
            n = 0
            while n < SEND_TRIES and not acked:
                n += 1
                self.enow.send_to(mac, msg)
                acked = self.enow.last_acked
            tries.append(n if acked else -n)
        ok = all(t > 0 for t in tries)
        # tries per player: n = ACKed on attempt n, -n = no ACK after n
        if not quiet or not ok:
            self.log("TX %s tries=%s%s" % (msg, tries, "" if ok else " NOT ACKED"))
        return ok

    def _set_phase(self, phase):
        self.phase = phase
        self.log("PHASE %s" % phase)

    def _ignore_splat(self, ev):
        """A Splat event outside repeat(): discarded, but a press is logged."""
        if ev == "press":
            self.ignored += 1
            self.log("SPLAT press on %d IGNORED (phase=%s, ignored=%d)"
                     % (self.splat.last_index, self.phase, self.ignored))

    # ── messages ──
    def poll(self):
        """One ESP-NOW message. Handles joining; returns (kind, data), or
        ("exit", None) on stop/start_game."""
        self.log.tick(self._snapshot)
        mt, data, mac = self.enow.poll()
        if mt is None:
            return None, None
        kind = data.get("type") if isinstance(data, dict) else None
        key = kind or mt
        self.rx[key] = self.rx.get(key, 0) + 1
        self.last_rx = (time.ticks_ms(), key, mac)
        if mt in ("stop", "start_game"):
            self.log("RX %s from %s: %s -- exiting" % (mt, mac, data))
            return "exit", None
        if kind == "echo_hello" and mac:
            if mac not in self.players and len(self.players) < 2:
                self.players.append(mac)
                ok = self.enow.add_peer(mac)
                print("  splatecho: player %d joined (%s)" % (len(self.players) - 1, mac))
                self.log("JOIN player %d = %s add_peer=%s"
                         % (len(self.players) - 1, mac, ok))
            if mac in self.players:
                ok = self.enow.send_to(mac, {"type": "echo_you",
                                             "player": self.players.index(mac)})
                n = self.you_sent.get(mac, 0) + 1
                self.you_sent[mac] = n
                if n <= 2 or not ok:
                    self.log("TX echo_you #%d to %s ok=%s" % (n, mac, ok))
                if self.phase not in ("start", "intro", "lobby") and n <= 5:
                    # A wand saying hello mid-game has restarted its game.
                    self.log("HELLO mid-game from %s (phase=%s)" % (mac, self.phase))
            else:
                self.log("HELLO from %s refused, players full" % mac)
        elif kind is not None and kind.startswith("echo_"):
            self.log("RX %s from %s (phase=%s)" % (data, mac, self.phase))
        elif self.rx[key] <= 3:
            self.log("RX other %s from %s: %s" % (mt, mac, data))
        return kind, data

    def wait(self, ms):
        """Service the Splats and messages for ms. Returns "exit" or None.
        Splat presses during the wait are discarded."""
        end = time.ticks_add(time.ticks_ms(), ms)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            kind, _ = self.poll()
            if kind == "exit":
                return "exit"
            self._ignore_splat(self.splat.poll())
            time.sleep_ms(1)
        return None

    def dark(self):
        self.splat.color("turnoff")

    # ── phases ──
    def intro(self):
        """Show each Splat's color and sound once, then wait for wands."""
        self._set_phase("intro")
        for i in range(min(len(UNITS), self.splat.count)):
            _light(self.splat, i)
            if self.wait(600) == "exit":
                return "exit"
            self.dark()
        self._set_phase("lobby")
        start = time.ticks_ms()
        step = 0
        while len(self.players) < 2:
            if self.players and time.ticks_diff(time.ticks_ms(), start) >= LOBBY_MS:
                print("  splatecho: one wand -- solo")
                self.log("SOLO: one wand after %d ms" % LOBBY_MS)
                break
            colors = [(0, 0, 0)] * self.leds.n
            colors[step % self.leds.n] = (40, 30, 0)
            self.leds.show_each(colors)
            step += 1
            if self.wait(120) == "exit":
                return "exit"
        return None

    def playback(self, p):
        self._set_phase("playback p%d" % p)
        rgb = PLAYER_RGB[p]
        _ring_count(self.leds, len(self.pattern), rgb)
        if self.wait(600) == "exit":
            return "exit"
        for unit in self.pattern:
            _light(self.splat, unit)
            if self.wait(SHOW_MS) == "exit":
                return "exit"
            self.dark()
            if self.wait(GAP_MS) == "exit":
                return "exit"
        return None

    def repeat(self, p):
        """Player p repeats the pattern. Returns True, False or "exit"."""
        rgb = PLAYER_RGB[p]
        splat = self.splat
        self.send({"type": "echo_repeat_now", "player": p, "len": len(self.pattern)})
        for idx, unit in enumerate(self.pattern):
            _ring_count(self.leds, len(self.pattern) - idx, rgb)
            want = unit % splat.count
            self._set_phase("repeat p%d step %d/%d want %d"
                            % (p, idx + 1, len(self.pattern), want))
            self.log("  splats at step start: %s" % self._units())
            t_step = time.ticks_ms()
            deadline = time.ticks_add(t_step, STEP_MS)
            while True:
                kind, _ = self.poll()
                if kind == "exit":
                    return "exit"
                ev = splat.poll()
                if ev is not None:
                    self.log("SPLAT %s on %d after %d ms (want %d)"
                             % (ev, splat.last_index,
                                time.ticks_diff(time.ticks_ms(), t_step), want))
                if ev == "press":
                    if splat.last_index == want:
                        _light(splat, unit)
                        self.send({"type": "echo_step", "player": p, "idx": idx})
                        if self.wait(PRESS_MS) == "exit":
                            return "exit"
                        self.dark()
                        break
                    print("  splatecho: player %d pressed Splat %d, wanted %d"
                          % (p, splat.last_index, want))
                    self.log("WRONG press: %d, wanted %d" % (splat.last_index, want))
                    return False
                if time.ticks_diff(time.ticks_ms(), deadline) >= 0:
                    print("  splatecho: player %d timed out on step %d" % (p, idx + 1))
                    self.log("TIMEOUT p%d step %d want %d; splats: %s"
                             % (p, idx + 1, want, self._units()))
                    return False
                time.sleep_ms(1)
        return True

    def add_step(self, p):
        """Player p adds one step with their wand. Returns "exit" or None."""
        self._set_phase("add p%d (len %d)" % (p, len(self.pattern)))
        self.add_id += 1
        add_id = self.add_id
        ask = {"type": "echo_add_now", "player": p, "len": len(self.pattern),
               "add": add_id}
        self.send(dict(ask))
        _ring_count(self.leds, len(self.pattern), PLAYER_RGB[p])
        t_add = time.ticks_ms()
        resend = time.ticks_add(t_add, ADD_RESEND_MS)
        while True:
            kind, data = self.poll()
            if kind == "exit":
                return "exit"
            if kind == "echo_add" and data.get("add") != add_id:
                self.log("STALE echo_add %s ignored (want add %d)" % (data, add_id))
                kind = None
            if kind == "echo_add" and isinstance(data.get("unit"), int):
                unit = data["unit"]
                self.pattern.append(unit)
                print("  splatecho: player %d added unit %d (length %d)"
                      % (p, unit, len(self.pattern)))
                self.log("ADDED unit %d after %d ms, pattern %s (resends so far %d)"
                         % (unit, time.ticks_diff(time.ticks_ms(), t_add),
                            self.pattern, self.resends))
                rgb = _light(self.splat, unit)
                _ring_count(self.leds, len(self.pattern), rgb)
                if self.wait(SHOW_MS) == "exit":
                    return "exit"
                self.dark()
                return self.wait(ADD_PAUSE_MS)
            if time.ticks_diff(time.ticks_ms(), resend) >= 0:
                self.resends += 1
                self.send(dict(ask), quiet=True)
                resend = time.ticks_add(time.ticks_ms(), ADD_RESEND_MS)
            self._ignore_splat(self.splat.poll())
            time.sleep_ms(1)

    def result(self, p, ok):
        """Show and send a repeat's result. A failed repeat scores for
        the other player (no score change when playing solo)."""
        if not ok and len(self.players) > 1:
            self.scores[1 - p] += 1
        self._set_phase("result p%d ok=%s" % (p, ok))
        self.send({"type": "echo_result", "ok": ok, "player": p,
                   "len": len(self.pattern), "scores": list(self.scores)})
        self.splat.color("turngreen" if ok else "turnred")
        self.leds.fill((0, 30, 0) if ok else (30, 0, 0))
        print("  splatecho: %s  scores %s" % ("correct" if ok else "round over", self.scores))
        r = self.wait(OK_MS if ok else FAIL_MS)
        self.dark()
        return r

    def run(self):
        print("  splatecho: %d Splat(s); waiting for wands" % self.splat.count)
        self.log("START %d Splat(s); splats: %s" % (self.splat.count, self._units()))
        self.splat.off()
        if self.intro() == "exit":
            return
        p = 0
        while True:
            self._set_phase("turn p%d len %d" % (p, len(self.pattern)))
            self.send({"type": "echo_turn", "player": p, "len": len(self.pattern)})
            print("  splatecho: player %d's turn, length %d" % (p, len(self.pattern)))
            if self.pattern:
                if self.playback(p) == "exit":
                    return
                ok = self.repeat(p)
                if ok == "exit":
                    return
                if self.result(p, ok) == "exit":
                    return
                if not ok:
                    self.pattern = []
                    p = (p + 1) % max(1, len(self.players))
                    continue
            if len(self.pattern) < MAX_LEN:
                if self.add_step(p) == "exit":
                    return
            p = (p + 1) % max(1, len(self.players))


def play(splat, leds, enow, batt=None):
    log = _Log("echo")
    log.flush("started (only this line later = hub reset or hard hang)")
    game = _Game(splat, leds, enow, log)
    why = "exit"
    try:
        game.run()
    except Exception as e:
        why = "exception %r" % e
        log("EXCEPTION in phase %s: %r" % (game.phase, e))
        raise
    finally:
        try:
            log("END phase=%s: %s" % (game.phase, game._snapshot()))
        except Exception as e:
            log("END snapshot failed: %r" % e)
        log.flush(why)
        leds.fill((0, 0, 0))
