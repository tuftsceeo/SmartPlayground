"""
Smoke tests for the six newly-vendored games (nfc_sound, gestures,
simpleicecream, melody, cooking, multiicecream) plus a regression test for
the NFC one-shot-consume bug these games exposed (gestures.py reads NFC
twice per polling frame; nfc_sound.py exercises the tag -> visible-effect
pipeline end to end).
"""

from __future__ import annotations

import asyncio

import pytest


def _any_lit(frame):
    return any(any(c > 0 for c in p) for p in frame)


def _red_dominant(frame):
    return any(p[0] > p[1] and p[0] > p[2] and p[0] > 0 for p in frame)


async def _pump(rt, seconds=0.05):
    await asyncio.sleep(seconds)


async def _run_until(rt, predicate, timeout=2.0, step=0.02):
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(step)
    return predicate()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    ["nfc_sound", "gestures", "simpleicecream", "melody", "cooking", "multiicecream"],
)
async def test_new_game_loads_and_runs(runtime, name):
    """Each newly-vendored game loads, starts, runs a few frames without
    raising, and stops cleanly."""
    rt = runtime
    rt.load_game(name)
    await rt.start()
    await _pump(rt, 0.1)
    assert rt.is_running()
    await rt.stop()


@pytest.mark.asyncio
async def test_jumpin_loads_and_runs(runtime):
    """jumpin.py is a leftover raw-MIFARE-style revision (imports
    _decode_ndef_text/COMMON_KEYS directly rather than using NfcReader) that
    had no test coverage and failed to import until nfc_reader.py grew a
    _decode_ndef_text stub. PN532.read_passive_target() always returns None
    in the sim, so its NFC path is inert here — this only exercises button
    press + the run loop."""
    rt = runtime
    rt.load_game("jumpin")
    await rt.start()
    await _pump(rt, 0.05)
    rt.sim_state.set_button(True)
    await _pump(rt, 0.05)
    rt.sim_state.set_button(False)
    await _pump(rt, 0.05)
    assert rt.is_running()
    await rt.stop()


@pytest.mark.asyncio
async def test_nfc_sound_tag_changes_note_color(runtime):
    """nfc_sound.py reads NFC once per frame and maps the tapped note tag to
    a bell color shown while the button is held — a plain end-to-end check
    that a tapped tag is actually seen by the game."""
    rt = runtime
    rt.load_game("nfc_sound")
    await rt.start()
    await _pump(rt, 0.05)

    rt.sim_state.tap_nfc("noteg")  # -> NOTE_COLORS['G4'] = BLUE
    await _pump(rt, 0.1)  # NFC_POLL_INTERVAL=5 frames, well within the dwell window

    rt.sim_state.set_button(True)
    ok = await _run_until(rt, lambda: _any_lit(rt.sim_state.led_frame))
    frame = list(rt.sim_state.led_frame)
    rt.sim_state.set_button(False)
    await rt.stop()

    assert ok, "holding button after a tag tap should light the bell color"
    # BLUE = (0, 20, 255) — blue channel should dominate every lit pixel.
    assert all(p[2] >= p[0] and p[2] >= p[1] for p in frame if any(frame[0]))


@pytest.mark.asyncio
async def test_gestures_tag_registers_despite_double_read(runtime):
    """Regression test: gestures.py calls read_command() twice per polling
    frame (_check_stop then _poll_tag). Before the sim_state NFC dwell-window
    fix, the first call consumed the tag and the second always saw None, so
    tapping red/green/blue/play could never register. Tapping "red" should
    move the border from idle gray (WHITE_DIM) toward red."""
    rt = runtime
    rt.load_game("gestures")
    await rt.start()
    await _pump(rt, 0.05)

    rt.sim_state.tap_nfc("red")
    ok = await _run_until(rt, lambda: _red_dominant(rt.sim_state.led_frame), timeout=2.0)
    await rt.stop()

    assert ok, "tapping 'red' should be seen despite the double read-per-frame"


@pytest.mark.asyncio
async def test_simpleicecream_runs_with_button(runtime):
    rt = runtime
    rt.load_game("simpleicecream")
    await rt.start()
    await _pump(rt, 0.05)
    rt.sim_state.set_button(True)
    await _pump(rt, 0.05)
    rt.sim_state.set_button(False)
    await _pump(rt, 0.05)
    assert rt.is_running()
    await rt.stop()


@pytest.mark.asyncio
async def test_melody_records_a_note(runtime):
    """melody.py reads note_* tags every loop iteration (not throttled) and
    appends to the recorded melody, then lights up on playback."""
    rt = runtime
    rt.load_game("melody")
    await rt.start()
    await _pump(rt, 0.05)

    rt.sim_state.tap_nfc("note_c")
    await _pump(rt, 0.1)

    rt.sim_state.set_button(True)
    await _pump(rt, 0.05)
    rt.sim_state.set_button(False)

    ok = await _run_until(rt, lambda: _any_lit(rt.sim_state.led_frame), timeout=2.0)
    await rt.stop()
    assert ok, "playing back a recorded note should light the LEDs"


@pytest.mark.asyncio
async def test_cooking_scans_an_ingredient(runtime):
    rt = runtime
    rt.load_game("cooking")
    await rt.start()
    await _pump(rt, 0.05)

    rt.sim_state.tap_nfc("tomato")
    await _pump(rt, 0.1)
    assert rt.is_running()
    await rt.stop()
