"""
Boot-path checks for MockWand Splat pairing (PLAN A4.3).

pairing.boot() runs against a fake ubluetooth / splat_hub / splat_api that
log every call:
  - unpaired boot never imports ubluetooth or the Splat modules;
  - a paired boot after a soft reset activates BLE, then builds the hub;
  - a power-on reset deletes /pairing.json and stays unpaired;
  - BLE().active(True) raising boots unpaired with the file deleted.

main.py's order is checked from its source (it runs main() at import and
cannot be booted here without the full stub set): enow.init() comes before
pairing.boot(), which comes before Stage 1; pair_idle is imported after
boot; nothing at module scope imports pairing, pair_idle or ubluetooth.

Run: python3 Bag3/Code/BroadcastCode/MockWand/tests/boot_wand_pairing.py
"""
import ast
import json
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
WAND = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(WAND, "lib"))

import time
import traceback
time.ticks_ms = getattr(time, "ticks_ms", lambda: 0)
time.ticks_diff = getattr(time, "ticks_diff", lambda a, b: a - b)
if not hasattr(sys, "print_exception"):
    sys.print_exception = lambda e, *a: traceback.print_exception(type(e), e, e.__traceback__)

import pairing

LOG = []
SPLAT_MODS = ("ubluetooth", "splat_hub", "splat_api", "splat_link", "ble_splat")


class Machine:
    PWRON_RESET = 1
    SOFT_RESET = 5

    def __init__(self, cause):
        self.cause = cause

    def reset_cause(self):
        return self.cause


def _install_fakes(active_raises=False):
    for m in SPLAT_MODS:
        sys.modules.pop(m, None)
    ub = types.ModuleType("ubluetooth")

    class BLE:
        def active(self, on=None):
            LOG.append(("ble.active", on))
            if active_raises:
                raise OSError(12, "ENOMEM")
            return True
    ub.BLE = BLE
    hubm = types.ModuleType("splat_hub")

    class SplatHub:
        def __init__(self, count=1, macs=None):
            LOG.append(("SplatHub", count, list(macs)))
            self.links = [types.SimpleNamespace(ready=False) for _ in macs]
    hubm.SplatHub = SplatHub
    apim = types.ModuleType("splat_api")

    class SplatGroup:
        def __init__(self, hub):
            LOG.append(("SplatGroup",))
            self.units = []
    apim.SplatGroup = SplatGroup
    real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__
    fakes = {"ubluetooth": ub, "splat_hub": hubm, "splat_api": apim}

    def imp(name, *a, **k):
        if name in fakes:
            LOG.append(("import", name))
            sys.modules[name] = fakes[name]
            return fakes[name]
        return real_import(name, *a, **k)
    return imp, real_import


def _boot(cause, macs, active_raises=False):
    import builtins
    d = tempfile.mkdtemp(prefix="wandboot-")
    path = os.path.join(d, "pairing.json")
    if macs is not None:
        with open(path, "w") as f:
            json.dump({"splats": macs}, f)
    del LOG[:]
    pairing._local = None
    imp, real = _install_fakes(active_raises)
    builtins.__import__ = imp
    try:
        r = pairing.boot(Machine(cause), own_mac="AA:BB:CC:DD:EE:01", path=path)
    finally:
        builtins.__import__ = real
    exists = os.path.exists(path)
    shutil.rmtree(d)
    return r, exists


def test_unpaired_never_imports_ble():
    r, _ = _boot(Machine.SOFT_RESET, None)
    assert r is None and LOG == [] and pairing.local() is None
    r, _ = _boot(Machine.SOFT_RESET, [])
    assert r is None and LOG == []


def test_paired_soft_reset_builds_hub():
    macs = ["AB:42:00:00:7E:B6", "AB:42:00:00:7E:B7"]
    r, exists = _boot(Machine.SOFT_RESET, macs)
    assert r is True and exists
    assert LOG[0] == ("import", "ubluetooth")
    assert LOG[1] == ("ble.active", True)
    assert ("SplatHub", 2, macs) in LOG
    assert LOG.index(("ble.active", True)) < LOG.index(("import", "splat_hub"))
    assert pairing.local().macs == macs


def test_power_on_reset_clears():
    r, exists = _boot(Machine.PWRON_RESET, ["AB:42:00:00:7E:B6"])
    assert r is None and not exists and LOG == []


def test_ble_failure_boots_unpaired():
    r, exists = _boot(Machine.SOFT_RESET, ["AB:42:00:00:7E:B6"], active_raises=True)
    assert r is False and not exists and pairing.local() is None


def test_main_order():
    with open(os.path.join(WAND, "main.py")) as f:
        src = f.read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
            for bad in ("pairing", "pair_idle", "ubluetooth", "splat_hub", "splat_api"):
                assert bad not in names, "module-scope import of %s in main.py" % bad
    main = src[src.index("\ndef main():"):]
    i_enow = main.index("enow.init()")
    i_boot = main.index("pairing.boot(machine)")
    i_stage1 = main.index("leds.boot_stage_start(1)")
    i_idle = main.index("import pair_idle")
    i_loop = main.index("while True:")
    assert i_enow < i_boot < i_stage1 < i_idle < i_loop
    assert main.index("if pull_flag.is_pending()") < i_enow


if __name__ == "__main__":
    n = 0
    for k, fn in sorted(globals().items()):
        if k.startswith("test_") and callable(fn):
            fn()
            print("ok  ", k)
            n += 1
    print("ALL %d BOOT PAIRING TESTS PASSED" % n)
