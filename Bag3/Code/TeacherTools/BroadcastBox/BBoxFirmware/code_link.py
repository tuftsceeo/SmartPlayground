# PEER: Bag3/Code/TeacherTools/BroadcastDial/BDialFirmware/code_link.py -- keep in sync.
"""
code_link.py -- serve game files to wands over the Dial's own ESP-NOW radio.

CodeLink has the slice of the old CodeServer interface bdial_server uses
(armed, serving_count, set_game, resolve, arm, disarm, poll). The transfer
protocol is code_sender.CodeSender; NativeManager is the radio under it.

Memory order: prewarm() runs right after M5.begin(), before the UI and NFC
reader allocate, so the WiFi driver's first allocation lands on a clean heap
(docs_and_design/2026-09-23-ap-memory-order.md). code_sender is imported in
arm(), after the radio is up.
"""

import gc
import json
import time
import machine
from binascii import hexlify

# Last four hex digits of the base MAC. Shown on the SERVE screen and
# appended to getcode cards as "@<id>".
HOST_ID = hexlify(machine.unique_id()[-2:]).decode()

GAMES_DIR = "/flash/games"
ACTIVE_PATH = "/flash/active.txt"

BROADCAST_MAC = b"\xff\xff\xff\xff\xff\xff"
SEND_RETRY_MS = 30
# Inbound traffic is code_req/code_get only (under 100 B each). The rx buffer
# comes out of internal DRAM, which the UI also draws on.
ESPNOW_RXBUF = 1024


def mac_bytes_to_str(mac_bytes):
    return ":".join("%02X" % b for b in mac_bytes)


class NativeManager:
    """add_peer/remove_peer/send_to/send_raw/poll/broadcast over `espnow`."""

    def __init__(self, tx_power=None):
        self.tx_power = tx_power     # dBm; None leaves the driver default
        self.enow = None
        self.sta = None
        self._active = False
        self._peers = {}

    @property
    def is_active(self):
        return self._active

    def init(self):
        if self._active:
            return
        import network
        import espnow
        self.sta = network.WLAN(network.STA_IF)
        self.sta.active(True)
        self.sta.disconnect()
        if self.tx_power is not None:
            try:
                self.sta.config(txpower=self.tx_power)
            except Exception as e:
                print("# code_link txpower: %s" % str(e))
        self.enow = espnow.ESPNow()
        try:
            self.enow.config(rxbuf=ESPNOW_RXBUF)
        except Exception:
            pass
        self.enow.active(True)
        try:
            self.enow.add_peer(BROADCAST_MAC)
        except Exception:
            pass
        self._active = True

    def shutdown(self):
        """ESP-NOW and the STA interface both off: no radio while the NFC
        field may be up."""
        if self.enow is not None:
            try:
                self.enow.active(False)
            except Exception:
                pass
        if self.sta is not None:
            try:
                self.sta.active(False)
            except Exception:
                pass
        self.enow = None
        self.sta = None
        self._active = False
        self._peers.clear()

    def add_peer(self, mac_str):
        if mac_str not in self._peers:
            mac = bytes([int(p, 16) for p in mac_str.split(":")])
            try:
                self.enow.add_peer(mac)
            except Exception:
                pass
            self._peers[mac_str] = mac

    def remove_peer(self, mac_str):
        mac = self._peers.pop(mac_str, None)
        if mac is not None:
            try:
                self.enow.del_peer(mac)
            except Exception:
                pass

    def broadcast(self, data):
        if not self._active:
            return False
        msg = data if isinstance(data, (str, bytes)) else json.dumps(data)
        for _ in range(2):
            try:
                self.enow.send(BROADCAST_MAC, msg, False)
                return True
            except OSError:
                time.sleep_ms(SEND_RETRY_MS)
            except Exception:
                return False
        return False

    def send_to(self, mac_str, data):
        if not self._active:
            return False
        mac = self._peers.get(mac_str)
        if mac is None:
            mac = bytes([int(p, 16) for p in mac_str.split(":")])
        msg = data if isinstance(data, (str, bytes)) else json.dumps(data)
        return self._send(mac, msg)

    def send_raw(self, mac_bytes, raw_bytes):
        if not self._active:
            return False
        return self._send(mac_bytes, raw_bytes)

    def _send(self, mac, msg):
        try:
            return bool(self.enow.send(mac, msg))
        except OSError as e:
            print("# code_link send failed: %s" % str(e))
            return False
        except Exception:
            return False

    def poll(self):
        """("raw", decoded, mac_str) or (None, None, None)."""
        if not self._active:
            return None, None, None
        try:
            mac, msg = self.enow.irecv(0)
        except Exception:
            return None, None, None
        if msg is None:
            return None, None, None
        mac_str = mac_bytes_to_str(mac) if mac else None
        try:
            return "raw", json.loads(msg), mac_str
        except (ValueError, UnicodeError):
            return "raw", bytes(msg), mac_str


def prewarm():
    """Bring the radio up and down once, before the UI is built."""
    m = NativeManager()
    m.init()
    m.shutdown()
    gc.collect()


class CodeLink:
    def __init__(self, tx_power=None):
        self.mgr = NativeManager(tx_power)
        self.sender = None
        self.active_slug = None
        self._armed = False
        self._failed_seen = 0
        self._sessions_seen = 0
        self.last_result = None

    @property
    def armed(self):
        return self._armed

    @property
    def serving_count(self):
        return len(self.sender.sessions) if self.sender is not None else 0

    def set_game(self, slug):
        self.active_slug = slug or None

    def _exists(self, slug):
        import os
        try:
            return os.stat(GAMES_DIR + "/" + slug + ".py")[6] > 0
        except OSError:
            return False

    def resolve(self, slug=None):
        """slug, else /flash/active.txt, if its file is on flash. Sets the
        active slug and returns it, or None."""
        if not slug:
            try:
                with open(ACTIVE_PATH) as f:
                    slug = f.read().strip()
            except OSError:
                slug = ""
        if not slug or not self._exists(slug):
            return None
        self.active_slug = slug
        return slug

    def arm(self):
        if self._armed:
            return True
        if not (self.active_slug and self._exists(self.active_slug)):
            if self.resolve() is None:
                return False
        gc.collect()
        try:
            self.mgr.init()
        except OSError as e:
            print("# CodeLink.arm: radio start failed: %s" % str(e))
            self.mgr.shutdown()
            return False
        if self.sender is None:
            from code_sender import CodeSender
            self.sender = CodeSender(self.mgr, games_dir=GAMES_DIR,
                                     host_id=HOST_ID)
        self.sender.mgr = self.mgr
        self._failed_seen = self.sender.failed
        self._sessions_seen = 0
        self._armed = True
        return True

    def disarm(self):
        if self.sender is not None:
            for s in self.sender.sessions.values():
                s.close()
            self.sender.sessions.clear()
            self.sender.last_result = None
        self.mgr.shutdown()
        self._armed = False
        gc.collect()

    def poll(self, on_event=None, should_abort=None):
        """Handle at most one radio message. on_event('serving') per offered
        wand, 'ok'/'fail' per finished one; finished transfers also set
        last_result. Returns 'abort' when should_abort() is true."""
        if not self._armed:
            return None
        if should_abort is not None and should_abort():
            self.disarm()
            return 'abort'
        mt, data, mac = self.mgr.poll()
        if mt is not None:
            self.sender.handle(mt, data, mac)
        else:
            self.sender._expire()
        n = len(self.sender.sessions)
        if n > self._sessions_seen:
            _emit(on_event, 'serving')
        self._sessions_seen = n
        # sender.failed counts failed code_done replies and idle sessions
        # dropped by _expire(); only the first kind sets last_result.
        expired = self.sender.failed - self._failed_seen
        self._failed_seen = self.sender.failed
        r = self.sender.last_result
        if r is not None:
            self.sender.last_result = None
            if not r["ok"]:
                expired -= 1
            self._finished(r, on_event)
        for _ in range(expired):
            self._finished({"mac": None, "path": None, "ok": False,
                            "why": "idle", "ms": None}, on_event)
        return None

    def _finished(self, r, on_event):
        self.last_result = r
        if r["path"]:
            _record(r.get("slug") or r["path"].rsplit("/", 1)[-1][:-3], r["ok"])
        _emit(on_event, 'ok' if r["ok"] else 'fail')


def _record(slug, ok):
    try:
        import stats_log
        stats_log.record_pull(slug, ok)
    except Exception as e:
        print("# stats pull failed: %s" % str(e))


def _emit(cb, event):
    if cb is None:
        return
    try:
        cb(event)
    except Exception as e:
        print("# code_link on_event(%s) err: %s" % (event, str(e)))
