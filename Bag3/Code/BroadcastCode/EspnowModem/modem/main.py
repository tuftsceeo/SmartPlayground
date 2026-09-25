"""
main.py -- ESP-NOW UART Modem (EUM) firmware, ESP32-S3
=======================================================
Bridges a hardware UART to ESP-NOW. The host drives every exchange
(request -> one reply); the modem never sends unsolicited frames.

Received ESP-NOW messages are classified (eum_classify) and queued in a
preallocated ring; the host pulls them with FETCH. status_poll is answered
here when the host has enabled auto-reply with SET_STATUS.

The radio is brought up before anything else is imported or allocated,
per the memory-order rule in AGENTS.md.
"""

import network
import espnow

ESPNOW_RXBUF = 8192          # driver buffer; default 526 B holds ~2 messages
BROADCAST_MAC = b'\xFF\xFF\xFF\xFF\xFF\xFF'

_sta = network.WLAN(network.STA_IF)
_sta.active(True)
_sta.disconnect()
_enow = espnow.ESPNow()
_enow.config(rxbuf=ESPNOW_RXBUF)
_enow.active(True)
_enow.add_peer(BROADCAST_MAC)

import gc
import json
import io
import os
import sys
import time
import machine
from machine import UART

import eum_proto as P
from eum_classify import classify

UART_ID = 1
UART_TX = 43
UART_RX = 44
UART_BAUD = 921600
UART_RXBUF = 2048

RING_SLOTS = 128
SLOT_LEN = P.REC_HDR_LEN + P.ESPNOW_MAX_DATA + 1   # 260

# 0 disables duplicate suppression. freeze_dance repeats MSG_STOP on purpose.
DEDUP_MS = 0

SEND_RETRY_MS = 30

# Recovery. A fault is any unexpected exception in a request or loop step.
# More than FAULT_LIMIT faults within FAULT_WINDOW_MS resets the chip; the
# host sees the new boot_id and restores its state.
FAULT_LIMIT = 5
FAULT_WINDOW_MS = 10000

# Watchdog: covers hangs that raise nothing (e.g. a send that never returns).
# It is armed only after WDT_ARM_AFTER_MS of uptime AND a first valid host
# request, leaving a window to Ctrl-C into the REPL or run mpremote. An ESP32
# watchdog cannot be disabled once armed: after that, stopping the loop
# resets the chip within WDT_TIMEOUT_MS. The file NO_WDT_PATH disables it.
WDT_TIMEOUT_MS = 5000
WDT_ARM_AFTER_MS = 180000

# UIFlow (M5) boards only allow writes under /flash; plain MicroPython uses /.
FS_ROOT = "/flash" if "flash" in os.listdir("/") else ""
NO_WDT_PATH = FS_ROOT + "/no_wdt"
LAST_ERROR_PATH = FS_ROOT + "/last_error.txt"

# Status auto-reply timing, from MockWand/lib/espnow_manager.py.
N_SLOTS = 16
BASE_DELAY_MS = 400
SLOT_MS = 180
REPORT_GAP_MS = 120


class Modem:
    def __init__(self, sta, enow):
        self.enow = enow
        self.mac = bytes(sta.config('mac'))
        self.mac_hex = ''.join('%02X' % b for b in self.mac)
        self.boot_id = os.urandom(1)[0]

        self.ring = bytearray(RING_SLOTS * SLOT_LEN)
        self.ring_mv = memoryview(self.ring)
        self.head = 0          # next slot to read
        self.count = 0

        self.accepting = True
        self.peers = {}        # mac bytes -> True (excludes broadcast)

        self.auto_status = False
        self.battery = P.BATTERY_NONE
        self.report_due = None
        self.report_second_due = None
        self.report_mac = None

        self.last_mac = bytearray(6)
        self.last_data = bytearray(P.ESPNOW_MAX_DATA)
        self.last_len = -1
        self.last_ms = 0

        self.n_rx = 0
        self.n_tx = 0
        self.n_tx_fail = 0
        self.n_overflow = 0
        self.n_dup = 0
        self.n_fault = 0
        self.host_seen = False
        self.fault_times = []
        self.reset_cause = machine.reset_cause()
        self.prev_error = self._load_last_error()

        self.uart = UART(UART_ID, baudrate=UART_BAUD, tx=UART_TX, rx=UART_RX,
                         rxbuf=UART_RXBUF)
        self.rbuf = bytearray(256)
        self.rbuf_mv = memoryview(self.rbuf)
        self.tx = bytearray(P.MAX_FRAME)
        self.tx_mv = memoryview(self.tx)
        self.parser = P.FrameParser()

    # ─── RX RING ─────────────────────────────

    def _rssi(self, mac):
        entry = self.enow.peers_table.get(mac)
        if entry is None:
            return P.RSSI_UNKNOWN
        return entry[0] & 0xFF

    def _is_dup(self, mac, msg, n, now):
        if DEDUP_MS <= 0 or n != self.last_len:
            return False
        if time.ticks_diff(now, self.last_ms) > DEDUP_MS:
            return False
        return self.last_mac == mac and self.last_data[:n] == msg

    def _remember(self, mac, msg, n, now):
        if DEDUP_MS <= 0:
            return
        self.last_mac[:] = mac
        self.last_data[:n] = msg
        self.last_len = n
        self.last_ms = now

    def _enqueue(self, mac, rssi, code, msg, n):
        if self.count == RING_SLOTS:
            self.head = (self.head + 1) % RING_SLOTS
            self.count -= 1
            self.n_overflow += 1
        slot = (self.head + self.count) % RING_SLOTS
        o = slot * SLOT_LEN
        r = self.ring_mv
        r[o:o + 6] = mac
        r[o + 6] = rssi
        r[o + 7] = code
        r[o + 8] = n
        r[o + P.REC_HDR_LEN:o + P.REC_HDR_LEN + n] = msg
        self.count += 1

    def drain_radio(self):
        """Move every waiting ESP-NOW message into the ring."""
        while True:
            mac, msg = self.enow.irecv(0)
            if mac is None:
                return
            self.n_rx += 1
            if not self.accepting:
                continue
            mac = bytes(mac)
            n = len(msg)
            now = time.ticks_ms()
            if self._is_dup(mac, msg, n, now):
                self.n_dup += 1
                continue
            self._remember(mac, msg, n, now)
            code = classify(msg, self.mac_hex)
            if code == P.C_DROP:
                continue
            if code == P.C_STATUS_POLL and self.auto_status:
                self._schedule_status_reply(mac)
                continue
            self._enqueue(mac, self._rssi(mac), code, msg, n)

    # ─── STATUS AUTO-REPLY ───────────────────

    def _schedule_status_reply(self, mac):
        slot = self.mac[5] % N_SLOTS
        self.report_due = time.ticks_add(time.ticks_ms(),
                                         BASE_DELAY_MS + slot * SLOT_MS)
        self.report_second_due = None
        self.report_mac = mac

    def _send_status_report(self):
        rssi = self._rssi(self.report_mac)
        report = {
            "type": "status_report",
            "battery": None if self.battery == P.BATTERY_NONE else self.battery,
            "rssi": None if rssi == P.RSSI_UNKNOWN else P.to_i8(rssi),
        }
        self._send(BROADCAST_MAC, json.dumps(report), False)

    def service_status(self):
        now = time.ticks_ms()
        if self.report_second_due is not None:
            if time.ticks_diff(now, self.report_second_due) >= 0:
                self._send_status_report()
                self.report_second_due = None
                self.report_due = None
                self.report_mac = None
            return
        if self.report_due is None:
            return
        if time.ticks_diff(now, self.report_due) < 0:
            return
        self._send_status_report()
        self.report_second_due = time.ticks_add(now, REPORT_GAP_MS)

    # ─── SENDING ─────────────────────────────

    def _send(self, mac, data, sync):
        """Send once, retrying once after SEND_RETRY_MS on OSError.

        Returns (status, err, acked).
        """
        for attempt in range(2):
            try:
                acked = self.enow.send(mac, data, sync)
                self.n_tx += 1
                if sync and not acked:
                    self.n_tx_fail += 1
                return P.ST_OK, 0, 1 if acked else 0
            except OSError as e:
                if attempt == 0:
                    time.sleep_ms(SEND_RETRY_MS)
                    continue
                self.n_tx_fail += 1
                return P.ST_ERR, e.args[0] if e.args else -1, 0

    # ─── FAULTS ──────────────────────────────

    def _load_last_error(self):
        """Previous boot's fault text, or '' if none was recorded."""
        try:
            with open(LAST_ERROR_PATH) as f:
                text = f.read(P.ERROR_TEXT_MAX)
        except OSError:
            return ""
        os.remove(LAST_ERROR_PATH)   # report each fault on one boot only
        return text

    def _fault(self, where, e):
        """Record an unexpected exception; reset if faults are too frequent.

        The traceback goes to the USB console and to LAST_ERROR_PATH so the
        host can read it (T_LAST_ERROR) after the next boot.
        """
        self.n_fault += 1
        buf = io.StringIO()
        buf.write("boot_id %d fault %d in %s\n" % (self.boot_id, self.n_fault, where))
        sys.print_exception(e, buf)
        text = buf.getvalue()
        print("EUM modem FAULT:", text)
        try:
            with open(LAST_ERROR_PATH, "w") as f:
                f.write(text[:P.ERROR_TEXT_MAX])
        except OSError as we:
            # Keep running: losing the record must not turn one fault into a
            # crash. Reported here and via the console traceback above.
            print("EUM modem: could not write %s: %s" % (LAST_ERROR_PATH, we))
        now = time.ticks_ms()
        self.fault_times = [t for t in self.fault_times
                            if time.ticks_diff(now, t) < FAULT_WINDOW_MS]
        self.fault_times.append(now)
        if len(self.fault_times) > FAULT_LIMIT:
            print("EUM modem: %d faults in %d ms, resetting"
                  % (len(self.fault_times), FAULT_WINDOW_MS))
            time.sleep_ms(50)
            machine.reset()
        return text

    def _handle_safe(self, ftype, seq, plen):
        """Dispatch one request; on an exception reply T_ERROR instead."""
        self.host_seen = True
        try:
            self._handle(ftype, seq, plen)
        except Exception as e:
            text = self._fault("request 0x%02X" % ftype, e)
            body = P.HDR_LEN + P.REPLY_HDR_LEN
            self.tx[body] = ftype
            P.put_i16(self.tx, body + 1,
                      e.args[0] if e.args and isinstance(e.args[0], int) else -1)
            msg = ("%s: %s" % (type(e).__name__, e)).encode()[:200]
            self.tx[body + 3:body + 3 + len(msg)] = msg
            self._reply(P.T_ERROR, seq, 3 + len(msg))

    # ─── UART REQUESTS ───────────────────────

    def service_uart(self):
        n = self.uart.any()
        if not n:
            return
        n = self.uart.readinto(self.rbuf)
        if n:
            self.parser.feed(self.rbuf_mv, n, self._handle_safe)

    def _reply(self, ftype, seq, body_len):
        """Write the common reply header and send buf[HDR_LEN:] + body."""
        t = self.tx
        o = P.HDR_LEN
        t[o] = self.boot_id
        P.put_u16(t, o + 1, self.n_overflow & 0xFFFF)
        t[o + 3] = self.count if self.count < 255 else 255
        n = P.build_frame(t, ftype | P.REPLY_FLAG, seq,
                          P.REPLY_HDR_LEN + body_len)
        self.uart.write(self.tx_mv[:n])

    def _status_body(self, status, err):
        o = P.HDR_LEN + P.REPLY_HDR_LEN
        self.tx[o] = status
        P.put_i16(self.tx, o + 1, err)
        return 3

    def _handle(self, ftype, seq, plen):
        p = self.parser.buf
        body = P.HDR_LEN + P.REPLY_HDR_LEN
        t = self.tx

        if ftype == P.T_HELLO:
            t[body] = P.PROTO_VERSION
            t[body + 1:body + 7] = self.mac
            self._reply(ftype, seq, 7)

        elif ftype == P.T_ACTIVATE:
            self.accepting = True
            self._reply(ftype, seq, self._status_body(P.ST_OK, 0))

        elif ftype == P.T_DEACTIVATE:
            self.accepting = False
            self.head = 0
            self.count = 0
            self.auto_status = False
            self.report_due = None
            self.report_second_due = None
            for mac in list(self.peers):
                self.enow.del_peer(mac)
            self.peers.clear()
            gc.collect()
            self._reply(ftype, seq, self._status_body(P.ST_OK, 0))

        elif ftype == P.T_ADD_PEER or ftype == P.T_DEL_PEER:
            mac = bytes(p[0:6])
            status, err = P.ST_OK, 0
            try:
                if ftype == P.T_ADD_PEER:
                    if mac not in self.peers:
                        self.enow.add_peer(mac)
                        self.peers[mac] = True
                elif mac in self.peers:
                    self.enow.del_peer(mac)
                    del self.peers[mac]
            except OSError as e:
                status, err = P.ST_ERR, e.args[0] if e.args else -1
            self._reply(ftype, seq, self._status_body(status, err))

        elif ftype == P.T_SEND:
            mac = bytes(p[0:6])
            sync = bool(p[6] & P.SEND_FLAG_SYNC)
            data = bytes(p[7:plen])
            status, err, acked = self._send(mac, data, sync)
            n = self._status_body(status, err)
            t[body + n] = acked
            self._reply(ftype, seq, n + 1)

        elif ftype == P.T_FETCH:
            want = p[0] if plen else 1
            if want > P.FETCH_MAX:
                want = P.FETCH_MAX
            o = body + 1
            got = 0
            while got < want and self.count:
                s = self.head * SLOT_LEN
                rec_len = P.REC_HDR_LEN + self.ring[s + 8]
                t[o:o + rec_len] = self.ring_mv[s:s + rec_len]
                o += rec_len
                self.head = (self.head + 1) % RING_SLOTS
                self.count -= 1
                got += 1
            t[body] = got
            self._reply(ftype, seq, o - body)

        elif ftype == P.T_GET_RSSI:
            t[body] = self._rssi(bytes(p[0:6]))
            self._reply(ftype, seq, 1)

        elif ftype == P.T_SET_STATUS:
            self.battery = P.to_i8(p[0])
            self.auto_status = bool(p[1])
            self._reply(ftype, seq, self._status_body(P.ST_OK, 0))

        elif ftype == P.T_FLUSH:
            dropped = self.count
            self.head = 0
            self.count = 0
            P.put_u16(t, body, dropped)
            self._reply(ftype, seq, 2)

        elif ftype == P.T_STATS:
            vals = (self.n_rx, self.n_tx, self.n_tx_fail, self.n_overflow,
                    self.parser.crc_errors, self.n_dup, self.parser.len_errors,
                    self.n_fault)
            for i, v in enumerate(vals):
                P.put_u16(t, body + 2 * i, v & 0xFFFF)
            self._reply(ftype, seq, 2 * len(vals))

        elif ftype == P.T_LAST_ERROR:
            t[body] = self.reset_cause & 0xFF
            msg = self.prev_error.encode()[:P.ERROR_TEXT_MAX]
            t[body + 1:body + 1 + len(msg)] = msg
            self._reply(ftype, seq, 1 + len(msg))

        else:
            self._reply(ftype, seq, self._status_body(P.ST_ERR, -ftype))

    # ─── MAIN LOOP ───────────────────────────

    def _step(self, where, fn):
        try:
            fn()
        except Exception as e:
            self._fault(where, e)

    def run(self):
        print("EUM modem: MAC %s boot_id %d reset_cause %d ring %dx%d "
              "uart%d tx=%d rx=%d @%d"
              % (self.mac_hex, self.boot_id, self.reset_cause, RING_SLOTS,
                 SLOT_LEN, UART_ID, UART_TX, UART_RX, UART_BAUD))
        if self.prev_error:
            print("EUM modem: previous boot's last fault:\n" + self.prev_error)
        try:
            os.stat(NO_WDT_PATH)
            wdt_allowed = False
        except OSError:
            wdt_allowed = True
        if wdt_allowed:
            print("EUM modem: watchdog (%d ms) arms after %d s uptime and a "
                  "host request; create %s to disable"
                  % (WDT_TIMEOUT_MS, WDT_ARM_AFTER_MS // 1000, NO_WDT_PATH))
        else:
            print("EUM modem: watchdog disabled (%s exists)" % NO_WDT_PATH)
        boot_ms = time.ticks_ms()
        wdt = None
        while True:
            if wdt is not None:
                wdt.feed()
            elif (wdt_allowed and self.host_seen and
                  time.ticks_diff(time.ticks_ms(), boot_ms) >= WDT_ARM_AFTER_MS):
                wdt = machine.WDT(timeout=WDT_TIMEOUT_MS)
                print("EUM modem: watchdog armed (%d ms)" % WDT_TIMEOUT_MS)
            self._step("drain_radio", self.drain_radio)
            self._step("service_uart", self.service_uart)
            self._step("drain_radio", self.drain_radio)
            self._step("service_status", self.service_status)
            time.sleep_ms(1)


_modem = Modem(_sta, _enow)
_modem.run()
