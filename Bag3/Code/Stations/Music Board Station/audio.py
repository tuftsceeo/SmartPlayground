"""
Streamed WAV playback over I2S.

One note plays at a time. start() opens a WAV and step() writes one chunk
per call from the main loop, so the radio and buttons stay serviced during
playback. All buffers are allocated in __init__, after the radio is up.
"""

import struct
from machine import I2S, Pin

I2S_ID = 0
SCK_PIN = 20   # BCLK, XIAO D9
WS_PIN = 18    # LRC, XIAO D10
SD_PIN = 19    # DIN, XIAO D8
CHUNK = 256    # bytes per step(): 16 ms at 8 kHz 16-bit mono
IBUF = 2048
HEADER_LEN = 44


class Audio:
    def __init__(self):
        self._buf = bytearray(CHUNK)
        self._mv = memoryview(self._buf)
        self._hdr = bytearray(HEADER_LEN)
        self._i2s = None
        self._fmt = None   # (rate, bits) the I2S peripheral is set up for
        self._f = None

    def _parse_header(self, f, path):
        """Read a canonical 44-byte PCM WAV header; return (rate, bits)."""
        if f.readinto(self._hdr) != HEADER_LEN:
            raise ValueError(f"{path}: short WAV header")
        h = self._hdr
        if h[0:4] != b'RIFF' or h[8:12] != b'WAVE' or h[36:40] != b'data':
            raise ValueError(f"{path}: not a 44-byte-header PCM WAV")
        channels = struct.unpack('<H', h[22:24])[0]
        if channels != 1:
            raise ValueError(f"{path}: {channels} channels, need mono")
        rate = struct.unpack('<I', h[24:28])[0]
        bits = struct.unpack('<H', h[34:36])[0]
        return rate, bits

    def _setup(self, fmt):
        if self._fmt == fmt:
            return
        if self._i2s is not None:
            self._i2s.deinit()
        rate, bits = fmt
        self._i2s = I2S(I2S_ID, sck=Pin(SCK_PIN), ws=Pin(WS_PIN), sd=Pin(SD_PIN),
                        mode=I2S.TX, bits=bits, format=I2S.MONO, rate=rate, ibuf=IBUF)
        self._fmt = fmt

    def start(self, path):
        """Stop any current note and begin streaming path."""
        self.stop()
        f = open(path, 'rb')
        try:
            fmt = self._parse_header(f, path)
        except Exception:
            f.close()
            raise
        self._setup(fmt)
        self._f = f

    def step(self):
        """Write one chunk. Returns True while the note still has data."""
        if self._f is None:
            return False
        n = self._f.readinto(self._buf)
        if not n:
            self.stop()
            return False
        self._i2s.write(self._mv[:n])
        return True

    def stop(self):
        if self._f is not None:
            self._f.close()
            self._f = None

    @property
    def busy(self):
        return self._f is not None
