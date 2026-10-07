"""Boot MockWand/main.py under the stubs: Splat pairing at boot (A4).

Checks the stub call log: no ubluetooth import on an unpaired boot, BLE after
enow.init() and before Stage 1, the pairing file's fate per reset cause, a
BLE failure booting unpaired, a Splat that never connects being dropped after
PAIR_CONNECT_MS.

Run: python3 tools/devtests/boot_wand_pairing.py
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wandboot  # noqa: E402
import wandsim  # noqa: E402
from wandboot import A, B, boot, machine, pairing_file  # noqa: E402

check = wandsim.Checker()


def run(**kw):
    b = boot(**kw)
    b.m.stage0 = b.stage0
    return b.m, b.wand, b.order, b.out


# ── Unpaired boot ──
m, wand, order, out = run(cause=machine.SOFT_RESET)
check("unpaired boot does not import ubluetooth", "ubluetooth" not in sys.modules)
check("unpaired boot does not import the Splat modules",
      not any(n in sys.modules for n in ("splatpair", "splat_hub", "splat_link", "splat_api",
                                         "ble_splat", "pairing")))
check("unpaired boot has no controller", m._pair_ctl is None)
check("boot ran to the idle loop", "Boot complete" in out)

# ── Paired boot after a soft reset ──
for label, cause in (("soft reset", machine.SOFT_RESET), ("hard reset", machine.HARD_RESET),
                     ("watchdog reset", machine.WDT_RESET)):
    m, wand, order, out = run(cause=cause, macs=[A, B], in_range=[A, B], ticks=40)
    ub = sys.modules.get("ubluetooth")
    check("paired boot (%s) builds the hub" % label,
          m._pair_ctl is not None and m._pair_ctl.hub.count == 2 and m._pair_ctl.macs == [A, B],
          str(getattr(m._pair_ctl, "macs", None)))
    check("%s keeps the pairing file" % label, pairing_file() == [A, B])
    check("both Splats reach READY (%s)" % label,
          m._pair_ctl is not None and all(l.ready for l in m._pair_ctl.hub.links))

m, wand, order, out = run(cause=machine.SOFT_RESET, macs=[A, B], in_range=[A, B], ticks=5)
check("order: enow.init, then BLE.active, then Stage 1",
      "BLE.active" in order and order.index("enow.init") < order.index("BLE.active")
      < order.index("stage1"), str(order[:8]))
check("BLE.active(True) is called once", order.count("BLE.active") == 1, str(order))
check("the Splat modules were imported after BLE came up",
      all(n in sys.modules for n in ("splatpair", "splat_hub", "ble_splat")))

# ── Power-on reset ends every pairing ──
m, wand, order, out = run(cause=machine.PWRON_RESET, macs=[A, B], in_range=[A, B])
check("power-on reset deletes the pairing file", pairing_file() is None)
check("power-on reset boots unpaired without ubluetooth",
      m._pair_ctl is None and "ubluetooth" not in sys.modules)

# ── BLE failure: boot unpaired, file deleted, amber in stage 0's data row ──
m, wand, order, out = run(cause=machine.SOFT_RESET, macs=[A], in_range=[A],
                           ble_fail=OSError(-1, "BLE init failed"))
check("BLE active() raising boots unpaired", m._pair_ctl is None and "Boot complete" in out)
check("...deletes the pairing file", pairing_file() is None)
check("...logs the error", "BLE init failed" in out and '"where": "pairing"' in out)
amber = [c for n, c in m.stage0 if c is not None and c[2] == m.AMBER]
check("...shows amber in stage 0's data row", bool(amber), str(m.stage0))
check("...ESP-NOW is unaffected", wand.enow.is_active and "enow.init" in order)

# ── Corrupt file ──
m, wand, order, out = run(cause=machine.SOFT_RESET, file_text="{not json", ticks=3)
check("a corrupt pairing file boots unpaired and reports it",
      m._pair_ctl is None and "Boot complete" in out and "unpaired" in out)

# ── PAIR_CONNECT_MS ──
m, wand, order, out = run(cause=machine.SOFT_RESET, macs=[A, B], in_range=[A], ticks=400)
ctl = m._pair_ctl
check("a Splat that never connects is dropped from the file", pairing_file() == [A], str(pairing_file()))
check("...and from the group, leaving the connected one",
      ctl is not None and ctl.macs == [A] and ctl.group.count == 1 and ctl.hub.links[0].ready)
check("...with error feedback", "play:reject" in wand.buz.names(), str(wand.buz.names()))
check("...after PAIR_CONNECT_MS, not before",
      ctl is not None and ctl.dropped == [B])

m, wand, order, out = run(cause=machine.SOFT_RESET, macs=[A], in_range=[], ticks=400)
check("the last Splat dropped leaves an unpaired wand and no file",
      pairing_file() is None and m._pair_ctl.group is None)

shutil.rmtree(wandboot.TMP, ignore_errors=True)
check.finish("wand boot pairing OK")
