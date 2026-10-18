"""
Streamed WAV playback over I2S.

One note plays at a time. start() opens a WAV and step() writes one chunk
per call from the main loop, so the radio and buttons stay serviced during
playback. I2S.write() blocks while the DMA buffer is full, which paces the
loop to the audio. start() of the next note does not drain the buffer, so
consecutive notes play without a gap. All buffers are allocated in
__init__, after the radio is up.
"""

import struct
from machine import I2S, Pin

I2S_ID = 0
SCK_PIN = 20   # BCLK, XIAO D9
WS_PIN = 18    # LRC, XIAO D10
SD_PIN = 19    # DIN, XIAO D8
CHUNK = 1024   # bytes per step(): 64 ms at 8 kHz 16-bit mono, as in the pilot
IBUF = 4096    # DMA buffer: ~256 ms of audio queued ahead of the main loop
HEADER_LEN = 44
DEFAULT_FMT = (8000, 16)   # used for silence before any note has set the format


class Audio:
    def __init__(self):
        self._buf = bytearray(CHUNK)
        self._mv = memoryview(self._buf)
        self._zeros = memoryview(bytearray(CHUNK))
        self._silence = 0   # bytes of silence still to write
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

    def silence(self, ms):
        """Queue ms of silence (a rest) through I2S, so rests keep sample time."""
        self.stop()
        self._setup(self._fmt or DEFAULT_FMT)
        rate, bits = self._fmt
        self._silence = rate * (bits // 8) * ms // 1000

    def step(self):
        """Write one chunk. Returns True while the note or rest still has data."""
        if self._silence:
            n = min(self._silence, CHUNK)
            self._i2s.write(self._zeros[:n])
            self._silence -= n
            return True
        if self._f is None:
            return False
        n = self._f.readinto(self._buf)
        if not n:
            self.stop()
            return False
        self._i2s.write(self._mv[:n])
        return True

    def stop(self):
        self._silence = 0
        if self._f is not None:
            self._f.close()
            self._f = None

    @property
    def busy(self):
        return self._f is not None or self._silence > 0
