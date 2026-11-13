"""
Golden-frame tests — CPython asyncio harness (no Pyodide).

Loads shims + fake devices + transformed games, scripts accelerometer /
button input, and asserts LED frames light up as expected.
"""

from __future__ import annotations

import asyncio

import pytest


def _lit_count(frame):
    return sum(1 for p in frame if any(c > 0 for c in p))


def _any_lit(frame):
    return _lit_count(frame) > 0


async def _pump(rt, seconds=0.05):
    """Let the game loop run briefly."""
    await asyncio.sleep(seconds)


async def _run_until(rt, predicate, timeout=3.0, step=0.02):
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(step)
    return predicate()


@pytest.mark.asyncio
async def test_jump_freefall_lights_leds(runtime):
    rt = runtime
    rt.sim_state.set_accel(0.0, 1.0, 0.0)

    rt.load_game("jump")
    await rt.start()

    await _pump(rt, 0.15)

    # Freefall pulse — magnitude ~0 triggers jump detection.
    rt.sim_state.set_accel(0.0, 0.0, 0.0)
    await _pump(rt, 0.1)
    # Restore gravity so in_jump clears and level is rendered.
    rt.sim_state.set_accel(0.0, 1.0, 0.0)
    await _pump(rt, 0.15)

    lit = await _run_until(rt, lambda: _any_lit(rt.sim_state.led_frame), timeout=2.0)
    count = _lit_count(rt.sim_state.led_frame)
    await rt.stop()
    assert lit, "expected at least one LED lit after freefall jump"
    assert count >= 1


@pytest.mark.asyncio
async def test_shake_fills_leds(runtime):
    rt = runtime
    rt.sim_state.set_accel(0.0, 1.0, 0.0)
    rt.load_game("shake")
    await rt.start()
    await _pump(rt, 0.15)

    # Strong shake: magnitude - 1 should be large → high fill level.
    rt.sim_state.set_accel(3.0, 3.0, 3.0)
    await _pump(rt, 0.2)

    ok = await _run_until(
        rt, lambda: _lit_count(rt.sim_state.led_frame) >= 5, timeout=2.0
    )
    await rt.stop()
    assert ok, "expected shake fill to light several LEDs, got %d" % _lit_count(
        rt.sim_state.led_frame
    )


@pytest.mark.asyncio
async def test_shake_rainbow_fills(runtime):
    rt = runtime
    rt.load_game("shake_rainbow")
    await rt.start()
    await _pump(rt, 0.15)
    rt.sim_state.set_accel(4.0, 4.0, 4.0)
    ok = await _run_until(rt, lambda: _any_lit(rt.sim_state.led_frame), timeout=2.0)
    await rt.stop()
    assert ok


@pytest.mark.asyncio
async def test_sound_button_lights_shape(runtime):
    rt = runtime
    rt.load_game("sound")
    await rt.start()
    await _pump(rt, 0.15)

    rt.sim_state.set_button(True)
    ok = await _run_until(rt, lambda: _any_lit(rt.sim_state.led_frame), timeout=2.0)
    rt.sim_state.set_button(False)
    await rt.stop()
    assert ok, "holding button in sound game should show a note shape"


@pytest.mark.asyncio
async def test_rainbow_shows_pattern(runtime):
    rt = runtime
    rt.sim_state.set_battery(volts=3.9, soc=70)
    rt.load_game("rainbow")
    await rt.start()
    ok = await _run_until(rt, lambda: _any_lit(rt.sim_state.led_frame), timeout=3.0)
    await rt.stop()
    assert ok, "rainbow game should light LEDs (battery bar or rainbow)"


@pytest.mark.asyncio
async def test_enow_stop_ends_game(runtime):
    rt = runtime
    rt.load_game("jump")
    task = await rt.start()
    await _pump(rt, 0.1)
    rt.sim_state.enqueue_enow("stop")
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
    except asyncio.TimeoutError:
        await rt.stop()
        pytest.fail("game did not stop after enow stop message")
    assert task.done()


@pytest.mark.asyncio
async def test_get_commands_nonempty(runtime):
    rt = runtime
    rt.load_game("jump")
    cmds = rt.get_commands()
    assert isinstance(cmds, list)
    assert len(cmds) >= 1
