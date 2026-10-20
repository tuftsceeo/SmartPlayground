"""CPython test: tools/devtests/espnow_serve.NativeManager under CodeSender.

Drives the real wand receiver (MockWandEUM/lib/espnow_code.py) against
host/code_sender.py with the host side on NativeManager over a fake `espnow`
module. The fake enforces what the real driver does: a unicast to a MAC that
is not a registered peer raises OSError, and the peer table holds 20.

Run: python tests/test_espnow_serve.py
"""

import os
import shutil
import sys
import tempfile
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools", "devtests"))

import test_code_xfer as T  # noqa: E402  (sets up the time/machine stubs)
import espnow_code  # noqa: E402
import game_store  # noqa: E402
import code_sender  # noqa: E402

BCAST = b"\xff\xff\xff\xff\xff\xff"


def mb(mac_str):
    return bytes(int(p, 16) for p in mac_str.split(":"))


def ms(mac_bytes):
    return ":".join("%02X" % b for b in mac_bytes)


class FakeESPNow:
    def __init__(self, air, me):
        self.air, self.me = air, me
        air.register(me)
        self.on = False
        self.peers = set()
        self.max_peers = 0
        self.sends = []

    def active(self, v=None):
        if v is None:
            return self.on
        self.on = bool(v)

    def add_peer(self, mac):
        if bytes(mac) in self.peers:
            raise OSError("ESP_ERR_ESPNOW_EXIST")
        if len(self.peers) >= T.PEER_LIMIT:
            raise OSError("ESP_ERR_ESPNOW_FULL")
        self.peers.add(bytes(mac))
        self.max_peers = max(self.max_peers, len(self.peers))

    def del_peer(self, mac):
        if bytes(mac) not in self.peers:
            raise OSError("ESP_ERR_ESPNOW_NOT_FOUND")
        self.peers.discard(bytes(mac))

    def send(self, mac, msg, sync=True):
        mac = bytes(mac)
        if mac not in self.peers:
            raise OSError("ESP_ERR_ESPNOW_NOT_FOUND")
        if isinstance(msg, str):
            msg = msg.encode()
        self.sends.append((mac, bytes(msg), sync))
        self.air.deliver(self.me, "FF:FF:FF:FF:FF:FF" if mac == BCAST else ms(mac), msg)
        return True

    def irecv(self, timeout_ms=0):
        item = self.air.take(self.me)
        if item is None:
            return None, None
        src, payload = item
        return mb(src), payload


def install_fakes(air):
    holder = {}
    espnow = types.ModuleType("espnow")
    espnow.ESPNow = lambda: holder.setdefault("e", FakeESPNow(air, T.HOST))
    network = types.ModuleType("network")

    class WLAN:
        def __init__(self, i):
            pass

        def active(self, v=None):
            return True

        def disconnect(self):
            pass

    network.WLAN = WLAN
    network.STA_IF = 0
    sys.modules["espnow"], sys.modules["network"] = espnow, network
    return holder


def setup():
    tmp = tempfile.mkdtemp()
    hg, wg = os.path.join(tmp, "h"), os.path.join(tmp, "w")
    os.mkdir(hg)
    shutil.copy(T.BIG_SRC, os.path.join(hg, "bigtest.py"))
    with open(os.path.join(hg, "tiny.py"), "w") as f:
        f.write("def play(*a):\n    return 1\n")
    game_store.GAMES_DIR = wg
    air = T.Air()
    holder = install_fakes(air)
    import espnow_serve
    espnow_serve.install_manager_shim()
    mgr = espnow_serve.NativeManager()
    mgr.init()
    sender = code_sender.CodeSender(mgr, games_dir=hg, verbose=False)
    ht = T.HostThread(mgr, sender)
    return tmp, air, T.FakeMgr(air, T.WAND), sender, ht, hg, wg, mgr, holder["e"]


def test_init_adds_broadcast_peer_only(ctx):
    mgr, enow = ctx[7], ctx[8]
    assert mgr.is_active and enow.on
    assert enow.peers == {BCAST}


def test_transfer_and_peer_cleanup(ctx):
    tmp, air, wand, sender, ht, hg, wg, mgr, enow = ctx
    assert espnow_code.receive(wand, "bigtest", "wand", verbose=False) is True
    assert T.same(os.path.join(hg, "bigtest.py"), os.path.join(wg, "bigtest.py"))
    r = T.host_result(sender)
    assert r["ok"] and r["send_fail"] == 0
    deadline = time.monotonic() + 2
    while enow.peers != {BCAST} and time.monotonic() < deadline:
        time.sleep(0.01)
    assert enow.peers == {BCAST}, enow.peers


def test_refusal_reply_reaches_wand_and_peer_removed(ctx):
    tmp, air, wand, sender, ht, hg, wg, mgr, enow = ctx
    assert espnow_code.receive(wand, "nosuch", "wand", verbose=False) == "norequest"
    deadline = time.monotonic() + 2
    while enow.peers != {BCAST} and time.monotonic() < deadline:
        time.sleep(0.01)
    assert enow.peers == {BCAST}


def test_poll_decodes_json_and_bytes(ctx):
    import espnow_serve
    m = espnow_serve.NativeManager()
    m.init()
    air = ctx[1]
    air.register("AA:00:00:00:00:01")
    air.deliver("AA:00:00:00:00:01", T.HOST, b'{"type": "x"}')
    air.deliver("AA:00:00:00:00:01", T.HOST, b"CX\x01")
    # the host thread owns the inbox; read through the module directly
    ctx[4].run.clear()
    time.sleep(0.05)
    got = [m.poll(), m.poll(), m.poll()]
    ctx[4].run.set()
    assert got[0] == ("raw", {"type": "x"}, "AA:00:00:00:00:01"), got
    assert got[1][0:2] == ("raw", b"CX\x01"), got
    assert got[2] == (None, None, None)


def test_broadcast_getcode_and_stop(ctx):
    tmp, air, wand, sender, ht, hg, wg, mgr, enow = ctx
    n = len(enow.sends)
    assert mgr.broadcast({"type": "getcode", "slug": "tiny"}) is True
    assert mgr.broadcast_stop() is True
    sent = enow.sends[n:]
    assert sent[0][0] == BCAST and sent[0][2] is False       # async, never ACKed
    assert b'"getcode"' in sent[0][1] and sent[1][1] == b'["stop"]'


def test_send_failures_return_false(ctx):
    mgr = ctx[7]
    assert mgr.send_to("02:00:00:00:00:99", {"a": 1}) is False   # not a peer
    assert mgr.send_raw(mb("02:00:00:00:00:99"), b"x") is False


def test_broadcast_retries_once_on_full_queue(ctx):
    mgr, enow = ctx[7], ctx[8]
    real, calls = enow.send, []

    def flaky(mac, msg, sync=True):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("ESP_ERR_ESPNOW_NO_MEM")
        return real(mac, msg, sync)

    enow.send = flaky
    assert mgr.broadcast(["stop"]) is True and len(calls) == 2
    enow.send = real


def test_inactive_manager_is_inert():
    import espnow_serve
    m = espnow_serve.NativeManager()
    assert m.poll() == (None, None, None)
    assert m.broadcast("x") is False and m.send_raw(b"\0" * 6, b"x") is False


def test_shim_provides_mac_helper_for_code_sender():
    import espnow_serve
    espnow_serve.install_manager_shim()
    assert sys.modules["espnow_manager"].mac_str_to_bytes("0A:0B:0C:0D:0E:0F") == \
        b"\x0a\x0b\x0c\x0d\x0e\x0f"


if __name__ == "__main__":
    espnow_code.GET_WAIT_MS = 60
    espnow_code.OFFER_WAIT_MS = 150
    espnow_code.REQ_JITTER_MS = 30
    ctx = setup()
    tests = [test_init_adds_broadcast_peer_only, test_transfer_and_peer_cleanup,
             test_refusal_reply_reaches_wand_and_peer_removed,
             test_poll_decodes_json_and_bytes, test_broadcast_getcode_and_stop,
             test_send_failures_return_false,
             test_broadcast_retries_once_on_full_queue]
    for fn in tests:
        fn(ctx)
        print("ok  ", fn.__name__)
    for fn in (test_inactive_manager_is_inert,
               test_shim_provides_mac_helper_for_code_sender):
        fn()
        print("ok  ", fn.__name__)
    ctx[4].stop = True
    shutil.rmtree(ctx[0])
    print("%d passed" % (len(tests) + 2))
