"""Success and fail beeps on the panel speaker (I2S amp on board.I2S_*), the Broadcast Dial's two sounds.

Import after radio bring-up: init() allocates the I2S DMA buffer and both sound buffers.
play() never waits: the I2S write runs in the background (irq mode) and a sound asked for
while another plays is dropped.
"""

import math

import board

RATE = 16000
AMP = 6000          # of 32767; adjust on the device
# (freq Hz, ms) tones with GAP_MS of silence between them, as on the Dial
SUCCESS = ((4800, 100), (4800, 100))
FAIL = ((3600, 70), (3600, 70), (3600, 70))
SUCCESS_GAP_MS = 80
FAIL_GAP_MS = 50

_i2s = None
_bufs = {}
_busy = False


def _tones(tones, gap_ms):
    n_gap = RATE * gap_ms // 1000
    total = sum(RATE * ms // 1000 for _, ms in tones) + n_gap * (len(tones) - 1)
    buf = bytearray(total * 2)
    i = 0
    for j, (freq, ms) in enumerate(tones):
        if j:
            i += n_gap
        n = RATE * ms // 1000
        w = 2 * math.pi * freq / RATE
        ramp = RATE // 400          # 2.5 ms fade in/out, no click
        for s in range(n):
            a = AMP
            if s < ramp:
                a = a * s // ramp
            elif n - s < ramp:
                a = a * (n - s) // ramp
            v = int(a * math.sin(w * s)) & 0xFFFF
            buf[2 * (i + s)] = v & 0xFF
            buf[2 * (i + s) + 1] = v >> 8
        i += n
    return buf


def _done(_):
    global _busy
    _busy = False


def init():
    """Set up I2S and build both sounds. False (and silent play()) when the amp can't be opened."""
    global _i2s
    if _i2s is not None:
        return True
    try:
        from machine import I2S, Pin
        _bufs["ok"] = _tones(SUCCESS, SUCCESS_GAP_MS)
        _bufs["fail"] = _tones(FAIL, FAIL_GAP_MS)
        _i2s = I2S(0, sck=Pin(board.I2S_BCLK), ws=Pin(board.I2S_LRCLK), sd=Pin(board.I2S_SDIN),
                   mode=I2S.TX, bits=16, format=I2S.MONO, rate=RATE,
                   ibuf=max(len(b) for b in _bufs.values()) + 1024)
        _i2s.irq(_done)
        return True
    except Exception as e:
        print(f"# beep init failed: {e}")
        _i2s = None
        return False


def play(name):
    """name: "ok" or "fail"."""
    global _busy
    if _i2s is None or _busy:
        return
    _busy = True
    try:
        _i2s.write(_bufs[name])
    except Exception as e:
        _busy = False
        print(f"# beep: {e}")


def ok():
    play("ok")


def fail():
    play("fail")
