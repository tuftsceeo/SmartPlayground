"""
Splat host role on the simulated wand (Wand Module/lib/splat_host.py,
lobby_game.py host lobbies): a host leads a host game's lobby without looking
for another; a game wand only joins a host lobby and never leads one.
"""

from __future__ import annotations

import asyncio

import pytest

from test_lobby_game import Air, PEER, WAND


@pytest.fixture
def air(runtime):
    a = Air(runtime.sim_state)
    yield a
    runtime.sim_state.set_radio_tx(None)


def test_host_role_raises_the_splat_cap(runtime):
    runtime.sim_state.set_own_mac(WAND)
    with pytest.raises(ValueError):
        runtime.set_local_splats(4)
    runtime.set_role("splat_host")
    runtime.set_local_splats(4)
    assert len(runtime.local_splat_macs()) == 4
    runtime.set_role("")
    assert len(runtime.local_splat_macs()) == 2


def test_capabilities_flag_host_games(runtime):
    runtime.load_game("host_splattag")
    caps = runtime.get_capabilities()
    assert caps["lobby_game"] is True and caps["splat_host"] is True
    runtime.load_game("splattag")
    assert runtime.get_capabilities()["splat_host"] is False


async def test_host_leads_and_counts_players(runtime, air):
    rt = runtime
    rt.set_role("splat_host")
    rt.set_game_splats(4)
    rt.load_game("host_lobbytest")
    task = await rt.start()
    lobby = await air.wait_for("pw_lobby")
    assert lobby["h"] == 1 and lobby["p"] == 0 and lobby["n"] == 4
    assert not air.frames("pw_find"), "a host does not look for another lobby"
    air.deliver({"type": "pw_join", "id": lobby["id"], "splats": 0})
    joined = await air.wait_for("pw_joined", PEER)
    assert [w[2] for w in joined["wands"]] == [4, 0]
    lobby2 = await air.wait_for("pw_lobby", n=2)
    assert lobby2["p"] == 1
    # A lower-MAC leader's lobby for the same game: the host does not yield.
    air.deliver({"type": "pw_lobby", "g": "host_lobbytest", "id": 9, "n": 1, "min": 1, "max": 4},
                src="02:00:00:00:01:01")
    rt.sim_state.set_button(True)
    await asyncio.sleep(0.05)
    rt.sim_state.set_button(False)
    start = await air.wait_for("pw_start", PEER)
    assert start["h"] == 1
    task.cancel()
    with pytest.raises((asyncio.CancelledError, Exception)):
        await task


async def test_game_wand_never_leads_a_host_game(runtime, air):
    rt = runtime
    rt.set_game_splats(0)
    rt.load_game("host_lobbytest")
    task = await rt.start()
    await air.wait_for("pw_find", n=2)
    assert not air.frames("pw_lobby"), "a game wand must not open a host game's lobby"
    # A legacy (no "h") lobby for the slug is ignored; a host lobby is joined.
    air.deliver({"type": "pw_lobby", "g": "host_lobbytest", "id": 5, "n": 1, "min": 1, "max": 4})
    await asyncio.sleep(0.05)
    assert not air.frames("pw_join")
    air.deliver({"type": "pw_lobby", "g": "host_lobbytest", "id": 6, "n": 4, "min": 1, "max": 4, "h": 1, "p": 0})
    join = await air.wait_for("pw_join", PEER)
    assert join["id"] == 6 and join["splats"] == 0
    task.cancel()
    with pytest.raises((asyncio.CancelledError, Exception)):
        await task
