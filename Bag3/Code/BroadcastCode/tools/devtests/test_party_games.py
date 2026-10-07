"""The demo party games (MockWand/games/partytest.py, splattag.py,
relaycolor.py) in a scripted session each, on the A6 simulation.

Run: python3 tools/devtests/test_party_games.py
"""
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wandsim  # noqa: E402
from partysim import Sc, W, S, net_of, press, evs, party, splatpair  # noqa: E402
from wandsim import BB  # noqa: E402

sys.path.insert(0, os.path.join(BB, "MockWand", "games"))
import partytest  # noqa: E402
import splattag  # noqa: E402
import relaycolor  # noqa: E402

check = wandsim.Checker()

GREEN, BLUE, PURPLE, RED, YELLOW = (0, 255, 0), (0, 0, 255), (160, 0, 200), (255, 0, 0), (255, 180, 0)
OFFC = (0, 0, 0)


def lit(p):
    """The color a fake Splat is showing, from replaying its writes."""
    c = OFFC
    for _, name, d in p.writes:
        if name == "setLEDs":
            c = tuple(d[-3:])
        elif name in ("allLEDsOff", "allTasksOff"):
            c = OFFC
    return c


def player(mod):
    def run(net, w):
        mod.play(w.nfc, w.leds, w.buz, None, None, w.enow, None, net)
    return run


def pixel0(w):
    return w.leds.pixels.get(0)


def pulse(sc, w, ms=0):
    press(sc, w, sc.sim.now + 5 + ms)
    sc.run(150 + ms)


def splat_press(sc, w, mac):
    w.ble.button(mac, True)
    sc.run(200)
    w.ble.button(mac, False)
    sc.run(200)


def start(sc, wands, mod, smin, leader=1, gap=2500):
    """Wand 1 taps first and leads; the others join; the leader's button starts."""
    for k, n in enumerate(wands):
        sc.tap(n, k * gap, player(mod), smin=smin)
    lw = sc.wands[leader]
    sc.sim.run_until(lambda: (net_of(lw) is not None and net_of(lw).phase == "lobby"
                              and len(net_of(lw)._members) == len(wands)
                              and net_of(lw).can_start()), 20000, 10)
    press(sc, lw, sc.sim.now + 10)
    sc.run(400)


def ident_rgb(n):
    return splatpair.WAND_RGB[splatpair.identity_name(W[n])]


# ── partytest ──
sc = Sc()
w1, w2, w3 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3)
start(sc, [1, 2, 3], partytest, smin=2)
n1 = net_of(w1)
check("partytest: the lobby started a game of 3 wands, 2 Splats", n1.phase == "game"
      and len(n1.wands) == 3 and n1.splat_count == 2)
p1, p2 = w1.periph(S[1]), w2.periph(S[2])
pulse(sc, w2)
sc.run(300)
check("a follower's button lights pool Splat 0 in the follower's identity color",
      lit(p1) == BLUE, "%s (wand 2 identity %s)" % (lit(p1), splatpair.identity_name(W[2])))
pulse(sc, w1)
sc.run(300)
check("the leader's button lights the next pool Splat (a follower's) in its own identity color",
      lit(p2) == GREEN, str(lit(p2)))
check("...and turns the previous one off", lit(p1) == OFFC, str(lit(p1)))
pulse(sc, w3)
sc.run(300)
check("a plain wand's button works: pool Splat 0 again, in its identity color",
      lit(p1) == PURPLE, str(lit(p1)))
splat_press(sc, w2, S[2])
check("a Splat press lights that Splat in its owner's identity color", lit(p2) == BLUE, str(lit(p2)))
check("each wand showed its identity color on the matrix",
      all(pixel0(w) is not None for w in (w1, w2, w3)))
w1.nfc.stop_at = sc.sim.now + 5
sc.run(1500)
check("a stop card on the leader ends the game for everyone",
      w1.result == "done" and w2.result == "done" and w3.result == "done"
      and lit(p1) == OFFC and lit(p2) == OFFC, "%s %s %s" % (w1.result, w2.result, w3.result))

# a follower leaving does not end the game for the others
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
start(sc, [1, 2], partytest, smin=2)
w2.nfc.stop_at = sc.sim.now + 5
sc.run(1500)
check("a stop card on a follower leaves only that wand", w2.result == "done" and w1.result is None)

# ── splattag ──
random.seed(3)
sc = Sc()
w1, w2, w3 = sc.wand(1, [1, 2]), sc.wand(2, [3]), sc.wand(3, [4])
start(sc, [1, 2, 3], splattag, smin=4)
n1 = net_of(w1)
check("splattag: 3 wands, 4 Splats in the pool", n1.phase == "game" and n1.splat_count == 4)
owners = {0: (w1, S[1]), 1: (w1, S[2]), 2: (w2, S[3]), 3: (w3, S[4])}
expected = [0, 0, 0]
for rnd in range(splattag.WIN_SCORE * 2):
    ok = sc.sim.run_until(lambda: any(lit(w.periph(m)) == GREEN for w, m in owners.values()), 4000, 5)
    if not ok:
        break
    idx = [i for i, (w, m) in owners.items() if lit(w.periph(m)) == GREEN]
    if len(idx) != 1:
        check("exactly one Splat is the target", False, str(idx))
        break
    w, m = owners[idx[0]]
    expected[w.n - 1] += 1
    splat_press(sc, w, m)
    sc.run(splattag.PAUSE_MS)
    if max(expected) >= splattag.WIN_SCORE:
        break
check("one target at a time, and a press on it scored for the Splat's owner",
      max(expected) == splattag.WIN_SCORE, str(expected))
msgs = [x[3]["d"] for x in sc.bus.sent(typ="pw_msg") if x[2] == W[2] or x[2] == "*"]
last_scores = [d["s"] for d in msgs if "s" in d][-1]
check("the leader's score messages match the presses", last_scores == expected, "%s vs %s" % (last_scores, expected))
check("the winner was announced to the followers", any("win" in d for d in msgs), str(msgs[-3:]))
sc.run(splattag.OVER_MS + 1500)
check("after the result the leader leaves and everyone's play() returns",
      all(w.result == "done" for w in (w1, w2, w3)), str([w.result for w in (w1, w2, w3)]))
check("every Splat was left dark", all(lit(w.periph(m)) == OFFC for w, m in owners.values()),
      str([lit(w.periph(m)) for w, m in owners.values()]))

# a wrong Splat press does not score
random.seed(5)
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
start(sc, [1, 2], splattag, smin=2)
sc.sim.run_until(lambda: lit(w1.periph(S[1])) == GREEN or lit(w2.periph(S[2])) == GREEN, 3000, 5)
target = (w1, S[1]) if lit(w1.periph(S[1])) == GREEN else (w2, S[2])
other = (w2, S[2]) if target[0] is w1 else (w1, S[1])
n_before = len(sc.bus.sent(typ="pw_msg"))
splat_press(sc, *other)
check("a press on a Splat that is not the target scores nothing",
      lit(target[0].periph(target[1])) == GREEN and len(sc.bus.sent(typ="pw_msg")) == n_before)

# target Splat drops: another target is picked, never the dropped one
random.seed(11)
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
start(sc, [1, 2], splattag, smin=2)
sc.sim.run_until(lambda: lit(w1.periph(S[1])) == GREEN or lit(w2.periph(S[2])) == GREEN, 3000, 5)
tw, tm = (w1, S[1]) if lit(w1.periph(S[1])) == GREEN else (w2, S[2])
ow, om = (w2, S[2]) if tw is w1 else (w1, S[1])
tw.ble.periph(tm).available = False
tw.ble.drop(tm)
ok = sc.sim.run_until(lambda: lit(ow.periph(om)) == GREEN, 4000, 5)
check("the target Splat dropping makes the leader pick another", ok)

# a wand that goes silent is skipped when picking targets
random.seed(2)
sc = Sc()
w1, w2, w3 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3, [3])
start(sc, [1, 2, 3], splattag, smin=3)
sc.bus.drop_frame = lambda src, dst, obj: src == W[3]
sc.run(party.WAND_LOST_MS + 1500)
check("(setup) the leader saw wand 3 go silent", net_of(w1)._members[2]["lost"])
picked = []
for rnd in range(6):
    ok = sc.sim.run_until(lambda: any(lit(w.periph(m)) == GREEN for w, m in ((w1, S[1]), (w2, S[2]), (w3, S[3]))),
                          splattag.ROUND_MS + 2000, 5)
    if not ok:
        break
    for w, m in ((w1, S[1]), (w2, S[2]), (w3, S[3])):
        if lit(w.periph(m)) == GREEN:
            picked.append(w.n)
            if w is not w3:
                splat_press(sc, w, m)
    sc.run(splattag.PAUSE_MS)
check("a silent wand's Splats are never the target while it is lost",
      len(picked) >= 4 and 3 not in picked, str(picked))
sc.bus.drop_frame = None

# ── relaycolor ──
sc = Sc()
w1, w2, w3 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3)
start(sc, [1, 2, 3], relaycolor, smin=1)
p1, p2 = w1.periph(S[1]), w2.periph(S[2])
sc.run(500)
check("relaycolor: the leader starts holding red on its matrix and Splat",
      lit(p1) == RED and pixel0(w1) == relaycolor.RED, "%s %s" % (lit(p1), pixel0(w1)))
check("...the others are dark", lit(p2) == OFFC)
pulse(sc, w1)
sc.run(400)
check("the holder's button passes the color to the next wand, green",
      lit(p2) == GREEN and pixel0(w2) == relaycolor.GREEN, "%s %s" % (lit(p2), pixel0(w2)))
check("...and the sender goes dark", lit(p1) == OFFC)
splat_press(sc, w2, S[2])
sc.run(400)
check("a press on the holder's own Splat passes it on; a wand with no Splats shows it on the matrix",
      pixel0(w3) == relaycolor.BLUE and lit(p2) == OFFC, "%s %s" % (pixel0(w3), lit(p2)))
pulse(sc, w3)
sc.run(400)
check("the last wand passes back to the first, purple", lit(p1) == PURPLE, str(lit(p1)))
splat_press(sc, w2, S[2])
sc.run(300)
check("the leader holding the token ignores a press on another wand's Splat",
      lit(p1) == PURPLE and lit(p2) == OFFC)
splat_press(sc, w1, S[1])
sc.run(400)
check("a press on the leader's own Splat passes the token on, yellow", lit(p2) == YELLOW, str(lit(p2)))
# the holder (wand 2) goes silent: the leader re-issues the token
sc.bus.drop_frame = lambda src, dst, obj: src == W[2]
sc.run(party.WAND_LOST_MS + 1500)
check("the holder's wand lost: the leader hands the token to the next live wand",
      pixel0(w3) == relaycolor.AMBER, str(pixel0(w3)))
sc.bus.drop_frame = None
w1.nfc.stop_at = sc.sim.now + 5
sc.run(1500)
check("the leader leaving ends the game and darkens the Splats",
      all(w.result == "done" for w in (w1, w2, w3)) and lit(p1) == OFFC and lit(p2) == OFFC)

check.finish("party games OK")
