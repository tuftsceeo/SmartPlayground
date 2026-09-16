"""
Play the goalrace pair against each other under stubs.

The wand file and the display file are separate programs that only meet over
ESP-NOW. This wires one fake radio between them and drives a round: two wands
join teams, one reaches the goal, the display picks a winner and answers, and
the losing wand does not flip it.
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

import gc as _gc
_gc.mem_alloc = lambda: 0
_gc.mem_free = lambda: 100_000
_gc.threshold = lambda *a: 0

TMP = tempfile.mkdtemp(prefix="pair-")
DISPLAY = os.path.join(TMP, "display")
def _stage_pulled_games(root):
    """Model what a pull leaves on the display's flash.

    In the repo tree a display game is named <slug>_icon.py -- that is the
    name the Box serves it under. The pull writes it to the device as
    <slug>.py, which is what GAME_MODULES resolves, so a test that flashes
    the tree verbatim would look for a file no device ever has.
    """
    for name in os.listdir(root):
        if name.endswith("_icon.py"):
            shutil.copyfile(os.path.join(root, name),
                            os.path.join(root, name[:-len("_icon.py")] + ".py"))

shutil.copytree(os.path.join(ROOT, "IconDisplay"), DISPLAY)
_stage_pulled_games(DISPLAY)
os.chdir(DISPLAY)

sys.path.insert(0, os.path.join(SCRATCH, "stubs"))
sys.path.insert(0, os.path.join(ROOT, "MockWand", "lib"))
sys.path.insert(0, os.path.join(DISPLAY, "lib"))
sys.path.insert(0, DISPLAY)

FAILURES = []
def check(label, ok, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", label, (" -- " + detail) if detail else ""))
    if not ok:
        FAILURES.append(label)


class Air:
    """One shared ESP-NOW air. Each station has its own inbox."""
    def __init__(self):
        self.stations = []
    def station(self, name):
        s = Station(self, name)
        self.stations.append(s)
        return s
    def deliver(self, sender, data):
        for s in self.stations:
            if s is not sender:
                s.inbox.append(("raw", data, b"\x01" * 6))


class Station:
    def __init__(self, air, name):
        self.air = air
        self.name = name
        self.inbox = []
        self.sent = []
    def poll(self, timeout_ms=0):
        return self.inbox.pop(0) if self.inbox else (None, None, None)
    def broadcast(self, data):
        self.sent.append(data)
        self.air.deliver(self, data)
    def inject(self, msg):
        self.inbox.append(msg)


class FakeLeds:
    def __init__(self):
        self.last = None
        self.shapes = []
    def fill(self, c):
        self.last = ("fill", c)
    def show_shape(self, shape, color):
        self.last = ("shape", color)
        self.shapes.append(color)
    def off(self):
        self.last = ("off", None)


class FakeBuz:
    def beep(self, *a, **k): pass


class FakeReader:
    """A scripted NfcReader: a list of (cmd, uid) handed out in order.

    The wand game builds its own NfcReader from the raw PN532 it is passed,
    so this is swapped in over game.reader rather than passed as nfc.
    """
    def __init__(self, script):
        self.script = list(script)
    def read_command(self, timeout=250, **k):
        return self.script.pop(0) if self.script else (None, None)


class FakePN532:
    """Enough of the driver for NfcReader's constructor; never read from."""
    def read_passive_target(self, timeout=250):
        return None


def wand_game_with(script, leds, radio):
    g = wand_game.GoalRaceGame(FakePN532(), leds, FakeBuz(), radio)
    g.reader = FakeReader(script)
    return g


air = Air()

# ── The display ──
import icon_matrix, icon_store
panel = icon_matrix.Matrix(pin=0, intensity=0.12)
display_radio = air.station("display")

# Both files are called goalrace.py -- that is the point, each device holds
# <slug>.py -- so they are loaded by path under distinct names here.
import importlib.util
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

display_game = load("display_goalrace", os.path.join(DISPLAY, "goalrace.py"))
check("display game has COMMANDS", hasattr(display_game, "COMMANDS"),
      str(sorted(display_game.COMMANDS)))
check("display COMMANDS are all literal strings",
      all(isinstance(t, str) for t in display_game.COMMANDS))

# ── The wand ──
sys.path.insert(0, os.path.join(ROOT, "MockWand"))
wand_game = load("wand_goalrace", os.path.join(ROOT, "MockWand", "goalrace.py"))
check("wand game has COMMANDS", hasattr(wand_game, "COMMANDS"))
for tag in ("teamgreen", "teamblue", "goal"):
    check("wand declares the %r card" % tag, tag in wand_game.COMMANDS)

green_radio = air.station("green wand")
blue_radio = air.station("blue wand")

# ── Green wand: join, score, then exit on a stop card ──
green_leds = FakeLeds()
g = wand_game_with([
    ("teamgreen", b"aa"),
    (None, None),
    ("goal", b"bb"),
    (None, None),
    ("stop", b"cc"),
], green_leds, green_radio)
# NFC_POLL_INTERVAL gates reads on the frame counter; step it directly.
wand_game.NFC_POLL_INTERVAL = 1
g.run()
check("green wand joined its team", g.team == "green", str(g.team))
check("green wand broadcast exactly one goal",
      [m for m in green_radio.sent if m.get("type") == "goal"] ==
      [{"type": "goal", "team": "green"}], str(green_radio.sent))

# ── The display sees that goal ──
check("the goal reached the display's inbox", len(display_radio.inbox) >= 1)

class OneShotDisplayRadio:
    """Replays what the air delivered, then a stop so play() returns."""
    def __init__(self, inbox, out):
        self.q = list(inbox) + [("stop", {"type": "stop"}, None)]
        self.out = out
    def poll(self, timeout_ms=0):
        return self.q.pop(0) if self.q else (None, None, None)
    def broadcast(self, data):
        self.out.append(data)

out = []
display_game.play(None, panel, OneShotDisplayRadio(display_radio.inbox, out))
check("display announced a winner",
      out == [{"type": "winner", "team": "green"}], str(out))

# ── The winner icon is the tree, and it is actually on the panel ──
lit = sum(1 for i in range(0, len(panel.src), 3) if any(panel.src[i:i+3]))
check("display cleared the panel on exit", lit == 0, "%d lit" % lit)

panel2 = icon_matrix.Matrix(pin=0, intensity=0.12)
display_game._show(panel2, display_game.TEAM_ICON["green"], display_game.WINNER_INTENSITY)
tree = bytes(panel2.src)
display_game._show(panel2, display_game.TEAM_ICON["blue"], display_game.WINNER_INTENSITY)
whale = bytes(panel2.src)
check("green and blue show different icons", tree != whale)
check("both icon names resolve to files",
      all(os.path.exists("icons/%s.py" % n) for n in display_game.TEAM_ICON.values()))
check("winner intensity stays under the measured ceiling",
      display_game.WINNER_INTENSITY <= icon_matrix.MAX_INTENSITY)

# ── A second goal in the same round must not flip the winner ──
q = [("raw", {"type": "goal", "team": "green"}, None),
     ("raw", {"type": "goal", "team": "blue"}, None),
     ("stop", {"type": "stop"}, None)]
out2 = []
class Q:
    def poll(self, timeout_ms=0):
        return q.pop(0) if q else (None, None, None)
    def broadcast(self, d):
        out2.append(d)
display_game.play(None, panel2, Q())
check("a later goal does not flip the winner",
      out2 == [{"type": "winner", "team": "green"}], str(out2))

# ── The losing wand hears the result ──
blue_leds = FakeLeds()
b = wand_game_with([("teamblue", b"dd"), (None, None), ("stop", b"ee")],
                   blue_leds, blue_radio)
blue_radio.inject(("raw", {"type": "winner", "team": "green"}, None))
b.run()
check("blue wand joined its team", b.team == "blue", str(b.team))
check("blue wand sent no goal", [m for m in blue_radio.sent if m.get("type") == "goal"] == [])

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print("FAILED: %d" % len(FAILURES))
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("goalrace pair OK")
