"""Plain lobby protocol, no Splats (Wand Module/lib/lobby_game.py, lib/splatpair.py, lib/pwire.py) on a
simulated ESP-NOW bus with fake BLE Splats. See wandsim.py for the harness.

Each simulated wand runs lobby_game.enter() and then a scripted game in its own
virtual-time thread, exactly the calls main.py makes.

Run: python3 tools/devtests/test_lobby_game.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wandsim  # noqa: E402
from lobbysim import *  # noqa: E402,F401,F403
from lobbysim import (Sc, W, S, NETS, net_of, press, loop, evs, long_loop,  # noqa: E402,F401
                      lobby_game, pwire, splatpair, nfc_reader)

check = wandsim.Checker()

# ── 1. Two wands in a plain lobby (no Splats): join, count, start, roster ──
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
sc.tap(1, 0, lambda net, w: loop(net, w, 6000))
sc.tap(2, 1500, lambda net, w: loop(net, w, 30000))
sc.run(1400)
n1 = net_of(w1)
check("first tapper becomes the leader, lobby open", n1 is not None and n1.is_leader and n1.phase == "lobby")
check("lobby shows 1 of 2 players, the leader counted", n1.lobby_players() == 1 and not n1.can_start())
check("a plain lobby holds no Splats, even the leader's own paired one", n1.lobby_splats() == 0)
from leds import BLUE_DIM, GREEN  # noqa: E402
ident1 = splatpair.WAND_RGB[splatpair.identity_name(W[1])]
check("lobby display: leader shows players joined (identity color) of PLAYERS_MIN (dim)",
      w1.leds.pixels.get(0) == ident1 and w1.leds.pixels.get(1) == BLUE_DIM
      and w1.leds.pixels.get(2) == (0, 0, 0), str(w1.leds.pixels))
press(sc, w1, sc.sim.now + 10)
sc.run(100)
check("the leader's button does nothing below PLAYERS_MIN", n1.phase == "lobby")
sc.run(1500)
check("second tapper joined: lobby shows 2 of 2", n1.lobby_players() == 2 and n1.can_start())
n2 = net_of(w2)
check("...as a follower in the lobby", n2 is not None and not n2.is_leader and n2.phase == "lobby")
check("...with the same game id", n1.id == n2.id and n1.id is not None)
check("lobby display: both players joined shows the filled bar in green",
      w1.leds.pixels.get(0) == GREEN and w1.leds.pixels.get(1) == GREEN, str(w1.leds.pixels))
check("lobby display: a follower shows a blue waiting spinner",
      any(c[0] == "animate_spin" and c[2] == sys.modules["leds"].BLUE_DIM for c in w2.leds.calls))
press(sc, w1, sc.sim.now + 10)
sc.run(300)
check("the leader's button starts the game", n1.phase == "game" and n2.phase == "game")
check("both wands got a Net from enter()", w1.net is n1 and w2.net is n2)
for n, name in ((n1, "leader"), (n2, "follower")):
    check("%s roster is the same ordered list, every wand with 0 Splats" % name,
          n.wands == [(W[1], splatpair.identity_name(W[1]), 0), (W[2], splatpair.identity_name(W[2]), 0)],
          str(n.wands))
check("indexes: leader 0, follower 1", n1.me == 0 and n2.me == 1 and n1.is_leader and not n2.is_leader)
check("net.players is every wand in a plain lobby", n1.players == [0, 1] and n2.players == [0, 1])
check("the pool is empty", n1.splat_count == 0 and n2.splat_count == 0)

# no Splats in a plain lobby game
for n, name in ((n1, "leader"), (n2, "follower")):
    try:
        n.splat(0)
        check("net.splat() is refused on the %s of a plain lobby" % name, False)
    except RuntimeError:
        check("net.splat() is refused on the %s of a plain lobby" % name, True)
w1.events[:] = []
sc.wands[1].ble.button(S[1], True)
sc.run(200)
check("the leader's own paired Splat press is not a game event", not evs(w1, "press"), str(w1.events))

# messages
w2.events[:] = []
w1.events[:] = []
w1.res = []
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

# end: the leader's play() returns, close() ends everyone
sc.run(8000)
check("the leader's game ended, followers got ('end',)", ("end",) in w2.events, str(w2.events[-3:]))
check("every peer was removed at game end",
      w1.enow.get_peer_macs() == [] and w2.enow.get_peer_macs() == [])


# ── 2. A wand with no Splats joins like any other; PLAYERS_MIN 1 starts alone ──
sc = Sc()
w1, w2, w3 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3)
for n, at in ((1, 0), (2, 700), (3, 900)):
    sc.tap(n, at, long_loop(), pmin=3)
sc.run(2600)
n1 = net_of(w1)
check("three wands, with and without Splats, are three players",
      n1.lobby_players() == 3 and n1.can_start(), "%d players" % n1.lobby_players())
press(sc, w1, sc.sim.now + 10)
sc.run(400)
check("...and the roster carries 0 Splats for each",
      [w[2] for w in n1.wands] == [0, 0, 0] and n1.splat_count == 0, str(n1.wands))

sc = Sc()
w1 = sc.wand(1)
sc.tap(1, 0, long_loop(), pmin=1)
sc.run(1500)
check("PLAYERS_MIN 1: the leader alone can start", net_of(w1).can_start())
press(sc, w1, sc.sim.now + 10)
sc.run(300)
check("...and its button starts the game", net_of(w1).phase == "game")

# ── 4. Simultaneous leaders: the lowest MAC wins, the others join it ──
sc = Sc()
w1, w2, w3 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3, [3])
sc.tap(1, 0, long_loop(), pmin=3)
sc.tap(2, 0, long_loop(), pmin=3)
sc.tap(3, 3, long_loop(), pmin=3)
sc.run(3500)
nets = [net_of(w) for w in (w1, w2, w3)]
check("simultaneous taps: one leader, the lowest MAC",
      [n.is_leader for n in nets] == [True, False, False], str([n.is_leader for n in nets]))
check("...one game id, all three players in the lobby",
      len({n.id for n in nets}) == 1 and nets[0].lobby_players() == 3, str([n.id for n in nets]))
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
sc.tap(1, 0, long_loop(), pmin=3)
sc.tap(2, 0, long_loop(), pmin=3)
sc.tap(3, 600, long_loop(), pmin=3)
sc.run(1300)
check("setup: the higher leader holds a follower of its own",
      net_of(w2).is_leader and net_of(w2).lobby_players() == 2 and net_of(w3).leader_mac == W[2],
      "w2 players=%d w3 leader=%s" % (net_of(w2).lobby_players(), net_of(w3).leader_mac))
sc.run(4000)
nets = [net_of(w) for w in (w1, w2, w3)]
check("the yielding leader and its follower both end up in the lowest MAC's lobby",
      [n.is_leader for n in nets] == [True, False, False] and nets[0].lobby_players() == 3
      and len({n.id for n in nets}) == 1, str([(n.is_leader, n.leader_mac) for n in nets]))

# ── 6. stop card: on the leader (cancels for all) and on a follower (leaves) ──
sc = Sc()
w1, w2, w3 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3, [3])
sc.tap(1, 0, long_loop(), pmin=3)
sc.tap(2, 700, long_loop(), pmin=3)
sc.tap(3, 900, long_loop(), pmin=3)
sc.run(2200)
n1 = net_of(w1)
check("setup: three in the lobby", n1.lobby_players() == 3)
w3.nfc.stop_at = sc.sim.now + 5
sc.run(600)
check("a follower's stop card: it leaves, with last_end 'left'", w3.net is None and w3.last_end == "left")
check("...the leader's lobby drops to 2 and stays open", n1.lobby_players() == 2 and n1.phase == "lobby")
check("...the other follower is unaffected", net_of(w2).phase == "lobby" and w2.result is None)
w1.nfc.stop_at = sc.sim.now + 5
sc.run(800)
check("the leader's stop card cancels for everyone",
      w1.net is None and w1.last_end == "left" and w2.net is None and w2.last_end == "ended",
      "%s %s" % (w1.last_end, w2.last_end))
check("...and every peer was removed", all(w.enow.get_peer_macs() == [] for w in (w1, w2, w3)))

# ── 7. A plain lobby leader's own paired Splat dropping is not a game event ──
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2)
sc.tap(1, 0, long_loop(), pmin=2)
sc.tap(2, 700, long_loop(), pmin=2)
sc.run(2200)
press(sc, w1, sc.sim.now + 10)
sc.run(500)
w1.events[:] = []
w1.ble.periph(S[1]).available = False
w1.ble.drop(S[1])
sc.run(500)
check("no splat_lost in a plain lobby game", not evs(w1, "splat_lost"), str(w1.events))
w1.ble.periph(S[1]).available = True
sc.run(500)

# ── 8. wand_lost / wand_back, leader_lost, leave ──
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
sc.tap(1, 0, long_loop(), pmin=2)
sc.tap(2, 700, long_loop(), pmin=2)
sc.run(2200)
press(sc, w1, sc.sim.now + 10)
sc.run(500)
w1.events[:] = []
w2.events[:] = []
t_cut = sc.sim.now
sc.bus.drop_frame = lambda src, dst, obj: src == W[2]
sc.run(lobby_game.WAND_LOST_MS - 500)
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
sc.run(lobby_game.WAND_LOST_MS + 1500)
check("a leader silent for WAND_LOST_MS is leader_lost on the follower, once",
      evs(w2, "leader_lost") == [("leader_lost",)], str(w2.events))
sc.bus.drop_frame = None

sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
sc.tap(1, 0, long_loop(), pmin=2)
sc.tap(2, 700, lambda net, w: loop(net, w, 1500), pmin=2)
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
sc.tap(1, 0, long_loop(), pmin=2)
sc.tap(2, 700, long_loop(), pmin=2)
sc.run(2200)
press(sc, w1, sc.sim.now + 10)
sc.run(500)
state = {"n": 0}


def lose_first_ack(src, dst, obj):
    if isinstance(obj, dict) and obj.get("type") == "pw_msg":
        state["n"] += 1
        return state["n"] == 1
    return False


sc.bus.drop_ack = lose_first_ack
w2.events[:] = []
res = []
sc.sim.spawn("msg", lambda: res.append(w1.net.send(1, {"k": 1})), w1)
sc.run(500)
msgs = sc.bus.sent(typ="pw_msg")
check("a lost ACK causes a resend and the sender sees success",
      res == [True] and [c[4] for c in msgs] == ["ack-lost", "acked"], str([c[4] for c in msgs]))
check("...with the same q on both frames", msgs[0][3]["q"] == msgs[1][3]["q"])
check("...and the duplicate q is dropped: one msg event", w2.events.count(("msg", 0, {"k": 1})) == 1,
      str(w2.events))
sc.bus.drop_ack = None

sc.bus.dup_frame = lambda src, dst, obj: isinstance(obj, dict) and obj.get("type") == "pw_msg"
w2.events[:] = []
sc.sim.spawn("dup", lambda: w1.net.send(1, {"k": 2}), w1)
sc.run(600)
check("duplicated pw_msg is one msg event", w2.events.count(("msg", 0, {"k": 2})) == 1, str(w2.events))
sc.bus.dup_frame = None

# a sender that never gets an ACK gives up after SEND_TRIES and says so
sc.bus.drop_frame = lambda src, dst, obj: isinstance(obj, dict) and obj.get("type") == "pw_msg"
res = []
n_before = len(sc.bus.sent(typ="pw_msg"))
sc.sim.spawn("fail", lambda: res.append(w1.net.send(1, {"k": 3})), w1)
sc.run(500)
check("an unreachable wand: SEND_TRIES attempts, then False",
      res == [False] and len(sc.bus.sent(typ="pw_msg")) - n_before == pwire.SEND_TRIES,
      "%s tries=%d" % (res, len(sc.bus.sent(typ="pw_msg")) - n_before))
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
sc.tap(1, 0, long_loop(), pmin=2)
sc.tap(2, 700, long_loop(), pmin=2)
sc.run(3000)
check("a join survives two lost frames (retries within SEND_TRIES)",
      net_of(w1).lobby_players() == 2 and net_of(w2).phase == "lobby", str(seen))

# 25% frame loss in both directions: messages still arrive at most once, in order
import random
rnd = random.Random(7)
sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
sc.tap(1, 0, long_loop(), pmin=2)
sc.tap(2, 700, long_loop(), pmin=2)
sc.run(2200)
press(sc, w1, sc.sim.now + 10)
sc.run(500)
sc.bus.drop_frame = lambda src, dst, obj: rnd.random() < 0.25
sc.bus.drop_ack = lambda src, dst, obj: rnd.random() < 0.25
w2.events[:] = []
oks = []
sc.sim.spawn("many", lambda: [oks.append(w1.net.send(1, {"i": i})) for i in range(24)], w1)
sc.run(8000)
got = [e[2]["i"] for e in w2.events if e[0] == "msg"]
check("under 25% frame and ACK loss every ACKed message arrives once, in order",
      got == sorted(set(got)) and set(i for i, ok in enumerate(oks) if ok) <= set(got),
      "sent=24 acked=%d got=%d" % (sum(oks), len(got)))
sc.bus.drop_frame = sc.bus.drop_ack = None

# ── 10. ESP-NOW stop / start_game end the game and the lobby ──
sc = Sc()
w1, w2, w3 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3)
sc.tap(1, 0, long_loop(), pmin=2)
sc.tap(2, 700, long_loop(), pmin=2)
sc.run(2200)
press(sc, w1, sc.sim.now + 10)
sc.run(500)
sc.sim.at(sc.sim.now + 10, lambda: w3.enow.broadcast(["stop"]))
sc.run(400)
check("an ESP-NOW stop is ('end',) to every wand in the game",
      ("end",) in w1.events and ("end",) in w2.events, "%s %s" % (w1.events[-2:], w2.events[-2:]))

sc = Sc()
w1, w2, w3 = sc.wand(1, [1]), sc.wand(2, [2]), sc.wand(3)
sc.tap(1, 0, long_loop(), pmin=3)
sc.tap(2, 700, long_loop(), pmin=3)
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
sc.tap(1, 0, long_loop(), pmin=2)
sc.tap(2, 700, long_loop(), pmin=2)
sc.run(4000)
check("no pw_joined within JOIN_WAIT_MS: enter() returns None, 'no_answer'",
      w2.net is None and w2.last_end == "no_answer", str(w2.last_end))
check("...and the leader's lobby stays open", w1.result is None and net_of(w1).phase == "lobby")

sc = Sc()
w1, w2 = sc.wand(1, [1]), sc.wand(2, [2])
sc.tap(1, 0, long_loop(), pmin=2, slug="gamea")
sc.tap(2, 700, long_loop(), pmin=2, slug="gameb")
sc.run(2500)
check("a lobby for another game is not joined: both lead their own",
      net_of(w1).is_leader and net_of(w2).is_leader and net_of(w1).id != net_of(w2).id)

check.finish("lobby game simulation OK")
