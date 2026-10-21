"""
Party games on the simulated wand: the vendored party.py, splatpair.py and
splat_api.py over py/shims/splat_hub.py, with the other wand's side of the
pw_* protocol played by hand-written frames.

js/peers.js is the full peer; tests/js/peers.test.mjs covers it, and
tools/sim_run.mjs runs the two together.
"""

from __future__ import annotations

import asyncio
import json

import pytest

WAND = "02:00:00:00:0a:01"
PEER = "02:00:00:00:0b:01"
PEER_SPLAT = 0


class Air:
    """The bus: records what the wand sends, ACKs every unicast."""

    def __init__(self, sim_state):
        self.sim_state = sim_state
        self.sent = []          # (dst, dict)
        sim_state.set_own_mac(WAND)
        sim_state.set_radio_tx(self.tx)

    def tx(self, src, dst, payload_hex):
        try:
            self.sent.append((dst, json.loads(bytes.fromhex(payload_hex))))
        except ValueError:
            pass
        return 1

    def frames(self, t, dst=None):
        return [d for to, d in self.sent
                if d.get("type") == t and (dst is None or to == dst)]

    def deliver(self, obj, src=PEER):
        self.sim_state.deliver_enow(src, json.dumps(obj).encode())

    async def wait_for(self, t, dst=None, n=1, timeout=3.0):
        loop = asyncio.get_event_loop()
        end = loop.time() + timeout
        while len(self.frames(t, dst)) < n:
            if loop.time() > end:
                raise AssertionError("no %s (sent: %s)" % (t, [d.get("type") for _, d in self.sent]))
            await asyncio.sleep(0.005)
        return self.frames(t, dst)[n - 1]


@pytest.fixture
def air(runtime):
    a = Air(runtime.sim_state)
    yield a
    runtime.sim_state.set_radio_tx(None)


@pytest.fixture
def writes():
    import splat_hub
    out = []
    splat_hub.set_write_callback(lambda mac, op, args: out.append((mac, op, json.loads(args))))
    yield out
    splat_hub.set_write_callback(None)


async def _lead_with_peer(rt, air, game):
    """Start `game` on the wand, which leads; the peer joins with one Splat."""
    rt.load_game(game)
    task = await rt.start()
    await air.wait_for("pw_find")
    lobby = await air.wait_for("pw_lobby")
    air.deliver({"type": "pw_join", "id": lobby["id"], "splats": 1})
    joined = await air.wait_for("pw_joined", PEER)
    return task, lobby["id"], joined


async def _press_wand_button(rt):
    rt.sim_state.set_button(True)
    await asyncio.sleep(0.02)
    rt.sim_state.set_button(False)
    await asyncio.sleep(0.02)


async def _stop(rt, task):
    rt.sim_state.tap_nfc("stop")
    await asyncio.wait_for(task, 3.0)


def test_capabilities_of_the_party_games(runtime):
    for game, smin in (("partytest", 2), ("splattag", 2), ("relaycolor", 1)):
        runtime.load_game(game)
        caps = runtime.get_capabilities()
        assert caps["party"] is True and caps["splats_min"] == smin
        assert caps["local_splats"] == 1


def test_local_splat_macs(runtime):
    runtime.sim_state.set_own_mac(WAND)
    assert runtime.local_splat_macs() == ["5A:00:0A:01:00:00"]
    runtime.set_local_splats(2)
    assert runtime.local_splat_macs() == ["5A:00:0A:01:00:00", "5A:00:0A:01:00:01"]
    with pytest.raises(ValueError):
        runtime.set_local_splats(3)


def test_game_splats_set_by_the_host(runtime):
    game = "SPLATS_MIN = 1\ndef play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):\n    pass\n"
    runtime.set_game_splats(2)
    runtime.load_game(game)
    assert runtime.get_capabilities()["local_splats"] == 2
    # A restart reloads the same source and keeps a count set meanwhile.
    runtime.set_local_splats(0)
    runtime.load_game(game)
    assert runtime.get_capabilities()["local_splats"] == 0
    # A new setting, or another game, starts from the setting again.
    runtime.set_game_splats(1)
    runtime.load_game(game)
    assert runtime.get_capabilities()["local_splats"] == 1
    runtime.set_local_splats(2)
    runtime.load_game("relaycolor")
    assert runtime.get_capabilities()["local_splats"] == 1
    with pytest.raises(ValueError):
        runtime.set_game_splats(3)


async def test_partytest_wand_leads(runtime, air, writes):
    rt = runtime
    task, gid, joined = await _lead_with_peer(rt, air, "partytest")
    assert joined["first"] == 1
    assert [w[2] for w in joined["wands"]] == [1, 1]

    # The leader's button starts the game once the lobby has SPLATS_MIN.
    await _press_wand_button(rt)
    start = await air.wait_for("pw_start", PEER)
    assert start["id"] == gid and start["pool"] == 2
    assert [w[0] for w in start["wands"]] == ["02:00:00:00:0A:01", "02:00:00:00:0B:01"]
    assert rt.net is not None and rt.net.is_leader

    # Button: pool Splat 0 (the wand's own) in the leader's identity color.
    writes.clear()
    await _press_wand_button(rt)
    await asyncio.sleep(0.05)
    assert ("5A:00:0A:01:00:00", "leds", [0, 255, 0]) in writes   # 0x01 % 6 -> turngreen

    # Button again: pool Splat 1 is the peer's, so it goes out as pw_cmd.
    await _press_wand_button(rt)
    cmd = await air.wait_for("pw_cmd", PEER)
    assert (cmd["s"], cmd["op"], cmd["v"]) == (PEER_SPLAT, "color", "turngreen")

    # A press on the peer's Splat: lit for its owner (0x01 -> turngreen too).
    air.deliver({"type": "pw_hb", "id": gid, "l": 1})
    air.deliver({"type": "pw_evt", "id": gid, "q": 1, "s": 1, "e": 1})
    await air.wait_for("pw_cmd", PEER, n=2)

    await _stop(rt, task)
    assert air.frames("pw_end", PEER)


async def test_wand_follows_a_leader(runtime, air, writes):
    rt = runtime
    rt.load_game("partytest")
    task = await rt.start()
    find = await air.wait_for("pw_find")
    assert find["g"] == "partytest"
    air.deliver({"type": "pw_lobby", "g": "partytest", "id": 77, "n": 1, "min": 2, "max": None})
    join = await air.wait_for("pw_join", PEER)
    assert join == {"type": "pw_join", "id": 77, "splats": 1}
    air.deliver({"type": "pw_joined", "id": 77, "first": 1,
                 "wands": [[PEER.upper(), "turngreen", 1], [WAND.upper(), "turngreen", 1]]})
    air.deliver({"type": "pw_start", "id": 77, "pool": 2,
                 "wands": [[PEER.upper(), "turngreen", 1], [WAND.upper(), "turngreen", 1]]})
    await air.wait_for("pw_hb")
    for _ in range(100):
        if rt.net is not None:
            break
        await asyncio.sleep(0.01)
    assert rt.net is not None and not rt.net.is_leader and rt.net.me == 1

    # The leader drives this wand's Splat through pw_cmd.
    writes.clear()
    air.deliver({"type": "pw_cmd", "id": 77, "q": 5, "s": 0, "op": "color", "v": "turnblue"})
    for _ in range(100):
        if writes:
            break
        await asyncio.sleep(0.01)
    assert writes[0] == ("5A:00:0A:01:00:00", "leds", [0, 0, 255])

    # A press on this wand's Splat goes to the leader as pw_evt, pool index 1.
    import splat_hub
    splat_hub.press("5A:00:0A:01:00:00")
    evt = await air.wait_for("pw_evt", PEER)
    assert (evt["s"], evt["e"]) == (1, 1)

    # The leader ends the game: play() returns, no pw_leave goes back.
    air.deliver({"type": "pw_end", "id": 77})
    await asyncio.wait_for(task, 3.0)
    assert not air.frames("pw_leave")


async def test_relaycolor_passes_the_token(runtime, air, writes):
    rt = runtime
    task, gid, _ = await _lead_with_peer(rt, air, "relaycolor")
    await _press_wand_button(rt)
    await air.wait_for("pw_start", PEER)
    await asyncio.sleep(0.05)
    assert ("5A:00:0A:01:00:00", "leds", [255, 0, 0]) in writes   # the leader holds turnred
    # A press on the wand's own Splat passes the token to the peer.
    import splat_hub
    splat_hub.press("5A:00:0A:01:00:00")
    msg = await air.wait_for("pw_msg", PEER)
    assert msg["d"] == {"relay": 1}
    # The peer passes it back.
    air.deliver({"type": "pw_msg", "id": gid, "q": 1, "d": {"relay": 2}})
    await asyncio.sleep(0.05)
    assert ("5A:00:0A:01:00:00", "leds", [0, 0, 255]) in writes
    await _stop(rt, task)


async def test_unplugged_splat_reports_in_the_heartbeat(runtime, air, writes):
    rt = runtime
    task, gid, _ = await _lead_with_peer(rt, air, "splattag")
    await _press_wand_button(rt)
    await air.wait_for("pw_start", PEER)
    import splat_hub
    hb = await air.wait_for("pw_hb", n=len(air.frames("pw_hb")) + 1)
    assert hb["l"] == 1
    splat_hub.set_ready("5A:00:0A:01:00:00", False)
    hb = await air.wait_for("pw_hb", n=len(air.frames("pw_hb")) + 1)
    assert hb["l"] == 0
    await _stop(rt, task)


async def test_lobby_stop_card_cancels(runtime, air):
    rt = runtime
    rt.load_game("partytest")
    task = await rt.start()
    await air.wait_for("pw_lobby")
    rt.sim_state.tap_nfc("stop")
    await asyncio.wait_for(task, 3.0)
    assert rt.party_end == "left"
