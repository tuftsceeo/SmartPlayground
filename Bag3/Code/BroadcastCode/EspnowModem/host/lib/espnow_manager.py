"""
espnow_manager.py -- ESP-NOW via an external UART modem (EUM)
==============================================================
Drop-in for Bag3/Code/BroadcastCode/MockWand/lib/espnow_manager.py: same
module-level names and ESPNowManager methods, but the radio lives on a
separate ESP32 running EspnowModem/modem/main.py. This module imports
neither `network` nor `espnow`.

Tracks: MockWand (Bag3) espnow_manager.py. Message classification runs on
the modem (modem/lib/eum_classify.py); this side decodes payloads only.

Differences from the built-in manager:
- get_own_mac() returns the modem's MAC (the address peers see).
- send_raw()/send_score() send broadcasts async; the built-in sends them
  sync and gets ETIMEDOUT.
- Failures to reach the modem raise OSError from init().

Usage:
    from espnow_manager import ESPNowManager

    mgr = ESPNowManager()
    mgr.init()
    mgr.broadcast(["turnred", "turnblue"])
    msg_type, data, mac = mgr.poll()
"""

import json
import time
from machine import UART

import eum_proto as P


BROADCAST_MAC = b'\xFF\xFF\xFF\xFF\xFF\xFF'

UART_ID = 1
UART_TX = 43
UART_RX = 44
UART_BAUD = 921600
UART_RXBUF = 1536            # holds one full FETCH(4) reply (~1050 B)

HELLO_WAIT_MS = 2000         # covers a modem that is still booting
REPLY_TIMEOUT_MS = 100
SEND_SYNC_TIMEOUT_MS = 300   # unicast waits for the ESP-NOW ACK on the modem
FETCH_INTERVAL_MS = 5
STATUS_PUSH_MS = 30000
LINK_DOWN_AFTER = 3          # consecutive timeouts before the link is down
RECONNECT_EVERY_MS = 1000
RECONNECT_TIMEOUT_MS = 50


def mac_str_to_bytes(mac_str):
    parts = mac_str.split(':')
    return bytes([int(p, 16) for p in parts])


def mac_bytes_to_str(mac_bytes):
    return ':'.join('%02X' % b for b in mac_bytes)


class _Link:
    """UART request/reply transport to the modem. One request in flight.

    After LINK_DOWN_AFTER consecutive timeouts the link is marked down:
    requests then fail immediately, except for one HELLO attempt every
    RECONNECT_EVERY_MS. A successful HELLO marks the link up and sets
    boot_changed so the manager restores modem state.
    """

    def __init__(self):
        self.uart = UART(UART_ID, baudrate=UART_BAUD, tx=UART_TX, rx=UART_RX,
                         rxbuf=UART_RXBUF)
        self.parser = P.FrameParser()
        self.tx = bytearray(P.MAX_FRAME)
        self.tx_mv = memoryview(self.tx)
        self.hello_tx = bytearray(P.HDR_LEN + 1)   # keeps tx payload intact
        self.hello_mv = memoryview(self.hello_tx)
        self.rbuf = bytearray(256)
        self.rbuf_mv = memoryview(self.rbuf)
        self.seq = 0
        self.want_type = 0
        self.want_seq = 0
        self.got_len = -1
        self.got_error = False
        self.boot_id = None
        self.boot_changed = False
        self.rx_overflow = 0
        self.pending = 0
        self.modem_mac = None
        self.down = False
        self.consecutive_timeouts = 0
        self.next_reconnect = 0
        self.timeouts = 0
        self.stale_frames = 0
        self.modem_errors = 0
        self.link_down_events = 0
        self.reconnects = 0
        self.resets_seen = 0

    def _on_frame(self, ftype, seq, plen):
        if seq != self.want_seq or plen < P.REPLY_HDR_LEN:
            self.stale_frames += 1
            return
        if ftype == self.want_type:
            self.got_error = False
        elif ftype == P.T_ERROR | P.REPLY_FLAG:
            self.got_error = True
        else:
            self.stale_frames += 1
            return
        self.got_len = plen

    def _flush_input(self):
        while self.uart.any():
            n = self.uart.readinto(self.rbuf)
            if not n:
                break
            self.parser.feed(self.rbuf_mv, n, self._on_frame)
        self.parser.reset()

    def _exchange(self, buf, mv, ftype, plen, timeout_ms):
        self.seq = (self.seq + 1) & 0xFF
        self.want_type = ftype | P.REPLY_FLAG
        self.want_seq = self.seq
        self.got_len = -1
        self._flush_input()
        n = P.build_frame(buf, ftype, self.seq, plen)
        self.uart.write(mv[:n])
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while True:
            if self.uart.any():
                r = self.uart.readinto(self.rbuf)
                if r:
                    self.parser.feed(self.rbuf_mv, r, self._on_frame)
                if self.got_len >= 0:
                    return True
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                return False
            time.sleep_ms(1)

    def _read_header(self):
        b = self.parser.buf
        boot_id = b[0]
        if self.boot_id is not None and boot_id != self.boot_id:
            self.boot_changed = True
            self.resets_seen += 1
        self.boot_id = boot_id
        overflow = P.get_u16(b, 1)
        if overflow != self.rx_overflow:
            if overflow > self.rx_overflow:
                print("EUM: %d messages dropped (modem ring full)"
                      % (overflow - self.rx_overflow))
            self.rx_overflow = overflow
        self.pending = b[3]

    def _body(self):
        return self.parser.mv[P.REPLY_HDR_LEN:self.got_len]

    def _timed_out(self):
        self.timeouts += 1
        self.consecutive_timeouts += 1
        if not self.down and self.consecutive_timeouts >= LINK_DOWN_AFTER:
            self.down = True
            self.link_down_events += 1
            self.next_reconnect = time.ticks_add(time.ticks_ms(),
                                                 RECONNECT_EVERY_MS)
            print("EUM: link down after %d timeouts; requests fail until "
                  "the modem answers" % self.consecutive_timeouts)

    def _hello_once(self, timeout_ms):
        """One HELLO exchange. Returns the reply body or None."""
        if not self._exchange(self.hello_tx, self.hello_mv, P.T_HELLO, 0,
                              timeout_ms):
            return None
        if self.got_error:
            return None
        self._read_header()
        body = self._body()
        if body[0] != P.PROTO_VERSION:
            raise OSError("EUM: modem protocol %d, host expects %d"
                          % (body[0], P.PROTO_VERSION))
        self.modem_mac = bytes(body[1:7])
        return body

    def _try_reconnect(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.next_reconnect) < 0:
            return False
        self.next_reconnect = time.ticks_add(now, RECONNECT_EVERY_MS)
        if self._hello_once(RECONNECT_TIMEOUT_MS) is None:
            return False
        self.down = False
        self.consecutive_timeouts = 0
        self.reconnects += 1
        self.boot_changed = True      # modem state is unknown; restore it
        print("EUM: link restored")
        return True

    def request(self, ftype, plen=0, timeout_ms=REPLY_TIMEOUT_MS, retry=True):
        """Send tx[HDR_LEN:HDR_LEN+plen] as ftype and wait for the reply.

        Returns a memoryview of the reply body (after the common header),
        valid until the next request, or None on timeout, link down, or a
        modem internal error (printed). retry resends once on timeout; only
        safe for idempotent requests.
        """
        if self.down and not self._try_reconnect():
            return None
        ok = self._exchange(self.tx, self.tx_mv, ftype, plen, timeout_ms)
        if not ok and retry:
            ok = self._exchange(self.tx, self.tx_mv, ftype, plen, timeout_ms)
        if not ok:
            self._timed_out()
            return None
        self.consecutive_timeouts = 0
        self._read_header()
        body = self._body()
        if self.got_error:
            self.modem_errors += 1
            print("EUM: modem internal error on request 0x%02X (err %d): %s"
                  % (body[0], P.get_i16(body, 1),
                     bytes(body[3:]).decode("utf-8", "replace")))
            return None
        return body

    def payload(self):
        """Writable view of the outgoing payload area."""
        return self.tx_mv[P.HDR_LEN:]

    def hello(self):
        deadline = time.ticks_add(time.ticks_ms(), HELLO_WAIT_MS)
        while self._hello_once(REPLY_TIMEOUT_MS) is None:
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                raise OSError("EUM: no modem on UART%d (tx=%d rx=%d)"
                              % (UART_ID, UART_TX, UART_RX))
        self.down = False
        self.consecutive_timeouts = 0
        self.boot_changed = False
        return self.modem_mac


_link = None


def _get_link():
    global _link
    if _link is None:
        _link = _Link()
    if _link.modem_mac is None:
        _link.hello()
    return _link


def get_own_mac():
    """MAC of the modem's radio, as 'AA:BB:CC:DD:EE:FF'."""
    return mac_bytes_to_str(_get_link().modem_mac)


class ESPNowManager:
    def __init__(self):
        self.enow = None          # kept for code that clears it (code_puller)
        self._link = None
        self._active = False
        self._peers = {}          # mac_str -> mac_bytes
        self._status_provider = None
        self._status_pushed_ms = None
        self._rx = []             # local batch: (code, mac_bytes, rssi, bytes)
        self._rssi = {}           # mac_str -> last rssi seen in a record

    # ─── INIT / SHUTDOWN ──────────────────────

    def init(self):
        if self._active:
            return
        self._link = _get_link()
        self._simple(P.T_ACTIVATE, 0, "activate", raise_on_fail=True)
        self._active = True
        for mac_bytes in self._peers.values():
            self._peer_op(P.T_ADD_PEER, mac_bytes)
        self._push_status()
        print("  ESPNow(EUM): active (MAC: %s)" % get_own_mac())

    def shutdown(self):
        """Tell peers to stop, then deactivate the modem's RX queue and peers.

        The modem keeps its radio up; there is no host radio to release.
        """
        if not self._active:
            return
        try:
            self.send_stop_all_peers()
        except OSError as e:
            print("  ESPNow(EUM): stop-all on shutdown failed: %s" % str(e))
        self._simple(P.T_DEACTIVATE, 0, "deactivate")
        self._active = False
        self._peers.clear()
        self._rx = []
        self._status_pushed_ms = None

    @property
    def is_active(self):
        return self._active

    def _simple(self, ftype, plen, what, raise_on_fail=False):
        """Request with a status reply. Returns True on ST_OK."""
        body = self._link.request(ftype, plen)
        if body is None:
            msg = "EUM: %s: modem request failed" % what
            if raise_on_fail:
                raise OSError(msg)
            print("  " + msg)
            return False
        if body[0] != P.ST_OK:
            msg = "EUM: %s failed (err %d)" % (what, P.get_i16(body, 1))
            if raise_on_fail:
                raise OSError(msg)
            print("  " + msg)
            return False
        self._check_reboot()
        return True

    def _check_reboot(self):
        """Restore modem state after a modem reset (boot_id changed)."""
        link = self._link
        if not link.boot_changed:
            return
        link.boot_changed = False
        print("  EUM: modem reset or reconnect; restoring state")
        self._report_last_error()
        if not self._active:
            return
        self._link.request(P.T_ACTIVATE, 0)
        for mac_bytes in self._peers.values():
            self._peer_op(P.T_ADD_PEER, mac_bytes)
        self._status_pushed_ms = None
        self._push_status()

    def _report_last_error(self):
        """Print the modem's reset cause and its previous boot's fault."""
        body = self._link.request(P.T_LAST_ERROR, 0)
        if body is None:
            return
        cause = body[0]
        text = bytes(body[1:]).decode("utf-8", "replace")
        print("  EUM: modem reset_cause %d" % cause)
        if text:
            print("  EUM: modem fault before reset:\n" + text)

    # ─── PEER MANAGEMENT ─────────────────────

    def _peer_op(self, ftype, mac_bytes):
        self._link.payload()[0:6] = mac_bytes
        return self._simple(ftype, 6, "peer op %s" % mac_bytes_to_str(mac_bytes))

    def add_peer(self, mac_str):
        if not self._active:
            self.init()
        mac_bytes = mac_str_to_bytes(mac_str)
        if mac_str not in self._peers:
            self._peer_op(P.T_ADD_PEER, mac_bytes)
            self._peers[mac_str] = mac_bytes
            print("  ESPNow: added peer %s" % mac_str)

    def remove_peer(self, mac_str):
        if mac_str in self._peers:
            if self._active:
                self._peer_op(P.T_DEL_PEER, self._peers[mac_str])
            del self._peers[mac_str]

    def clear_peers(self):
        for ms in list(self._peers.keys()):
            self.remove_peer(ms)

    def has_peers(self):
        return len(self._peers) > 0

    def get_peer_macs(self):
        return list(self._peers.keys())

    # ─── STATUS AUTO-REPLY ───────────────────

    def set_status_provider(self, fn):
        """Register fn() -> battery SOC int or None. Wands only.

        The modem answers status_poll itself using the last pushed value.
        """
        self._status_provider = fn
        self._status_pushed_ms = None
        if self._active:
            self._push_status()

    def _read_battery(self):
        if not self._status_provider:
            return None
        try:
            batt = self._status_provider()
            if batt is None:
                return None
            return int(batt)
        except (TypeError, ValueError):
            return None

    def _push_status(self):
        if not self._active:
            return
        batt = self._read_battery()
        if batt is None:
            batt = P.BATTERY_NONE
        batt = max(-1, min(127, batt))
        pl = self._link.payload()
        pl[0] = batt & 0xFF
        pl[1] = 1 if self._status_provider else 0
        self._simple(P.T_SET_STATUS, 2, "set status")
        self._status_pushed_ms = time.ticks_ms()

    def _maybe_push_status(self):
        if not self._status_provider:
            return
        if (self._status_pushed_ms is None or
                time.ticks_diff(time.ticks_ms(), self._status_pushed_ms)
                >= STATUS_PUSH_MS):
            self._push_status()

    def get_rssi(self, mac_str):
        rssi = self._rssi.get(mac_str)
        if rssi is not None:
            return rssi
        if not self._active:
            return None
        try:
            mac_bytes = self._peers.get(mac_str) or mac_str_to_bytes(mac_str)
        except (ValueError, AttributeError):
            return None
        self._link.payload()[0:6] = mac_bytes
        body = self._link.request(P.T_GET_RSSI, 6)
        if body is None:
            return None
        rssi = body[0]
        self._check_reboot()
        if rssi == P.RSSI_UNKNOWN:
            return None
        return P.to_i8(rssi)

    # ─── SENDING ──────────────────────────────

    def _send(self, mac_bytes, msg, what):
        if not self._active:
            return False
        if isinstance(msg, str):
            msg = msg.encode()
        n = len(msg)
        if n > P.ESPNOW_MAX_DATA:
            print("  ESPNow: %s err: %d bytes > %d" % (what, n, P.ESPNOW_MAX_DATA))
            return False
        sync = mac_bytes != BROADCAST_MAC
        pl = self._link.payload()
        pl[0:6] = mac_bytes
        pl[6] = P.SEND_FLAG_SYNC if sync else 0
        pl[7:7 + n] = msg
        # No retry: the modem may already have sent it.
        body = self._link.request(
            P.T_SEND, 7 + n,
            SEND_SYNC_TIMEOUT_MS if sync else REPLY_TIMEOUT_MS, retry=False)
        if body is None:
            print("  ESPNow: %s err: modem request failed" % what)
            return False
        ok = body[0] == P.ST_OK
        if not ok:
            print("  ESPNow: %s err: %d" % (what, P.get_i16(body, 1)))
        self._check_reboot()
        return ok

    def broadcast(self, data):
        msg = json.dumps(data) if not isinstance(data, (str, bytes)) else data
        return self._send(BROADCAST_MAC, msg, "broadcast")

    def send_to(self, mac_str, data):
        mac_bytes = self._peers.get(mac_str)
        if mac_bytes is None:
            mac_bytes = mac_str_to_bytes(mac_str)
        msg = json.dumps(data) if not isinstance(data, (str, bytes)) else data
        return self._send(mac_bytes, msg, "send to %s" % mac_str)

    def send_raw(self, mac_bytes, raw_bytes):
        return self._send(bytes(mac_bytes), raw_bytes, "raw send")

    # ─── CONVENIENCE SENDERS ──────────────────

    def send_splat_config(self, mac_str, action_chain):
        return self.send_to(mac_str, {
            "type": "splat_config",
            "actions": action_chain,
        })

    def send_scan_request(self):
        """Broadcast a request for the Programming Station to scan its tags
        and unicast the result back to this device."""
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
        """Targeted identify ping; only the wand whose MAC matches reacts."""
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
        return self._send(bytes(mac_bytes), msg, "score send")

    # ─── RECEIVING ────────────────────────────

    def _fetch(self):
        """Pull up to FETCH_MAX records from the modem into self._rx."""
        self._link.payload()[0] = P.FETCH_MAX
        # No retry: a lost reply's records were already dequeued on the modem.
        body = self._link.request(P.T_FETCH, 1, retry=False)
        if body is None:
            if not self._link.down:
                print("  ESPNow(EUM): fetch failed (any records in it are lost)")
            return
        count = body[0]
        o = 1
        for _ in range(count):
            mac = bytes(body[o:o + 6])
            rssi = body[o + 6]
            code = body[o + 7]
            n = body[o + 8]
            s = o + P.REC_HDR_LEN
            self._rx.append((code, mac, rssi, bytes(body[s:s + n])))
            o = s + n
        self._check_reboot()

    def _decode(self, code, mac, rssi, msg):
        mac_str = mac_bytes_to_str(mac)
        if rssi != P.RSSI_UNKNOWN:
            self._rssi[mac_str] = P.to_i8(rssi)
        if code == P.C_RAW_BYTES:
            return "raw", msg, mac_str
        data = json.loads(msg)
        if code == P.C_FIND_DEVICE:
            return "start_game", {"name": "finddevice",
                                  "mac": data.get("mac")}, mac_str
        name = P.CODE_NAMES.get(code)
        if name is None:
            return "raw", data, mac_str
        return name, data, mac_str

    def poll(self, timeout_ms=0):
        """
        Receive one message. Returns (msg_type, data, mac_str) or
        (None, None, None). Blocks up to timeout_ms when nothing is queued.

        msg_type: "colors", "score", "splat_config", "stop",
                  "battery", "scan_request", "start_game", "status_poll",
                  "status_report", "raw", or None
        """
        if not self._active:
            return None, None, None
        self._maybe_push_status()
        if not self._rx:
            self._fetch()
        if not self._rx and timeout_ms > 0:
            deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
            next_fetch = time.ticks_add(time.ticks_ms(), FETCH_INTERVAL_MS)
            while not self._rx:
                now = time.ticks_ms()
                if time.ticks_diff(deadline, now) <= 0:
                    break
                if time.ticks_diff(now, next_fetch) >= 0:
                    self._fetch()
                    next_fetch = time.ticks_add(now, FETCH_INTERVAL_MS)
                time.sleep_ms(1)
        if not self._rx:
            return None, None, None
        return self._decode(*self._rx.pop(0))

    def recv_blocking(self, timeout_ms=1000):
        return self.poll(timeout_ms)

    def drain(self):
        if not self._active:
            return
        self._rx = []
        self._link.request(P.T_FLUSH, 0)

    # ─── DIAGNOSTICS ──────────────────────────

    def link_stats(self):
        """Modem and host link counters as a dict (None if no reply)."""
        link = self._link or _get_link()
        body = link.request(P.T_STATS, 0)
        if body is None:
            return None
        names = ("rx", "tx", "tx_fail", "rx_overflow", "crc_err",
                 "dup_drop", "len_err", "faults")
        stats = {}
        for i, name in enumerate(names):
            stats["modem_" + name] = P.get_u16(body, 2 * i)
        stats["host_crc_err"] = link.parser.crc_errors
        stats["host_len_err"] = link.parser.len_errors
        stats["host_timeouts"] = link.timeouts
        stats["host_stale_frames"] = link.stale_frames
        stats["host_modem_errors"] = link.modem_errors
        stats["host_link_down_events"] = link.link_down_events
        stats["host_reconnects"] = link.reconnects
        stats["host_resets_seen"] = link.resets_seen
        stats["modem_pending"] = link.pending
        return stats
