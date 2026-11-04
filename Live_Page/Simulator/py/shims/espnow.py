"""
Bus-backed `espnow` module.

Follows MicroPython's espnow.ESPNow closely enough for the real
espnow_manager.py: send() needs the peer added first (broadcast included),
irecv() returns (mac, msg) or (None, None) on timeout, peers_table maps peer
MAC bytes to [rssi, time_ms].

Frames go out through sim_state.radio_send(), which hands them to the host
bus (js/bus.js) when one is attached; frames arrive in sim_state.enow_inbox
via sim_state.deliver_enow().

irecv() is a coroutine: the simulator's transform awaits every call in
espnow_manager.py, so a blocking receive with a timeout sleeps on the
virtual clock instead of blocking the browser thread.
"""

import time

import sim_state

BROADCAST = b"\xff\xff\xff\xff\xff\xff"
MAX_DATA_LEN = 250
MAX_TOTAL_PEER_NUM = 20
SIM_RSSI = -45


class ESPNow:
    def __init__(self):
        self._active = False
        self._peers = {}
        self.peers_table = {}
        self._irq = None

    def active(self, flag=None):
        if flag is None:
            return self._active
        self._active = bool(flag)
        if not self._active:
            self._peers.clear()
            self.peers_table.clear()
        return self._active

    def _check_active(self):
        if not self._active:
            raise OSError("ESP_ERR_ESPNOW_NOT_INIT")

    def add_peer(self, mac, *args, **kwargs):
        self._check_active()
        mac = sim_state.mac_to_bytes(mac)
        if mac in self._peers:
            raise OSError("ESP_ERR_ESPNOW_EXIST")
        if len(self._peers) >= MAX_TOTAL_PEER_NUM:
            raise OSError("ESP_ERR_ESPNOW_FULL")
        self._peers[mac] = args
        self.peers_table[mac] = [SIM_RSSI, 0]

    def del_peer(self, mac):
        mac = sim_state.mac_to_bytes(mac)
        if mac not in self._peers:
            raise OSError("ESP_ERR_ESPNOW_NOT_FOUND")
        del self._peers[mac]
        self.peers_table.pop(mac, None)

    def get_peers(self):
        return tuple((m,) + tuple(a) for m, a in self._peers.items())

    def send(self, mac, msg=None, sync=True):
        """Unicast returns True when the bus had the destination attached
        (stands in for the ACK); broadcast always returns True."""
        self._check_active()
        if msg is None:
            raise TypeError("send(msg) to all peers is not simulated; pass a MAC")
        mac = sim_state.mac_to_bytes(mac)
        if mac not in self._peers:
            raise OSError("ESP_ERR_ESPNOW_NOT_FOUND")
        if isinstance(msg, str):
            msg = msg.encode()
        msg = bytes(msg)
        if len(msg) > MAX_DATA_LEN:
            raise ValueError("ESP_ERR_ESPNOW_ARG: %d bytes > %d" % (len(msg), MAX_DATA_LEN))
        delivered = sim_state.radio_send(mac, msg)
        if mac == BROADCAST or not sync:
            return True
        return delivered > 0

    def any(self):
        return bool(sim_state.enow_inbox)

    def _take(self):
        mac, msg = sim_state.enow_inbox.pop(0)
        if mac in self.peers_table:
            self.peers_table[mac] = [SIM_RSSI, time.ticks_ms()]
        return mac, msg

    async def irecv(self, timeout_ms=None):
        self._check_active()
        if sim_state.enow_inbox:
            return self._take()
        if timeout_ms == 0:
            return None, None
        wait = 300000 if timeout_ms is None or timeout_ms < 0 else timeout_ms
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < wait:
            await time.sleep_ms(1)
            if sim_state.enow_inbox:
                return self._take()
        return None, None

    async def recv(self, timeout_ms=None):
        mac, msg = await self.irecv(timeout_ms)
        return [mac, msg]

    def irq(self, callback):
        self._irq = callback

    def config(self, *args, **kwargs):
        return None

    def stats(self):
        return (0, 0, 0, 0, 0)
