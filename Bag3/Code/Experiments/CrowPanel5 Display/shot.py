"""Bench screenshots and taps from the REPL only, after bring-up: grab(), tap(x, y, ms), steps(ms).

grab() prints the active screen (RGB565) and, when it has visible children, the top layer
(ARGB8888) as run-length base64 frames for shot_host.py. tap() drives a virtual pointer, so
LVGL's own hit-testing picks the object, and runs panel steps so queued actions happen.
"""

import binascii
import time

import lvgl as lv
import micropython

import panel

_pt = [0, 0, False]
_indev = None
LONG_MS = 900


@micropython.viper
def _rle16(src, n: int, out) -> int:
    s = ptr16(src)
    o = ptr8(out)
    i = 0
    j = 0
    while i < n:
        v = s[i]
        c = 1
        while i + c < n and c < 255 and s[i + c] == v:
            c += 1
        o[j] = c
        o[j + 1] = v & 0xFF
        o[j + 2] = (v >> 8) & 0xFF
        j += 3
        i += c
    return j


@micropython.viper
def _rle32(src, n: int, out) -> int:
    s = ptr32(src)
    o = ptr8(out)
    i = 0
    j = 0
    while i < n:
        v = s[i]
        c = 1
        while i + c < n and c < 255 and s[i + c] == v:
            c += 1
        o[j] = c
        o[j + 1] = v & 0xFF
        o[j + 2] = (v >> 8) & 0xFF
        o[j + 3] = (v >> 16) & 0xFF
        o[j + 4] = (v >> 24) & 0xFF
        j += 5
        i += c
    return j


def _send(name, obj, cf, bpp):
    buf = lv.snapshot_take(obj, cf)
    w = buf.header.w
    h = buf.header.h
    stride = buf.header.stride
    mv = buf.data.__dereference__(stride * h)
    pb = bpp // 8
    print(f"#F {name} {w} {h} {bpp}")
    rows = 24
    out = bytearray(w * rows * (1 + pb))
    row = bytearray(w * rows * pb)
    y = 0
    while y < h:
        r = min(rows, h - y)
        for k in range(r):
            a = (y + k) * stride
            row[k * w * pb:(k + 1) * w * pb] = mv[a:a + w * pb]
        n = (_rle16 if bpp == 16 else _rle32)(row, w * r, out)
        for i in range(0, n, 570):
            print(binascii.b2a_base64(out[i:min(n, i + 570)]).decode().strip())
        y += r
    print("#E")
    buf.destroy()


def grab():
    """Top-layer objects (game sheet, toast) are moved onto the screen for the snapshot,
    so one RGB565 frame holds everything the panel shows."""
    top = lv.layer_top()
    scr = lv.screen_active()
    moved = [top.get_child(i) for i in range(top.get_child_count())
             if not top.get_child(i).has_flag(lv.obj.FLAG.HIDDEN)]
    for o in moved:
        o.set_parent(scr)
    scr.update_layout()
    try:
        _send("screen", scr, lv.COLOR_FORMAT.RGB565, 16)
    finally:
        for o in moved:
            o.set_parent(top)
        top.update_layout()


def _read(indev, data):
    data.point.x = _pt[0]
    data.point.y = _pt[1]
    data.state = lv.INDEV_STATE.PRESSED if _pt[2] else lv.INDEV_STATE.RELEASED


def _ensure():
    global _indev
    if _indev is None:
        _indev = lv.indev_create()
        _indev.set_type(lv.INDEV_TYPE.POINTER)
        _indev.set_read_cb(_read)


def steps(ms=300):
    """Run the panel loop for ms, as panel.run() would."""
    end = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        if panel.P is not None:
            panel.P.step()
        lv.task_handler()
        time.sleep_ms(1)


def tap(x, y, ms=80, after=500):
    """Press at (x, y) for ms (LONG_MS or more for a long press), release, then run the loop."""
    _ensure()
    _pt[0] = x
    _pt[1] = y
    _pt[2] = True
    steps(ms)
    _pt[2] = False
    steps(after)
