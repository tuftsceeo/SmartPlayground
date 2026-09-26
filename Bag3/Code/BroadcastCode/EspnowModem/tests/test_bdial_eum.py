"""CPython simulation: BDialEUM Dial -> EUM modem -> ESP-NOW -> MockWandEUM wand.

What runs for real:
  - BDialEUM/bdial_server.py: BdialServer.run(), the Dial's main loop, in a
    thread (its JSON link, UI and NFC reader replaced by fakes)
  - BDialEUM/code_link.py and code_sender.py, and espnow_manager.py
    (the host/lib copy, byte-identical to BDialEUM's; checked below)
  - EspnowModem/modem/main.py, the modem firmware, on test_sim.py's fake UART
    and fake radio (importing test_sim starts it)
  - MockWandEUM/lib/espnow_code.receive() and nfc_reader.split_prefixed(),
    on a fake wand manager bridged to that radio

What is faked: LVGL/m5ui/M5 (no screen off-device), the rotary and button,
the NFC reader (a card "appears" when the test says so) and write_text()
(captures the card text instead of writing a chip). The screen is checked
through the painter calls and the breadcrumb text bdial_server asks for.

Run: python tests/test_bdial_eum.py
"""

import filecmp
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BDIAL = os.path.join(ROOT, "BDialEUM")
sys.path.insert(0, HERE)

import test_sim as S  # noqa: E402  (installs machine/espnow fakes, boots the modem)

# ─── extra fakes the Dial needs ──────────────

S.machine.unique_id = lambda: b"\x01\x02\x03\x04\x7a\x3f"
HOST_ID = "7a3f"
WAND_MAC = bytes.fromhex("A0F262879201")
WAND2_MAC = bytes.fromhex("A0F262879202")
WAND3_MAC = bytes.fromhex("A0F262879203")


class _Any:
    """Absorbs any attribute chain or call (LVGL / m5ui widgets)."""

    def __getattr__(self, name):
        return _Any()

    def __call__(self, *a, **k):
        return _Any()


class _Btn:
    @staticmethod
    def isPressed():
        return False


class _Rotary:
    def reset_rotary_value(self):
        pass

    def get_rotary_value(self):
        return 0

    def get_rotary_status(self):
        return False


for name in ("M5", "m5ui", "lvgl", "hardware"):
    m = types.ModuleType(name)
    m.__getattr__ = lambda n: _Any()
    sys.modules[name] = m
sys.modules["M5"].begin = lambda: None
sys.modules["M5"].update = lambda: None
sys.modules["M5"].BtnA = _Btn
sys.modules["hardware"].Rotary = _Rotary
for attr in ("ALIGN", "SYMBOL", "PART", "EVENT", "TEXT_ALIGN", "obj", "roller",
             "color_hex"):
    setattr(sys.modules["lvgl"], attr, _Any())
S.machine.I2C = _Any
S.machine.Pin = _Any

# BDialEUM first, so code_link / code_sender / bdial_server come from the
# Dial tree. espnow_manager is already imported from host/lib by test_sim.
sys.path.insert(0, BDIAL)
sys.path.insert(1, os.path.join(ROOT, "MockWandEUM", "lib"))

import espnow_manager as EM  # noqa: E402

_uart_pins = []


class _RecordingUART(S.UART):
    def __init__(self, uid, baudrate, tx, rx, rxbuf):
        _uart_pins.append((tx, rx))
        super().__init__(uid, baudrate, tx, rx, rxbuf)


EM.UART = _RecordingUART

import dial_ui  # noqa: E402
import reset_log  # noqa: E402
import stats_log  # noqa: E402
import code_sender  # noqa: E402
import bdial_server as BS  # noqa: E402
import espnow_code  # noqa: E402
import game_store  # noqa: E402
import nfc_reader  # noqa: E402

dial_ui.IC.update({"serve": "[share]", "busy": "[busy]", "warn": "[warn]",
                   "fail": "[fail]", "ok": "[ok]", "open": "[>]",
                   "back": "[<]", "scan": "[scan]", "usb": "[usb]"})

TMP = tempfile.mkdtemp()
DIAL_FLASH = os.path.join(TMP, "dial")
DIAL_GAMES = os.path.join(DIAL_FLASH, "games")
WAND_GAMES = os.path.join(TMP, "wand_games")
os.makedirs(DIAL_GAMES)
os.makedirs(WAND_GAMES)
shutil.copy(os.path.join(BDIAL, "games", "tilt_tones.py"), DIAL_GAMES)
shutil.copy(os.path.join(BDIAL, "games", "tilt_tones.tags.json"), DIAL_GAMES)
BIG_SRC = os.path.join(ROOT, "MockWandEUM", "gestures.py")   # ~28 KB
shutil.copy(BIG_SRC, os.path.join(DIAL_GAMES, "gestures.py"))

reset_log.PATH = os.path.join(DIAL_FLASH, "resetlog.txt")
reset_log.MODE_PATH = os.path.join(DIAL_FLASH, "lastmode.txt")
stats_log.PATH = os.path.join(DIAL_FLASH, "stats.log")
stats_log._SINCE_PATH = os.path.join(DIAL_FLASH, "stats_since.txt")
BS.GAMES_DIR = DIAL_GAMES
BS.ACTIVE_PATH = os.path.join(DIAL_FLASH, "active.txt")
BS.INDEX_PATH = os.path.join(DIAL_GAMES, "index.json")
code_sender.ACTIVE_PATH = BS.ACTIVE_PATH
game_store.GAMES_DIR = WAND_GAMES

espnow_code.GET_WAIT_MS = 150
espnow_code.OFFER_WAIT_MS = 400
espnow_code.REQ_JITTER_MS = 30
BS.RESULT_HOLD_OK_MS = 1500     # long enough that a pull overlaps the hold


# ─── fake Dial peripherals ───────────────────

class FakeLink:
    """JsonLink stand-in: records sent JSON, feeds queued commands."""

    def __init__(self, on_command, debug=False):
        self.on_command = on_command
        self.lock = threading.Lock()
        self.sent = []
        self.inbox = []

    def send(self, obj):
        json.dumps(obj)            # must be encodable, as on the device
        with self.lock:
            self.sent.append(obj)

    def pump(self, idle_ms=20, drain_ms=40):
        with self.lock:
            cmds, self.inbox = self.inbox, []
        for c in cmds:
            self.on_command(c)
        time.sleep(0.001)
        return len(cmds)

    def command(self, cmd):
        with self.lock:
            self.inbox.append(cmd)

    def of_type(self, t):
        with self.lock:
            return [m for m in self.sent if m.get("type") == t]


class FakeUI:
    """Records painter calls; share_crumb() is the real formatter."""

    def __init__(self, inputs=None):
        self.lock = threading.Lock()
        self.calls = []
        self.crumbs = []

    def share_crumb(self, state, wands=0, host_id=""):
        return dial_ui.DialUI.share_crumb(self, state, wands, host_id)

    def set_share_crumb(self, text):
        with self.lock:
            self.crumbs.append(text)

    def paint_tag_list(self, entries, cursor, crumb="Tag Writer"):
        with self.lock:
            self.calls.append(("paint_tag_list", entries, cursor))
            self.crumbs.append(crumb)

    def __getattr__(self, name):
        def f(*a, **k):
            with self.lock:
                self.calls.append((name,) + a)
        return f

    def last_crumb(self):
        with self.lock:
            return self.crumbs[-1] if self.crumbs else None


class FakeNfc:
    def __init__(self):
        self.next_tag = None

    def detect_tag(self, timeout=80):
        t, self.next_tag = self.next_tag, None
        time.sleep(0.005)
        return t

    def antenna_on(self):
        pass

    def antenna_off(self):
        pass

    def antenna_is_on(self):
        return False

    def crypto_on(self):
        return False

    def stop_crypto1(self):
        pass


written_cards = []


def fake_write_text(nfc, tag, text):
    written_cards.append(text)
    return True


BS.JsonLink = FakeLink
BS.DialUI = FakeUI
BS.make_reader = FakeNfc
BS.existing_text = lambda nfc, tag: ""
BS.write_text = fake_write_text


# ─── fake wand on the simulated air ──────────

class Bridge:
    """Moves frames the modem's radio sent into the wands' inboxes."""

    def __init__(self):
        self.wands = {}
        self.stop = False
        self.t = threading.Thread(target=self._loop, daemon=True)
        self.t.start()

    def _loop(self):
        while not self.stop:
            radio = S.radio()
            moved = False
            while radio is not None and radio.air:
                mac, data, sync = radio.air.pop(0)
                for wmac, w in list(self.wands.items()):
                    if mac == S.BCAST or mac == wmac:
                        w.deliver(data)
                moved = True
            if not moved:
                time.sleep(0.0005)


BRIDGE = Bridge()


class FakeWand:
    """ESPNowManager stand-in for the wand, poll() contract as the real one."""

    def __init__(self, mac):
        self.mac = mac
        self.mac_str = ":".join("%02X" % b for b in mac)
        self.lock = threading.Lock()
        self.inbox = []
        self.peers = set()
        self.is_active = True
        BRIDGE.wands[mac] = self

    def deliver(self, data):
        with self.lock:
            self.inbox.append(bytes(data))

    def poll(self, timeout_ms=0):
        with self.lock:
            data = self.inbox.pop(0) if self.inbox else None
        if data is None:
            return None, None, None
        modem = EM.get_own_mac()
        try:
            return "raw", json.loads(data), modem
        except (ValueError, UnicodeError):
            return "raw", data, modem

    def _air(self, dst, data):
        if isinstance(data, (dict, list)):
            data = json.dumps(data)
        if isinstance(data, str):
            data = data.encode()
        if dst in ("FF:FF:FF:FF:FF:FF", EM.get_own_mac()):
            S.radio().inject(self.mac, data)
        return True

    def broadcast(self, data):
        return self._air("FF:FF:FF:FF:FF:FF", data)

    def send_to(self, mac_str, data):
        assert mac_str in self.peers, "send_to %s without add_peer" % mac_str
        return self._air(mac_str, data)

    def add_peer(self, mac_str):
        self.peers.add(mac_str)

    def remove_peer(self, mac_str):
        self.peers.discard(mac_str)


def wait_for(cond, timeout=10.0, what="condition"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return
        time.sleep(0.01)
    raise AssertionError("timed out waiting for %s" % what)


def same(a, b):
    with open(a, "rb") as fa, open(b, "rb") as fb:
        return fa.read() == fb.read()


# ─── start the Dial ──────────────────────────

SRV = BS.BdialServer()
SRV.code.sender.games_dir = DIAL_GAMES
SRV.code.sender.verbose = False
_dial_error = []


def _run_dial():
    try:
        SRV.run()
    except BaseException as e:      # surfaced by the tests, not swallowed
        _dial_error.append(e)
        raise


DIAL_T = threading.Thread(target=_run_dial, daemon=True)
DIAL_T.start()


def link():
    return SRV.link


def check_dial_alive():
    assert not _dial_error, "Dial loop died: %r" % (_dial_error,)
    assert DIAL_T.is_alive(), "Dial loop exited"


# ─── tests ───────────────────────────────────

def test_copies_match_host():
    for rel, src in (("code_sender.py", "host/code_sender.py"),
                     ("espnow_manager.py", "host/lib/espnow_manager.py"),
                     ("eum_proto.py", "host/lib/eum_proto.py")):
        assert filecmp.cmp(os.path.join(BDIAL, rel), os.path.join(ROOT, src),
                           shallow=False), "BDialEUM/%s differs from %s" % (rel, src)


def test_boot_modem_up_and_identity():
    wait_for(lambda: link().of_type("identity") and SRV._mode == BS.MODE_WRITE,
             what="Dial boot")
    check_dial_alive()
    ident = link().of_type("identity")[0]
    assert ident["device"] == "broadcast_dial", ident
    assert ident["variant"] == "eum" and ident["host_id"] == HOST_ID, ident
    assert _uart_pins == [(2, 1)], _uart_pins      # dial_board EUM pins
    modem_events = link().of_type("modem")
    assert modem_events and modem_events[0]["up"] is True, modem_events
    assert SRV.code.linked
    assert link().of_type("mode")[-1]["ssid"] is None
    # DONE / Enable Share is gone; top level is games + utilities only.
    assert "DONE" not in SRV._entries, SRV._entries
    assert SRV.ui.last_crumb() == "[share] Sharing " + HOST_ID, SRV.ui.last_crumb()


def _write_getcode_card(slug):
    """Drive the menu to the game's getcode row and let a card appear."""
    group = [t for t, _ in SRV._groups].index(
        SRV._index[slug].get("name") or slug)
    written_before = len(written_cards)
    # Top-level cursor to the group, open it, row 0 is getcode:<slug>.
    SRV._cursor = group
    SRV._input.enqueue(BS.ACT)
    wait_for(lambda: SRV._write_state == BS.W_GROUP, what="group open")
    assert SRV._current_entry() == "getcode:" + slug, SRV._current_entry()
    SRV._input.enqueue(BS.ACT)
    wait_for(lambda: SRV._write_state == BS.W_SCAN, what="scan")
    SRV.nfc.next_tag = {"uid_hex": "04AABBCC", "sak": 0, "tag_type": "ntag"}
    wait_for(lambda: len(written_cards) > written_before, what="card write")
    return written_cards[-1]


def _wand_pull(wand, card_text):
    """What MockWandEUM main.py does on a getcode tap."""
    head, slug, host = nfc_reader.split_prefixed(card_text)
    assert head == "getcode", card_text
    return espnow_code.receive(wand, slug=slug, hubtype="wand",
                               verbose=False, host_id=host)


def test_card_then_pull_during_result_hold():
    card = _write_getcode_card("gestures")
    assert card == "getcode:gestures@" + HOST_ID, card
    # The Dial is now holding the "Written!" screen (RESULT_HOLD_OK_MS);
    # the pull must still be served during it.
    assert SRV._write_state == BS.W_SCAN
    wand = FakeWand(WAND_MAC)
    pulls_before = len(link().of_type("pull"))
    t0 = time.monotonic()
    r = _wand_pull(wand, card)
    assert r is True, (r, espnow_code.LAST_STATS)
    assert time.monotonic() - t0 < BS.RESULT_HOLD_OK_MS / 1000 + 5
    assert same(os.path.join(DIAL_GAMES, "gestures.py"),
                os.path.join(WAND_GAMES, "gestures.py"))
    wait_for(lambda: len(link().of_type("pull")) > pulls_before, what="pull event")
    ev = link().of_type("pull")[-1]
    assert ev["ok"] is True and ev["slug"] == "gestures", ev
    assert ev["mac"] == wand.mac_str and ev["bytes"] == os.path.getsize(BIG_SRC), ev
    wait_for(lambda: SRV._write_state == BS.W_GROUP, what="hold end")
    with open(stats_log.PATH) as f:
        assert "gestures" in f.read()
    assert SRV._pulls_total >= 1
    check_dial_alive()


def test_crumb_tracks_transfer():
    SRV._input.enqueue(BS.BACK)
    wait_for(lambda: SRV._write_state == BS.W_MENU, what="back to menu")
    SRV.ui.crumbs.clear()
    wand = FakeWand(WAND2_MAC)
    os.remove(os.path.join(WAND_GAMES, "gestures.py"))
    assert _wand_pull(wand, "getcode:gestures@" + HOST_ID) is True
    wait_for(lambda: SRV.ui.last_crumb() == "[share] Sharing " + HOST_ID,
             what="crumb back to ready")
    assert "[busy] Sending" in SRV.ui.crumbs, SRV.ui.crumbs


def test_pinned_to_other_host_ignored():
    wand = FakeWand(WAND3_MAC)
    ignored = SRV.code.sender.ignored
    r = _wand_pull(wand, "getcode:gestures@beef")
    assert r == "nohost", r
    assert SRV.code.sender.ignored >= ignored + 1
    assert not SRV.code.sender.sessions
    assert not EM.get_own_mac() in wand.peers


def test_unpinned_and_refusal():
    wand = FakeWand(WAND3_MAC)
    assert espnow_code.receive(wand, slug="tilt_tones", hubtype="wand",
                               verbose=False) is True
    assert espnow_code.receive(wand, slug="nosuch", hubtype="wand",
                               verbose=False, host_id=HOST_ID) == "norequest"
    # The refusal's remove_peer runs after the send the wand already answered.
    wait_for(lambda: SRV.code.mgr.get_peer_macs() == [], what="peer removed")


def test_three_wands_at_once():
    # One slug per wand: the simulated wands share one games directory, so
    # the same slug would collide on its .part file (real wands do not).
    for i in range(3):
        shutil.copy(BIG_SRC, os.path.join(DIAL_GAMES, "g%d.py" % i))
    wands = [FakeWand(bytes.fromhex("02000000B0%02X" % i)) for i in range(3)]
    results = [None] * 3

    def run(i):
        results[i] = _wand_pull(wands[i], "getcode:g%d@%s" % (i, HOST_ID))

    threads = [threading.Thread(target=run, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert results == [True] * 3, (results, espnow_code.LAST_STATS)
    wait_for(lambda: not SRV.code.sender.sessions, what="sessions closed")
    assert SRV.code.mgr.get_peer_macs() == []


def test_json_arm_disarm_info():
    n = len(link().sent)
    link().command({"cmd": "arm", "id": 11})
    link().command({"cmd": "disarm", "id": 12})
    link().command({"cmd": "info", "id": 13})
    wait_for(lambda: len([m for m in link().sent[n:] if m.get("id") in (11, 12, 13)]) == 3,
             what="replies")
    by_id = {m["id"]: m for m in link().sent[n:] if m.get("id") in (11, 12, 13)}
    assert by_id[11]["type"] == "ok" and by_id[11]["modem"] is True, by_id[11]
    assert by_id[12]["type"] == "error" and by_id[12]["code"] == "always_serving"
    info = by_id[13]
    assert info["modem"] is True and info["served"] >= 5 and info["wands"] == 0, info
    assert SRV._mode == BS.MODE_WRITE


def test_modem_reset_recovers():
    """Modem reboots mid-session: the Dial's link restores and serving resumes."""
    boots = S._state["boots"]
    # Same mechanism test_sim uses: repeated loop faults reset the modem.
    S.radio().fail_irecv = S._modem_globals["g"]["FAULT_LIMIT"] + 1
    S.wait_boot(boots + 1)
    wand = FakeWand(WAND_MAC)
    os.remove(os.path.join(WAND_GAMES, "tilt_tones.py"))
    r = None
    deadline = time.monotonic() + 15
    while r is not True and time.monotonic() < deadline:
        r = _wand_pull(wand, "getcode:tilt_tones@" + HOST_ID)
    assert r is True, r
    assert EM._link.resets_seen >= 1
    check_dial_alive()


def test_shutdown():
    SRV.running = False
    DIAL_T.join(5)
    assert not DIAL_T.is_alive()
    assert not _dial_error, _dial_error
    assert not SRV.code.mgr.is_active


if __name__ == "__main__":
    tests = [test_copies_match_host, test_boot_modem_up_and_identity,
             test_card_then_pull_during_result_hold, test_crumb_tracks_transfer,
             test_pinned_to_other_host_ignored, test_unpinned_and_refusal,
             test_three_wands_at_once, test_json_arm_disarm_info,
             test_modem_reset_recovers, test_shutdown]
    try:
        for fn in tests:
            fn()
            print("ok  ", fn.__name__)
    finally:
        BRIDGE.stop = True
        S._stop.set()
        shutil.rmtree(TMP)
    print("%d passed" % len(tests))
