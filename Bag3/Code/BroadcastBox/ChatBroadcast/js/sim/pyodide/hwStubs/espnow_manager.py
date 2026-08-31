"""Browser stub for ESP-NOW manager — message queue fed by sim buttons."""

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

    def get_rssi(self, mac_str):
        return -50

    def broadcast(self, data):
        pass

    def send_to(self, mac_str, data):
        pass

    def send_raw(self, mac_bytes, raw_bytes):
        pass

    def send_splat_config(self, *args, **kwargs):
        pass

    def send_scan_request(self):
        pass

    def send_stop_to(self, mac_str):
        pass

    def send_stop_all_peers(self):
        pass

    def broadcast_stop(self):
        pass

    def send_start_game(self, mac_str, name):
        pass

    def broadcast_start_game(self, name):
        pass

    def broadcast_find_device(self, mac_str):
        pass

    def broadcast_status_poll(self):
        pass

    def broadcast_status_report(self, *args, **kwargs):
        pass

    def send_score(self, mac_bytes, colors, elapsed_ms):
        pass

    def poll(self, timeout_ms=0):
        from sim_bootstrap import input_state
        queue = input_state.get("espnow_queue") or []
        if queue:
            msg = queue.pop(0)
            input_state["espnow_queue"] = queue
            return msg
        return None, None, None

    def recv_blocking(self, timeout_ms):
        return self.poll(timeout_ms)

    def drain(self):
        from sim_bootstrap import input_state
        input_state["espnow_queue"] = []
