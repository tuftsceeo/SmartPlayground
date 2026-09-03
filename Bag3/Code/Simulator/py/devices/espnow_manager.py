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

    def broadcast(self, data):
        sim_state.emit_log("espnow.broadcast %r" % (data,))

    def send_to(self, mac_str, data):
        sim_state.emit_log("espnow.send_to %s %r" % (mac_str, data))

    def broadcast_stop(self):
        sim_state.emit_log("espnow.broadcast_stop")

    def broadcast_start_game(self, name):
        sim_state.emit_log("espnow.broadcast_start_game %s" % name)

    def send_score(self, *a, **k):
        sim_state.emit_log("espnow.send_score")

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
