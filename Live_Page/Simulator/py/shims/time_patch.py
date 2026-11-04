"""
Patch CPython's `time` module with MicroPython-compatible helpers.

sleep_ms / sleep_us / sleep become async wrappers over asyncio.sleep so
transformed game loops can await them without blocking the event loop.
ticks_* read a clock source: time.monotonic by default, or the shared
virtual clock (js/clock.js nowMs) once set_clock_source() is called, so
every simulated device measures timeouts against one time base.
"""

from __future__ import annotations

import asyncio
import time as _time

# Pretend the device has already been up for a while. Games like jump.py
# seed last_jump_time=0 and require ticks_diff(now, 0) > MIN_EVENT_SPACING
# (1s) before the first event counts — real wands are always past that.
_BOOT = _time.monotonic()
_UPTIME_OFFSET_MS = 60_000

# Virtual-time multiplier: 1.0 = real time. Tests raise this so multi-second
# in-game animations (melody, cooking, gestures) run in a fraction of the
# wall-clock time. sleep_* and ticks_* are scaled by the SAME factor, so
# ticks_diff() still reports the virtual duration a game expects while the
# real await is short enough that transform.py's busy-loop watchdog (which
# is keyed on real wall-clock time) never fires.
_SCALE = 1.0


# Optional external clock: a callable returning virtual ms (js/clock.js
# nowMs). When set, it replaces monotonic()*_SCALE for ticks_*; the source
# already includes its own scale. sleep_* still divide by _SCALE, so the
# host keeps set_time_scale() equal to the clock scale.
_SOURCE = None


def set_clock_source(fn):
    """Read ticks from *fn* (returns virtual ms); None restores monotonic."""
    global _SOURCE
    if fn is not None and not callable(fn):
        raise TypeError("clock source must be callable or None")
    _SOURCE = fn


# Or a mirror of that clock: set_clock_anchor(virtual_ms, scale) records
# where the host clock stood, and ticks run on from there on this side's
# monotonic(). The rooms use this, which keeps a JS call out of every
# ticks_ms() (a lobby game's loops make thousands a second). The host
# re-anchors periodically; ticks never step backwards across a re-anchor.
_ANCHOR = None          # (monotonic s, virtual ms, scale)
_last_ms = 0.0


def set_clock_anchor(virtual_ms, scale=1.0):
    """Mirror a host clock that read *virtual_ms* now and runs at *scale*
    virtual ms per real ms. None restores monotonic."""
    global _ANCHOR
    _ANCHOR = None if virtual_ms is None else (_time.monotonic(), float(virtual_ms), float(scale))


def _virtual_ms():
    global _last_ms
    if _SOURCE is not None:
        return float(_SOURCE())
    if _ANCHOR is not None:
        m, v, k = _ANCHOR
        now = v + (_time.monotonic() - m) * 1000 * k
        if now < _last_ms:
            now = _last_ms
        _last_ms = now
        return now
    return (_time.monotonic() - _BOOT) * 1000 * _SCALE


def set_time_scale(k):
    global _SCALE
    _SCALE = max(1e-6, float(k))


def get_time_scale():
    return _SCALE


# Sleeps started so far; transform.py's busy-loop watchdog reads it.
sleeps = 0


async def sleep_ms(ms):
    global sleeps
    sleeps += 1
    await asyncio.sleep(max(0, float(ms)) / 1000.0 / _SCALE)


async def sleep_us(us):
    global sleeps
    sleeps += 1
    await asyncio.sleep(max(0, float(us)) / 1_000_000.0 / _SCALE)


async def sleep(seconds):
    global sleeps
    sleeps += 1
    await asyncio.sleep(max(0, float(seconds)) / _SCALE)


def ticks_ms():
    return int(_virtual_ms() + _UPTIME_OFFSET_MS) & 0x3FFFFFFF


def ticks_us():
    return int((_virtual_ms() + _UPTIME_OFFSET_MS) * 1000) & 0x3FFFFFFF


def ticks_diff(a, b):
    # MicroPython-compatible signed wraparound diff on 30-bit ticks.
    return ((int(a) - int(b) + 0x20000000) & 0x3FFFFFFF) - 0x20000000


def ticks_add(t, delta):
    return (int(t) + int(delta)) & 0x3FFFFFFF


def patch_time_module(mod=None):
    """Install MicroPython time helpers onto *mod* (default: the time module)."""
    if mod is None:
        mod = _time
    mod.sleep_ms = sleep_ms
    mod.sleep_us = sleep_us
    if not hasattr(mod, "_sync_sleep"):
        mod._sync_sleep = mod.sleep
    mod.sleep = sleep
    mod.ticks_ms = ticks_ms
    mod.ticks_us = ticks_us
    mod.ticks_diff = ticks_diff
    mod.ticks_add = ticks_add
    return mod
