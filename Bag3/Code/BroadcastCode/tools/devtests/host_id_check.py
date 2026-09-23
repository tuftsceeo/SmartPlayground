"""
Host-side check for per-host identity AP selection (code_puller.py's
_find_ap()), stubbed against MockWand/lib's game_store/nfc_reader/pn532 and
this directory's machine/network stubs -- no hardware, no radio.

Three cases matter for "several hosts in one room, each serving different
code" (see the plan this lands with):

  1. A card that named a host id must join THAT host and no other, however
     loud the others are.
  2. A card with no host id (every one written before per-host identity, or
     a bare "getcode") must join the loudest SP-FILEPUSH* host visible.
  3. A card that named a host id that simply isn't in the room must find
     nothing, even though other SP-FILEPUSH* hosts are audible.

Run:  python3 Bag3/Code/BroadcastCode/tools/devtests/host_id_check.py
Exits non-zero on any mismatch. It does NOT touch hardware.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BROADCASTCODE = os.path.dirname(os.path.dirname(HERE))  # tools/devtests -> tools -> BroadcastCode

sys.path.insert(0, os.path.join(HERE, "stubs"))
sys.path.insert(0, os.path.join(BROADCASTCODE, "MockWand", "lib"))  # game_store, nfc_reader, pn532
sys.path.insert(0, os.path.join(BROADCASTCODE, "MockWand"))

# MicroPython's `time` has sleep_ms/ticks_*; CPython's doesn't. code_puller.py
# only calls sleep_ms() inside functions this check never reaches (the real
# radio join/transfer path), so a no-op stands in fine -- same technique
# wire_contract.py uses for the same reason.
import time as _time
_time.sleep_ms = lambda ms: None

import code_puller as CP

fail = 0


def check(label, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(("ok   " if ok else "FAIL ") + label)
    if not ok:
        print("      got  %r" % (got,))
        print("      want %r" % (want,))


class FakeSta:
    """Just enough of network.WLAN's STA surface for _find_ap()/_scan_for_ap()."""

    def __init__(self, nets):
        # scan() tuple shape: (ssid, bssid, channel, rssi, security, hidden).
        self._nets = nets

    def scan(self):
        return self._nets


def net(ssid, bssid=b'\x01', channel=1, rssi=-50, security=3, hidden=False):
    return (ssid.encode('utf-8'), bssid, channel, rssi, security, hidden)


PREFIX = CP.SSID_PREFIX  # 'SP-FILEPUSH'

# --- case 1: an exact host id pins to that host, ignoring louder others ---
nets = [
    net(PREFIX + '-aaaa', bssid=b'\x0a', rssi=-30),   # louder...
    net(PREFIX + '-bbbb', bssid=b'\x0b', rssi=-80),   # ...but this is wanted
    net('SOME-OTHER-AP', bssid=b'\x0c', rssi=-20),
]
ssid, bssid, ch, got_nets = CP._find_ap(FakeSta(nets), PREFIX, 'bbbb', verbose=False)
check("exact host id: picks the named host, not the louder one",
      (ssid, bssid), (PREFIX + '-bbbb', b'\x0b'))

# Case-insensitive match, since a card's slug/host text is lowercased by the
# reader but a real AP's SSID case is whatever the writing host set (also
# lowercase hex here, but this is worth pinning down explicitly).
ssid, bssid, ch, _ = CP._find_ap(FakeSta(nets), PREFIX, 'BBBB', verbose=False)
check("exact host id match is case-insensitive",
      (ssid, bssid), (PREFIX + '-bbbb', b'\x0b'))

# --- case 2: no host id -> strongest SP-FILEPUSH* wins ---
nets2 = [
    net(PREFIX + '-aaaa', bssid=b'\x0a', rssi=-70),
    net(PREFIX + '-bbbb', bssid=b'\x0b', rssi=-40),   # loudest SP-FILEPUSH*
    net(PREFIX + '-cccc', bssid=b'\x0c', rssi=-60),
    net('SOME-OTHER-AP', bssid=b'\x0d', rssi=-10),    # loudest overall, but not a match
]
ssid, bssid, ch, _ = CP._find_ap(FakeSta(nets2), PREFIX, '', verbose=False)
check("no host id: picks the strongest SP-FILEPUSH* host",
      (ssid, bssid), (PREFIX + '-bbbb', b'\x0b'))

# --- case 3: the wanted host id is simply not in the room ---
ssid, bssid, ch, got_nets3 = CP._find_ap(FakeSta(nets2), PREFIX, 'zzzz', verbose=False)
check("absent host id: finds nothing, even with other hosts audible",
      (ssid, bssid, ch), (None, None, None))
check("absent host id: still hands back the raw scan for logging",
      got_nets3, nets2)

# --- no SP-FILEPUSH* host at all ---
ssid, bssid, ch, _ = CP._find_ap(FakeSta([net('SOME-OTHER-AP')]), PREFIX, '', verbose=False)
check("nothing matching the prefix: finds nothing",
      (ssid, bssid, ch), (None, None, None))

# --- a scan() failure is reported as "nothing found", not a crash ---
class BrokenSta:
    def scan(self):
        raise OSError("radio wedged")


ssid, bssid, ch, nets4 = CP._find_ap(BrokenSta(), PREFIX, '', verbose=False)
check("scan() failure: finds nothing", (ssid, bssid, ch), (None, None, None))
check("scan() failure: nets is None (nothing to log)", nets4, None)

print("\n%s" % ("all host id checks passed" if not fail else "%d FAILURES" % fail))
sys.exit(1 if fail else 0)
