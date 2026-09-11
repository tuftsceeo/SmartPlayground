"""Thin ESPNowManager fake — poll() drains sim_state.enow_queue."""

import sim_state

BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"


def mac_str_to_bytes(mac_str):
    return bytes(int(x, 16) for x in mac_str.split(":"))


def mac_bytes_to_str(mac_bytes):
    return ":".join("{:02x}".format(b) for b in mac_bytes)


def get_own_mac():
    return "aa:bb:cc:dd:ee:ff"


class ESPNowManager:
    def __init__(self):
        self._active = False

    def init(self):
        self._active = True

    def shutdown(self):
        self._active = False

    @property
    def is_active(self):
        return self._active

    def poll(self, timeout_ms=0):
        return sim_state.dequeue_enow()

    def recv_blocking(self, timeout_ms):
        return self.poll(timeout_ms)

    def drain(self):
        while True:
            msg = sim_state.dequeue_enow()
            if msg[0] is None:
                break

    # Outgoing traffic goes to emit_enow_sent, not emit_log: with no second
    # wand in the simulator, showing what was transmitted is the only output
    # a send has. `send_raw` is spelled out rather than left to __getattr__
    # because freeze_dance.py drives the whole game through it.
    def send_raw(self, mac_str, data):
        sim_state.emit_enow_sent("raw", data, mac_str)

    def broadcast(self, data):
        sim_state.emit_enow_sent("broadcast", data, BROADCAST_MAC)

    def send_to(self, mac_str, data):
        sim_state.emit_enow_sent("send_to", data, mac_str)

    def broadcast_sys(self, op, **kw):
        sim_state.emit_enow_sent("sys", op, BROADCAST_MAC)

    def broadcast_cap(self, hub, op, args=None):
        sim_state.emit_enow_sent("cap", "%s %s" % (hub, op), BROADCAST_MAC)

    def broadcast_evt(self, ev, data=None, slug=None):
        sim_state.emit_enow_sent("evt", ev, BROADCAST_MAC)

    def stop_all(self):
        self.broadcast_sys("stop")

    def start_all(self, slug):
        self.broadcast_sys("start", slug=slug)

    def find(self, hub):
        return []

    def send_score(self, *a, **k):
        sim_state.emit_enow_sent("score", a[0] if a else None, None)

    def add_peer(self, mac_str):
        pass

    def remove_peer(self, mac_str):
        pass

    def clear_peers(self):
        pass

    def has_peers(self):
        return False

    def get_peer_macs(self):
        return []

    def set_status_provider(self, fn):
        self._status_provider = fn

    def __getattr__(self, name):
        def _noop(*a, **k):
            sim_state.emit_log("espnow.%s (noop)" % name)
            return None

        return _noop
