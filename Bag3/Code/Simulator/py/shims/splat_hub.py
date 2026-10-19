"""
Simulated Splats, in place of lib/splat_hub.py and the BLE stack under it
(splat_link.py, ble_splat.py).

The real splatpair.SplatPairing builds `SplatHub(count=n, macs=[...])` and
the real splat_api.SplatGroup drives its links, so pairing feedback, the
idle glow, party.py's ready mask and every game's Splat calls run the
vendored code unchanged. Only the radio is missing: a link is ready unless
the host unplugs it, and every write goes to the host.

Host side:
    set_write_callback(cb)   cb(mac, op, args_json) per link write; op is
                             "leds" [r, g, b], "sound" [idx], "noteOn"
                             [value, octave], "noteOff" [value, octave],
                             "tasksOff" [] or "ledsOff" []
    press(mac) / release(mac)  the Splat's button
    set_ready(mac, up)       unplug (False) or reconnect (True); a
                             reconnect counts as a new connect, as on BLE.
                             Remembered for a hub built later.
    macs()                   the current hub's Splat MACs, in local order
"""

import json

_write_cb = None
_hub = None
_want = {}              # mac -> ready, as last set by the host (default True)


def set_write_callback(cb):
    global _write_cb
    _write_cb = cb


def _link(mac):
    if _hub is not None:
        for link in _hub.links:
            if link.mac_address == mac:
                return link
    raise KeyError("no simulated Splat %s" % mac)


def press(mac):
    _link(mac)._events.append(1)


def release(mac):
    _link(mac)._events.append(0)


def set_ready(mac, up):
    _want[mac] = bool(up)
    if _hub is not None:
        for link in _hub.links:
            if link.mac_address == mac:
                link.want_ready = bool(up)


def macs():
    return [] if _hub is None else [link.mac_address for link in _hub.links]


class SplatLink:
    """The surface of splat_link.SplatLink that splat_api and splatpair use."""

    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.pinned = True
        self.ready = False
        self.want_ready = _want.get(mac_address, True)
        self.connects = 0
        self.drops = 0
        self.scan_gate = None
        self._events = []

    def service(self, now):
        if self.want_ready and not self.ready:
            self.ready = True
            self.connects += 1
        elif self.ready and not self.want_ready:
            self.ready = False
            self.drops += 1
            self._events = []

    def take_events(self):
        ev, self._events = self._events, []
        return ev

    def _w(self, op, args=()):
        if not self.ready:
            return False
        if _write_cb is not None:
            _write_cb(self.mac_address, op, json.dumps(list(args)))
        return True

    def keepAlive(self):
        return self.ready

    def readSwitches(self):
        return self.ready

    def setLEDsON(self, rgb):
        return self._w("leds", rgb)

    def playSound(self, idx, volume):
        return self._w("sound", (idx,))

    def noteOn(self, value, velocity, octave, instrument):
        return self._w("noteOn", (value, octave))

    def noteOff(self, value, velocity, octave, instrument):
        return self._w("noteOff", (value, octave))

    def allTasksOff(self):
        return self._w("tasksOff")

    def allLEDsOff(self):
        return self._w("ledsOff")

    def _stop_scan(self):
        pass

    def close(self):
        self.ready = False
        self.want_ready = False


class SplatHub:
    def __init__(self, count=1, macs=None):
        global _hub
        macs = [m.upper() for m in (macs or [])]
        self.pinned = list(macs)
        self.links = [SplatLink(m) for m in macs]
        self.discovering = False
        self.misrouted = 0
        _hub = self
