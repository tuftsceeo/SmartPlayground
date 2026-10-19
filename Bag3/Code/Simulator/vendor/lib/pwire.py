"""
pwire.py -- ESP-NOW helpers shared by splatpair.py and party.py
================================================================
Unicast through the raw ESPNow object so the MAC-layer ACK is visible:
espnow_manager.send_to() reports True whether or not the peer ACKed.
"""

import json
import time

from espnow_manager import mac_str_to_bytes

SEND_TRIES = 3          # synchronous unicast attempts before giving up
DEDUPE_KEEP = 16        # recent q values remembered per sender


def ensure_peer(enow, mac_str):
    """Register mac_str as an ESP-NOW peer. True if this call added it."""
    if mac_str in enow.get_peer_macs():
        return False
    enow.add_peer(mac_str)
    return True


def send_acked(enow, mac_str, obj, tries=SEND_TRIES):
    """Unicast obj (dict) to a registered peer; True once a try is ACKed.
    OSError (TX queue full) counts as a failed try. A final failure prints."""
    raw = enow.enow
    if raw is None:
        return False
    msg = json.dumps(obj)
    mac = mac_str_to_bytes(mac_str)
    err = None
    for _ in range(tries):
        try:
            if raw.send(mac, msg):
                return True
            err = "no ACK"
        except OSError as e:
            err = str(e)
        time.sleep_ms(1)
    print("  [WARN] pwire: %s to %s failed after %d tries (%s)"
          % (obj.get("type"), mac_str, tries, err))
    return False


class Dedupe:
    """Drops a q already seen from the same sender (a lost ACK causes a
    resend of a frame that was delivered)."""

    def __init__(self):
        self._seen = {}

    def fresh(self, sender, q):
        if q is None:
            return True
        seen = self._seen.setdefault(sender, [])
        if q in seen:
            return False
        seen.append(q)
        if len(seen) > DEDUPE_KEEP:
            del seen[0]
        return True

    def forget(self, sender):
        self._seen.pop(sender, None)
