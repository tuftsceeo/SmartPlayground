"""Boot MockWand/main.py under the stubs: Splat pairing at boot (A4).

Each scenario copies MockWand to a temp "flash", boots main.main() with the
NFC reader replaced by a script, and checks the stub call log: no
ubluetooth import on an unpaired boot, BLE after enow.init() and before
Stage 1, the pairing file's fate per reset cause, a BLE failure booting
unpaired, a Splat that never connects being dropped after PAIR_CONNECT_MS.

Run: python3 tools/devtests/boot_wand_pairing.py
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

check = wandsim.Checker()

A = "AB:42:00:00:7E:B6"
B = "AB:42:00:00:20:60"
MY_MAC = "AA:00:00:00:00:07"
PAIRING = os.path.join(FLASH, "pairing.json")


class _Reset(Exception):
    pass


def _reset():
    raise _Reset()


machine.reset = _reset


class FakePN532:
    def __init__(self, i2c, addr):
        pass

    def begin(self):
        return (0x32, 1, 6)


class FakeReader:
    """detect_tag() burns 250 ms like the PN532's timeout, then reports no
    tag; after `ticks` calls it raises KeyboardInterrupt, which ends main()."""
    ticks = 10

    def __init__(self, nfc, commands, prefixes=()):
        self.n = 0

    def detect_tag(self, timeout=250):
        import time
        time.sleep_ms(timeout)
        self.n += 1
        if self.n > FakeReader.ticks:
            raise KeyboardInterrupt
        return None, None

    def read_command(self, **kw):
        return None, None


class _PairingPath(importlib.abc.MetaPathFinder):
    """Points lib/pairing.py at the temp file when (and only when) it is
    imported, so the test never imports it ahead of main()."""

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


def boot(cause=machine.SOFT_RESET, macs=None, in_range=(), ble_fail=None, ticks=10,
         file_text=None):
    """Boot main.main() once. Returns (module, wand, order, stdout)."""
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
    wand = wandsim.Wand(sim, bus, MY_MAC)
    wand.ble_fail_active = ble_fail
    for mac in in_range:
        wand.splat(mac)
    sim.default_wand = wand
    FakeReader.ticks = ticks

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

    order = wandsim.CALLS
    del order[:]

    def log(name):
        order.append(name)

    real_init = wand.enow.init
    wand.enow.init = lambda: (log("enow.init"), None)[1]
    real_stage_start = m.leds.boot_stage_start
    m.leds.boot_stage_start = lambda n: (log("stage%d" % n), real_stage_start(n))[1]
    stage0 = []
    real_stage_ok = m.leds.boot_stage_ok
    m.leds.boot_stage_ok = lambda n, row_colors=None, **kw: (
        stage0.append((n, row_colors)) if n == 0 else None, real_stage_ok(n, row_colors=row_colors, **kw))[1]
    m.stage0 = stage0

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        m.main()
    out = buf.getvalue()
    return m, wand, order, out


def pairing_file():
    if not os.path.exists(PAIRING):
        return None
    with open(PAIRING) as f:
        return json.load(f)["splats"]


# ── Unpaired boot ──
m, wand, order, out = boot(cause=machine.SOFT_RESET)
check("unpaired boot does not import ubluetooth", "ubluetooth" not in sys.modules)
check("unpaired boot does not import the Splat modules",
      not any(n in sys.modules for n in ("splatpair", "splat_hub", "splat_link", "splat_api",
                                         "ble_splat", "pairing")))
check("unpaired boot has no controller", m._pair_ctl is None)
check("boot ran to the idle loop", "Boot complete" in out)

# ── Paired boot after a soft reset ──
for label, cause in (("soft reset", machine.SOFT_RESET), ("hard reset", machine.HARD_RESET),
                     ("watchdog reset", machine.WDT_RESET)):
    m, wand, order, out = boot(cause=cause, macs=[A, B], in_range=[A, B], ticks=40)
    ub = sys.modules.get("ubluetooth")
    check("paired boot (%s) builds the hub" % label,
          m._pair_ctl is not None and m._pair_ctl.hub.count == 2 and m._pair_ctl.macs == [A, B],
          str(getattr(m._pair_ctl, "macs", None)))
    check("%s keeps the pairing file" % label, pairing_file() == [A, B])
    check("both Splats reach READY (%s)" % label,
          m._pair_ctl is not None and all(l.ready for l in m._pair_ctl.hub.links))

m, wand, order, out = boot(cause=machine.SOFT_RESET, macs=[A, B], in_range=[A, B], ticks=5)
check("order: enow.init, then BLE.active, then Stage 1",
      "BLE.active" in order and order.index("enow.init") < order.index("BLE.active")
      < order.index("stage1"), str(order[:8]))
check("BLE.active(True) is called once", order.count("BLE.active") == 1, str(order))
check("the Splat modules were imported after BLE came up",
      all(n in sys.modules for n in ("splatpair", "splat_hub", "ble_splat")))

# ── Power-on reset ends every pairing ──
m, wand, order, out = boot(cause=machine.PWRON_RESET, macs=[A, B], in_range=[A, B])
check("power-on reset deletes the pairing file", pairing_file() is None)
check("power-on reset boots unpaired without ubluetooth",
      m._pair_ctl is None and "ubluetooth" not in sys.modules)

# ── BLE failure: boot unpaired, file deleted, amber in stage 0's data row ──
m, wand, order, out = boot(cause=machine.SOFT_RESET, macs=[A], in_range=[A],
                           ble_fail=OSError(-1, "BLE init failed"))
check("BLE active() raising boots unpaired", m._pair_ctl is None and "Boot complete" in out)
check("...deletes the pairing file", pairing_file() is None)
check("...logs the error", "BLE init failed" in out and '"where": "pairing"' in out)
amber = [c for n, c in m.stage0 if c is not None and c[2] == m.AMBER]
check("...shows amber in stage 0's data row", bool(amber), str(m.stage0))
check("...ESP-NOW is unaffected", wand.enow.is_active and "enow.init" in order)

# ── Corrupt file ──
m, wand, order, out = boot(cause=machine.SOFT_RESET, file_text="{not json", ticks=3)
check("a corrupt pairing file boots unpaired and reports it",
      m._pair_ctl is None and "Boot complete" in out and "unpaired" in out)

# ── PAIR_CONNECT_MS ──
m, wand, order, out = boot(cause=machine.SOFT_RESET, macs=[A, B], in_range=[A], ticks=200)
ctl = m._pair_ctl
check("a Splat that never connects is dropped from the file", pairing_file() == [A], str(pairing_file()))
check("...and from the group, leaving the connected one",
      ctl is not None and ctl.macs == [A] and ctl.group.count == 1 and ctl.hub.links[0].ready)
check("...with error feedback", "play:reject" in wand.buz.names(), str(wand.buz.names()))
check("...after PAIR_CONNECT_MS, not before",
      ctl is not None and ctl.dropped == [B])

m, wand, order, out = boot(cause=machine.SOFT_RESET, macs=[A], in_range=[], ticks=200)
check("the last Splat dropped leaves an unpaired wand and no file",
      pairing_file() is None and m._pair_ctl.group is None)

shutil.rmtree(TMP, ignore_errors=True)
check.finish("wand boot pairing OK")
