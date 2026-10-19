"""
solo.py -- Splat game setup and the solo `net` (SoloNet)
========================================================
SPEC: docs_and_design/2026-10-07-splat-pairing/SPEC.md section 6
("Solo Splat games").

Imported lazily by main.py, after a game module loads, only when it
declares SPLATS_LOCAL or SPLATS_MIN. party.py is imported only for
SPLATS_MIN games.

    prepare(mod, slug, nfc, leds, buz, enow)
        -> SoloNet or party.Net to pass to play(), or None when the game
           must not start (too few READY Splats, lobby cancelled).
           Raises ValueError when the game declares both constants.
    check(local, n)  -> True if at least n local Splats are READY

SoloNet has the SPEC section 7 members. is_leader is True, wands holds
only this wand, me is 0; splat(i) is local Splat i; poll() services the
local Splats; send() raises. close() turns the local Splats off;
run(fn, *args) calls fn and closes on return, stop or error.

UNVERIFIED on hardware: the amber refusal feedback.
"""

import time

import pairing

_REFUSE_SHAPE = (0, 4, 6, 8, 12, 16, 18, 20, 24)   # leds.SHAPE_X
_AMBER = (120, 80, 0)


def kind(mod):
    """("solo", n, None), ("party", min, max) or None. ValueError if both."""
    n_local = getattr(mod, "SPLATS_LOCAL", None)
    n_min = getattr(mod, "SPLATS_MIN", None)
    if n_local is not None and n_min is not None:
        raise ValueError("game declares both SPLATS_LOCAL and SPLATS_MIN")
    if n_local is not None:
        return ("solo", int(n_local), None)
    if n_min is not None:
        n_max = getattr(mod, "SPLATS_MAX", None)
        return ("party", int(n_min), None if n_max is None else int(n_max))
    return None


def check(local, n):
    return local is not None and len(local.ready()) >= n


def refuse(leds, buz, why):
    print(f"  solo: not starting: {why}")
    for _ in range(2):
        leds.show_shape(_REFUSE_SHAPE, _AMBER)
        buz.beep(350, 150)
        time.sleep_ms(150)
        leds.off()
        time.sleep_ms(100)


def prepare(mod, slug, nfc, leds, buz, enow):
    k = kind(mod)
    if k is None:
        return None
    local = pairing.local()
    if k[0] == "solo":
        if not check(local, k[1]):
            have = 0 if local is None else len(local.ready())
            refuse(leds, buz, f"{slug} needs {k[1]} READY Splat(s), {have} READY")
            return None
        from espnow_manager import get_own_mac
        return SoloNet(local, get_own_mac())
    import party
    return party.lobby(enow, leds, buz, nfc, slug, k[1], k[2])


class SoloNet:
    is_leader = True
    me = 0

    def __init__(self, local, own_mac):
        self.local = local
        self.wands = [(own_mac, local.identity[0], local.count)]
        self.splat_count = local.count
        self._closed = False

    def splat(self, i):
        return self.local.splat(i)

    def owner(self, i):
        if not 0 <= i < self.splat_count:
            raise IndexError(i)
        return 0

    def send(self, to, data):
        raise RuntimeError("solo game: there are no other wands to send to")

    def poll(self):
        return self.local.poll()

    def wrap(self, enow):
        return enow

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.local.off()

    def run(self, fn, *args):
        try:
            return fn(*args)
        finally:
            self.close()
