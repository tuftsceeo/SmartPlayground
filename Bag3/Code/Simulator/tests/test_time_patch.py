import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py", "shims"))

import time_patch


def test_clock_source_drives_ticks():
    now = [1000.0]
    time_patch.set_clock_source(lambda: now[0])
    try:
        a = time_patch.ticks_ms()
        now[0] += 250
        assert time_patch.ticks_diff(time_patch.ticks_ms(), a) == 250
        assert time_patch.ticks_us() == (1250 + time_patch._UPTIME_OFFSET_MS) * 1000
    finally:
        time_patch.set_clock_source(None)


def test_default_source_is_monotonic():
    time_patch.set_clock_source(None)
    a = time_patch.ticks_ms()
    assert time_patch.ticks_diff(time_patch.ticks_ms(), a) >= 0


def test_rejects_non_callable():
    try:
        time_patch.set_clock_source(5)
    except TypeError:
        return
    raise AssertionError("expected TypeError")
