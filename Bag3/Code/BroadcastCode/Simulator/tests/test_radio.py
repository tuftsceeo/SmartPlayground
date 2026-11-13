"""
The bus-backed radio stack: the real espnow_manager.py (vendored, through
the transform) over py/shims/espnow.py, and the capabilities that decide
which <sim-room> panels appear.
"""

from __future__ import annotations

import asyncio
import json

import pytest


async def _manager():
    from espnow_manager import ESPNowManager
    mgr = await ESPNowManager()
    await mgr.init()
    return mgr


def _bus(sim_state):
    """Attach a fake host bus; returns the list of (src, dst, bytes) sent."""
    sent = []

    def tx(src, dst, payload_hex):
        sent.append((src, dst, bytes.fromhex(payload_hex)))
        return 1

    sim_state.set_radio_tx(tx)
    return sent


async def test_own_mac_comes_from_sim_state(runtime):
    import sim_state
    import espnow_manager
    sim_state.set_own_mac("02:00:00:00:00:2A")
    assert await espnow_manager.get_own_mac() == "02:00:00:00:00:2A"


async def test_dict_broadcast_goes_out_as_json(runtime):
    import sim_state
    sent = _bus(sim_state)
    try:
        mgr = await _manager()
        assert await mgr.broadcast({"type": "goal", "team": "blue"}) is True
    finally:
        sim_state.set_radio_tx(None)
    assert sent == [(sim_state.own_mac, "ff:ff:ff:ff:ff:ff",
                     json.dumps({"type": "goal", "team": "blue"}).encode())]


async def test_unicast_needs_peer_and_acks_from_bus(runtime):
    import sim_state
    sent = _bus(sim_state)
    try:
        mgr = await _manager()
        # The real manager does not add a peer in send_to; the radio refuses
        # an unknown peer, and the manager reports False.
        assert await mgr.send_to("02:00:00:00:00:09", {"type": "x"}) is False
        await mgr.add_peer("02:00:00:00:00:09")
        assert await mgr.send_to("02:00:00:00:00:09", {"type": "x"}) is True
    finally:
        sim_state.set_radio_tx(None)
    assert [s[1] for s in sent] == ["02:00:00:00:00:09"]


@pytest.mark.parametrize("payload, expected_type", [
    ({"type": "goal", "team": "green"}, "raw"),
    ({"type": "start_game", "name": "jump"}, "start_game"),
    ({"type": "start_game"}, "raw"),
    ({"type": "stop"}, "stop"),
    (["stop"], "stop"),
])
async def test_poll_classification(runtime, payload, expected_type):
    import sim_state
    mgr = await _manager()
    sim_state.deliver_enow("02:00:00:00:00:05", json.dumps(payload).encode())
    msg_type, data, mac = await mgr.poll()
    assert msg_type == expected_type
    assert data == payload
    assert mac == "02:00:00:00:00:05".upper()


async def test_find_device_only_for_this_mac(runtime):
    import sim_state
    sim_state.set_own_mac("02:00:00:00:00:07")
    mgr = await _manager()
    sim_state.deliver_enow("02:00:00:00:00:01", json.dumps(
        {"type": "find_device", "mac": "02:00:00:00:00:08"}).encode())
    assert (await mgr.poll())[0] is None
    sim_state.deliver_enow("02:00:00:00:00:01", json.dumps(
        {"type": "find_device", "mac": "02:00:00:00:00:07"}).encode())
    msg_type, data, _ = await mgr.poll()
    assert msg_type == "start_game" and data["name"] == "finddevice"


async def test_blocking_poll_waits_for_a_frame(runtime):
    import sim_state
    mgr = await _manager()

    async def later():
        await asyncio.sleep(0.01)
        sim_state.deliver_enow("02:00:00:00:00:03", b"hello")

    asyncio.ensure_future(later())
    msg_type, data, _ = await mgr.poll(2000)
    assert (msg_type, data) == ("raw", b"hello")
    assert await mgr.poll(20) == (None, None, None)


def test_panel_messages_encode_like_hub_messages(runtime):
    import sim_state
    enc = sim_state.encode_panel_message
    assert json.loads(enc("stop")) == {"type": "stop"}
    assert json.loads(enc("start_game", b"goalrace")) == {"type": "start_game", "name": "goalrace"}
    assert enc("raw", b"FD_GO") == b"FD_GO"
    assert json.loads(enc('{"type": "winner", "team": "blue"}')) == {"type": "winner", "team": "blue"}
    with pytest.raises(ValueError):
        enc("{not json")


def test_sent_dict_readout_is_json(runtime):
    import sim_state
    assert sim_state._as_text({"type": "goal"}) == '{"type": "goal"}'


@pytest.mark.parametrize("name", ["goalrace", "color_quest", "finddevice"])
async def test_new_vendored_games_run(runtime, name):
    rt = runtime
    rt.load_game(name)
    await rt.start()
    await asyncio.sleep(0.1)
    assert rt.is_running() or rt._task.exception() is None
    await rt.stop()


def test_target_resolves(runtime):
    import target
    assert len(target.SCORE_MAC) == 6
    runtime.load_game("color_quest")


async def test_goalrace_broadcasts_goal_on_bus(runtime):
    rt = runtime
    sim_state = rt.sim_state
    sent = _bus(sim_state)
    try:
        rt.load_game("goalrace")
        await rt.start()
        await asyncio.sleep(0.05)
        sim_state.tap_nfc("teamblue")
        await asyncio.sleep(0.4)
        sim_state.tap_nfc("goal")
        for _ in range(100):
            if any(b'"goal"' in p for _, _, p in sent):
                break
            await asyncio.sleep(0.02)
        await rt.stop()
    finally:
        sim_state.set_radio_tx(None)
    goals = [json.loads(p) for _, d, p in sent if d == "ff:ff:ff:ff:ff:ff" and b'"goal"' in p]
    assert goals == [{"type": "goal", "team": "blue"}]


def test_capabilities_new_fields(runtime):
    rt = runtime
    rt.load_game("goalrace")
    caps = rt.get_capabilities()
    assert caps["lobby_game"] is False
    assert caps["local_splats"] == 1 and caps["splats_min"] is None
    assert caps["splats_max"] is None
    assert caps["uses_display"] is True
    assert caps["has_display_file"] is True

    rt.load_game("jump")
    caps = rt.get_capabilities()
    assert caps["uses_display"] is False and caps["has_display_file"] is False
    rt.set_display_source("def play(nfc, panel, enow):\n    pass\n")
    assert rt.get_capabilities()["has_display_file"] is True


def test_capabilities_splat_declarations(runtime):
    rt = runtime
    rt.load_game(
        "import time\nSPLATS_MIN = 2\nSPLATS_MAX = 4\n"
        "def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):\n"
        "    time.sleep_ms(10)\n")
    caps = rt.get_capabilities()
    assert caps["lobby_game"] is True
    assert (caps["splats_min"], caps["splats_max"]) == (2, 4)

    # There is no solo Splat path: SPLATS_LOCAL is not a declaration.
    rt.load_game("import time\nSPLATS_LOCAL = 1\n"
                 "def play(nfc, leds, buz, accel, i2c, enow, batt=None):\n"
                 "    time.sleep_ms(10)\n")
    caps = rt.get_capabilities()
    assert caps["lobby_game"] is False and caps["splats_min"] is None
