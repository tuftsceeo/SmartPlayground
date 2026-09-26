"""
dep_loopback.py -- CPython check of dep_proto.py's request/response logic.

Connects pull() to handle_request() in memory, with no PN532 or I2C
involved. Covers chunking, the short final chunk, offsets, and sha256 and
reply-mismatch detection.

Also drives pn532_dep.PN532Dep against a fake I2C bus that answers with
well-formed PN532 frames, to check command framing, response parsing and
read sizing. This checks the frame format only, not a real PN532's
behaviour. Run:  python3 dep_loopback.py
"""

import os
import sys
import time

# MicroPython time functions used by pn532_dep, mapped onto CPython.
time.sleep_ms = lambda ms: None
time.ticks_ms = lambda: int(time.monotonic() * 1000)
time.ticks_us = lambda: int(time.monotonic() * 1000000)
time.ticks_diff = lambda a, b: a - b

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dep_proto import build_header, handle_request, pull, ProtoError, MAX_CHUNK
import pn532_dep
from pn532_dep import PN532Dep, DepError


def pn532_frame(body):
    """I2C read image of a PN532 response: status byte + normal information frame."""
    n = len(body)
    return (bytes([0x01, 0x00, 0x00, 0xFF, n, (-n) & 0xFF]) + body
            + bytes([(-sum(body)) & 0xFF, 0x00]))


class FakeI2C:
    """Answers each command with reply(cmd, params) -> response data (after TFI/code)."""

    def __init__(self, reply):
        self.reply = reply
        self.pending = []
        self.written = []

    def writeto(self, addr, frame):
        self.written.append(bytes(frame))
        if bytes(frame) == pn532_dep._ACK_FRAME:
            return
        n = frame[3]
        cmd, params = frame[6], bytes(frame[7:5 + n])
        body = bytes([0xD5, cmd + 1]) + self.reply(cmd, params)
        self.pending = [b'\x01\x00\x00\xFF\x00\xFF\x00', pn532_frame(body)]

    def readfrom(self, addr, n):
        if n == 1:
            return b'\x01' if self.pending else b'\x00'
        out = self.pending.pop(0)
        return (out + bytes(n))[:n]


def driver_checks():
    data = bytes(range(256)) * 2
    header = build_header("x", data)

    def reply(cmd, params):
        if cmd == pn532_dep.CMD_GETFIRMWAREVERSION:
            return b'\x32\x01\x06\x07'
        if cmd in (pn532_dep.CMD_SAMCONFIGURATION, pn532_dep.CMD_RFCONFIGURATION):
            return b''
        if cmd == pn532_dep.CMD_INJUMPFORDEP:
            return b'\x00\x01' + bytes(10) + b'\x00\x00\x00\x0e\x32'
        if cmd == pn532_dep.CMD_INDATAEXCHANGE:
            return b'\x00' + handle_request(params[1:], header, data)
        if cmd == pn532_dep.CMD_INRELEASE:
            return b'\x00'
        raise AssertionError("unexpected cmd 0x%02X" % cmd)

    nfc = PN532Dep(FakeI2C(reply))
    assert nfc.begin() == (0x32, 0x01, 0x06)
    nfc.configure_initiator()
    assert nfc.jump_for_dep()[13] == 0x0E
    for chunk in (64, MAX_CHUNK):
        assert pull(nfc.exchange, chunk) == ("x", data), chunk
        assert nfc.timing['rx'] == 3, nfc.timing   # last exchange: status + b'OK'
    nfc.release()

    def fail(cmd, params):
        return b'\x29' if cmd == pn532_dep.CMD_INDATAEXCHANGE else reply(cmd, params)
    nfc = PN532Dep(FakeI2C(fail))
    try:
        nfc.exchange(b'H', 80)
        raise AssertionError("expected DepError")
    except DepError as e:
        assert e.status == 0x29 and "released by initiator" in str(e), e
        assert 'read' in e.timing, e.timing


def link(header, data, tamper=None):
    """Return an exchange() that serves header/data, optionally passing replies through tamper()."""
    def exchange(req, max_resp):
        resp = handle_request(req, header, data)
        if len(resp) > max_resp:
            raise AssertionError("reply %d exceeds max_resp %d" % (len(resp), max_resp))
        return tamper(req, resp) if tamper else resp
    return exchange


def expect_fail(fn, what):
    try:
        fn()
    except ProtoError:
        return
    raise AssertionError("expected ProtoError: " + what)


def main():
    data = bytes((i * 7) & 0xFF for i in range(7048))   # jumpin.py-sized
    header = build_header("jumpin.py", data)
    for chunk in (1, 64, 128, 192, MAX_CHUNK):
        seen = []
        name, got = pull(link(header, data), chunk, lambda off, n: seen.append(n))
        assert (name, got) == ("jumpin.py", data), chunk
        assert sum(seen) == len(data), chunk
        assert seen[-1] == (len(data) % chunk or chunk), chunk
    assert pull(link(build_header("e", b""), b""), 64) == ("e", b"")

    def flip(req, resp):
        return resp[:-1] + bytes([resp[-1] ^ 1]) if req[:1] == b'C' else resp
    expect_fail(lambda: pull(link(header, data, flip), 128), "corrupt byte")

    def shift(req, resp):
        return bytes([resp[0] ^ 1]) + resp[1:] if req[:1] == b'C' else resp
    expect_fail(lambda: pull(link(header, data, shift), 128), "wrong offset")
    expect_fail(lambda: pull(link(header, data), MAX_CHUNK + 1), "oversize chunk")
    expect_fail(lambda: handle_request(b'C\x00\x00\x00\x00', header, data), "short request")
    driver_checks()
    print("dep_loopback OK")


main()
