"""
espnow_manager.py — Unified ESP-NOW communication for all devices
==================================================================
Goes in /lib/. Handles init, sending, receiving, peer management,
and broadcast message routing.

Usage:
    from espnow_manager import ESPNowManager

    mgr = ESPNowManager()
    mgr.init()
    mgr.broadcast(["turnred", "turnblue"])
    msg_type, data, mac = mgr.poll()
"""

import network
import espnow
import json


BROADCAST_MAC = b'\xFF\xFF\xFF\xFF\xFF\xFF'


def mac_str_to_bytes(mac_str):
    parts = mac_str.split(':')
    return bytes([int(p, 16) for p in parts])


def mac_bytes_to_str(mac_bytes):
    return ':'.join('%02X' % b for b in mac_bytes)


def get_own_mac():
    sta = network.WLAN(network.STA_IF)
    was = sta.active()
    if not was:
        sta.active(True)
    mac = ':'.join('%02X' % b for b in sta.config('mac'))
    if not was:
        sta.active(False)
    return mac


class ESPNowManager:
    def __init__(self):
        self.enow = None
        self._active = False
        self._peers = {}  # mac_str -> mac_bytes

    # ─── INIT / SHUTDOWN ──────────────────────

    def init(self):
        if self._active:
            return
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        sta.disconnect()
        self.enow = espnow.ESPNow()
        self.enow.active(True)
        try:
            self.enow.add_peer(BROADCAST_MAC)
        except Exception:
            pass
        self._active = True
        print("  ESPNow: active (MAC: %s)" % get_own_mac())

    def shutdown(self):
        if not self._active:
            return
        self.send_stop_all_peers()
        try:
            self.enow.active(False)
        except Exception:
            pass
        self._active = False
        self._peers.clear()

    @property
    def is_active(self):
        return self._active

    # ─── PEER MANAGEMENT ─────────────────────

    def add_peer(self, mac_str):
        if not self._active:
            self.init()
        mac_bytes = mac_str_to_bytes(mac_str)
        if mac_str not in self._peers:
            try:
                self.enow.add_peer(mac_bytes)
            except Exception:
                pass
            self._peers[mac_str] = mac_bytes
            print("  ESPNow: added peer %s" % mac_str)

    def remove_peer(self, mac_str):
        if mac_str in self._peers:
            try:
                self.enow.del_peer(self._peers[mac_str])
            except Exception:
                pass
            del self._peers[mac_str]

    def clear_peers(self):
        for ms in list(self._peers.keys()):
            self.remove_peer(ms)

    def has_peers(self):
        return len(self._peers) > 0

    def get_peer_macs(self):
        return list(self._peers.keys())

    # ─── SENDING ──────────────────────────────

    def broadcast(self, data):
        if not self._active:
            return False
        msg = json.dumps(data) if not isinstance(data, (str, bytes)) else data
        try:
            self.enow.send(BROADCAST_MAC, msg)
            return True
        except Exception as e:
            print("  ESPNow: broadcast err: %s" % str(e))
            return False

    def send_to(self, mac_str, data):
        if not self._active:
            return False
        mac_bytes = self._peers.get(mac_str)
        if mac_bytes is None:
            mac_bytes = mac_str_to_bytes(mac_str)
        msg = json.dumps(data) if not isinstance(data, (str, bytes)) else data
        try:
            self.enow.send(mac_bytes, msg)
            return True
        except Exception as e:
            print("  ESPNow: send err to %s: %s" % (mac_str, str(e)))
            return False

    def send_raw(self, mac_bytes, raw_bytes):
        if not self._active:
            return False
        try:
            self.enow.send(mac_bytes, raw_bytes)
            return True
        except Exception as e:
            print("  ESPNow: raw send err: %s" % str(e))
            return False

    # ─── CONVENIENCE SENDERS ──────────────────

    def send_splat_config(self, mac_str, action_chain):
        return self.send_to(mac_str, {
            "type": "splat_config",
            "actions": action_chain,
        })

    def send_stop_to(self, mac_str):
        return self.send_to(mac_str, {"type": "stop"})

    def send_stop_all_peers(self):
        for ms in list(self._peers.keys()):
            self.send_stop_to(ms)

    def broadcast_stop(self):
        return self.broadcast(["stop"])

    def send_score(self, mac_bytes, colors, elapsed_ms):
        msg = json.dumps({
            "type": "score",
            "colors": colors,
            "time_ms": elapsed_ms,
            "time_s": round(elapsed_ms / 1000, 2),
        })
        if not self._active:
            return False
        try:
            self.enow.send(mac_bytes, msg)
            return True
        except Exception as e:
            print("  ESPNow: score send err: %s" % str(e))
            return False

    # ─── RECEIVING ────────────────────────────

    def poll(self, timeout_ms=0):
        """
        Non-blocking receive.
        Returns (msg_type, data, mac_str) or (None, None, None).

        msg_type: "colors", "score", "splat_config", "stop",
                  "battery", "raw", or None
        """
        if not self._active:
            return None, None, None
        try:
            mac, msg = self.enow.irecv(timeout_ms)
        except Exception:
            return None, None, None
        if msg is None:
            return None, None, None

        mac_str = mac_bytes_to_str(mac) if mac else None

        try:
            data = json.loads(msg)
        except (ValueError, UnicodeError):
            return "raw", bytes(msg), mac_str

        if isinstance(data, list):
            if "stop" in data:
                return "stop", data, mac_str
            if "battery" in data:
                return "battery", data, mac_str
            return "colors", data, mac_str

        if isinstance(data, dict):
            mt = data.get("type")
            if mt == "stop":
                return "stop", data, mac_str
            if mt == "splat_config":
                return "splat_config", data, mac_str
            if mt == "score":
                return "score", data, mac_str
            return "raw", data, mac_str

        return "raw", data, mac_str

    def recv_blocking(self, timeout_ms=1000):
        return self.poll(timeout_ms)

    def drain(self):
        if not self._active:
            return
        while True:
            try:
                mac, msg = self.enow.irecv(0)
                if msg is None:
                    break
            except Exception:
                break