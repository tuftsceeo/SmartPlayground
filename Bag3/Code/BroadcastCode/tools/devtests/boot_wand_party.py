"""Party games through main.py (A6): the lobby before play(), the 8-parameter
play() contract, invalid SPLATS_* declarations, net.close() on every exit.

The real main.py idle loop launches games from scripted cards; other wands on
the fake bus run party.enter() as peers.

Run: python3 tools/devtests/boot_wand_party.py
"""
import os
import shutil
import sys
import time
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wandboot  # noqa: E402
import wandsim  # noqa: E402
from wandboot import A, B, boot, FakePN532  # noqa: E402

check = wandsim.Checker()

gamelog = types.ModuleType("gamelog")
sys.modules["gamelog"] = gamelog

PEER_MAC = "AA:00:00:00:00:21"
NONE = [None]

PARTY8 = '''
import gamelog
import time
SPLATS_MIN = 2
SPLATS_MAX = None


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    gamelog.calls.append(("party8", net is not None and net.is_leader,
                          net.splat_count, len(net.wands), net.me))
    end = time.ticks_ms() + gamelog.run_ms
    while time.ticks_ms() < end:
        if net.poll() == ("end",):
            gamelog.calls.append(("end",))
            return
        time.sleep_ms(1)
'''
GAMES = {
    "pgame": PARTY8,
    "plain8": '''
import gamelog
def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    gamelog.calls.append(("plain8", net))
''',
    "old7": '''
import gamelog
def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    gamelog.calls.append(("old7", batt))
''',
    "old6": '''
import gamelog
def play(nfc, leds, buz, accel, i2c, enow):
    gamelog.calls.append(("old6",))
''',
    "badmin": PARTY8.replace("SPLATS_MIN = 2", "SPLATS_MIN = 0"),
    "badmax": PARTY8.replace("SPLATS_MIN = 2", "SPLATS_MIN = 3").replace("SPLATS_MAX = None", "SPLATS_MAX = 2"),
    "badtype": PARTY8.replace("SPLATS_MIN = 2", 'SPLATS_MIN = "2"'),
    "boomy": '''
import gamelog
SPLATS_MIN = 2
def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    gamelog.calls.append(("boomy", net.is_leader))
    raise RuntimeError("game bug")
''',
    "nonet": '''
import gamelog
SPLATS_MIN = 1
def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    gamelog.calls.append(("nonet",))
''',
}


def reset_log(run_ms=1500):
    gamelog.calls = []
    gamelog.run_ms = run_ms


def peer(b, mac=PEER_MAC, splats=(), at_ms=0, slug="pgame", smin=2, smax=None, game_ms=1500,
         press_start_ms=None):
    """Another wand on the bus: taps `slug` at at_ms, then polls its Net."""
    w = wandsim.Wand(b.sim, b.bus, mac)
    for s in splats:
        w.splat(s)
    w.events = []
    w.net = None
    w.last_end = "unset"
    w.nfc = FakePN532()
    w.button = False
    b.peer = w

    def run():
        import party
        import splatpair
        ctl = None
        if splats:
            ctl = splatpair.SplatPairing(list(splats), w.enow, w.leds, w.buz, my_mac=mac)
            t0 = time.ticks_ms()
            while not all(l.ready for l in ctl.hub.links) and time.ticks_ms() - t0 < 5000:
                ctl.poll()
                time.sleep_ms(5)
        if time.ticks_ms() < at_ms:
            time.sleep_ms(at_ms - time.ticks_ms())
        net = party.enter(w.enow, slug, smin, smax, ctl, mac, w.nfc, w.leds, w.buz,
                          lambda: w.button)
        w.net = net
        w.last_end = party.last_end
        if net is not None:
            end = time.ticks_ms() + game_ms
            try:
                while time.ticks_ms() < end:
                    ev = net.poll()
                    if ev is not None:
                        w.events.append(ev)
                        if ev == ("end",):
                            break
                    time.sleep_ms(1)
            finally:
                net.close()

    b.sim.spawn("peer", run, w)
    return w


# ── The booted wand leads: lobby, then play(…, net) ──
reset_log()


def lead_setup(b):
    b.sim.max_ms = 60000
    peer(b, splats=[B], at_ms=6500, game_ms=6000)
    b.sim.at(8200, lambda: setattr(b.button, "down", True))
    b.sim.at(8300, lambda: setattr(b.button, "down", False))


b = boot(macs=[A], in_range=[A], games=GAMES, cards=NONE * 25 + ["pgame"] + NONE * 40, setup=lead_setup)
m = b.m
check("the party game's module was unloaded after the game", "pgame" not in sys.modules)
calls = [c for c in gamelog.calls if c[0] == "party8"]
check("a party game is entered through a lobby and play() gets a Net: leader, 2 Splats, 2 wands, me=0",
      calls == [("party8", True, 2, 2, 0)], str(gamelog.calls))
check("the peer joined as follower", b.peer.net is not None and not b.peer.net.is_leader, str(b.peer.last_end))
check("the leader's game ending ends the follower's ('end',)", ("end",) in b.peer.events, str(b.peer.events[-2:]))
check("game_start was emitted after the lobby, game_end after play",
      '"type": "game_start", "slug": "pgame"' in b.out and '"type": "game_end", "slug": "pgame"' in b.out)
check("net.close() removed every peer", b.wand.enow.get_peer_macs() == [], str(b.wand.enow.get_peer_macs()))
check("the wand's Splat got its idle glow back after the game",
      b.wand.periph(A).colors()[-1] == (0, 38, 0), str(b.wand.periph(A).colors()[-2:]))
check("no error in the main loop", "[ERR] Main loop" not in b.out, b.out[-400:])

# ── The booted wand follows ──
reset_log()


def follow_setup(b):
    b.sim.max_ms = 60000
    w = peer(b, splats=[B], at_ms=0, game_ms=6000)
    b.sim.at(7500, lambda: setattr(w, "button", True))
    b.sim.at(7600, lambda: setattr(w, "button", False))


b = boot(macs=[A], in_range=[A], games=GAMES, cards=NONE * 25 + ["pgame"] + NONE * 30, setup=follow_setup)
calls = [c for c in gamelog.calls if c[0] == "party8"]
check("a wand tapping an open lobby plays as a follower: not leader, 2 Splats, me=1",
      calls == [("party8", False, 2, 2, 1)], str(gamelog.calls))

# ── Arity: 6, 7 and 8 parameter play() ──
reset_log()
b = boot(games=GAMES, cards=NONE * 2 + ["old6", "old7", "plain8"] + NONE * 5)
check("an older six-parameter play() still runs", ("old6",) in gamelog.calls, str(gamelog.calls))
check("a seven-parameter play() still runs, batt passed", any(c[0] == "old7" for c in gamelog.calls))
check("an eight-parameter play() of a non-party game gets net=None", ("plain8", None) in gamelog.calls,
      str(gamelog.calls))

# ── Invalid declarations are load failures, not crashes ──
for slug in ("badmin", "badmax", "badtype"):
    reset_log()
    b = boot(games=GAMES, cards=NONE * 2 + [slug] + NONE * 4)
    check("%s: an invalid SPLATS_* declaration is a loud load failure" % slug,
          "[FAIL] game load" in b.out and "SPLATS_MIN" in b.out and not gamelog.calls
          and not b.reset, b.out[-300:])

# ── net.close() on a game that raises ──
reset_log()


def boomy_setup(b):
    b.sim.max_ms = 60000
    w = peer(b, splats=[B], at_ms=6500, slug="boomy", game_ms=4000)
    b.sim.at(8200, lambda: setattr(b.button, "down", True))
    b.sim.at(8300, lambda: setattr(b.button, "down", False))


b = boot(macs=[A], in_range=[A], games=GAMES, cards=NONE * 25 + ["boomy"] + NONE * 40, setup=boomy_setup)
check("a game that raises is reported by the main loop, as before", "game bug" in b.out)
check("...net.close() still ran: peers removed, the follower told the game ended",
      b.wand.enow.get_peer_macs() == [] and b.peer.net is not None and ("end",) in b.peer.events,
      "%s %s" % (b.wand.enow.get_peer_macs(), b.peer.events))

# ── A lobby cancelled by ESP-NOW stop: no game_start, back to idle ──
reset_log()


def stop_setup(b):
    b.sim.max_ms = 60000
    w = wandsim.Wand(b.sim, b.bus, "AA:00:00:00:00:31")
    b.sim.at(7000, lambda: w.enow.broadcast(["stop"]))


b = boot(macs=[A], in_range=[A], games=GAMES, cards=NONE * 25 + ["pgame"] + NONE * 10, setup=stop_setup)
check("an ESP-NOW stop in the lobby cancels it: play() never runs, no game_start",
      not gamelog.calls and '"type": "game_start"' not in b.out and not b.reset, str(gamelog.calls))
check("...and the wand is back in its idle loop", "Main loop" not in b.out or "[ERR] Main loop" not in b.out)

# ── A party game whose play() has no net parameter still runs after its lobby ──
reset_log()


def nonet_setup(b):
    b.sim.max_ms = 60000
    b.sim.at(7000, lambda: setattr(b.button, "down", True))
    b.sim.at(7100, lambda: setattr(b.button, "down", False))


b = boot(macs=[A], in_range=[A], games=GAMES, cards=NONE * 25 + ["nonet"] + NONE * 10, setup=nonet_setup)
check("a SPLATS_MIN game whose play() takes seven parameters runs after its lobby (net not passed)",
      ("nonet",) in gamelog.calls, str(gamelog.calls))

shutil.rmtree(wandboot.TMP, ignore_errors=True)
check.finish("wand party boot OK")
