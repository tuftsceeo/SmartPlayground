"""
CPython simulation of party games (lib/party.py) and solo Splat games
(lib/solo.py, solotest.py, solo_echo.py). SPEC sections 6-8.

Run: python3 Bag3/Code/BroadcastCode/MockWand/tests/test_party.py
     (or pytest on this file)

Several wands share a fake ESP-NOW bus (tests/fakes.py) with optional
broadcast loss, unicast loss and lost ACKs; their Splats are real
pairing.LocalSplats / splat_api objects over fake BLE links. Every wand is
stepped every SIM_STEP_MS of fake time.

Transcripts
-----------
Party tests write tests/transcripts/<scenario>.json, one file per scenario,
for the Simulator's virtual peers to replay (integration PLAN 5.6):

    {
      "format": "pw-transcript/1",
      "scenario": "<name>",
      "description": "<what happens>",
      "constants": {"FIND_WAIT_MS": 500, ...},     party.py timing in force
      "wands": {"A": "AA:00:00:00:00:01", ...},    label -> wand MAC
      "splats": {"A": 1, ...},                     paired Splats per wand
      "frames": [
        {"t": 0, "src": "AA:..:01", "dst": "*" | "<MAC>",
         "msg": {...},                              the JSON as sent
         "delivered": ["<MAC>", ...] | true | false,
         "acked": true | false | null}              null for broadcasts
      ]
    }

frames is every ESP-NOW frame in send order, retries included. For a
broadcast, "delivered" lists the MACs that received it; for a unicast it is
whether that attempt reached its target, and "acked" whether the sender
saw the ACK (false with delivered true is a lost ACK: the next attempt is
a duplicate with the same "q"). "t" is fake milliseconds. Only pw_
messages appear; their fields follow SPEC section 8, plus "q" on every
unicast.
"""
import json
import os
import sys

import fakes
from fakes import now, Bus, make_local, inject, offs

import party
import solo

HERE = os.path.dirname(os.path.abspath(__file__))
TRANSCRIPTS = os.path.join(HERE, "transcripts")
SIM_STEP_MS = 10
SLUG = "partytest"

A = "AA:00:00:00:00:01"
B = "AA:00:00:00:00:02"
C = "AA:00:00:00:00:03"
LABELS = {A: "A", B: "B", C: "C"}


class Wand:
    def __init__(self, bus, mac, splats):
        self.mac = mac
        self.enow = bus.node(mac)
        self.local = make_local(mac, splats) if splats else None
        self.lob = None
        self.net = None
        self.result = None
        self.events = []

    def tap(self, smin, smax=None, slug=SLUG):
        self.lob = party.Lobby(party.Link(self.enow, self.mac), slug, smin, smax, self.local)
        self.net = None
        self.result = None

    def link(self, i):
        return self.local.hub.links[i]


class Sim:
    def __init__(self, splats=(1, 1, 1), **bus_kw):
        now[0] = 0
        self.bus = Bus(**bus_kw)
        self.wands = [Wand(self.bus, m, n) for m, n in zip((A, B, C), splats)]

    def run(self, ms, press=(), stop=()):
        """Step every wand for ms. press/stop: wands given a button press /
        stop card on the first step."""
        end = now[0] + ms
        first = True
        while now[0] < end:
            for w in self.wands:
                if w.lob is not None:
                    r = w.lob.step(first and w in press, first and w in stop)
                    if r is not None:
                        w.lob = None
                        if r[0] == "start":
                            w.net = r[1]
                        else:
                            w.result = r
                elif w.net is not None:
                    while True:
                        ev = w.net.poll()
                        if ev is None:
                            break
                        w.events.append(ev)
                else:
                    w.enow.inbox = []    # idle loop: party messages are not for it
            first = False
            now[0] += SIM_STEP_MS

    def save(self, name, description):
        os.makedirs(TRANSCRIPTS, exist_ok=True)
        frames = [f for f in self.bus.frames
                  if isinstance(f["msg"], dict) and str(f["msg"].get("type", "")).startswith("pw_")]
        doc = {
            "format": "pw-transcript/1",
            "scenario": name,
            "description": description,
            "constants": {k: getattr(party, k) for k in
                          ("FIND_WAIT_MS", "LOBBY_PERIOD_MS", "HB_PERIOD_MS",
                           "WAND_LOST_MS", "SEND_TRIES", "JOIN_WAIT_MS")},
            "wands": {LABELS[w.mac]: w.mac for w in self.wands},
            "splats": {LABELS[w.mac]: (w.local.count if w.local else 0) for w in self.wands},
            "frames": frames,
        }
        with open(os.path.join(TRANSCRIPTS, name + ".json"), "w") as f:
            json.dump(doc, f, indent=1)
            f.write("\n")


def types_sent(sim, src=None, dst=None):
    return [f["msg"]["type"] for f in sim.bus.frames
            if (src is None or f["src"] == src) and (dst is None or f["dst"] == dst)]


def _lobby3(sim, smin=3, smax=None):
    a, b, c = sim.wands
    a.tap(smin, smax)
    sim.run(600)                 # A finds nothing and leads
    b.tap(smin, smax)
    c.tap(smin, smax)
    sim.run(600)
    return a, b, c


# ─── Lobby ───────────────────────────────────

def test_join_and_start_at_min():
    sim = Sim()
    a, b, c = _lobby3(sim)
    assert a.lob.state == "lead" and b.lob.state == "member" and c.lob.state == "member"
    assert a.lob.total() == 3
    sim.run(100)
    assert a.net is None, "no start before the button"
    sim.run(50, press=(a,))
    assert a.net is not None and b.net is not None and c.net is not None
    assert a.net.is_leader and not b.net.is_leader
    assert [w[0] for w in a.net.wands] == [A, B, C]
    assert [w[0] for w in b.net.wands] == [A, B, C]
    assert a.net.splat_count == 3 and b.net.splat_count == 3
    assert (b.net.me, c.net.me) == (1, 2)
    assert a.net.owner(2) == 2
    sim.save("join_start", "A leads, B and C tap and join (unicast pw_lobby reply "
             "to each pw_find), A presses its button at SPLATS_MIN = 3")


def test_find_answered_by_unicast_lobby():
    sim = Sim(bc_loss=1.0)       # every broadcast lost: only the unicast reply gets through
    a, b, c = sim.wands
    a.tap(2)
    sim.run(600)
    sim.bus.bc_loss = 0.0
    b.tap(2)
    sim.bus.bc_loss = 1.0
    sim.run(300)
    assert b.lob.state == "member"
    lob = [f for f in sim.bus.frames if f["msg"]["type"] == "pw_lobby" and f["dst"] == B]
    assert lob and lob[0]["delivered"] is True


def test_button_below_min_does_nothing():
    sim = Sim()
    a, b, c = sim.wands
    a.tap(3)
    sim.run(600)
    b.tap(3)
    sim.run(300)
    sim.run(50, press=(a,))
    assert a.net is None and a.lob.total() == 2


def test_auto_start_at_max():
    sim = Sim(splats=(1, 2, 0))
    a, b, c = sim.wands
    a.tap(2, 3)
    sim.run(600)
    b.tap(2, 3)
    sim.run(300)
    assert a.net is not None and b.net is not None
    assert a.net.splat_count == 3
    assert a.net.owner(1) == 1 and a.net.owner(2) == 1
    sim.save("auto_start_max", "B joins with 2 Splats, the total reaches SPLATS_MAX = 3 "
             "and A starts without a button press")


def test_unpaired_wand_counts_zero():
    sim = Sim(splats=(1, 0, 1))
    a, b, c = _lobby3(sim, smin=2)
    assert a.lob.total() == 2
    sim.run(50, press=(a,))
    assert b.net.wands[1][2] == 0 and a.net.splat_count == 2


def test_simultaneous_leaders_merge_to_lower_mac():
    sim = Sim()
    a, b, c = sim.wands
    sim.bus.bc_loss = 1.0        # the two lead announcements cross and are lost
    a.tap(2)
    b.tap(2)
    sim.run(600)
    sim.bus.bc_loss = 0.0
    assert a.lob.state == "lead" and b.lob.state == "lead"
    sim.run(1500)                # lobby broadcasts cross; B (higher MAC) joins A
    assert a.lob.state == "lead" and b.lob.state == "member"
    assert a.lob.total() == 2
    sim.save("simultaneous_leaders", "A and B tap together and both lead; B hears A's "
             "pw_lobby, A has the lower MAC, so B closes its lobby and joins A")


def test_merge_moves_followers():
    sim = Sim()
    a, b, c = sim.wands
    b.tap(3)
    sim.run(600)
    c.tap(3)
    sim.run(300)
    assert c.lob.state == "member" and c.lob.leader == B
    sim.bus.down.add(B)          # B's lobby broadcasts do not reach A yet
    a.tap(3)
    sim.run(600)
    sim.bus.down.discard(B)
    sim.run(2500)
    assert b.lob.state == "member" and c.lob.state == "member"
    assert c.lob.leader == A and a.lob.total() == 3


def test_two_groups_same_slug():
    sim = Sim()
    a, b, c = sim.wands
    a.tap(2)
    sim.run(600)
    b.tap(2)
    sim.run(300)
    sim.run(50, press=(a,))
    assert a.net is not None
    c.tap(1)
    sim.run(700)
    assert c.lob is not None and c.lob.state == "lead", "C must not join a started game"
    assert c.lob.id != a.net.id
    sim.run(2000)
    assert not [e for e in a.events + b.events if e[0] in ("wand_lost", "leader_lost")]


def test_stop_on_leader_in_lobby():
    sim = Sim()
    a, b, c = _lobby3(sim)
    sim.run(50, stop=(a,))
    sim.run(50)
    assert a.result == ("cancel", "stop")
    assert b.result == ("cancel", "end") and c.result == ("cancel", "end")
    assert a.enow.peers == [] and b.enow.peers == []
    sim.save("lobby_stop_leader", "A, B, C in A's lobby; a stop card on A cancels it "
             "for everyone (pw_end)")


def test_stop_on_follower_in_lobby():
    sim = Sim()
    a, b, c = _lobby3(sim)
    sim.run(50, stop=(b,))
    assert b.result == ("cancel", "stop")
    assert a.lob.total() == 2 and c.lob.state == "member"
    assert "pw_leave" in types_sent(sim, src=B, dst=A)


def test_follower_lobby_leader_gone():
    sim = Sim()
    a, b, c = _lobby3(sim)
    sim.bus.down.add(A)
    sim.run(party.WAND_LOST_MS + 200)
    assert b.result == ("cancel", "leader_lost")


# ─── Game ────────────────────────────────────

def _started(sim=None, **kw):
    sim = sim or Sim(**kw)
    a, b, c = _lobby3(sim)
    sim.run(20, press=(a,))
    assert a.net and b.net and c.net
    return sim, a, b, c


def test_pooled_command_delivery():
    sim, a, b, c = _started()
    assert a.net.splat(1).color("turnblue")
    assert a.net.splat(2).play(["turnred", "cat"])
    assert a.net.splat(0).color("turngreen")          # local, no ESP-NOW
    sim.run(30)
    assert ("leds", (0, 0, 255)) in b.link(0).writes
    assert ("leds", (255, 0, 0)) in c.link(0).writes and ("sound", 19) in c.link(0).writes
    assert ("leds", (0, 255, 0)) in a.link(0).writes
    assert a.net.splat(1).off()
    sim.run(30)
    assert offs(b.link(0)) == 1
    sim.save("pooled_commands", "A (leader) drives B's and C's Splats by pool index "
             "with pw_cmd: color, play, off")


def test_follower_splat_is_leader_only():
    sim, a, b, c = _started()
    try:
        b.net.splat(0)
    except RuntimeError:
        pass
    else:
        raise AssertionError("follower net.splat() must raise")
    assert b.net.local.splat(0).color("turnred")


def test_remote_press():
    sim, a, b, c = _started()
    c.link(0).press()
    sim.run(30)
    c.link(0).release()
    sim.run(30)
    assert ("press", 2) in a.events and ("release", 2) in a.events
    assert ("press", 0) in c.events and ("release", 0) in c.events
    a.link(0).press()
    sim.run(30)
    assert ("press", 0) in a.events
    sim.save("remote_press", "C's Splat button: pw_evt press and release to A as pool "
             "index 2; delivered on C as local index 0")


def test_messages():
    sim, a, b, c = _started()
    assert b.net.send(0, {"k": "hi"})
    assert a.net.send(None, {"k": "all"})
    sim.run(30)
    assert ("msg", 1, {"k": "hi"}) in a.events
    assert ("msg", 0, {"k": "all"}) in b.events and ("msg", 0, {"k": "all"}) in c.events
    sim.save("messages", "B sends A a pw_msg; A sends one to every other wand")


def test_follower_sends_to_followers():
    sim, a, b, c = _started()
    assert C in b.enow.peers and B in c.enow.peers
    assert b.net.send(2, {"k": "toC"})
    assert c.net.send(None, {"k": "fromC"})
    sim.run(30)
    assert ("msg", 1, {"k": "toC"}) in c.events
    assert ("msg", 2, {"k": "fromC"}) in a.events and ("msg", 2, {"k": "fromC"}) in b.events
    a.net.close(); b.net.close(); c.net.close()
    assert not b.enow.peers and not c.enow.peers


def test_splat_lost_and_back():
    sim, a, b, c = _started()
    sim.run(1200)
    b.link(0).ready = False
    sim.run(1200)
    assert ("splat_lost", 1) in a.events
    b.link(0).ready = True
    sim.run(1200)
    assert ("splat_back", 1) in a.events
    a.link(0).ready = False
    sim.run(30)
    assert ("splat_lost", 0) in a.events
    sim.save("splat_lost_back", "B's Splat drops and returns: A sees it in B's pw_hb "
             "bitmask and reports splat_lost / splat_back for pool index 1")


def test_wand_lost_and_back():
    sim, a, b, c = _started()
    sim.bus.down.add(C)
    sim.run(party.WAND_LOST_MS + 500)
    assert ("wand_lost", 2) in a.events
    assert ("leader_lost",) in c.events
    sim.bus.down.discard(C)
    sim.run(1500)
    assert ("wand_back", 2) in a.events
    assert a.events.count(("wand_lost", 2)) == 1
    sim.save("wand_lost_back", "C goes out of range for longer than WAND_LOST_MS: A "
             "reports wand_lost, C reports leader_lost; C's heartbeat returns and A "
             "reports wand_back")


def test_leader_lost():
    sim, a, b, c = _started()
    sim.bus.down.add(A)
    sim.run(party.WAND_LOST_MS + 500)
    assert ("leader_lost",) in b.events and ("leader_lost",) in c.events
    assert b.events.count(("leader_lost",)) == 1


def test_duplicate_q_dropped():
    sim, a, b, c = _started(ack_loss=0.5, seed=7)
    for k in range(12):
        a.net.splat(1).color("turnred" if k % 2 else "turnblue")
        sim.run(20)
    sim.bus.ack_loss = 0.0
    sim.run(30)
    sent = [f for f in sim.bus.frames if f["dst"] == B and f["msg"]["type"] == "pw_cmd"]
    delivered = [f for f in sent if f["delivered"]]
    qs = set(f["msg"]["q"] for f in delivered)
    assert len(delivered) > len(qs), "seed must produce at least one lost ACK"
    leds = [w for w in b.link(0).writes if w[0] == "leds"]
    assert len(leds) == len(qs) == 12
    sim.save("duplicate_q", "Lost ACKs make A resend pw_cmd to B with the same q; B "
             "executes each q once")


def test_lossy_join_and_play():
    sim = Sim(bc_loss=0.15, uni_loss=0.1, ack_loss=0.1, seed=3)
    a, b, c = _lobby3(sim)
    sim.run(2000)
    assert a.lob.total() == 3
    sim.run(20, press=(a,))
    assert a.net and b.net and c.net
    c.link(0).press()
    sim.run(3000)
    assert ("press", 2) in a.events
    assert not [e for e in a.events if e[0] == "wand_lost"]


def test_end_on_return_and_cleanup():
    sim, a, b, c = _started()
    a.net.run(lambda: None)
    sim.run(30)
    assert ("end",) in b.events and ("end",) in c.events
    assert offs(a.link(0)) == 1 and a.enow.peers == []
    b.net.close()
    c.net.close()
    assert "pw_leave" not in types_sent(sim, src=B), "an ended follower does not leave"
    assert offs(b.link(0)) == 1
    sim.save("leader_end", "A's game returns: pw_end to B and C; every wand turns its "
             "Splats off")


def test_cleanup_on_error_leader_and_follower():
    sim, a, b, c = _started()

    def boom():
        raise ValueError("game bug")

    try:
        b.net.run(boom)
    except ValueError:
        pass
    else:
        raise AssertionError("error must re-raise after cleanup")
    sim.run(30)
    assert "pw_leave" in types_sent(sim, src=B, dst=A)
    assert ("wand_lost", 1) in a.events
    assert offs(b.link(0)) == 1 and b.enow.peers == []
    try:
        a.net.run(boom)
    except ValueError:
        pass
    sim.run(30)
    assert ("end",) in c.events
    assert [f for f in sim.bus.frames if f["src"] == A and f["dst"] == B
            and f["msg"]["type"] == "pw_end"] == [], "no pw_end to a wand that left"
    sim.save("follower_error_leave", "B's game raises: B sends pw_leave and turns its "
             "Splat off; A reports wand_lost. A's game then raises: pw_end to C only")


def test_game_enow_filters_pw():
    sim, a, b, c = _started()
    ge = b.net.wrap(b.enow)
    inject(b.enow, {"type": "stop"}, A)
    a.net.send(1, {"k": 1})
    sim.bus.broadcast(C, {"type": "other_game_msg"})
    seen = []
    for _ in range(5):
        mt, data, mac = ge.poll()
        if mt is not None:
            seen.append((mt, data.get("type")))
    assert seen == [("stop", "stop"), ("raw", "other_game_msg")]
    assert b.net.poll() == ("msg", 0, {"k": 1})


# ─── Solo ────────────────────────────────────

class _Mod:
    pass


def _mod(**consts):
    m = _Mod()
    for k, v in consts.items():
        setattr(m, k, v)
    return m


def test_kind_and_conflicting_constants():
    assert solo.kind(_mod()) is None
    assert solo.kind(_mod(SPLATS_LOCAL=1)) == ("solo", 1, None)
    assert solo.kind(_mod(SPLATS_MIN=2, SPLATS_MAX=4)) == ("party", 2, 4)
    try:
        solo.kind(_mod(SPLATS_LOCAL=1, SPLATS_MIN=2))
    except ValueError:
        pass
    else:
        raise AssertionError("both constants must fail the load")
    try:
        solo.prepare(_mod(SPLATS_LOCAL=1, SPLATS_MIN=2), "x", None,
                     fakes.FakeLeds(), fakes.FakeBuz(), None)
    except ValueError:
        pass
    else:
        raise AssertionError("prepare must raise for both constants")


def _with_local(ls):
    import pairing
    pairing._local = ls


def test_solo_not_enough_splats():
    leds, buz = fakes.FakeLeds(), fakes.FakeBuz()
    _with_local(None)
    assert solo.prepare(_mod(SPLATS_LOCAL=1), "soloecho", None, leds, buz, None) is None
    assert leds.shapes and leds.shapes[0][1] == (120, 80, 0) and buz.beeps
    ls = make_local("AA:00:00:00:00:09", 2)
    ls.hub.links[1].ready = False
    _with_local(ls)
    leds2 = fakes.FakeLeds()
    assert solo.prepare(_mod(SPLATS_LOCAL=2), "x", None, leds2, fakes.FakeBuz(), None) is None
    assert leds2.shapes
    _with_local(None)


def _solonet(n=1, mac="AA:00:00:00:00:09"):
    fakes.install_espnow_stub()
    fakes.own_mac[0] = mac
    ls = make_local(mac, n)
    _with_local(ls)
    net = solo.prepare(_mod(SPLATS_LOCAL=n), "solotest", None,
                       fakes.FakeLeds(), fakes.FakeBuz(), fakes.ScriptEnow())
    assert isinstance(net, solo.SoloNet)
    return ls, net


def test_solonet_members_and_send_raises():
    ls, net = _solonet(2)
    assert net.is_leader and net.me == 0 and net.splat_count == 2
    assert net.wands == [("AA:00:00:00:00:09", ls.identity[0], 2)]
    assert net.owner(1) == 0
    assert net.splat(1) is ls.splat(1)
    try:
        net.send(None, {"x": 1})
    except RuntimeError:
        pass
    else:
        raise AssertionError("SoloNet.send must raise")
    ls.hub.links[0].press()
    assert net.poll() == ("press", 0)
    _with_local(None)


def test_solonet_cleanup_on_error():
    ls, net = _solonet(1)

    def boom():
        raise KeyError("bug")

    try:
        net.run(boom)
    except KeyError:
        pass
    else:
        raise AssertionError("error must re-raise")
    assert offs(ls.hub.links[0]) == 1
    net.close()
    assert offs(ls.hub.links[0]) == 1, "close is idempotent"
    _with_local(None)


def _game(modname):
    fakes.install_game_stubs()
    sys.modules.pop(modname, None)
    return __import__(modname)


def test_solotest_session_with_dropout():
    g = _game("solotest")
    assert g.SPLATS_LOCAL == 1
    ls, net = _solonet(1)
    link = ls.hub.links[0]
    t0 = now[0]
    leds = fakes.FakeLeds()
    enow = fakes.ScriptEnow([(t0 + 3000, "stop", {"type": "stop"})])
    script = [
        (t0 + 200, lambda: link.press()),
        (t0 + 260, lambda: link.release()),
        (t0 + 400, lambda: fakes.FakePin.level.__setitem__(0, 0)),
        (t0 + 500, lambda: fakes.FakePin.level.__setitem__(0, 1)),
        (t0 + 1000, lambda: setattr(link, "ready", False)),
        (t0 + 1500, lambda: setattr(link, "ready", True)),
    ]
    real_poll = net.poll

    def poll():
        while script and now[0] >= script[0][0]:
            script.pop(0)[1]()
        return real_poll()

    net.poll = poll
    net.run(g.play, None, leds, fakes.FakeBuz(), fakes.FakeAccel(), None, enow, None, net)
    colors = [w[1] for w in link.writes if w[0] == "leds"]
    import pairing
    from splat_api import COLOR_RGB
    want = [COLOR_RGB[pairing.IDENTITY[k][0]] for k in (0, 1, 2)]
    assert colors[:3] == want, colors
    assert g.LOST_RGB in leds.fills
    assert colors[-1] == want[2], "color restored after splat_back"
    assert offs(link) == 1 and leds.fills[-1] == "off"
    _with_local(None)


def test_soloecho_session_watch_dropout_stop():
    g = _game("solo_echo")
    assert g.SPLATS_LOCAL == 1
    ls, net = _solonet(1)
    link = ls.hub.links[0]
    t0 = now[0]
    leds = fakes.FakeLeds()
    enow = fakes.ScriptEnow([(t0 + 6000, "stop", {"type": "stop"})])
    real_poll = net.poll
    plan = [(t0 + 1500, False), (t0 + 2500, True)]

    def poll():
        while plan and now[0] >= plan[0][0]:
            link.ready = plan.pop(0)[1]
        return real_poll()

    net.poll = poll
    net.run(g.play, None, leds, fakes.FakeBuz(), fakes.FakeAccel(), None, enow, None, net)
    notes = [w for w in link.writes if w[0] == "noteOn"]
    assert len(notes) >= 2, "sequence played, then replayed after splat_back"
    assert g.LOST_RGB in leds.np.seen, "dropout shown on the wand"
    assert offs(link) >= 1 and leds.fills[-1] == "off"
    _with_local(None)


if __name__ == "__main__":
    n = 0
    for k, fn in list(globals().items()):
        if k.startswith("test_") and callable(fn):
            fn()
            print("ok  ", k)
            n += 1
    print("ALL %d PARTY TESTS PASSED" % n)
