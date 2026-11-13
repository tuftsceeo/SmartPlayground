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
from lobbysim import Sc, W, S, net_of, press, lobby_game, splatpair  # noqa: E402
from wandsim import BB  # noqa: E402
import pairing  # noqa: E402

sys.path.insert(0, os.path.join(BB, "..", "Wand Module", "games"))
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
    press(sc, w, sc.sim.now + 5)
    sc.run(300)


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


# ── lobby: the host leads, players join, count shown, nobody else leads ──
sc, h, (p2, p3) = setup(host_lobbytest, [2, 3])
nh = net_of(h)
check("the host leads its lobby", nh.is_leader and nh.is_host)
check("the host counts 2 players, not itself", nh.lobby_players() == 2, str(nh.lobby_players()))
check("players joined, none leads", not net_of(p2).is_leader and not net_of(p3).is_leader)
import leds as _L  # noqa: E402
shapes = [c for c in h.leds.calls if c[0] == "show_shape"]
check("the host shows the numeral 2, in green once it can start",
      shapes and shapes[-1][1] == tuple(_L.SHAPE_2) and shapes[-1][2] == _L.GREEN, str(shapes[-1:]))
press(sc, h, sc.sim.now + 10)
sc.run(600)
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

# ── host_splattag ──
random.seed(5)
sc, h, (p2, p3) = setup(host_splattag, [2, 3])
press(sc, h, sc.sim.now + 10)
sc.run(600)
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
sc.run(host_splattag.OVER_MS + 1500)
check("...and every wand leaves after the win", h.result == p2.result == p3.result == "done")

# ── host_relaycolor ──
sc, h, (p2, p3) = setup(host_relaycolor, [2, 3])
press(sc, h, sc.sim.now + 10)
sc.run(800)
check("host_relaycolor: the first player holds the token; every Splat in their color",
      all(lit(h.periph(m)) == ident_rgb(2) for m in macs))
pulse(sc, p2)
sc.run(400)
check("the holder's button passes it on; Splats follow",
      all(lit(h.periph(m)) == ident_rgb(3) for m in macs))
h.nfc.stop_at = sc.sim.now + 5
sc.run(1500)

check.finish("splat host OK")
