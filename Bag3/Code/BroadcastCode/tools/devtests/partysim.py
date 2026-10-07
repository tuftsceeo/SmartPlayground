"""Scaffolding shared by test_party.py and test_party_games.py: simulated wands
running party.enter() and a game in virtual-time threads (see wandsim.py).

Importing this module patches nfc_reader's tag readers and machine.Pin for the
simulation: a `stop` card appears on a wand's reader at FakeNfc.stop_at, and
Pin(0) reads the running wand's `.button`.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wandsim  # noqa: E402

import nfc_reader  # noqa: E402  (MockWand/lib, via wandsim.setup_paths)
import party  # noqa: E402
import pwire  # noqa: E402
import splatpair  # noqa: E402

SLUG = "pgame"
S = {n: "AB:42:00:00:00:%02X" % n for n in range(1, 9)}      # fake Splat MACs
W = {n: "AA:00:00:00:00:%02X" % n for n in range(1, 9)}      # wand MACs


class FakeNfc:
    """stop_at: virtual ms at which a `stop` card is on the reader."""
    def __init__(self):
        self.stop_at = None


def _fake_read(nfc, timeout=500, resel_timeout=150):
    time.sleep_ms(timeout)
    if nfc.stop_at is not None and time.ticks_ms() >= nfc.stop_at:
        return "stop", "UIDSTOP"
    return None, None


nfc_reader.read_ndef_text = _fake_read
nfc_reader.read_tag_command = _fake_read


class _FakePin:
    """machine.Pin for the running wand's games: pin 0 is its button."""
    IN = 0
    OUT = 1
    PULL_UP = 2

    def __init__(self, pin, *a, **k):
        self.pin = pin

    def value(self, *a):
        w = wandsim.SIM.current_wand()
        return 0 if (self.pin == 0 and w is not None and getattr(w, "button", False)) else 1


sys.modules["machine"].Pin = _FakePin

NETS = []
_RealNet = party.Net


class RecNet(_RealNet):
    """party.Net that records itself, so a test can look at a lobby in progress."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        NETS.append(self)


party.Net = RecNet


def net_of(w):
    for n in reversed(NETS):
        if n.my_mac == w.mac:
            return n
    return None


def press(sc, w, at_ms, hold_ms=60):
    sc.sim.at(at_ms, lambda: setattr(w, "button", True))
    sc.sim.at(at_ms + hold_ms, lambda: setattr(w, "button", False))


class Sc:
    """One scenario: a Sim, a Bus and the wands on it."""

    def __init__(self):
        self.sim, self.bus = wandsim.new_sim()
        self.wands = {}
        self.log = []

    def wand(self, n, splats=()):
        w = wandsim.Wand(self.sim, self.bus, W[n])
        w.n = n
        w.nfc = FakeNfc()
        w.button = False
        w.events = []
        w.net = None
        w.ctl = None
        w.result = None
        w.splat_macs = [S[s] for s in splats]
        for s in splats:
            w.splat(S[s])
        self.wands[n] = w
        return w

    def tap(self, n, at_ms, game, smin=2, smax=None, slug=SLUG, wait_ready=True):
        """Wand n taps the party game's card at at_ms and then runs game(net, w)."""
        w = self.wands[n]

        def run():
            if w.splat_macs:
                w.ctl = splatpair.SplatPairing(list(w.splat_macs), w.enow, w.leds, w.buz,
                                               my_mac=w.mac)
                if wait_ready:
                    t0 = time.ticks_ms()
                    while (not all(l.ready for l in w.ctl.hub.links)
                           and time.ticks_ms() - t0 < 5000):
                        w.ctl.poll()
                        time.sleep_ms(5)
            if time.ticks_ms() < at_ms:
                time.sleep_ms(at_ms - time.ticks_ms())
            w.tap_ms = time.ticks_ms()
            net = party.enter(w.enow, slug, smin, smax, w.ctl, w.mac, w.nfc, w.leds, w.buz,
                              lambda: w.button)
            w.net = net
            w.last_end = party.last_end
            w.started_ms = time.ticks_ms() if net is not None else None
            if net is not None:
                try:
                    game(net, w)
                finally:
                    net.close()
            w.finished_ms = time.ticks_ms()
            w.result = "done"

        return self.sim.spawn("wand%d" % n, run, w)

    def run(self, ms):
        self.sim.run(self.sim.now + ms)


def loop(net, w, ms, each=None, stop_on_end=True):
    """The shape of a game's play() loop: poll, record, sleep 1 ms."""
    end = time.ticks_ms() + ms
    while time.ticks_ms() < end:
        ev = net.poll()
        if ev is not None:
            w.events.append(ev)
            if ev == ("end",) and stop_on_end:
                return
        if each is not None:
            each(net, w)
        time.sleep_ms(1)


def passive(ms):
    return lambda net, w: loop(net, w, ms)



def evs(w, kind=None):
    return [e for e in w.events if kind is None or e[0] == kind]


def long_loop(ms=30000):
    return lambda net, w: loop(net, w, ms)


