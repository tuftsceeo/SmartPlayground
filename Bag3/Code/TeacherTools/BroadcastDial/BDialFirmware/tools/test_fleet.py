"""test_fleet.py -- host tests for fleet.Fleet (CPython, no hardware).

    python3 Bag3/Code/TeacherTools/BroadcastDial/BDialFirmware/tools/test_fleet.py
"""

import os
import sys
import time
import types
import unittest

BD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BD)

for name in ("machine", "network", "espnow"):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules["machine"].unique_id = lambda: b"\x01\x02\x03\x04\x00\x4c"

NOW = [0]
time.sleep_ms = lambda ms: None
time.ticks_ms = lambda: NOW[0]
time.ticks_diff = lambda a, b: a - b
time.ticks_add = lambda a, b: a + b

import fleet                                    # noqa: E402

A, B, C, D = "AA:00:00:00:00:01", "AA:00:00:00:00:02", "AA:00:00:00:00:03", "AA:00:00:00:00:04"


class FakeMgr:
    def __init__(self, nack=()):
        self._peers = {}
        self.sent = []
        self.nack = nack

    def broadcast(self, msg):
        self.sent.append(("bc", msg))
        return True

    def add_peer(self, mac):
        self._peers[mac] = mac

    def remove_peer(self, mac):
        self._peers.pop(mac, None)

    def send_to(self, mac, msg):
        self.sent.append((mac, msg))
        return mac not in self.nack


class FakeLink:
    def __init__(self):
        self.out = []

    def send(self, obj):
        self.out.append(obj)

    def of(self, t):
        return [o for o in self.out if o.get("type") == t]


class FakeUI:
    def __init__(self):
        self.progress = []

    def show_progress(self, done, total):
        self.progress.append((done, total))


def make(nack=()):
    NOW[0] = 1000
    link, ui, mgr = FakeLink(), FakeUI(), FakeMgr(nack)
    return fleet.Fleet(link, ui), link, ui, mgr


class Scan(unittest.TestCase):
    def test_reports_then_done(self):
        fl, link, ui, mgr = make()
        fl.scan(mgr)
        self.assertEqual(sum(1 for s in mgr.sent if s[1] == {"type": "status_poll"}),
                         fleet.POLL_REPEAT)
        fl.on_msg({"type": "status_report", "kind": "wand", "battery": 80, "rssi": -50}, A)
        fl.on_msg({"type": "other"}, B)
        self.assertEqual(link.of("status_report")[0]["kind"], "wand")
        self.assertEqual(len(link.of("status_report")), 1)
        NOW[0] += fleet.SCAN_MS
        fl.step()
        self.assertEqual(link.of("status_done"), [{"type": "status_done", "n": 1}])
        fl.on_msg({"type": "status_report"}, C)      # after the window
        self.assertEqual(len(link.of("status_report")), 1)


class Distribute(unittest.TestCase):
    def test_staggered_and_capped(self):
        fl, link, ui, mgr = make()
        fl.distribute(mgr, "g", [A, B, C, D])
        pushes = lambda: [s for s in mgr.sent if s[0] != "bc"]
        fl.step()
        self.assertEqual(len(pushes()), 1)
        fl.step()                                    # inside STAGGER_MS
        self.assertEqual(len(pushes()), 1)
        for _ in range(3):
            NOW[0] += fleet.STAGGER_MS
            fl.step()
        self.assertEqual(len(pushes()), fleet.MAX_INFLIGHT)   # D waits on the cap
        fl.on_pull({"mac": A, "ok": True, "why": ""})
        NOW[0] += fleet.STAGGER_MS
        fl.step()
        self.assertEqual(len(pushes()), 4)
        self.assertEqual(pushes()[0][1]["type"], "code_push")
        self.assertEqual(pushes()[0][1]["host"], fleet.HOST_ID)
        self.assertEqual(mgr._peers, {})             # temp peers removed

    def test_progress_timeout_nack_and_done(self):
        fl, link, ui, mgr = make(nack=(C,))
        fl.distribute(mgr, "g", [A, B, C])
        for _ in range(3):
            fl.step()
            NOW[0] += fleet.STAGGER_MS
        fl.on_pull({"mac": A.lower(), "ok": True, "why": ""})   # case-insensitive
        fl.on_pull({"mac": "FF:00:00:00:00:00", "ok": True})     # not ours
        NOW[0] += fleet.PUSH_TIMEOUT_MS
        fl.step()                                                # B times out
        final = [p for p in link.of("dist_progress") if p["ok"] is not None]
        self.assertEqual([(p["mac"], p["ok"], p["why"]) for p in final],
                         [(C, False, "no_ack"), (A, True, None), (B, False, "timeout")])
        self.assertEqual(link.of("dist_done"), [{"type": "dist_done", "done": 3,
                                                  "total": 3, "ok": 1}])
        self.assertFalse(fl.busy)
        self.assertEqual(ui.progress[-1], (3, 3))
        NOW[0] += fleet.PROGRESS_HOLD_MS
        fl.step()
        self.assertEqual(ui.progress[-1], (0, 0))

    def test_cancel(self):
        fl, link, ui, mgr = make()
        fl.distribute(mgr, "g", [A, B])
        fl.step()
        fl.cancel("radio_off")
        whys = [p["why"] for p in link.of("dist_progress") if p["ok"] is not None]
        self.assertEqual(whys, ["radio_off", "radio_off"])
        self.assertEqual(len(link.of("dist_done")), 1)


if __name__ == "__main__":
    unittest.main()
