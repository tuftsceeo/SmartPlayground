"""
dep_proto.py -- request/response file transfer over an NFC-DEP link.

Pure logic, no hardware imports: runs under MicroPython on the wands and
under CPython in dep_loopback.py. The initiator drives every exchange.

  b'H'                          -> size(4B BE) | sha256(32B) | name_len(1B) | name
  b'C' | offset(4B BE) | len(1B) -> offset(4B BE) | data
  b'D'                          -> b'OK'

The header layout matches the WiFi pull in MockWand/code_puller.py.
"""

from binascii import hexlify

try:
    import hashlib
except ImportError:
    import uhashlib as hashlib

MAX_CHUNK = 240   # 4-byte offset + data must fit one PN532 frame (252 bytes)
HEADER_MAX = 4 + 32 + 1 + 64


class ProtoError(Exception):
    pass


def _u32(b, i):
    return (b[i] << 24) | (b[i + 1] << 16) | (b[i + 2] << 8) | b[i + 3]


def _p32(n):
    return bytes([(n >> 24) & 0xFF, (n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF])


def build_header(name, data):
    """Header bytes for serving data under name."""
    nb = name.encode()
    if len(nb) > 64:
        raise ProtoError("name too long")
    return _p32(len(data)) + hashlib.sha256(data).digest() + bytes([len(nb)]) + nb


def parse_header(h):
    """Return (size, sha256, name) from header bytes."""
    if len(h) < 37 or len(h) < 37 + h[36]:
        raise ProtoError("short header: %d bytes" % len(h))
    return _u32(h, 0), bytes(h[4:36]), bytes(h[37:37 + h[36]]).decode()


def handle_request(req, header, data):
    """Target side: return the reply for one initiator request."""
    op = req[0:1]
    if op == b'H':
        return header
    if op == b'C':
        if len(req) != 6:
            raise ProtoError("bad chunk request length %d" % len(req))
        off, n = _u32(req, 1), req[5]
        if n > MAX_CHUNK or off > len(data):
            raise ProtoError("bad chunk request off=%d len=%d" % (off, n))
        return _p32(off) + data[off:off + n]
    if op == b'D':
        return b'OK'
    raise ProtoError("unknown op %r" % op)


def pull(exchange, chunk, on_chunk=None):
    """Initiator side: fetch the whole file through exchange(req, max_resp) -> bytes.

    Returns (name, data). Raises ProtoError on offset or sha256 mismatch.
    on_chunk(offset, n) is called after each chunk for progress/timing.
    """
    if not 1 <= chunk <= MAX_CHUNK:
        raise ProtoError("chunk must be 1..%d" % MAX_CHUNK)
    size, digest, name = parse_header(exchange(b'H', HEADER_MAX))
    buf = bytearray(size)
    off = 0
    while off < size:
        n = min(chunk, size - off)
        resp = exchange(b'C' + _p32(off) + bytes([n]), 4 + n)
        if len(resp) != 4 + n or _u32(resp, 0) != off:
            raise ProtoError("chunk reply mismatch at %d (got %d bytes)" % (off, len(resp)))
        buf[off:off + n] = resp[4:]
        off += n
        if on_chunk:
            on_chunk(off, n)
    got = hashlib.sha256(buf).digest()
    if got != digest:
        raise ProtoError("sha256 mismatch: header %s, received %s"
                         % (hexlify(digest[:8]), hexlify(got[:8])))
    if exchange(b'D', 2) != b'OK':
        raise ProtoError("bad done reply")
    return name, bytes(buf)


def stats(xs):
    """Return 'n=.. min=.. med=.. max=..' for a list of numbers ('n=0' if empty)."""
    if not xs:
        return "n=0"
    s = sorted(xs)
    return "n=%d min=%d med=%d max=%d" % (len(s), s[0], s[len(s) // 2], s[-1])
