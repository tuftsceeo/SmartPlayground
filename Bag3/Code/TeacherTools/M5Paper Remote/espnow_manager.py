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
import time
from machine import Pin


BROADCAST_MAC = b'\xFF\xFF\xFF\xFF\xFF\xFF'

N_SLOTS = 16
BASE_DELAY_MS = 400
SLOT_MS = 180
REPORT_GAP_MS = 120
# Pause + single retry when a broadcast hits a momentarily-full ESP-NOW TX
# queue (ESP_ERR_ESPNOW_NO_MEM) on rapid back-to-back sends.
SEND_RETRY_MS = 30


def _is_esp32c6():
    """True only on ESP32-C6 boards with the external-antenna GPIO switch."""
    try:
        import sys
        plat = (sys.platform or '').lower()
        if plat == 'esp32c6' or 'esp32c6' in plat:
            return True
    except Exception:
        pass
    try:
        import os
        machine = (os.uname().machine or '').upper()
        if 'ESP32C6' in machine:
            return True
    except Exception:
        pass
    return False


def _configure_external_antenna():
    """Switch to external antenna before WiFi activation (ESP32-C6 only)."""
    if not _is_esp32c6():
        return
    wifi_en = Pin(3, Pin.OUT)
    ant_cfg = Pin(14, Pin.OUT)
    wifi_en.value(0)
    time.sleep_ms(100)
    ant_cfg.value(1)  # External antenna


def mac_str_to_bytes(mac_str):
    parts = mac_str.split(':')
    return bytes([int(p, 16) for p in parts])


def mac_bytes_to_str(mac_bytes):
    return ':'.join('%02X' % b for b in mac_bytes)


def get_own_mac():
    sta = network.WLAN(network.STA_IF)
    was = sta.active()
    if not was:
        _configure_external_antenna()
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
        self._status_provider = None
        self._pending_report_due = None
        self._pending_report_mac = None
        self._pending_report_second_due = None
        self._own_mac_str = None

    # ─── INIT / SHUTDOWN ──────────────────────

    def init(self):
        if self._active:
            return
        _configure_external_antenna()
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

    def set_status_provider(self, fn):
        """Register fn() -> battery SOC int or None. Wands only."""
        self._status_provider = fn

    def get_rssi(self, mac_str):
        try:
            mb = self._peers.get(mac_str) or mac_str_to_bytes(mac_str)
            return self.enow.peers_table[mb][0]
        except (KeyError, IndexError, TypeError, AttributeError):
            return None

    def _get_own_mac_last_byte(self):
        if self._own_mac_str is None:
            self._own_mac_str = get_own_mac()
        parts = self._own_mac_str.split(':')
        return int(parts[-1], 16)

    def _is_for_me(self, mac_str):
        """True if mac_str (any case, with/without colons) is this device's MAC."""
        if not mac_str:
            return False
        if self._own_mac_str is None:
            self._own_mac_str = get_own_mac()
        return mac_str.replace(":", "").upper() == self._own_mac_str.replace(":", "").upper()

    def _read_battery_for_report(self):
        if not self._status_provider:
            return None
        try:
            batt = self._status_provider()
            if batt is None:
                return None
            return int(batt)
        except (TypeError, ValueError):
            return None

    def _maybe_send_pending_report(self):
        if not self._active or not self._status_provider:
            return
        now = time.ticks_ms()
        if self._pending_report_second_due is not None:
            if time.ticks_diff(now, self._pending_report_second_due) >= 0:
                batt = self._read_battery_for_report()
                rssi = self.get_rssi(self._pending_report_mac)
                self.broadcast_status_report(batt, rssi)
                self._pending_report_second_due = None
                self._pending_report_due = None
                self._pending_report_mac = None
            return
        if self._pending_report_due is None:
            return
        if time.ticks_diff(now, self._pending_report_due) < 0:
            return
        batt = self._read_battery_for_report()
        rssi = self.get_rssi(self._pending_report_mac)
        self.broadcast_status_report(batt, rssi)
        self._pending_report_second_due = time.ticks_add(now, REPORT_GAP_MS)

    def _schedule_status_reply(self, hub_mac_str):
        now = time.ticks_ms()
        slot = self._get_own_mac_last_byte() % N_SLOTS
        due = time.ticks_add(now, BASE_DELAY_MS + slot * SLOT_MS)
        self._pending_report_due = due
        self._pending_report_mac = hub_mac_str
        self._pending_report_second_due = None

    # ─── SENDING ──────────────────────────────

    def broadcast(self, data):
        if not self._active:
            return False
        msg = json.dumps(data) if not isinstance(data, (str, bytes)) else data
        # Broadcasts are never acknowledged, so a SYNCHRONOUS send waits for an
        # ACK that never arrives -> [Errno 116] ETIMEDOUT (even though the frame
        # went out). Send async (sync=False): queue it and return immediately.
        try:
            self.enow.send(BROADCAST_MAC, msg, False)
            return True
        except OSError:
            # TX queue momentarily full (ESP_ERR_ESPNOW_NO_MEM) on rapid
            # back-to-back sends. Brief pause and one retry.
            try:
                time.sleep_ms(SEND_RETRY_MS)
                self.enow.send(BROADCAST_MAC, msg, False)
                return True
            except Exception as e:
                print("  ESPNow: broadcast err: %s" % str(e))
                return False
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

    def send_scan_request(self):
        """Broadcast a request for the Programming Station to scan its tags
        and unicast the result back to this device. Used by Color Quest when
        a player taps the `color_quest_scan` NFC tag on a wand."""
        return self.broadcast({"type": "scan_request"})

    def send_stop_to(self, mac_str):
        return self.send_to(mac_str, {"type": "stop"})

    def send_stop_all_peers(self):
        for ms in list(self._peers.keys()):
            self.send_stop_to(ms)

    def broadcast_stop(self):
        return self.broadcast(["stop"])

    def send_start_game(self, mac_str, name):
        return self.send_to(mac_str, {"type": "start_game", "name": name})

    def broadcast_start_game(self, name):
        return self.broadcast({"type": "start_game", "name": name})

    def broadcast_find_device(self, mac_str):
        """Targeted identify ping. Uses a DISTINCT message type ("find_device")
        so un-updated wands ignore it (they only act on stop/start_game); only
        the wand whose MAC matches reacts. Broadcast (no peer added) -> no
        peer-table overflow with many devices."""
        return self.broadcast({"type": "find_device", "mac": mac_str})

    def broadcast_status_poll(self):
        return self.broadcast({"type": "status_poll"})

    def broadcast_status_report(self, battery, rssi):
        return self.broadcast({
            "type": "status_report",
            "battery": battery,
            "rssi": rssi,
        })

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
                  "battery", "scan_request", "start_game", "status_poll",
                  "status_report", "raw", or None
        """
        if not self._active:
            return None, None, None
        self._maybe_send_pending_report()
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
            if mt == "scan_request":
                return "scan_request", data, mac_str
            if mt == "start_game":
                name = data.get("name")
                if isinstance(name, str) and name:
                    return "start_game", data, mac_str
                return "raw", data, mac_str
            if mt == "find_device":
                # Distinct type (NOT start_game) so un-updated wands -- whose
                # game loops only exit on "stop"/"start_game" -- classify this
                # as "raw" and ignore it. Only the targeted wand reacts; we
                # rewrite it into the start_game force-switch path so the hidden
                # "finddevice" game dispatches with no other firmware changes.
                target = data.get("mac")
                if target is not None and not self._is_for_me(target):
                    return None, None, None   # for another device; ignore
                return "start_game", {"name": "finddevice", "mac": target}, mac_str
            if mt == "status_poll":
                if self._status_provider:
                    self._schedule_status_reply(mac_str)
                    return None, None, None
                return "status_poll", data, mac_str
            if mt == "status_report":
                return "status_report", data, mac_str
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