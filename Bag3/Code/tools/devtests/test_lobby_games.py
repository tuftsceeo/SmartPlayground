"""The Splat host demo games (Wand Module/games/host_lobbytest.py, host_splattag.py,
host_relaycolor.py) in one scripted session each, on the A6 simulation: the host
wand holds the Splats, players join and hold none. Turning the Splats off afterwards is main.py's job, not the games'.

Run: python3 tools/devtests/test_lobby_games.py
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
import splat_host  # noqa: E402
from splat_api import COLOR_RGB  # noqa: E402

sys.path.insert(0, os.path.join(BB, "Wand Module", "games"))
import host_lobbytest  # noqa: E402
import host_splattag  # noqa: E402
import host_relaycolor  # noqa: E402

check = wandsim.Checker()
pairing.max_splats = lambda: pairing.HOST_MAX_SPLATS      # every sim wand may hold 4

OFFC = (0, 0, 0)
MACS = [S[1], S[2], S[3], S[4]]


def lit(p):
    """The color a fake Splat is showing, from replaying its writes."""
    c = OFFC
    for _, name, d in p.writes:
        if name == "setLEDs":
            c = tuple(d[-3:])
        elif name in ("allLEDsOff", "allTasksOff"):
            c = OFFC
    return c


def ident(n):
    return tuple(COLOR_RGB[splatpair.identity_name(W[n])])


def session(mod, players):
    """Host wand 1 (4 Splats) and the player wands tap mod's lobby; the host's long hold
    starts the game. Returns (sc, host, players)."""
    sc = Sc()
    h = sc.wand(1, [1, 2, 3, 4])
    ps = [sc.wand(n) for n in players]
    for n, at, host in [(1, 0, True)] + [(n, 1500 + 500 * k, False) for k, n in enumerate(players)]:
        w = sc.wands[n]

        def run(w=w, at=at, host=host):
            if w.splat_macs:
                w.ctl = splatpair.SplatPairing(list(w.splat_macs), w.enow, w.leds, w.buz,
                                               my_mac=w.mac)
                t0 = time.ticks_ms()
                while not all(l.ready for l in w.ctl.hub.links) and time.ticks_ms() - t0 < 5000:
                    w.ctl.poll()
                    time.sleep_ms(5)
            if time.ticks_ms() < at:
                time.sleep_ms(at - time.ticks_ms())
            net = lobby_game.enter(w.enow, mod.__name__, mod.SPLATS_MIN, mod.SPLATS_MAX, w.ctl,
                                   w.mac, w.nfc, w.leds, w.buz, lambda: w.button,
                                   True, host, mod.PLAYERS_MIN)
            w.net = net
            if net is not None:
                try:
                    mod.play(w.nfc, w.leds, w.buz, None, None, w.enow, None, net)
                finally:
                    net.close()
            w.result = "done"

        sc.sim.spawn("wand%d" % n, run, w)
    sc.sim.run_until(lambda: net_of(h) is not None and net_of(h).phase == "lobby"
                     and net_of(h).lobby_players() == len(players), 20000, 10)
    press(sc, h, sc.sim.now + 10, splat_host.START_HOLD_MS + 100)
    sc.run(splat_host.START_HOLD_MS + 1500)     # players show the game icon for 700 ms first
    return sc, h, ps


def pulse(sc, w):
    press(sc, w, sc.sim.now + 5, 200)           # longer than one 100 ms exit-card read
    sc.run(450)


def splat_press(sc, w, mac):
    w.ble.button(mac, True)
    sc.run(200)
    w.ble.button(mac, False)
    sc.run(200)


def stop(sc, w, wands):
    w.nfc.stop_at = sc.sim.now + 5
    sc.run(4500)
    return all(x.result == "done" for x in wands)


# ── host_lobbytest ──
sc, h, (p2, p3) = session(host_lobbytest, [2, 3])
nh = net_of(h)
check("lobbytest: the host holds all 4 Splats, the players none",
      nh.phase == "game" and nh.splat_count == 4 and net_of(p2).splat_count == 4
      and [w[2] for w in nh.wands] == [4, 0, 0], str(nh.wands))
pulse(sc, p2)
check("a player's button lights Splat 0 in that player's identity color",
      lit(h.periph(S[1])) == ident(2), str(lit(h.periph(S[1]))))
pulse(sc, p3)
check("the next press lights Splat 1 and turns Splat 0 off",
      lit(h.periph(S[2])) == ident(3) and lit(h.periph(S[1])) == OFFC)
splat_press(sc, h, S[4])
check("a Splat press lights that Splat white", lit(h.periph(S[4])) == COLOR_RGB["turnwhite"],
      str(lit(h.periph(S[4]))))
check("a stop card on the host ends the game for all",
      stop(sc, h, (h, p2, p3)))

# ── host_splattag ──
random.seed(5)
sc, h, (p2, p3) = session(host_splattag, [2, 3])
cols = (ident(2), ident(3))
scores = {2: 0, 3: 0}
wrong_done = False
for _ in range(host_splattag.WIN_SCORE * 3):
    if not sc.sim.run_until(lambda: any(lit(h.periph(m)) in cols for m in MACS), 9000, 5):
        break
    m = [m for m in MACS if lit(h.periph(m)) in cols][0]
    if not wrong_done:
        other = [x for x in MACS if x != m][0]
        splat_press(sc, h, other)
        wrong_done = lit(h.periph(m)) in cols
        check("a press on a Splat that is not the target scores nothing", wrong_done)
    scores[2 if lit(h.periph(m)) == cols[0] else 3] += 1
    splat_press(sc, h, m)
    sc.run(host_splattag.PAUSE_MS)
    if max(scores.values()) >= host_splattag.WIN_SCORE:
        break
check("splattag: presses on the target score for the player it was lit for until a win",
      max(scores.values()) == host_splattag.WIN_SCORE, str(scores))
sent = [x[3]["d"] for x in sc.bus.sent(typ="pw_msg") if x[1] == W[1]]
check("the host sent the scores, then the winner", any(d.get("s") for d in sent if "s" in d)
      and any("win" in d for d in sent), str(sent[-2:]))
sc.run(4500)
check("every wand's play() returns after the win", h.result == p2.result == p3.result == "done")

# ── host_relaycolor ──
sc, h, (p2, p3) = session(host_relaycolor, [2, 3])
sc.run(200)
check("relaycolor: the first player holds the token; every Splat in their color",
      all(lit(h.periph(m)) == ident(2) for m in MACS))
pulse(sc, p3)
check("a button on a wand that does not hold the token is ignored",
      all(lit(h.periph(m)) == ident(2) for m in MACS))
pulse(sc, p2)
check("the holder's button passes the token to the next player; Splats follow",
      all(lit(h.periph(m)) == ident(3) for m in MACS))
pulse(sc, p3)
check("the last player passes back to the first",
      all(lit(h.periph(m)) == ident(2) for m in MACS))
sc.bus.drop_frame = lambda src, dst, obj: src == W[2]
sc.run(lobby_game.WAND_LOST_MS + 1500)
check("the holder's wand lost: the host hands the token to the next live player",
      all(lit(h.periph(m)) == ident(3) for m in MACS))
sc.bus.drop_frame = None
check("a stop card on the host ends the game", stop(sc, h, (h, p2, p3)))

check.finish("lobby games OK")
