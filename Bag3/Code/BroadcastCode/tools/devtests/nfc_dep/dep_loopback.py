"""
dep_loopback.py -- CPython check of dep_proto.py's request/response logic.

Connects pull() to handle_request() in memory, with no PN532 or I2C
involved. Covers chunking, the short final chunk, offsets, and sha256 and
reply-mismatch detection. Run:  python3 dep_loopback.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dep_proto import build_header, handle_request, pull, ProtoError, MAX_CHUNK


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
    print("dep_loopback OK")


main()
