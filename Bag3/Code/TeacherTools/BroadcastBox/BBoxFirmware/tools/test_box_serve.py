"""Off-device check of the Box's power rule: the radio and the NFC field are
never on together, and the radio serves by default (WRITE or IDLE, game or
not). Hardware is stubbed; this does NOT touch a Box.

Run from anywhere:  python3 BBoxFirmware/tools/test_box_serve.py
"""
import sys, types, os

BB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BB)
for name in ("M5", "machine", "network", "espnow"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["M5"].Lcd = types.SimpleNamespace()
sys.modules["M5"].Speaker = types.SimpleNamespace()
sys.modules["machine"].unique_id = lambda: b"\x01\x02\x03\x04\x05\x06"
import time as _t
_t.ticks_ms = lambda: int(_t.time() * 1000)
_t.sleep_ms = lambda ms: None
_t.ticks_diff = lambda a, b: a - b
_t.ticks_add = lambda a, b: a + b

import bbox_server as BS

fail = 0
def check(label, got, want=True):
    global fail
    ok = got == want
    fail += not ok
    print("%s %s%s" % ("ok  " if ok else "FAIL", label, "" if ok else " -- got %r" % (got,)))


class FakeCode:
    def __init__(self):
        self.is_on = False
        self.game = None
        self.polls = 0
    def set_game(self, slug): self.game = slug
    def radio_on(self):
        assert not srv._nfc_field_on, "radio_on with the field on"
        self.is_on = True
        return True
    def radio_off(self): self.is_on = False
    def poll(self, on_event=None, on_msg=None): self.polls += 1


class FakeNfc:
    def antenna_on(self):
        assert not srv.code.is_on, "field on with the radio on"
    def antenna_off(self): pass
    def stop_crypto1(self): pass
    def antenna_is_on(self): return True
    def crypto_on(self): return False


class FakeUI:
    def __getattr__(self, n):
        return lambda *a, **k: None


srv = BS.BboxServer.__new__(BS.BboxServer)
srv.ui = FakeUI()
srv.code = FakeCode()
srv.nfc = FakeNfc()
srv._nfc_field_on = False
srv._share_retry_at = 0
srv._reader_last_uid = None
srv._written = {}
srv._pulls = {}
srv._index = {"my_jump": {"name": "My Jump", "tags": ["jump"]}}
srv._active = "my_jump"
srv._groups = []
srv._entries = []
srv._cursor = 0
srv._group_cursor = 0
srv._rebuild_entries()

# IDLE, no game: the radio still comes up.
srv._mode = BS.MODE_IDLE
srv._write_state = BS.W_MENU
srv._active = None
srv._serve()
check("IDLE with no game: radio on", srv.code.is_on)
srv._serve()
check("radio on: _serve polls", srv.code.polls, 1)

# WRITE on the menu: radio on, serving the active game.
srv.code.radio_off()
srv._mode = BS.MODE_WRITE
srv._active = "my_jump"
srv._serve()
check("WRITE menu: radio on", srv.code.is_on)
check("WRITE menu: active game set", srv.code.game, "my_jump")

# Start a scan: the radio goes off before the field comes on.
srv._cursor = 0
srv._to_scan()
check("scan: field on", srv._nfc_field_on)
check("scan: radio off", srv.code.is_on, False)
for _ in range(3):
    srv._serve()
check("scan: _serve keeps the radio off", srv.code.is_on, False)

# Field off mid-scan (NFC re-init path) still keeps the radio off.
srv._nfc_field_on = False
srv._serve()
check("W_SCAN with field off: radio stays off", srv.code.is_on, False)
srv._nfc_field_on = True

# Back to the menu: field off, then the radio returns.
srv._to_menu()
check("menu: field off", srv._nfc_field_on, False)
srv._serve()
check("menu: radio back on", srv.code.is_on)

# arm / disarm are gone.
srv.handlers = {}
check("no do_arm", hasattr(srv, "do_arm"), False)
check("no do_disarm", hasattr(srv, "do_disarm"), False)

print("\n%s" % ("box serve OK" if not fail else "%d FAILED" % fail))
sys.exit(1 if fail else 0)
