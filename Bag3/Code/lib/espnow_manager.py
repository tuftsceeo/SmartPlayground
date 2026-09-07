"""
espnow_manager.py -- ESP-NOW messaging for every hubtype.

    from espnow_manager import ESPNowManager

    net = ESPNowManager()
    net.init()
    net.broadcast_cap("score_station", "push", {"v": 8420, "c": "blue"})
    kind, data, mac = net.poll()

Three message kinds travel on the air, all JSON:

    sys   framework traffic -- stop, start, who/here, ident
    cap   a command to a station's hardware, addressed by hubtype
    evt   something a device reports; game vocabulary lives here

poll() returns (kind, data, mac_str), or (None, None, None) when nothing is
waiting. "sys who" is answered inside poll(); everything else is handed up.

Nothing here is acknowledged, ordered, de-duplicated or fragmented. A sender
that needs an event to land repeats it and the receiver guards on state.

The only failures caught here are the two that are ordinary radio outcomes: a
momentarily full TX queue, and a payload that is not JSON. Everything else
raises.
"""

import gc
import network
import espnow
import json
import time
from machine import Pin

from hubtype import HUB_TYPE

BROADCAST_MAC = b'\xFF\xFF\xFF\xFF\xFF\xFF'

# ESP-NOW carries 250 bytes. Oversized messages raise rather than fail quietly.
MAX_PAYLOAD = 250

# "who" replies are slotted by MAC so a room full of devices does not answer
# at once. Worst-case spread is BASE_DELAY_MS + (N_SLOTS - 1) * SLOT_MS.
N_SLOTS = 16
BASE_DELAY_MS = 400
SLOT_MS = 180

# Pause + single retry when a broadcast hits a full ESP-NOW TX queue.
SEND_RETRY_MS = 30

# True only on a board with an antenna on the u.FL connector. code_puller
# reads this too -- one radio, one pair of select pins.
EXTERNAL_ANTENNA = False

# Settle time after releasing the radio, before anything else claims it.
RADIO_SETTLE_MS = 300


def _is_esp32c6():
    """True on ESP32-C6 boards, which have the GPIO3/14 antenna switch."""
    import os
    import sys
    return ('esp32c6' in sys.platform.lower()
            or 'ESP32C6' in os.uname().machine.upper())


def _configure_antenna(external=EXTERNAL_ANTENNA):
    """Select onboard or u.FL antenna. C6 only; both directions driven.

    GPIO3 = switch enable (active low), GPIO14 = select (0 onboard, 1 u.FL).
    """
    if not _is_esp32c6():
        return
    wifi_en = Pin(3, Pin.OUT)
    ant_cfg = Pin(14, Pin.OUT)
    wifi_en.value(0)
    time.sleep_ms(100)
    ant_cfg.value(1 if external else 0)


def mac_str_to_bytes(mac_str):
    return bytes([int(p, 16) for p in mac_str.split(':')])


def mac_bytes_to_str(mac_bytes):
    return ':'.join('%02X' % b for b in mac_bytes)


def get_own_mac():
    sta = network.WLAN(network.STA_IF)
    was = sta.active()
    if not was:
        _configure_antenna()
        sta.active(True)
    mac = mac_bytes_to_str(sta.config('mac'))
    if not was:
        sta.active(False)
    return mac


def _encode(obj):
    """JSON-encode and refuse anything ESP-NOW cannot carry."""
    msg = obj if isinstance(obj, (str, bytes)) else json.dumps(obj)
    raw = msg.encode('utf-8') if isinstance(msg, str) else msg
    if len(raw) > MAX_PAYLOAD:
        raise ValueError("message is %d bytes, limit is %d: %s"
                         % (len(raw), MAX_PAYLOAD, msg))
    return raw


class ESPNowManager:

    def __init__(self):
        self.enow = None
        self._active = False
        self._peers = {}          # mac_str -> mac_bytes
        self._seen = {}           # hubtype -> mac_str, from "here" replies
        self._status_provider = None
        self._reply_due = None
        self._own_mac = None

    # -- lifecycle ---------------------------------------------------

    def init(self):
        if self._active:
            return
        _configure_antenna()
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        sta.disconnect()
        self.enow = espnow.ESPNow()
        self.enow.active(True)
        self.enow.add_peer(BROADCAST_MAC)
        self._active = True
        print("  ESPNow: active as %s (MAC %s)" % (HUB_TYPE, get_own_mac()))

    def shutdown(self):
        """Release the radio and drop the ESPNow object.

        While an espnow.ESPNow object is alive it holds the WiFi interface and
        a later sta.connect() is refused silently. init() recreates it.
        """
        if not self._active:
            return
        self.broadcast_sys("stop")
        self.enow.active(False)
        self.enow = None
        self._active = False
        self._peers.clear()
        gc.collect()
        time.sleep_ms(RADIO_SETTLE_MS)

    @property
    def is_active(self):
        return self._active

    def _require_active(self):
        if not self._active:
            raise OSError("ESPNow: init() has not run")

    # -- peers and discovery -----------------------------------------

    def add_peer(self, mac_str):
        """Register a unicast peer. The broadcast peer is added by init()."""
        self._require_active()
        mac_bytes = mac_str_to_bytes(mac_str)
        if mac_str in self._peers or mac_bytes == BROADCAST_MAC:
            return
        self.enow.add_peer(mac_bytes)
        self._peers[mac_str] = mac_bytes

    def remove_peer(self, mac_str):
        mac_bytes = self._peers.pop(mac_str, None)
        if mac_bytes is not None:
            self.enow.del_peer(mac_bytes)

    def clear_peers(self):
        for mac_str in list(self._peers):
            self.remove_peer(mac_str)

    def get_peer_macs(self):
        return list(self._peers)

    def get_rssi(self, mac_str):
        """Last RSSI for a peer, or None if the radio has not heard from it."""
        mac_bytes = self._peers.get(mac_str) or mac_str_to_bytes(mac_str)
        table = self.enow.peers_table
        return table[mac_bytes][0] if mac_bytes in table else None

    def find(self, hub):
        """MAC of a hubtype seen replying to "who", or None.

        Only needed when two devices share a hubtype. Capability messages are
        addressed by hubtype and reach every one of them without this.
        """
        return self._seen.get(hub)

    def set_status_provider(self, fn):
        """Register fn() -> battery percent or None, reported in "here"."""
        self._status_provider = fn

    # -- sending -----------------------------------------------------

    def broadcast(self, obj):
        """Broadcast, retrying once past a momentarily full TX queue.

        Sent async: a broadcast is never acked, so a synchronous send waits for
        an ACK that never arrives. A second OSError is a real fault and raises.
        """
        self._require_active()
        raw = _encode(obj)
        for attempt in range(2):
            try:
                self.enow.send(BROADCAST_MAC, raw, False)
                return
            except OSError:
                if attempt:
                    raise
                time.sleep_ms(SEND_RETRY_MS)

    def send_to(self, mac_str, obj):
        self._require_active()
        if mac_str not in self._peers:
            self.add_peer(mac_str)
        self.enow.send(self._peers[mac_str], _encode(obj))

    def send_raw(self, mac_bytes, raw_bytes):
        """Send bytes with no encoding. For binary payloads only."""
        self._require_active()
        if len(raw_bytes) > MAX_PAYLOAD:
            raise ValueError("raw payload is %d bytes, limit is %d"
                             % (len(raw_bytes), MAX_PAYLOAD))
        self.enow.send(mac_bytes, raw_bytes, False)

    def broadcast_sys(self, op, **kw):
        msg = {"type": "sys", "op": op}
        msg.update(kw)
        self.broadcast(msg)

    def broadcast_cap(self, hub, op, args=None):
        """Command every station of hubtype `hub` to do `op`."""
        msg = {"type": "cap", "hub": hub, "op": op}
        if args:
            msg["a"] = args
        self.broadcast(msg)

    def broadcast_evt(self, ev, data=None, slug=None):
        """Report something. Game events carry the slug they belong to."""
        msg = {"type": "evt", "src": HUB_TYPE, "ev": ev}
        if data is not None:
            msg["d"] = data
        if slug:
            msg["slug"] = slug
        self.broadcast(msg)

    def stop_all(self):
        self.broadcast_sys("stop")

    def start_all(self, slug):
        self.broadcast_sys("start", slug=slug)

    # -- receiving ---------------------------------------------------

    def _is_me(self, mac_str):
        if not mac_str:
            return False
        if self._own_mac is None:
            self._own_mac = get_own_mac()
        return mac_str.replace(":", "").upper() == self._own_mac.replace(":", "").upper()

    def _my_slot_delay(self):
        if self._own_mac is None:
            self._own_mac = get_own_mac()
        slot = int(self._own_mac.split(':')[-1], 16) % N_SLOTS
        return BASE_DELAY_MS + slot * SLOT_MS

    def _send_here(self):
        soc = self._status_provider() if self._status_provider else None
        self.broadcast_sys("here", hub=HUB_TYPE, soc=soc)

    def _service_reply(self):
        """Send a due "here" reply. Called at the top of every poll()."""
        if self._reply_due is None:
            return
        if time.ticks_diff(time.ticks_ms(), self._reply_due) < 0:
            return
        self._reply_due = None
        self._send_here()

    def poll(self, timeout_ms=0):
        """Receive one message, waiting up to timeout_ms. Returns
        (kind, data, mac_str), or (None, None, None) if nothing arrived.

        kind is "sys", "cap", "evt" or "raw". "cap" is delivered only when this
        device's hubtype is the one addressed.
        """
        self._require_active()
        self._service_reply()
        mac, msg = self.enow.irecv(timeout_ms)
        if msg is None:
            return None, None, None

        mac_str = mac_bytes_to_str(mac) if mac else None

        try:
            data = json.loads(msg)
        except (ValueError, UnicodeError):
            return "raw", bytes(msg), mac_str
        if not isinstance(data, dict):
            return "raw", data, mac_str

        kind = data.get("type")

        if kind == "sys":
            op = data.get("op")
            if op == "who":
                self._reply_due = time.ticks_add(time.ticks_ms(),
                                                 self._my_slot_delay())
                return None, None, None
            if op == "here":
                hub = data.get("hub")
                if hub and mac_str:
                    self._seen[hub] = mac_str
                return "sys", data, mac_str
            if op == "ident" and not self._is_me(data.get("mac")):
                return None, None, None
            return "sys", data, mac_str

        if kind == "cap":
            if data.get("hub") != HUB_TYPE:
                return None, None, None
            return "cap", data, mac_str

        if kind == "evt":
            return "evt", data, mac_str

        return "raw", data, mac_str

    def drain(self):
        self._require_active()
        while True:
            _, msg = self.enow.irecv(0)
            if msg is None:
                break
