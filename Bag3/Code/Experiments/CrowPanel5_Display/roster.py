"""Device roster keyed by MAC: last heard, battery, signal. Pattern of the WebApp hub's recent_devices."""

import time

STALE_MS = 60000


def tag_of(mac):
    return mac.replace(":", "")[-4:].upper()


def signal_word(rssi):
    if rssi is None:
        return "-"
    return "Strong" if rssi > -60 else ("Good" if rssi > -75 else "Weak")


class Roster:
    def __init__(self, names):
        self.d = {}
        self.names = names      # mac -> nickname (store.names)

    def touch(self, mac, data=None):
        e = self.d.get(mac)
        if e is None:
            e = self.d[mac] = {"mac": mac, "kind": "wand", "battery": None, "rssi": None,
                               "seen": None, "heard": False, "game": None}
        e["seen"] = time.ticks_ms()
        if data:
            if data.get("kind"):
                e["kind"] = data["kind"]
            if data.get("battery") is not None:
                e["battery"] = data["battery"]
            if data.get("rssi") is not None:
                e["rssi"] = data["rssi"]
        return e

    def macs(self):
        return list(self.d)

    def is_wand(self, e):
        return e["kind"] in ("wand", None)

    def name(self, mac):
        n = self.names.get(mac)
        if n:
            return n
        e = self.d.get(mac)
        return ("W-" if e is None or self.is_wand(e) else "S-") + tag_of(mac)

    def low(self, e):
        return e["battery"] is not None and e["battery"] < 20

    def age(self, e):
        """'3 min ago' style text, or 'Not heard'."""
        if e["seen"] is None:
            return "Not heard"
        s = time.ticks_diff(time.ticks_ms(), e["seen"]) // 1000
        if s < 60:
            return "just now"
        return f"{s // 60} min ago"

    def items(self, kind="all"):
        out = []
        for mac, e in self.d.items():
            if kind == "wands" and not self.is_wand(e):
                continue
            if kind == "stations" and self.is_wand(e):
                continue
            out.append(e)
        return out

    def begin_roll_call(self):
        for e in self.d.values():
            e["heard"] = False

    def summary(self):
        heard = [e for e in self.d.values() if e["heard"]]
        wands = [e for e in heard if self.is_wand(e)]
        low = sum(1 for e in wands if self.low(e))
        return len(heard), len(wands) - low, low, len(heard) - len(wands)

    def rank(self, e, playing=None):
        """Sort key: not heard, low battery, playing, named, then the rest."""
        if e["seen"] is None:
            return 0
        if self.low(e):
            return 1
        if playing and playing.get(e["mac"]):
            return 2
        return 3

    def ranked(self, kind="all", playing=None):
        out = self.items(kind)
        out.sort(key=lambda e: self.rank(e, playing))
        return out
