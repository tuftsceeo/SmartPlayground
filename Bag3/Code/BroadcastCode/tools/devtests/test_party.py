"""Party games (MockWand/lib/party.py, lib/splatpair.py, lib/pwire.py) on a
simulated ESP-NOW bus with fake BLE Splats. See wandsim.py for the harness.

Each simulated wand runs party.enter() and then a scripted game in its own
virtual-time thread, exactly the calls main.py makes.

Run: python3 tools/devtests/test_party.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wandsim  # noqa: E402
from partysim import *  # noqa: E402,F401,F403
from partysim import (Sc, W, S, NETS, net_of, press, loop, evs, long_loop,  # noqa: E402,F401
                      party, pwire, splatpair, nfc_reader)

check = wandsim.Checker()

# ── 1. Two wands, one Splat each: join, lobby count, start, roster, pool ──
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
sc.tap(1, 0, lambda net, w: loop(net, w, 6000))
sc.tap(2, 1500, lambda net, w: loop(net, w, 30000))
sc.run(1400)
n1 = net_of(w1)
check("first tapper becomes the leader, lobby open", n1 is not None and n1.is_leader and n1.phase == "lobby")
check("lobby shows 1 of 2 Splats", n1.lobby_splats() == 1 and not n1.can_start())
from leds import BLUE_DIM, GREEN  # noqa: E402
ident1 = splatpair.WAND_RGB[splatpair.identity_name(W[1])]
check("lobby display: leader shows its Splats joined (identity color) of SPLATS_MIN (dim)",
      w1.leds.pixels.get(0) == ident1 and w1.leds.pixels.get(1) == BLUE_DIM
      and w1.leds.pixels.get(2) == (0, 0, 0), str(w1.leds.pixels))
press(sc, w1, sc.sim.now + 10)
sc.run(100)
check("the leader's button does nothing below SPLATS_MIN", n1.phase == "lobby")
sc.run(1500)
check("second tapper joined: lobby shows 2 of 2", n1.lobby_splats() == 2 and n1.can_start())
n2 = net_of(w2)
check("...as a follower in the lobby", n2 is not None and not n2.is_leader and n2.phase == "lobby")
check("...with the same game id", n1.id == n2.id and n1.id is not None)
check("lobby display: both Splats joined shows the filled bar in green",
      w1.leds.pixels.get(0) == GREEN and w1.leds.pixels.get(1) == GREEN, str(w1.leds.pixels))
check("lobby display: a follower shows the waiting icon in its identity color",
      any(c[0] == "show_shape" and c[2] == splatpair.WAND_RGB[splatpair.identity_name(W[2])]
          for c in w2.leds.calls))
press(sc, w1, sc.sim.now + 10)
sc.run(300)
check("the leader's button starts the game", n1.phase == "game" and n2.phase == "game")
check("both wands got a Net from enter()", w1.net is n1 and w2.net is n2)
for n, name in ((n1, "leader"), (n2, "follower")):
    check("%s roster is the same ordered list" % name,
          n.wands == [(W[1], splatpair.identity_name(W[1]), 1), (W[2], splatpair.identity_name(W[2]), 1)],
          str(n.wands))
check("indexes: leader 0, follower 1", n1.me == 0 and n2.me == 1 and n1.is_leader and not n2.is_leader)
check("pool size 2, owners follow join order", n1.splat_count == 2 and n1.owner(0) == 0 and n1.owner(1) == 1)
check("net.local is each wand's own SplatGroup", n1.local is w1.ctl.group and n2.local is w2.ctl.group)

# pooled commands
p1, p2 = w1.periph(S[1]), w2.periph(S[2])
c1, c2 = len(p1.writes), len(p2.writes)
w1.res = []
def lead_cmds(net, w):
    w.res.append(net.splat(0).color("turnred"))
    w.res.append(net.splat(1).color("turnblue"))
    w.res.append(net.splat(1).play(["turnyellow", "cat"]))
    w.res.append(net.splat(1).off())
    w.res.append(net.splat(0).sound("dog"))
sc.sim.spawn("cmds", lambda: lead_cmds(n1, w1), w1)
sc.run(1500)
check("leader's own Splat is driven directly", p1.cmds()[-2:] != [] and p1.colors()[-1] == (255, 0, 0))
check("a pool Splat held by another wand is driven by pw_cmd, ACKed", w1.res[:4] == [True] * 4, str(w1.res))
check("...the owner's Splat shows the color", (0, 0, 255) in p2.colors())
check("...play() runs the whole group", (255, 180, 0) in p2.colors()
      and "playSound" in [n for n, _ in p2.cmds()])
check("...off() cleared it", [n for n, _ in p2.cmds()][-2:] == ["allTasksOff", "allLEDsOff"], str(p2.cmds()[-3:]))
n_cmd = len(sc.bus.sent(typ="pw_cmd"))
check("a bad name is refused at the leader, not sent",
      n1.splat(1).color("turnpink") is False and len(sc.bus.sent(typ="pw_cmd")) == n_cmd == 3,
      str(n_cmd))

# remote press and local press
w1.events[:] = []
w2.events[:] = []
sc.wands[2].ble.button(S[2], True)
sc.run(200)
sc.wands[2].ble.button(S[2], False)
sc.run(400)
check("a follower's Splat press reaches the leader as a pool event",
      ("press", 1) in w1.events and ("release", 1) in w1.events, str(w1.events))
check("...and the follower locally with its local index",
      ("press", 0) in w2.events and ("release", 0) in w2.events, str(w2.events))
w1.events[:] = []
sc.wands[1].ble.button(S[1], True)
sc.run(200)
check("the leader's own Splat press is a pool event", ("press", 0) in w1.events, str(w1.events))

# messages
w2.events[:] = []
w1.events[:] = []
sc.sim.spawn("m1", lambda: (w1.res.append(n1.send(1, {"hello": 1})), w1.res.append(n1.send(None, {"all": 2}))), w1)
sc.run(400)
check("net.send() reaches the addressed wand as a msg event with the sender's index",
      ("msg", 0, {"hello": 1}) in w2.events and ("msg", 0, {"all": 2}) in w2.events, str(w2.events))
w2.res = []
sc.sim.spawn("m3", lambda: w2.res.append(n2.send(0, {"back": 3})), w2)
sc.run(300)
check("...and a follower can message the leader", ("msg", 1, {"back": 3}) in w1.events, str(w1.events))
try:
    n1.send(1, {"x": "y" * 300})
    check("an oversized message is refused", False)
except ValueError:
    check("an oversized message is refused", True)
try:
    n2.splat(0)
    check("net.splat() is leader-only", False)
except RuntimeError:
    check("net.splat() is leader-only", True)

# end: the leader's play() returns, close() ends everyone
sc.run(8000)
check("the leader's game ended, followers got ('end',)", ("end",) in w2.events, str(w2.events[-3:]))
check("every peer was removed at game end",
      w1.enow.get_peer_macs() == [] and w2.enow.get_peer_macs() == [])


# ── 1b. A command sent the moment the game starts is not lost on a follower that is still in enter() ──
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])


def eager_leader(net, w):
    w.res = [net.splat(1).color("turnred")]
    loop(net, w, 2000)


def lazy_follower(net, w):
    time.sleep_ms(50)               # starts polling late
    loop(net, w, 2000)


sc.tap(1, 0, eager_leader, smin=2)
sc.tap(2, 700, lazy_follower, smin=2)
sc.run(1800)
press(sc, w1, sc.sim.now + 10)
sc.run(1200)
check("a pw_cmd sent right after pw_start is applied by the follower",
      (255, 0, 0) in w2.periph(S[2]).colors(), str(w2.periph(S[2]).colors()))

# ── 2. Plain wands count 0 Splats; auto-start at SPLATS_MAX ──
sc = Sc()
w1, w2, w3 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3)
for n, at in ((1, 0), (2, 700), (3, 900)):
    sc.tap(n, at, long_loop(), smin=2)
sc.run(2600)
n1, n3 = net_of(w1), net_of(w3)
check("a plain wand joins and counts 0 Splats", n1.lobby_splats() == 2 and len(n1._members) == 3,
      "%d splats, %d members" % (n1.lobby_splats(), len(n1._members)))
press(sc, w1, sc.sim.now + 10)
sc.run(400)
check("...roster has the plain wand with 0, pool has 2",
      n1.wands[2] == (W[3], splatpair.identity_name(W[3]), 0) and n1.splat_count == 2, str(n1.wands))
check("...net.local is None on the plain wand", n3.local is None and n3.local_count == 0)

sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
sc.tap(1, 0, long_loop(), smin=2, smax=2)
sc.tap(2, 700, long_loop(), smin=2, smax=2)
sc.run(3000)
check("reaching SPLATS_MAX starts the game with no button press",
      w1.net is not None and w2.net is not None and w1.net.phase == "game")

# ── 3. A join that would exceed SPLATS_MAX is refused ──
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2, 3])
sc.tap(1, 0, long_loop(), smin=1, smax=2)
sc.tap(2, 700, long_loop(), smin=1, smax=2)
sc.run(3000)
check("a joiner that would exceed SPLATS_MAX is told the lobby is full",
      w2.net is None and w2.last_end == "full" and net_of(w1).lobby_splats() == 1,
      "%s %s" % (w2.last_end, net_of(w1).lobby_splats()))

# ── 4. Simultaneous leaders: the lowest MAC wins, the others join it ──
sc = Sc()
w1, w2, w3 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3, [3])
sc.tap(1, 0, long_loop(), smin=3)
sc.tap(2, 0, long_loop(), smin=3)
sc.tap(3, 3, long_loop(), smin=3)
sc.run(3500)
nets = [net_of(w) for w in (w1, w2, w3)]
check("simultaneous taps: one leader, the lowest MAC",
      [n.is_leader for n in nets] == [True, False, False], str([n.is_leader for n in nets]))
check("...one game id, all three Splats in the lobby",
      len({n.id for n in nets}) == 1 and nets[0].lobby_splats() == 3, str([n.id for n in nets]))
press(sc, w1, sc.sim.now + 10)
sc.run(400)
check("...and the game starts with the roster in join order",
      all(n.phase == "game" for n in nets) and {w[0] for w in nets[0].wands} == {W[1], W[2], W[3]}
      and nets[0].wands[0][0] == W[1])

# ── 4b. A follower of a leader that yields re-finds the winner ──
sc = Sc()
w1, w2, w3 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3, [3])
sc.bus.drop_frame = lambda src, dst, obj: (
    isinstance(obj, dict) and obj.get("type") == "pw_lobby" and src == W[1]
    and dst in (W[2], W[3]) and sc.sim.now < 1300)
sc.tap(1, 0, long_loop(), smin=3)
sc.tap(2, 0, long_loop(), smin=3)
sc.tap(3, 600, long_loop(), smin=3)
sc.run(1300)
check("setup: the higher leader holds a follower of its own",
      net_of(w2).is_leader and net_of(w2).lobby_splats() == 2 and net_of(w3).leader_mac == W[2],
      "w2 splats=%d w3 leader=%s" % (net_of(w2).lobby_splats(), net_of(w3).leader_mac))
sc.run(4000)
nets = [net_of(w) for w in (w1, w2, w3)]
check("the yielding leader and its follower both end up in the lowest MAC's lobby",
      [n.is_leader for n in nets] == [True, False, False] and nets[0].lobby_splats() == 3
      and len({n.id for n in nets}) == 1, str([(n.is_leader, n.leader_mac) for n in nets]))

# ── 5. Two groups run the same game at once, with different ids ──
sc = Sc()
w1, w2, w3, w4 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3, [3]), sc.wand(4, [4])
sc.tap(1, 0, long_loop(), smin=2)
sc.tap(2, 700, long_loop(), smin=2)
sc.run(2200)
press(sc, w1, sc.sim.now + 10)
sc.run(300)
sc.tap(3, sc.sim.now + 10, long_loop(), smin=2)
sc.tap(4, sc.sim.now + 900, long_loop(), smin=2)
sc.run(3000)
press(sc, w3, sc.sim.now + 10)
sc.run(400)
g1, g2 = w1.net, w3.net
check("both groups are in a game", g1 is not None and g2 is not None and g1.phase == "game" and g2.phase == "game")
check("...with different game ids and rosters",
      g1.id != g2.id and {w[0] for w in g1.wands} == {W[1], W[2]} and {w[0] for w in g2.wands} == {W[3], W[4]},
      "%s %s" % (g1.id, g2.id))
sc.sim.spawn("c1", lambda: g1.splat(1).color("turnred"), w1)
sc.sim.spawn("c2", lambda: g2.splat(1).color("turngreen"), w3)
sc.run(1500)
check("a leader's command reaches only its own group's follower",
      w2.periph(S[2]).colors()[-1] == (255, 0, 0) and w4.periph(S[4]).colors()[-1] == (0, 255, 0)
      and (0, 255, 0) not in [c for c in w2.periph(S[2]).colors() if c != (0, 38, 0)]
      and (255, 0, 0) not in w4.periph(S[4]).colors())

# ── 6. stop card: on the leader (cancels for all) and on a follower (leaves) ──
sc = Sc()
w1, w2, w3 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3, [3])
sc.tap(1, 0, long_loop(), smin=3)
sc.tap(2, 700, long_loop(), smin=3)
sc.tap(3, 900, long_loop(), smin=3)
sc.run(2200)
n1 = net_of(w1)
check("setup: three in the lobby", n1.lobby_splats() == 3)
w3.nfc.stop_at = sc.sim.now + 5
sc.run(600)
check("a follower's stop card: it leaves, with last_end 'left'", w3.net is None and w3.last_end == "left")
check("...the leader's lobby drops to 2 and stays open", n1.lobby_splats() == 2 and n1.phase == "lobby")
check("...the other follower is unaffected", net_of(w2).phase == "lobby" and w2.result is None)
w1.nfc.stop_at = sc.sim.now + 5
sc.run(800)
check("the leader's stop card cancels for everyone",
      w1.net is None and w1.last_end == "left" and w2.net is None and w2.last_end == "ended",
      "%s %s" % (w1.last_end, w2.last_end))
check("...and every peer was removed", all(w.enow.get_peer_macs() == [] for w in (w1, w2, w3)))

# ── 7. Splat dropouts: splat_lost / splat_back ──
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
sc.tap(1, 0, long_loop(), smin=2)
sc.tap(2, 700, long_loop(), smin=2)
sc.run(2200)
press(sc, w1, sc.sim.now + 10)
sc.run(500)
w1.events[:] = []
w2.ble.periph(S[2]).available = False
w2.ble.drop(S[2])
sc.run(2500)
check("a follower's Splat dropping reaches the leader as splat_lost with the pool index",
      ("splat_lost", 1) in w1.events, str(w1.events))
check("...and no wand_lost", not evs(w1, "wand_lost"))
w2.ble.periph(S[2]).available = True
sc.run(14000)
check("...it reconnects through SplatLink and the leader sees splat_back",
      ("splat_back", 1) in w1.events, str(w1.events))
w1.events[:] = []
w1.ble.periph(S[1]).available = False
w1.ble.drop(S[1])
sc.run(500)
check("the leader's own Splat dropping is splat_lost on the leader", ("splat_lost", 0) in w1.events, str(w1.events))
w1.ble.periph(S[1]).available = True
sc.run(14000)
check("...and splat_back after the reconnect", ("splat_back", 0) in w1.events, str(w1.events))

# ── 8. wand_lost / wand_back, leader_lost, leave ──
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
sc.tap(1, 0, long_loop(), smin=2)
sc.tap(2, 700, long_loop(), smin=2)
sc.run(2200)
press(sc, w1, sc.sim.now + 10)
sc.run(500)
w1.events[:] = []
w2.events[:] = []
t_cut = sc.sim.now
sc.bus.drop_frame = lambda src, dst, obj: src == W[2]
sc.run(party.WAND_LOST_MS - 500)
check("a follower silent for less than WAND_LOST_MS is not lost", not evs(w1, "wand_lost"))
sc.run(1500)
check("a follower silent for WAND_LOST_MS is wand_lost on the leader",
      evs(w1, "wand_lost") == [("wand_lost", 1)], str(w1.events))
check("...and the leader keeps playing", w1.result is None and not evs(w2, "leader_lost"))
sc.bus.drop_frame = None
sc.run(1500)
check("...when it is heard again, wand_back", evs(w1, "wand_back") == [("wand_back", 1)], str(w1.events))
w1.events[:] = []
w2.events[:] = []
sc.bus.drop_frame = lambda src, dst, obj: src == W[1]
sc.run(party.WAND_LOST_MS + 1500)
check("a leader silent for WAND_LOST_MS is leader_lost on the follower, once",
      evs(w2, "leader_lost") == [("leader_lost",)], str(w2.events))
sc.bus.drop_frame = None

sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
sc.tap(1, 0, long_loop(), smin=2)
sc.tap(2, 700, lambda net, w: loop(net, w, 1500), smin=2)
sc.run(2200)
press(sc, w1, sc.sim.now + 10)
sc.run(300)
w1.events[:] = []
sc.run(2500)
check("a follower's play() returning is wand_lost on the leader at once, not after WAND_LOST_MS",
      evs(w1, "wand_lost") == [("wand_lost", 1)] and w2.result == "done", str(w1.events))

# ── 9. Lost frames, lost ACKs, duplicates ──
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
sc.tap(1, 0, long_loop(), smin=2)
sc.tap(2, 700, long_loop(), smin=2)
sc.run(2200)
press(sc, w1, sc.sim.now + 10)
sc.run(500)
state = {"n": 0}


def lose_first_ack(src, dst, obj):
    if isinstance(obj, dict) and obj.get("type") == "pw_cmd":
        state["n"] += 1
        return state["n"] == 1
    return False


sc.bus.drop_ack = lose_first_ack
p2 = w2.periph(S[2])
before = len(p2.colors())
res = []
sc.sim.spawn("cmd", lambda: res.append(w1.net.splat(1).color("turnpurple")), w1)
sc.run(500)
cmds = sc.bus.sent(typ="pw_cmd")
check("a lost ACK causes a resend and the sender sees success",
      res == [True] and [c[4] for c in cmds] == ["ack-lost", "acked"], str([c[4] for c in cmds]))
check("...with the same q on both frames", cmds[0][3]["q"] == cmds[1][3]["q"])
check("...and the duplicate q is dropped: the Splat saw one write",
      p2.colors()[before:] == [(160, 0, 200)], str(p2.colors()[before:]))
sc.bus.drop_ack = None

sc.bus.dup_frame = lambda src, dst, obj: isinstance(obj, dict) and obj.get("type") in ("pw_msg", "pw_evt", "pw_cmd")
w1.events[:] = []
w2.events[:] = []
before = len(p2.colors())
sc.sim.spawn("dup", lambda: (w1.net.send(1, {"k": 1}), w1.net.splat(1).color("turnred")), w1)
sc.wands[2].ble.button(S[2], True)
sc.run(1500)
sc.wands[2].ble.button(S[2], False)
sc.run(600)
check("duplicated pw_msg is one msg event", w2.events.count(("msg", 0, {"k": 1})) == 1, str(w2.events))
check("duplicated pw_cmd is one command", p2.colors()[before:] == [(255, 0, 0)], str(p2.colors()[before:]))
check("duplicated pw_evt is one press and one release at the leader",
      w1.events.count(("press", 1)) == 1 and w1.events.count(("release", 1)) == 1, str(w1.events))
sc.bus.dup_frame = None

# a sender that never gets an ACK gives up after SEND_TRIES and says so
sc.bus.drop_frame = lambda src, dst, obj: isinstance(obj, dict) and obj.get("type") == "pw_cmd"
res = []
n_before = len(sc.bus.sent(typ="pw_cmd"))
sc.sim.spawn("fail", lambda: res.append(w1.net.splat(1).color("turnblue")), w1)
sc.run(500)
check("an unreachable owner: SEND_TRIES attempts, then False",
      res == [False] and len(sc.bus.sent(typ="pw_cmd")) - n_before == pwire.SEND_TRIES,
      "%s tries=%d" % (res, len(sc.bus.sent(typ="pw_cmd")) - n_before))
sc.bus.drop_frame = None

# the lobby survives losing the first frames of a join
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
seen = {"join": 0}


def lose_two_joins(src, dst, obj):
    if isinstance(obj, dict) and obj.get("type") == "pw_join":
        seen["join"] += 1
        return seen["join"] <= 2
    return False


sc.bus.drop_frame = lose_two_joins
sc.tap(1, 0, long_loop(), smin=2)
sc.tap(2, 700, long_loop(), smin=2)
sc.run(3000)
check("a join survives two lost frames (retries within SEND_TRIES)",
      net_of(w1).lobby_splats() == 2 and net_of(w2).phase == "lobby", str(seen))

# 25% frame loss in both directions: commands still arrive at most once
import random
rnd = random.Random(7)
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
sc.tap(1, 0, long_loop(), smin=2)
sc.tap(2, 700, long_loop(), smin=2)
sc.run(2200)
press(sc, w1, sc.sim.now + 10)
sc.run(500)
sc.bus.drop_frame = lambda src, dst, obj: rnd.random() < 0.25
sc.bus.drop_ack = lambda src, dst, obj: rnd.random() < 0.25
p2 = w2.periph(S[2])
before = len(p2.colors())
names = ["turnred", "turngreen", "turnblue", "turnpurple", "turnyellow", "turnwhite"] * 4
oks = []
sc.sim.spawn("many", lambda: [oks.append(w1.net.splat(1).color(n)) for n in names], w1)
sc.run(8000)
got = p2.colors()[before:]
COLORS = {"turnred": (255, 0, 0), "turngreen": (0, 255, 0), "turnblue": (0, 0, 255),
          "turnpurple": (160, 0, 200), "turnyellow": (255, 180, 0), "turnwhite": (200, 200, 200)}
want = [COLORS[n] for n in names]
it = iter(want)
in_order = all(any(c == x for x in it) for c in got)       # got is a subsequence of what was sent
check("under 25% frame and ACK loss every ACKed command is applied, none twice, in order",
      in_order and sum(oks) <= len(got) <= len(names) and len(got) <= sum(oks) + (len(oks) - sum(oks)),
      "sent=%d acked=%d applied=%d" % (len(names), sum(oks), len(got)))
sc.bus.drop_frame = sc.bus.drop_ack = None

# ── 10. ESP-NOW stop / start_game end the game and the lobby ──
sc = Sc()
w1, w2, w3 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3)
sc.tap(1, 0, long_loop(), smin=2)
sc.tap(2, 700, long_loop(), smin=2)
sc.run(2200)
press(sc, w1, sc.sim.now + 10)
sc.run(500)
sc.sim.at(sc.sim.now + 10, lambda: w3.enow.broadcast(["stop"]))
sc.run(400)
check("an ESP-NOW stop is ('end',) to every wand in the game",
      ("end",) in w1.events and ("end",) in w2.events, "%s %s" % (w1.events[-2:], w2.events[-2:]))

sc = Sc()
w1, w2, w3 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3)
sc.tap(1, 0, long_loop(), smin=3)
sc.tap(2, 700, long_loop(), smin=3)
sc.run(1900)
sc.sim.at(sc.sim.now + 10, lambda: w3.enow.broadcast({"type": "start_game", "name": "other"}))
sc.run(400)
check("an ESP-NOW start_game cancels a lobby, last_end 'external'",
      w1.net is None and w2.net is None and w1.last_end == "external" and w2.last_end == "external",
      "%s %s" % (w1.last_end, w2.last_end))

# ── 11. No answer from the leader; another game's lobby ──
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
sc.bus.drop_frame = lambda src, dst, obj: isinstance(obj, dict) and obj.get("type") == "pw_joined"
sc.tap(1, 0, long_loop(), smin=2)
sc.tap(2, 700, long_loop(), smin=2)
sc.run(4000)
check("no pw_joined within JOIN_WAIT_MS: enter() returns None, 'no_answer'",
      w2.net is None and w2.last_end == "no_answer", str(w2.last_end))
check("...and the leader's lobby stays open", w1.result is None and net_of(w1).phase == "lobby")

sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
sc.tap(1, 0, long_loop(), smin=2, slug="gamea")
sc.tap(2, 700, long_loop(), smin=2, slug="gameb")
sc.run(2500)
check("a lobby for another game is not joined: both lead their own",
      net_of(w1).is_leader and net_of(w2).is_leader and net_of(w1).id != net_of(w2).id)

# ── 12. A leader holding enough Splats starts alone ──
sc = Sc()
w1 = sc.wand(1, [1, 2])
sc.tap(1, 0, long_loop(), smin=2)
sc.run(1800)
press(sc, w1, sc.sim.now + 10)
sc.run(400)
check("a leader with 2 Splats and SPLATS_MIN 2 can start alone",
      w1.net is not None and w1.net.splat_count == 2 and w1.net.owner(1) == 0)
check("...net.splat(i) is the local SplatAPI for its own Splats", w1.net.splat(1) is w1.ctl.group.unit(1))

check.finish("party simulation OK")
