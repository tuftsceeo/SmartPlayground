"""
eum_proto.py -- ESP-NOW UART Modem (EUM) wire protocol
=======================================================
Shared by the modem firmware and the host-side espnow_manager.py.
modem/lib/eum_proto.py and host/lib/eum_proto.py must be byte-identical;
nothing checks this automatically (compare with `cmp` before flashing).

Frame layout:
    0xA5 0x5A | type(1) | seq(1) | len(2, LE) | payload(len) | crc8(1)
crc8 (poly 0x07, init 0) covers type..payload.

Every reply (type = request | REPLY_FLAG) begins with a common header:
    boot_id(1) | rx_overflow(2, LE) | pending(1)
followed by the request-specific body. See README.md for the table.

Pure Python, no MicroPython-only imports, so it runs under CPython tests.
"""

PROTO_VERSION = 1

SYNC1 = 0xA5
SYNC2 = 0x5A
HDR_LEN = 6                  # sync(2) type seq len(2)
MAX_PAYLOAD = 1100
MAX_FRAME = HDR_LEN + MAX_PAYLOAD + 1

# Request types (host -> modem). Reply type = request | REPLY_FLAG.
T_HELLO = 0x01
T_ACTIVATE = 0x02
T_DEACTIVATE = 0x03
T_ADD_PEER = 0x04
T_DEL_PEER = 0x05
T_SEND = 0x06
T_FETCH = 0x07
T_GET_RSSI = 0x08
T_SET_STATUS = 0x09
T_STATS = 0x0A
T_FLUSH = 0x0B
REPLY_FLAG = 0x80

REPLY_HDR_LEN = 4            # boot_id(1) rx_overflow(2) pending(1)

SEND_FLAG_SYNC = 0x01        # wait for the unicast ACK

# FETCH record: mac(6) rssi(i8) code(1) len(1) data(len)
REC_HDR_LEN = 9
ESPNOW_MAX_DATA = 250
FETCH_MAX = 4

RSSI_UNKNOWN = 0x7F
BATTERY_NONE = -1

# Status byte in replies
ST_OK = 0
ST_ERR = 1

# Message classification codes, assigned by the modem.
C_DROP = 0                   # modem-internal: not queued
C_RAW_BYTES = 1              # not JSON -> ("raw", bytes)
C_RAW_JSON = 2               # JSON, unrecognised -> ("raw", decoded)
C_COLORS = 3
C_STOP = 4
C_BATTERY = 5
C_SPLAT_CONFIG = 6
C_SCORE = 7
C_SCAN_REQUEST = 8
C_START_GAME = 9
C_FIND_DEVICE = 10           # addressed to this modem (or untargeted)
C_STATUS_POLL = 11           # only queued when auto-reply is off
C_STATUS_REPORT = 12

# Host-facing msg_type for each code (C_FIND_DEVICE maps to "start_game").
CODE_NAMES = {
    C_RAW_BYTES: "raw",
    C_RAW_JSON: "raw",
    C_COLORS: "colors",
    C_STOP: "stop",
    C_BATTERY: "battery",
    C_SPLAT_CONFIG: "splat_config",
    C_SCORE: "score",
    C_SCAN_REQUEST: "scan_request",
    C_START_GAME: "start_game",
    C_FIND_DEVICE: "start_game",
    C_STATUS_POLL: "status_poll",
    C_STATUS_REPORT: "status_report",
}


def _make_table():
    t = bytearray(256)
    for i in range(256):
        c = i
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
        t[i] = c
    return bytes(t)


_CRC_TABLE = _make_table()


def crc8(buf, start, end, crc=0):
    """CRC-8 (poly 0x07) of buf[start:end], continuing from crc."""
    t = _CRC_TABLE
    for i in range(start, end):
        crc = t[crc ^ buf[i]]
    return crc


def put_u16(buf, off, v):
    buf[off] = v & 0xFF
    buf[off + 1] = (v >> 8) & 0xFF


def get_u16(buf, off):
    return buf[off] | (buf[off + 1] << 8)


def put_i16(buf, off, v):
    put_u16(buf, off, v & 0xFFFF)


def get_i16(buf, off):
    v = get_u16(buf, off)
    return v - 0x10000 if v & 0x8000 else v


def to_i8(v):
    return v - 256 if v & 0x80 else v


def build_frame(buf, ftype, seq, plen):
    """Fill the header and CRC around a payload already at buf[HDR_LEN:].

    Returns the total frame length. No allocation.
    """
    if plen > MAX_PAYLOAD:
        raise ValueError("EUM: payload %d > %d" % (plen, MAX_PAYLOAD))
    buf[0] = SYNC1
    buf[1] = SYNC2
    buf[2] = ftype
    buf[3] = seq & 0xFF
    buf[4] = plen & 0xFF
    buf[5] = (plen >> 8) & 0xFF
    end = HDR_LEN + plen
    buf[end] = crc8(buf, 2, end)
    return end + 1


_S_SYNC1 = 0
_S_SYNC2 = 1
_S_TYPE = 2
_S_SEQ = 3
_S_LEN0 = 4
_S_LEN1 = 5
_S_PAYLOAD = 6
_S_CRC = 7


class FrameParser:
    """Incremental frame decoder with a preallocated payload buffer.

    feed(mv, n, handler) consumes mv[:n] and calls handler(ftype, seq, plen)
    for each valid frame; the payload is self.buf[:plen] and is only valid
    until the next frame completes. Bad CRCs and oversized lengths are
    counted in crc_errors / len_errors and the parser resyncs on 0xA5 0x5A.
    """

    def __init__(self, max_payload=MAX_PAYLOAD):
        self.max_payload = max_payload
        self.buf = bytearray(max_payload)
        self.mv = memoryview(self.buf)
        self.crc_errors = 0
        self.len_errors = 0
        self.reset()

    def reset(self):
        self.state = _S_SYNC1
        self.ftype = 0
        self.seq = 0
        self.plen = 0
        self.pos = 0
        self.crc = 0

    def feed(self, mv, n, handler):
        i = 0
        while i < n:
            st = self.state
            if st == _S_PAYLOAD:
                take = self.plen - self.pos
                if take > n - i:
                    take = n - i
                self.mv[self.pos:self.pos + take] = mv[i:i + take]
                self.pos += take
                i += take
                if self.pos == self.plen:
                    self.state = _S_CRC
                continue
            b = mv[i]
            i += 1
            if st == _S_SYNC1:
                if b == SYNC1:
                    self.state = _S_SYNC2
            elif st == _S_SYNC2:
                if b == SYNC2:
                    self.state = _S_TYPE
                    self.crc = 0
                elif b != SYNC1:
                    self.state = _S_SYNC1
            elif st == _S_TYPE:
                self.ftype = b
                self.crc = _CRC_TABLE[self.crc ^ b]
                self.state = _S_SEQ
            elif st == _S_SEQ:
                self.seq = b
                self.crc = _CRC_TABLE[self.crc ^ b]
                self.state = _S_LEN0
            elif st == _S_LEN0:
                self.plen = b
                self.crc = _CRC_TABLE[self.crc ^ b]
                self.state = _S_LEN1
            elif st == _S_LEN1:
                self.plen |= b << 8
                self.crc = _CRC_TABLE[self.crc ^ b]
                if self.plen > self.max_payload:
                    self.len_errors += 1
                    self.state = _S_SYNC1
                else:
                    self.pos = 0
                    self.state = _S_PAYLOAD if self.plen else _S_CRC
            else:  # _S_CRC
                self.state = _S_SYNC1
                if crc8(self.buf, 0, self.plen, self.crc) == b:
                    handler(self.ftype, self.seq, self.plen)
                else:
                    self.crc_errors += 1
