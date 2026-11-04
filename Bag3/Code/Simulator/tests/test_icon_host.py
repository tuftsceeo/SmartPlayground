"""
py/icon_host.py: the display panel's Python side, running the vendored
IconDisplay goalrace.py through IconDisplay/main.py's idle loop.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest

SIM_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DISPLAY_MAC = "02:00:00:00:0d:01"
WAND_MAC = "02:00:00:00:0a:01"


def _icon_bytes(path):
    """Parse an icon file the way icon_store does, for comparison."""
    vals = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("("):
                for grp in line.split("),"):
                    grp = grp.replace("(", "").replace(")", "").strip().strip(",")
                    if grp:
                        vals.extend(int(v) for v in grp.split(","))
    return bytes(vals)


@pytest.fixture
def host(tmp_path):
    for name in list(sys.modules):
        if name in ("sim_state", "machine", "neopixel", "_thread", "network", "espnow",
                    "micropython", "time_patch", "transform", "icon_host", "icon_matrix",
                    "icon_store", "shapes", "display_tags", "espnow_manager", "goalrace"):
            del sys.modules[name]
    cwd = os.getcwd()
    from icon_host import IconHost
    h = IconHost()
    frames, prints, sent = [], [], []
    h.set_frame_callback(lambda src_hex, inten: frames.append((bytes.fromhex(src_hex), inten)))
    h.set_print_callback(prints.append)
    h.bootstrap(workdir=str(tmp_path), mac=DISPLAY_MAC)
    import time_patch
    time_patch.set_time_scale(20)
    h.sim_state.set_radio_tx(
        lambda src, dst, p: sent.append((src, dst, bytes.fromhex(p))) or 1)
    game_dir = os.path.join(SIM_ROOT, "vendor", "display", "games")
    with open(os.path.join(game_dir, "goalrace.py")) as f:
        h.set_game("goalrace", f.read())
    icons = {}
    for fn in os.listdir(os.path.join(game_dir, "goalrace_icons")):
        with open(os.path.join(game_dir, "goalrace_icons", fn)) as f:
            icons[fn[:-3]] = f.read()
    h.set_icons("goalrace", icons)
    h.frames, h.prints, h.sent, h.game_dir = frames, prints, sent, game_dir
    yield h
    os.chdir(cwd)


async def _until(pred, timeout=3.0):
    for _ in range(int(timeout / 0.02)):
        if pred():
            return True
        await asyncio.sleep(0.02)
    return pred()


def _send(h, payload):
    h.sim_state.deliver_enow(WAND_MAC, json.dumps(payload).encode())


async def test_goal_shows_team_icon_and_announces_winner(host):
    h = host
    ready = _icon_bytes(os.path.join(h.game_dir, "goalrace_icons", "ready.py"))
    whale = _icon_bytes(os.path.join(h.game_dir, "goalrace_icons", "whale.py"))
    await h.start()
    try:
        assert await _until(lambda: h.panel is not None)
        _send(h, {"type": "start_game", "name": "goalrace"})
        assert await _until(lambda: any(f == ready for f, _ in h.frames))
        assert h.running_game == "goalrace"
        _send(h, {"type": "goal", "team": "blue"})
        assert await _until(lambda: any(f == whale for f, _ in h.frames))
        assert h.frames[-1][1] == pytest.approx(0.15)
        assert await _until(lambda: any(b'"winner"' in p for _, _, p in h.sent))
        winner = [json.loads(p) for s, d, p in h.sent if b'"winner"' in p]
        assert winner == [{"type": "winner", "team": "blue"}]
        _send(h, {"type": "stop"})
        assert await _until(lambda: h.running_game is None)
    finally:
        await h.stop()
    assert any("team blue took it" in line for line in h.prints)


async def test_unknown_game_stays_idle(host):
    h = host
    await h.start()
    try:
        assert await _until(lambda: h.panel is not None)
        _send(h, {"type": "start_game", "name": "nosuch"})
        assert await _until(lambda: any("no game 'nosuch'" in p for p in h.prints))
        assert h.is_running()
    finally:
        await h.stop()


async def test_icons_written_where_icon_store_reads(host):
    import icon_store
    from icon_host import icon_text
    h = host
    duty = [7] * 768
    h.set_icons("goalrace", {"whale": duty})
    assert os.path.isfile("goalrace_icons/whale.py")
    assert bytes(icon_store.read_icon("whale")) == bytes(duty)
    assert icon_text(duty).startswith("SIZE = (16, 16)")


def test_bad_game_refused_at_install(host):
    with pytest.raises(SyntaxError):
        host.set_game("broken", "def play(:\n")
