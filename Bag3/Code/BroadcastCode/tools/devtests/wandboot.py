"""Boot harness shared by the MockWand boot tests (boot_wand_*.py).

Copies MockWand to a temp "flash", loads main.py under the stubs on a virtual
clock (wandsim) and runs main.main() with the NFC reader replaced by a
script. Importing this module changes the working directory and sys.path.

boot() returns a Boot: the main module `m`, the booted Wand, the Sim and Bus,
the ordered call names, captured output, and `reset` (True if main() called
machine.reset(), which ends the boot).
"""
import contextlib
import importlib.abc
import importlib.machinery
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wandsim  # noqa: E402

TMP = tempfile.mkdtemp(prefix="wandboot-")
FLASH = os.path.join(TMP, "flash")
shutil.copytree(wandsim.WAND_DIR, FLASH)
os.chdir(FLASH)
for p in list(sys.path):
    if p in (wandsim.WAND_DIR, wandsim.WAND_LIB, wandsim.STUBS):
        sys.path.remove(p)
sys.path.insert(0, FLASH)
sys.path.insert(0, os.path.join(FLASH, "lib"))
sys.path.insert(0, wandsim.STUBS)

import traceback  # noqa: E402
sys.print_exception = lambda e, *a: traceback.print_exception(type(e), e, e.__traceback__)

import gc as _gc  # noqa: E402
_gc.mem_alloc = lambda: 0
_gc.mem_free = lambda: 100_000
_gc.threshold = lambda *a: 0

import machine  # noqa: E402  (the stub)
import game_store  # noqa: E402
game_store.GAMES_DIR = os.path.join(FLASH, "games")

A = "AB:42:00:00:7E:B6"
B = "AB:42:00:00:20:60"
MY_MAC = "AA:00:00:00:00:07"
PAIRING = os.path.join(FLASH, "pairing.json")


class _Reset(BaseException):
    """machine.reset(): never returns, and escapes main()'s `except Exception`."""


def _reset():
    raise _Reset()


machine.reset = _reset


class FakePN532:
    def __init__(self, i2c, addr):
        pass

    def begin(self):
        return (0x32, 1, 6)


class FakeReader:
    """Replaces NfcReader. `steps` is consumed one entry per detect_tag():
    None is no card, a string is a card carrying that text (each card gets a
    new UID). detect_tag() burns its timeout like the PN532 does; once the
    steps run out it raises KeyboardInterrupt, which ends main()."""
    steps = []
    timeouts = []

    def __init__(self, nfc, commands, prefixes=()):
        self.cur = None
        self.n = 0

    def detect_tag(self, timeout=250):
        import time
        time.sleep_ms(timeout)
        FakeReader.timeouts.append(timeout)
        if not FakeReader.steps:
            raise KeyboardInterrupt
        step = FakeReader.steps.pop(0)
        self.cur = step
        if step is None:
            return None, None
        self.n += 1
        return "UID%d" % self.n, 0

    def read_command(self, **kw):
        if self.cur is None:
            return None, None
        return self.cur, "UID%d" % self.n


class _PairingPath(importlib.abc.MetaPathFinder):
    """Points lib/pairing.py at the temp file when (and only when) it is
    imported, so a test never imports it ahead of main()."""

    def find_spec(self, name, path, target=None):
        if name != "pairing":
            return None
        spec = importlib.machinery.PathFinder.find_spec(name, path)
        real_exec = spec.loader.exec_module

        def exec_module(module):
            real_exec(module)
            module.PATH = PAIRING
        spec.loader.exec_module = exec_module
        return spec


sys.meta_path.insert(0, _PairingPath())


def _purge():
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None) or ""
        if f.startswith(FLASH) or name == "ubluetooth":
            del sys.modules[name]


class Boot:
    pass


def boot(cause=machine.SOFT_RESET, macs=None, in_range=(), ble_fail=None, ticks=10,
         file_text=None, cards=None, setup=None, my_mac=MY_MAC):
    """Boot main.main() once.

    cards: list of None / card text, one per NFC detect (see FakeReader); when
      None, `ticks` empty detects.
    setup(b): called with the Boot (m, wand, sim, bus filled in) just before
      main() runs, to spawn other wands or schedule events.
    """
    _purge()
    for f in (PAIRING, PAIRING + ".tmp"):
        if os.path.exists(f):
            os.remove(f)
    if macs is not None:
        with open(PAIRING, "w") as f:
            f.write(json.dumps({"splats": macs}))
    if file_text is not None:
        with open(PAIRING, "w") as f:
            f.write(file_text)
    machine._reset_cause = cause
    sim, bus = wandsim.new_sim()
    wand = wandsim.Wand(sim, bus, my_mac)
    wand.ble_fail_active = ble_fail
    for mac in in_range:
        wand.splat(mac)
    sim.default_wand = wand
    FakeReader.steps = list(cards) if cards is not None else [None] * ticks
    FakeReader.timeouts = []

    src = open(os.path.join(FLASH, "main.py")).read()
    assert src.rstrip().endswith("\nmain()"), "main.py no longer ends with main()"
    src = src.rstrip()[:-len("main()")]
    m = type(sys)("main")
    m.__file__ = os.path.join(FLASH, "main.py")
    sys.modules["main"] = m
    exec(compile(src, m.__file__, "exec"), m.__dict__)
    m._PAIRING_PATH = PAIRING
    m.buz = wand.buz
    m.PN532 = FakePN532
    m.NfcReader = FakeReader
    m.ESPNowManager = lambda: wand.enow

    b = Boot()
    b.m, b.wand, b.sim, b.bus = m, wand, sim, bus
    b.reset = False
    b.order = wandsim.CALLS
    del b.order[:]

    def log(name):
        b.order.append(name)

    wand.enow.init = lambda: log("enow.init")
    real_stage_start = m.leds.boot_stage_start
    m.leds.boot_stage_start = lambda n: (log("stage%d" % n), real_stage_start(n))[1]
    b.stage0 = []
    real_stage_ok = m.leds.boot_stage_ok
    m.leds.boot_stage_ok = lambda n, row_colors=None, **kw: (
        b.stage0.append((n, row_colors)) if n == 0 else None,
        real_stage_ok(n, row_colors=row_colors, **kw))[1]
    if setup is not None:
        setup(b)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            m.main()
        except _Reset:
            b.reset = True
    b.out = buf.getvalue()
    return b


def pairing_file():
    if not os.path.exists(PAIRING):
        return None
    with open(PAIRING) as f:
        return json.load(f)["splats"]
