"""CPython tests for eum_proto and eum_classify. Run: python tests/test_proto.py"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "modem", "lib"))

import eum_proto as P
from eum_classify import classify

MAC_HEX = "AABBCCDDEEFF"


def frame(ftype, seq, payload):
    buf = bytearray(P.MAX_FRAME)
    buf[P.HDR_LEN:P.HDR_LEN + len(payload)] = payload
    n = P.build_frame(buf, ftype, seq, len(payload))
    return bytes(buf[:n])


def parse(data, chunk=None, parser=None):
    parser = parser or P.FrameParser()
    out = []

    def h(t, s, n):
        out.append((t, s, bytes(parser.buf[:n])))

    mv = memoryview(bytearray(data))
    if chunk is None:
        parser.feed(mv, len(data), h)
    else:
        for i in range(0, len(data), chunk):
            part = memoryview(bytearray(data[i:i + chunk]))
            parser.feed(part, len(part), h)
    return out, parser


def test_crc_known_value():
    # CRC-8/SMBUS check value for "123456789"
    assert P.crc8(b"123456789", 0, 9) == 0xF4


def test_roundtrip_and_split_feed():
    payloads = [b"", b"x", bytes(range(256)) * 4]
    data = b"".join(frame(0x06, i, p) for i, p in enumerate(payloads))
    for chunk in (None, 1, 3, 64):
        out, _ = parse(data, chunk)
        assert [(t, s, p) for t, s, p in out] == \
            [(0x06, i, p) for i, p in enumerate(payloads)], chunk


def test_corruption_counted_and_resync():
    good = frame(0x07, 1, b"hello")
    bad = bytearray(frame(0x07, 2, b"world"))
    bad[8] ^= 0xFF
    data = b"\x00\xA5\x13garbage\xA5" + bytes(bad) + good
    out, parser = parse(data)
    assert out == [(0x07, 1, b"hello")]
    assert parser.crc_errors == 1


def test_length_cap():
    hdr = bytes([P.SYNC1, P.SYNC2, 0x01, 0x00, 0xFF, 0xFF])
    out, parser = parse(hdr + frame(0x01, 9, b"ok"))
    assert out == [(0x01, 9, b"ok")]
    assert parser.len_errors == 1
    try:
        P.build_frame(bytearray(P.MAX_FRAME + 10), 1, 0, P.MAX_PAYLOAD + 1)
    except ValueError:
        pass
    else:
        raise AssertionError("oversize payload accepted")


def test_int_helpers():
    b = bytearray(2)
    P.put_i16(b, 0, -12391)
    assert P.get_i16(b, 0) == -12391
    assert P.to_i8(0xFF) == -1 and P.to_i8(0x7F) == 127


def test_classify():
    cases = [
        (b'["turnred","turnblue"]', P.C_COLORS),
        (b'["stop"]', P.C_STOP),
        (b'["battery"]', P.C_BATTERY),
        (b'{"type":"stop"}', P.C_STOP),
        (b'{"type":"splat_config","actions":[]}', P.C_SPLAT_CONFIG),
        (b'{"type":"score"}', P.C_SCORE),
        (b'{"type":"scan_request"}', P.C_SCAN_REQUEST),
        (b'{"type":"start_game","name":"shake"}', P.C_START_GAME),
        (b'{"type":"start_game","name":""}', P.C_RAW_JSON),
        (b'{"type":"find_device","mac":"aa:bb:cc:dd:ee:ff"}', P.C_FIND_DEVICE),
        (b'{"type":"find_device","mac":"11:22:33:44:55:66"}', P.C_DROP),
        (b'{"type":"find_device"}', P.C_FIND_DEVICE),
        (b'{"type":"find_device","mac":7}', P.C_DROP),
        (b'{"type":"status_poll"}', P.C_STATUS_POLL),
        (b'{"type":"status_report","battery":80}', P.C_STATUS_REPORT),
        (b'{"type":"other"}', P.C_RAW_JSON),
        (b'42', P.C_RAW_JSON),
        (b'\x01\x02\xff', P.C_RAW_BYTES),
    ]
    for msg, want in cases:
        got = classify(bytearray(msg), MAC_HEX)
        assert got == want, (msg, got, want)


def test_copies_identical():
    a = os.path.join(HERE, "..", "modem", "lib", "eum_proto.py")
    b = os.path.join(HERE, "..", "host", "lib", "eum_proto.py")
    with open(a, "rb") as fa, open(b, "rb") as fb:
        assert fa.read() == fb.read(), "modem/host eum_proto.py differ"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print("%d passed" % len(tests))
