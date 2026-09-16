"""
Check the icon editor's USB link still works on the Broadcast display, and
that it shares the panel with the idle loop and the game dispatcher.

JsonLink reads stdin, which a test cannot drive, so the link is replaced with
a recorder and commands are handed to dispatch() directly -- what is under
test is the server's behaviour and the split loop, not line framing.
"""
import os, sys, tempfile, shutil

import os
# BroadcastBox/, two levels up from tools/devtests/.
_BB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = _BB
SCRATCH = os.path.dirname(os.path.abspath(__file__))

import time as _time
_time.sleep_ms = lambda ms: None
_clock = [0]
def _tick():
    _clock[0] += 50
    return _clock[0]
_time.ticks_ms = _tick
_time.ticks_diff = lambda a, b: a - b
_time.ticks_add = lambda a, b: a + b

import gc as _gc
_gc.mem_alloc = lambda: 0
_gc.mem_free = lambda: 100_000
_gc.threshold = lambda *a: 0

TMP = tempfile.mkdtemp(prefix="usb-")
DEV = os.path.join(TMP, "display")
# The repo tree now carries device names directly (goalrace.py, not
# goalrace_icon.py -- that suffix lives only in the Box/Dial staging tree),
# so flashing the tree verbatim is exactly what a real device has.
shutil.copytree(os.path.join(ROOT, "IconDisplay"), DEV)
os.chdir(DEV)
sys.path.insert(0, os.path.join(SCRATCH, "stubs"))
sys.path.insert(0, os.path.join(DEV, "lib"))
sys.path.insert(0, DEV)

fails = []
def check(l, ok, d=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", l, (" -- " + d) if d else ""))
    if not ok: fails.append(l)

import icon_matrix, icon_store
from icon_server import IconServer

class Recorder:
    """Stands in for JsonLink: records replies, never touches stdin."""
    def __init__(self, on_command, debug=False):
        self.sent = []
        self.on_command = on_command
    def send(self, obj): self.sent.append(obj)
    def note(self, msg): pass
    def pump(self, idle_ms=20, drain_ms=40): pass

import json_link
json_link.JsonLink = Recorder
import icon_server
icon_server.JsonLink = Recorder

panel = icon_matrix.Matrix(pin=0, intensity=0.12)
srv = IconServer(panel, debug=False)
check("server took the panel it was given, not a new one", srv.m is panel)

srv.start()
hello = [m for m in srv.link.sent if m.get("type") == "hello"]
check("start() announces the device", len(hello) == 1)
check("hello reports the real panel geometry",
      hello[0]["w"] == 16 and hello[0]["h"] == 16)
check("hello reports the real intensity ceiling",
      hello[0]["max_intensity"] == icon_matrix.MAX_INTENSITY)
check("hello reports this panel's orientation, not a default",
      hello[0]["mirror_x"] == panel.mirror_x)

check("step() is non-blocking and keeps running", srv.step() is True)

# ── the editor's core commands ──
srv.dispatch({"cmd": "list", "id": 1})
icons = [m for m in srv.link.sent if m.get("type") == "icons"][-1]
names = sorted(e["name"] for e in icons["list"])
check("list returns the icons on this device", "whale" in names and "tree" in names,
      ",".join(names))

srv.dispatch({"cmd": "show", "name": "whale", "id": 2})
check("show draws a stored icon",
      any(m.get("type") == "shown" for m in srv.link.sent))
lit = sum(1 for i in range(0, len(panel.src), 3) if any(panel.src[i:i+3]))
check("...and the panel actually changed", lit > 0, "%d lit" % lit)

import binascii
frame = bytes([9, 0, 0] * 256)
srv.dispatch({"cmd": "frame", "d": binascii.b2a_base64(frame).decode().strip(), "id": 3})
check("frame accepts a full 768-byte push",
      any(m.get("type") == "frame_ok" for m in srv.link.sent))
check("...and the panel holds it", panel.src[0] == 9)

srv.dispatch({"cmd": "intensity", "value": 0.9, "id": 4})
inten = [m for m in srv.link.sent if m.get("type") == "intensity"][-1]
check("intensity is clamped to the measured ceiling",
      inten["value"] <= icon_matrix.MAX_INTENSITY and inten["clamped"] is True,
      str(inten["value"]))

srv.dispatch({"cmd": "save", "name": "testicon", "id": 5})
check("save writes an icon to flash", os.path.exists("icons/testicon.py"))
srv.dispatch({"cmd": "delete", "name": "testicon", "id": 6})
check("delete removes it", not os.path.exists("icons/testicon.py"))

# ── panel sharing with the idle loop ──
srv.dispatch({"cmd": "show", "name": "whale", "id": 20})
check("editor owns the panel just after a draw",
      srv.owns_panel(_time.ticks_ms(), 300000) is True)
for _ in range(200):   # 10s of stub clock, no further drawing
    _time.ticks_ms()
check("...and keeps it while the link is merely quiet",
      srv.owns_panel(_time.ticks_ms(), 300000) is True)

check("a card tap hands the panel back", srv.release_panel() is None
      and srv.owns_panel(_time.ticks_ms(), 300000) is False)

srv.dispatch({"cmd": "clear", "id": 21})
check("a deliberate blank keeps the hold -- the breath must not paint over it",
      srv.owns_panel(_time.ticks_ms(), 300000) is True)

for _ in range(200):   # 10s of stub clock
    _time.ticks_ms()
check("a silence past the backstop is the stand-in for a lost browser",
      srv.owns_panel(_time.ticks_ms(), 5000) is False)

srv2 = IconServer(icon_matrix.Matrix(pin=0, intensity=0.12), debug=False)
srv2.start()
check("a display with no browser attached never withholds the panel",
      srv2.owns_panel(_time.ticks_ms(), 300000) is False)

# ── the two ways the loop ends ──
srv.dispatch({"cmd": "repl", "id": 7})
check("repl stops the loop", srv.step() is False)
check("...and says why", srv.exit_reason == "repl")
srv.finish()
check("repl does NOT reset -- it would take the browser's port with it",
      srv._reboot_hard is False)
check("...and leaves the panel dark", all(v == 0 for v in panel.src))

srv3 = IconServer(icon_matrix.Matrix(pin=0, intensity=0.12), debug=False)
srv3.start()
srv3.dispatch({"cmd": "reboot", "hard": True, "id": 8})
check("reboot stops the loop", srv3.step() is False)
check("...and is distinguishable from repl", srv3.exit_reason == "reboot")
check("...and asks for the reset", srv3._reboot_hard is True)

# ── main.py still boots with all of this in it ──
import main
check("main.py imports with the USB server wired in", True)
check("game dispatch is unaffected", main.is_game("goalrace") is True)

shutil.rmtree(TMP, ignore_errors=True)
print()
if fails:
    print("FAILED: %d" % len(fails))
    for f in fails: print("  -", f)
    sys.exit(1)
print("USB link on the Broadcast display OK")
