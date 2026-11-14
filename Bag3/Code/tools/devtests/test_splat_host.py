"""Splat host role: a host wand holding 4 Splats leads a host game's lobby;
game wands (no Splats) only join it. Runs the ported host games
(Wand Module/games/host_*.py) on the A6 simulation.

Run: python3 tools/devtests/test_splat_host.py
"""
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wandsim  # noqa: E402
from lobbysim import Sc, W, S, NETS, net_of, press, lobby_game, splatpair  # noqa: E402
from wandsim import BB  # noqa: E402
import pairing  # noqa: E402
import splat_host  # noqa: E402

sys.path.insert(0, os.path.join(BB, "Wand Module", "games"))
import host_lobbytest  # noqa: E402
import host_splattag  # noqa: E402
import host_relaycolor  # noqa: E402

check = wandsim.Checker()
pairing.max_splats = lambda: pairing.HOST_MAX_SPLATS      # every sim wand may hold 4

OFFC = (0, 0, 0)
WHITE = (255, 255, 255)


def lit(p):
    c = OFFC
    for _, name, d in p.writes:
        if name == "setLEDs":
            c = tuple(d[-3:])
        elif name in ("allLEDsOff", "allTasksOff"):
            c = OFFC
    return c


def tap(sc, n, at_ms, mod, host=False):
    """Wand n enters mod's lobby at at_ms (as the Splat host if host) and plays it."""
    w = sc.wands[n]
    slug = mod.__name__

    def run():
        if w.splat_macs:
            w.ctl = splatpair.SplatPairing(list(w.splat_macs), w.enow, w.leds, w.buz, my_mac=w.mac)
            t0 = time.ticks_ms()
            while not all(l.ready for l in w.ctl.hub.links) and time.ticks_ms() - t0 < 5000:
                w.ctl.poll()
                time.sleep_ms(5)
        if time.ticks_ms() < at_ms:
            time.sleep_ms(at_ms - time.ticks_ms())
        net = lobby_game.enter(w.enow, slug, mod.SPLATS_MIN, mod.SPLATS_MAX, w.ctl, w.mac,
                               w.nfc, w.leds, w.buz, lambda: w.button,
                               True, host, getattr(mod, "PLAYERS_MIN", 1))
        w.net = net
        w.last_end = lobby_game.last_end
        if net is not None:
            try:
                mod.play(w.nfc, w.leds, w.buz, None, None, w.enow, None, net)
            finally:
                net.close()
        w.result = "done"

    return sc.sim.spawn("wand%d" % n, run, w)


def splat_press(sc, w, mac):
    w.ble.button(mac, True)
    sc.run(200)
    w.ble.button(mac, False)
    sc.run(200)


def pulse(sc, w):
    # held longer than one 100 ms exit-card read: the host games poll the button between reads
    press(sc, w, sc.sim.now + 5, 200)
    sc.run(450)


def ident_rgb(n):
    """The Splat LED color for wand n's identity name."""
    from splat_api import COLOR_RGB
    return tuple(COLOR_RGB[splatpair.identity_name(W[n])])


def setup(mod, players, host_first=True):
    sc = Sc()
    h = sc.wand(1, [1, 2, 3, 4])
    ps = [sc.wand(n) for n in players]
    if host_first:
        tap(sc, 1, 0, mod, host=True)
        for k, n in enumerate(players):
            tap(sc, n, 1500 + 500 * k, mod)
    else:
        for k, n in enumerate(players):
            tap(sc, n, 0 + 300 * k, mod)
        tap(sc, 1, 3000, mod, host=True)
    sc.sim.run_until(lambda: net_of(h) is not None and net_of(h).phase == "lobby"
                     and net_of(h).lobby_players() == len(players), 20000, 10)
    return sc, h, ps


def hold_start(sc, h):
    press(sc, h, sc.sim.now + 10, splat_host.START_HOLD_MS + 100)
    sc.run(splat_host.START_HOLD_MS + 700)
    sc.run(800)         # a player's wand shows the game icon for 700 ms before it reads the button


# ── host screen and slots (no radio) ──
R, G, B = (100, 0, 0), (0, 100, 0), (0, 0, 100)
px = splat_host.frame([(R, G), None, None, None], [True, False, False, False], "idle", 0)
check("corner TL shows the pair: left column A, right column B",
      px[0] == px[5] == splat_host._scale(R, splat_host.PAIR_SCALE)
      and px[1] == px[6] == splat_host._scale(G, splat_host.PAIR_SCALE))
check("the corner blocks are (0,1,5,6) (3,4,8,9) (15,16,20,21) (18,19,23,24)",
      splat_host.CORNERS == ((0, 1, 5, 6), (3, 4, 8, 9), (15, 16, 20, 21), (18, 19, 23, 24)))
check("idle: the cross is off", all(px[i] == (0, 0, 0) for i in splat_host.CROSS_FILL + (12,)))
check("only the next empty slot breathes",
      px[3] != splat_host.EMPTY_RGB and px[15] == px[18] == splat_host.EMPTY_RGB, str((px[3], px[15])))
on = splat_host.frame([(R, G)] * 4, [False] * 4, "idle", 0)
off = splat_host.frame([(R, G)] * 4, [False] * 4, "idle", splat_host.MISSING_FLASH_MS)
check("a missing Splat flashes", on[0] != (0, 0, 0) and off[0] == (0, 0, 0))
check("...but shows solid during boot",
      splat_host.frame([(R, G)] * 4, [False] * 4, "idle", splat_host.MISSING_FLASH_MS, boot=True)[0] != (0, 0, 0))
lob = splat_host.frame([None] * 4, [False] * 4, "lobby", 1000, hold=0.5, lobby_rgb=B)
check("lobby: center pixel is the lobby color; a half hold lights half the cross",
      lob[12] == B and [lob[i] for i in splat_host.CROSS_FILL].count(splat_host.HOLD_RGB) == 4)
check("forget hold: corners go out from the last",
      splat_host.frame([(R, G)] * 4, [True] * 4, "idle", 0, gone=1)[18] == (0, 0, 0))

wandsim.new_sim()            # patches time.ticks_*
hs = splat_host.HostScreen(born=0)
a, _, _ = hs.button(True, "lobby", 0)
a, _, _ = hs.button(False, "lobby", splat_host.SHORT_PRESS_MS - 50)
check("a short press is a peek", a == "peek" and hs.peeking(splat_host.SHORT_PRESS_MS))
check("the peek ends after PEEK_MS", not hs.peeking(splat_host.SHORT_PRESS_MS + splat_host.PEEK_MS))
hs.button(True, "lobby", 10000)
a, hold, _ = hs.button(True, "lobby", 10000 + splat_host.START_HOLD_MS - 1)
check("a hold just under START_HOLD_MS does not start", a is None and 0 < hold < 1)
a, _, _ = hs.button(True, "lobby", 10000 + splat_host.START_HOLD_MS, can_start=False)
check("a full hold with no players is refused", a == "refuse")
hs.button(False, "lobby", 20000)
hs.button(True, "playing", 30000)
a1, _, _ = hs.button(True, "playing", 30000 + splat_host.START_HOLD_MS)
a2, _, _ = hs.button(True, "playing", 30000 + splat_host.END_HOLD_MS)
check("ending needs the longer hold", a1 is None and a2 == "end"
      and splat_host.END_HOLD_MS > splat_host.START_HOLD_MS)
hs.button(False, "playing", 40000)
hs.button(True, "idle", 50000)
_, _, g2 = hs.button(True, "idle", 52000)
a, _, _ = hs.button(True, "idle", 50000 + splat_host.FORGET_HOLD_MS)
check("idle hold: a corner goes out per second, then forget", g2 == 2 and a == "forget")

used = []
for m in ("AB:42:00:00:00:00", "AB:42:00:00:06:06", "AB:42:00:00:0C:0C"):
    used.append(splatpair.pick_pair(m, used))
check("pairs differ in their halves and never repeat on a host",
      all(a != b for a, b in used) and len(set(used)) == 3, str(used))

import tempfile
_path = pairing.PATH
pairing.PATH = os.path.join(tempfile.mkdtemp(), "pairing.json")
pairing.os.rename = os.replace     # MicroPython rename overwrites; Windows does not
_is_host = pairing.is_host
pairing.is_host = lambda: True
pairing.clear()
for m in ("AB:42:00:00:00:01", "AB:42:00:00:00:02", "AB:42:00:00:00:03", "AB:42:00:00:00:04"):
    pairing.add(m, splatpair.pick_pair)
sl = pairing.load_slots()
check("four Splats fill the four slots in order", [e[0][-2:] for e in sl] == ["01", "02", "03", "04"])
try:
    pairing.add("AB:42:00:00:00:05", splatpair.pick_pair)
    check("a fifth Splat is refused", False)
except ValueError:
    check("a fifth Splat is refused", True)
pairing.remove("AB:42:00:00:00:02")
check("a removed Splat leaves its slot missing", pairing.load_slots()[1] == sl[1]
      and "AB:42:00:00:00:02" not in pairing.load())
pairing.add("AB:42:00:00:00:09", splatpair.pick_pair)
s2 = pairing.load_slots()[1]
check("a new Splat fills the missing slot and takes its pair",
      s2[0] == "AB:42:00:00:00:09" and s2[1:] == sl[1][1:], str(s2))
pairing.clear()
pairing.is_host = _is_host
pairing.PATH = _path


# ── lobby: the host leads, players join, count shown, nobody else leads ──
sc, h, (p2, p3) = setup(host_lobbytest, [2, 3])
nh = net_of(h)
check("the host leads its lobby", nh.is_leader and nh.is_host)
check("the host counts 2 players, not itself", nh.lobby_players() == 2, str(nh.lobby_players()))
check("players joined, none leads", not net_of(p2).is_leader and not net_of(p3).is_leader)
import leds as _L  # noqa: E402
check("the host's lobby screen has no numeral until a short press",
      not [c for c in h.leds.calls if c[0] == "show_shape"])
press(sc, h, sc.sim.now + 10)
sc.run(200)
shapes = [c for c in h.leds.calls if c[0] == "show_shape"]
check("a short press peeks the player count as the numeral 2",
      shapes and shapes[-1][1] == tuple(_L.SHAPE_2), str(shapes[-1:]))
check("...and does not start the game", nh.phase == "lobby")
hold_start(sc, h)
check("the host's button starts the game for all three", all(
    net_of(w).phase == "game" for w in (h, p2, p3)))
check("net.players excludes the host on every wand",
      nh.players == [1, 2] and net_of(p2).players == [1, 2], "%s %s" % (nh.players, net_of(p2).players))
check("the pool is the host's 4 Splats", nh.splat_count == 4 and net_of(p2).splat_count == 4)
pulse(sc, p2)
check("a player's button lights Splat 0 in the player's identity color",
      lit(h.periph(S[1])) == ident_rgb(2), str(lit(h.periph(S[1]))))
pulse(sc, p3)
check("...the next player's press lights Splat 1 and turns Splat 0 off",
      lit(h.periph(S[2])) == ident_rgb(3) and lit(h.periph(S[1])) == OFFC)
splat_press(sc, h, S[4])
check("a Splat press reaches the host's game", lit(h.periph(S[4])) != OFFC, str(lit(h.periph(S[4]))))
h.nfc.stop_at = sc.sim.now + 5
sc.run(1500)
check("a stop card on the host ends the game for everyone",
      h.result == p2.result == p3.result == "done")

# ── players tap before the host exists: they wait, then join ──
sc, h, (p2,) = setup(host_lobbytest, [2], host_first=False)
check("a player that tapped first waited for the host instead of leading",
      net_of(h).is_leader and not net_of(p2).is_leader and net_of(h).lobby_players() == 1)

# ── teacher start_game starts a host lobby ──
teacher = sc.wand(6)
sc.sim.at(sc.sim.now + 5, lambda: teacher.enow.broadcast({"type": "start_game", "name": "host_lobbytest"}))
sc.run(800)
check("the teacher's start_game for the slug starts the host lobby (players stay in)",
      net_of(h).phase == "game" and net_of(p2).phase == "game")
sc.sim.at(sc.sim.now + 5, lambda: teacher.enow.broadcast(["stop"]))
sc.run(1500)

# ── no host: a host game's player gives up ──
sc = Sc()
p2 = sc.wand(2)
tap(sc, 2, 0, host_lobbytest)
sc.run(lobby_game.HOST_FIND_TRIES * 700 + 2000)
check("with no host, a player never leads and ends with no_host",
      p2.result == "done" and p2.net is None and p2.last_end == "no_host", str(p2.last_end))

# ── a player wand's own paired Splats stay out of a host game ──
class _Passive:
    """A host game that only records net events, per wand."""
    __name__ = "host_passive"
    SPLATS_MIN = 1
    SPLATS_MAX = None
    PLAYERS_MIN = 1
    EVENTS = {}

    @staticmethod
    def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
        evs_ = _Passive.EVENTS.setdefault(net.my_mac, [])
        end = time.ticks_ms() + 30000
        while time.ticks_ms() < end:
            ev = net.poll()
            if ev is not None:
                evs_.append(ev)
                if ev in (("end",), ("leader_lost",)):
                    return
            time.sleep_ms(1)


NETS[:] = []
sc = Sc()
h = sc.wand(1, [1, 2, 3, 4])
p2 = sc.wand(2, [5])
tap(sc, 1, 0, _Passive, host=True)
tap(sc, 2, 1500, _Passive)
sc.sim.run_until(lambda: net_of(h) is not None and net_of(h).phase == "lobby"
                 and net_of(h).lobby_players() == 1, 20000, 10)
check("a player wand with its own Splat joins the host lobby with 0 Splats",
      net_of(h).lobby_splats() == 4, str(net_of(h).lobby_splats()))
hold_start(sc, h)
nh, np2 = net_of(h), net_of(p2)
check("...the roster gives the player 0 Splats and the pool is the host's 4",
      nh.wands[1][2] == 0 and nh.splat_count == 4 and np2.splat_count == 4, str(nh.wands))
for _v in _Passive.EVENTS.values():
    _v[:] = []
p2.ble.button(S[5], True)
sc.run(200)
p2.ble.button(S[5], False)
sc.run(300)
check("...and its own Splat's press is a game event on no wand",
      not any(e[0] in ("press", "release") for evl in _Passive.EVENTS.values() for e in evl),
      str(_Passive.EVENTS))
try:
    np2.splat(0)
    check("net.splat() is refused on a player wand", False)
except RuntimeError:
    check("net.splat() is refused on a player wand", True)

# the host's own Splat dropping: splat_lost / splat_back on the host
for _v in _Passive.EVENTS.values():
    _v[:] = []
h.ble.periph(S[2]).available = False
h.ble.drop(S[2])
sc.run(500)
hev = _Passive.EVENTS.get(W[1], [])
check("a host Splat dropping is splat_lost on the host", ("splat_lost", 1) in hev, str(hev))
h.ble.periph(S[2]).available = True
sc.run(14000)
hev = _Passive.EVENTS.get(W[1], [])
check("...and splat_back after the reconnect", ("splat_back", 1) in hev, str(hev))
h.nfc.stop_at = sc.sim.now + 5
sc.run(1500)

# ── host_splattag ──
random.seed(5)
sc, h, (p2, p3) = setup(host_splattag, [2, 3])
hold_start(sc, h)
macs = [S[1], S[2], S[3], S[4]]
scores = {2: 0, 3: 0}
for _ in range(host_splattag.WIN_SCORE * 3):
    ok = sc.sim.run_until(lambda: any(lit(h.periph(m)) in (ident_rgb(2), ident_rgb(3)) for m in macs), 9000, 5)
    if not ok:
        break
    m = [m for m in macs if lit(h.periph(m)) in (ident_rgb(2), ident_rgb(3))][0]
    who = 2 if lit(h.periph(m)) == ident_rgb(2) else 3
    scores[who] += 1
    splat_press(sc, h, m)
    sc.run(host_splattag.PAUSE_MS)
    if max(scores.values()) >= host_splattag.WIN_SCORE:
        break
check("host_splattag: targets in player colors; presses score to that player until a win",
      max(scores.values()) == host_splattag.WIN_SCORE, str(scores))
sc.run(4500)        # the players show the winner for 3 s
check("...and every wand leaves after the win", h.result == p2.result == p3.result == "done")

# ── host_relaycolor ──
sc, h, (p2, p3) = setup(host_relaycolor, [2, 3])
hold_start(sc, h)
sc.run(200)
check("host_relaycolor: the first player holds the token; every Splat in their color",
      all(lit(h.periph(m)) == ident_rgb(2) for m in macs))
pulse(sc, p2)
sc.run(400)
check("the holder's button passes it on; Splats follow",
      all(lit(h.periph(m)) == ident_rgb(3) for m in macs))
h.nfc.stop_at = sc.sim.now + 5
sc.run(1500)

check.finish("splat host OK")
