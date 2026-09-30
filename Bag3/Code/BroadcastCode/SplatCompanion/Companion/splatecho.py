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
  from a wand  {"type": "echo_hello"}
               {"type": "echo_add", "unit": i}
  to one wand  {"type": "echo_you", "player": p}              (p = 0 or 1)
  broadcast    {"type": "echo_turn", "player": p, "len": n}
               {"type": "echo_add_now", "player": p}
               {"type": "echo_step", "player": p, "idx": k}
               {"type": "echo_result", "ok": bool, "player": p,
                "len": n, "scores": [s0, s1]}

Exits on ESP-NOW "stop" or "start_game" (cards arrive the same way; see
main.py's _GameEnow).
"""

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
OK_MS = 600            # green after a full repeat
FAIL_MS = 1500         # red when a round ends
MAX_LEN = 12           # ring pixels; the pattern stops growing here


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
    def __init__(self, splat, leds, enow):
        self.splat = splat
        self.leds = leds
        self.enow = enow
        self.players = []            # wand MAC strings, index = player number
        self.scores = [0, 0]
        self.pattern = []

    # ── messages ──
    def poll(self):
        """One ESP-NOW message. Handles joining; returns (kind, data), or
        ("exit", None) on stop/start_game."""
        mt, data, mac = self.enow.poll()
        if mt in ("stop", "start_game"):
            return "exit", None
        kind = data.get("type") if isinstance(data, dict) else None
        if kind == "echo_hello" and mac:
            if mac not in self.players and len(self.players) < 2:
                self.players.append(mac)
                self.enow.add_peer(mac)
                print("  splatecho: player %d joined (%s)" % (len(self.players) - 1, mac))
            if mac in self.players:
                self.enow.send_to(mac, {"type": "echo_you",
                                        "player": self.players.index(mac)})
        return kind, data

    def wait(self, ms):
        """Service the Splats and messages for ms. Returns "exit" or None.
        Splat presses during the wait are discarded."""
        end = time.ticks_add(time.ticks_ms(), ms)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            kind, _ = self.poll()
            if kind == "exit":
                return "exit"
            self.splat.poll()
            time.sleep_ms(1)
        return None

    def dark(self):
        self.splat.color("turnoff")

    # ── phases ──
    def intro(self):
        """Show each Splat's color and sound once, then wait for wands."""
        for i in range(min(len(UNITS), self.splat.count)):
            _light(self.splat, i)
            if self.wait(600) == "exit":
                return "exit"
            self.dark()
        start = time.ticks_ms()
        step = 0
        while len(self.players) < 2:
            if self.players and time.ticks_diff(time.ticks_ms(), start) >= LOBBY_MS:
                print("  splatecho: one wand -- solo")
                break
            colors = [(0, 0, 0)] * self.leds.n
            colors[step % self.leds.n] = (40, 30, 0)
            self.leds.show_each(colors)
            step += 1
            if self.wait(120) == "exit":
                return "exit"
        return None

    def playback(self, p):
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
        for idx, unit in enumerate(self.pattern):
            _ring_count(self.leds, len(self.pattern) - idx, rgb)
            want = unit % splat.count
            deadline = time.ticks_add(time.ticks_ms(), STEP_MS)
            while True:
                kind, _ = self.poll()
                if kind == "exit":
                    return "exit"
                if splat.poll() == "press":
                    if splat.last_index == want:
                        _light(splat, unit)
                        self.enow.broadcast({"type": "echo_step", "player": p, "idx": idx})
                        if self.wait(PRESS_MS) == "exit":
                            return "exit"
                        self.dark()
                        break
                    print("  splatecho: player %d pressed Splat %d, wanted %d"
                          % (p, splat.last_index, want))
                    return False
                if time.ticks_diff(time.ticks_ms(), deadline) >= 0:
                    print("  splatecho: player %d timed out on step %d" % (p, idx + 1))
                    return False
                time.sleep_ms(1)
        return True

    def add_step(self, p):
        """Player p adds one step with their wand. Returns "exit" or None."""
        self.enow.broadcast({"type": "echo_add_now", "player": p})
        _ring_count(self.leds, len(self.pattern), PLAYER_RGB[p])
        while True:
            kind, data = self.poll()
            if kind == "exit":
                return "exit"
            if kind == "echo_add" and isinstance(data.get("unit"), int):
                unit = data["unit"]
                self.pattern.append(unit)
                print("  splatecho: player %d added unit %d (length %d)"
                      % (p, unit, len(self.pattern)))
                rgb = _light(self.splat, unit)
                _ring_count(self.leds, len(self.pattern), rgb)
                if self.wait(SHOW_MS) == "exit":
                    return "exit"
                self.dark()
                return None
            self.splat.poll()
            time.sleep_ms(1)

    def result(self, p, ok):
        """Show and broadcast a repeat's result. A failed repeat scores for
        the other player (no score change when playing solo)."""
        if not ok and len(self.players) > 1:
            self.scores[1 - p] += 1
        self.enow.broadcast({"type": "echo_result", "ok": ok, "player": p,
                             "len": len(self.pattern), "scores": list(self.scores)})
        self.splat.color("turngreen" if ok else "turnred")
        self.leds.fill((0, 30, 0) if ok else (30, 0, 0))
        print("  splatecho: %s  scores %s" % ("correct" if ok else "round over", self.scores))
        r = self.wait(OK_MS if ok else FAIL_MS)
        self.dark()
        return r

    def run(self):
        print("  splatecho: %d Splat(s); waiting for wands" % self.splat.count)
        self.splat.off()
        if self.intro() == "exit":
            return
        p = 0
        while True:
            self.enow.broadcast({"type": "echo_turn", "player": p, "len": len(self.pattern)})
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
    try:
        _Game(splat, leds, enow).run()
    finally:
        leds.fill((0, 0, 0))
