"""
Patch CPython's `time` module with MicroPython-compatible helpers.

sleep_ms / sleep_us / sleep become async wrappers over asyncio.sleep so
transformed game loops can await them without blocking the event loop.
ticks_* use time.monotonic for a stable millisecond clock.
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


def set_time_scale(k):
    global _SCALE
    _SCALE = max(1e-6, float(k))


def get_time_scale():
    return _SCALE


async def sleep_ms(ms):
    await asyncio.sleep(max(0, float(ms)) / 1000.0 / _SCALE)


async def sleep_us(us):
    await asyncio.sleep(max(0, float(us)) / 1_000_000.0 / _SCALE)


async def sleep(seconds):
    await asyncio.sleep(max(0, float(seconds)) / _SCALE)


def ticks_ms():
    return int((_time.monotonic() - _BOOT) * 1000 * _SCALE + _UPTIME_OFFSET_MS) & 0x3FFFFFFF


def ticks_us():
    return int((_time.monotonic() - _BOOT) * 1_000_000 * _SCALE + _UPTIME_OFFSET_MS * 1000) & 0x3FFFFFFF


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
