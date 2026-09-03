"""Shared fixtures for Simulator tests."""

from __future__ import annotations

import os
import sys

import pytest

SIM_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PY_DIR = os.path.join(SIM_ROOT, "py")


@pytest.fixture(scope="session")
def sim_root():
    return SIM_ROOT


@pytest.fixture
def runtime():
    """Fresh Runtime bootstrapped against on-disk vendor/ + shims."""
    # Isolate from other tests' sys.modules pollution.
    for name in list(sys.modules):
        if name in (
            "sim_state", "machine", "neopixel", "_thread", "network",
            "espnow", "ubluetooth", "micropython", "time_patch",
            "lis2dw12", "max17048", "opt3002", "pn532", "nfc_reader",
            "espnow_manager", "brightness", "hubtype", "leds", "buzzer",
            "game_tags", "actions", "battery", "runtime", "transform",
            "jump", "shake", "shake_rainbow", "sound", "rainbow", "jumpin",
        ) or name.startswith("vendor"):
            del sys.modules[name]

    if PY_DIR not in sys.path:
        sys.path.insert(0, PY_DIR)

    from runtime import Runtime

    rt = Runtime()
    rt.bootstrap(workdir=os.path.join(SIM_ROOT, "vendor"))

    # Speed up tests without decoupling ticks_*() from sleep_*(): scaling both
    # by the same factor means a game that sleeps "3000ms" really only waits
    # 3000/scale real ms, but ticks_diff() still reports ~3000 — so multi-
    # second animations (melody, cooking, gestures) finish fast without
    # tripping the busy-loop watchdog in transform.py (which is keyed on
    # real wall-clock time, not on ticks_*()).
    import time_patch
    time_patch.set_time_scale(20)

    # Readable LEDs regardless of lux mapping.
    import brightness
    brightness.MULTIPLIER = 1.0
    rt.sim_state.set_ambient_lux(10000.0)
    rt.sim_state.set_battery(volts=3.9, soc=85)

    yield rt

    # Best-effort cleanup
    try:
        import asyncio as aio
        if rt.is_running():
            aio.get_event_loop().run_until_complete(rt.stop())
    except Exception:
        pass
