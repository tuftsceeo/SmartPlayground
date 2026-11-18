"""Boot MockWand/main.py under the stubs: Splat pairing at boot (A4).

Checks the stub call log: no ubluetooth import on an unpaired boot, BLE after
enow.init() and before Stage 1, the pairing file kept only on the boot after a
Splat card tap (/pair_boot) and cleared on any other, a BLE failure booting
unpaired, a Splat that never connects being dropped after PAIR_CONNECT_MS, and
a connected Splat that drops: retries, the lost glyph at LOST_RETRY_MS, spaced
retries, release at LOST_GIVE_UP_MS, or recovery before it.

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

# ── Paired boot: kept only after a Splat card tap (/pair_boot), any reset cause ──
for label, cause in (("soft reset", machine.SOFT_RESET), ("hard reset", machine.HARD_RESET),
                     ("watchdog reset", machine.WDT_RESET), ("power-on reset", machine.PWRON_RESET)):
    m, wand, order, out = run(cause=cause, macs=[A, B], in_range=[A, B], ticks=40, pair_boot=True)
    check("/pair_boot + %s builds the hub" % label,
          m._pair_ctl is not None and m._pair_ctl.hub.count == 2 and m._pair_ctl.macs == [A, B],
          str(getattr(m._pair_ctl, "macs", None)))
    check("...keeps the pairing file", pairing_file() == [A, B])
    check("...removes /pair_boot", not os.path.exists(wandboot.PAIR_BOOT))
    check("...both Splats reach READY",
          m._pair_ctl is not None and all(l.ready for l in m._pair_ctl.hub.links))

# ── Any boot without /pair_boot clears the pairing ──
for label, cause in (("soft reset", machine.SOFT_RESET), ("hard reset", machine.HARD_RESET),
                     ("watchdog reset", machine.WDT_RESET), ("power-on reset", machine.PWRON_RESET)):
    m, wand, order, out = run(cause=cause, macs=[A, B], in_range=[A, B], pair_boot=False)
    check("no /pair_boot, %s: the pairing file is deleted" % label, pairing_file() is None)
    check("...boots unpaired without ubluetooth",
          m._pair_ctl is None and "ubluetooth" not in sys.modules and "BLE.active" not in order)
m, wand, order, out = run(cause=machine.SOFT_RESET, pair_boot=True)
check("a stray /pair_boot with no pairing file boots unpaired", m._pair_ctl is None)

# ── A Splat card tap writes /pair_boot before the reset ──
b = boot(cards=[None, "splat-ab4200007eb6", None])
check("Splat card tap: pairing file written, /pair_boot written, reset",
      b.reset and pairing_file() == [A] and os.path.exists(wandboot.PAIR_BOOT))
m, wand, order, out = run(cause=machine.SOFT_RESET, in_range=[A], ticks=40, keep_files=True)
check("...the next boot keeps that pairing and connects",
      m._pair_ctl is not None and m._pair_ctl.macs == [A] and m._pair_ctl.hub.links[0].ready)

m, wand, order, out = run(cause=machine.SOFT_RESET, macs=[A, B], in_range=[A, B], ticks=5)
check("order: enow.init, then BLE.active, then Stage 1",
      "BLE.active" in order and order.index("enow.init") < order.index("BLE.active")
      < order.index("stage1"), str(order[:8]))
check("BLE.active(True) is called once", order.count("BLE.active") == 1, str(order))
check("the Splat modules were imported after BLE came up",
      all(n in sys.modules for n in ("splatpair", "splat_hub", "ble_splat")))

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

# ── A connected Splat drops and stays away ──
DROP_AT = 8000


def lost_setup(back_at=None):
    """Drop Splat A at DROP_AT and keep it out of range (until back_at).
    Records each new connect attempt (scan_gate True) and each lost glyph."""
    def setup(b):
        b.sim.max_ms = 400000
        b.begins = []
        b.glyphs = []

        def hook():
            sp = sys.modules["splatpair"]
            ctl = b.m._pair_ctl
            for link in ctl.hub.links:
                real = link.scan_gate

                def gate(l, real=real):
                    ok = real(l)
                    if ok:
                        b.begins.append(time.ticks_ms())
                    return ok
                link.scan_gate = gate
            real_show = b.m.leds.show_shape

            def show(shape, *a, **k):
                if tuple(shape) == sp.SHAPE_SPLAT_LOST:
                    b.glyphs.append(time.ticks_ms())
                return real_show(shape, *a, **k)
            b.m.leds.show_shape = show
            p = b.wand.periph(A)
            p.available = False
            b.wand.ble.drop(A)

        b.sim.at(DROP_AT, hook)
        if back_at is not None:
            b.sim.at(back_at, lambda: setattr(b.wand.periph(A), "available", True))
    return setup


import time  # noqa: E402

b = boot(macs=[A], in_range=[A], cards=[None] * 1800, setup=lost_setup())
sp = sys.modules["splatpair"]
from splat_link import CONNECT_TIMEOUT_MS  # noqa: E402
lost_ms = DROP_AT + sp.LOST_RETRY_MS
early = [t for t in b.begins if t < lost_ms]
late = [t for t in b.begins if t >= lost_ms]
check("dropped Splat: normal retries before LOST_RETRY_MS", len(early) >= 2, str(b.begins))
blinks = [t for t in b.glyphs if t < lost_ms + 5000]
check("...the lost glyph blinks 3 times at LOST_RETRY_MS",
      len(blinks) == 3 and lost_ms <= blinks[0] < lost_ms + 1000, str(b.glyphs))
gaps = [late[i + 1] - late[i] for i in range(len(late) - 1)]
want = [CONNECT_TIMEOUT_MS + g for g in sp.LOST_GAPS_MS]
check("...then attempts spaced by CONNECT_TIMEOUT_MS + LOST_GAPS_MS",
      len(late) >= 2 and all(gaps[i] >= want[min(i, len(want) - 1)] for i in range(len(gaps)))
      and gaps[0] < want[0] + 1000, "begins=%s gaps=%s" % (late, gaps))
give_up = DROP_AT + sp.LOST_GIVE_UP_MS
check("...no attempt after the release", all(t < give_up + 1000 for t in b.begins), str(b.begins))
check("...released at LOST_GIVE_UP_MS: pairing removed, wand unpaired",
      pairing_file() is None and b.m._pair_ctl.dropped == [A] and b.m._pair_ctl.group is None,
      str(pairing_file()))
check("...with the lost glyph again (6 blinks in all, the last after LOST_GIVE_UP_MS)",
      len(b.glyphs) == 6 and give_up <= b.glyphs[3] < give_up + 1000, str(b.glyphs))
check("...and the warn tone twice", b.wand.buz.names().count("play:warn") == 2, str(b.wand.buz.names()))

# ── A dropped Splat that comes back before LOST_GIVE_UP_MS ──
back = DROP_AT + sp.LOST_RETRY_MS + 25000
b = boot(macs=[A], in_range=[A], cards=[None] * 1800, setup=lost_setup(back_at=back))
ctl = b.m._pair_ctl
link = ctl.hub.links[0] if ctl.hub else None
check("Splat back after the lost glyph: reconnects", link is not None and link.ready and link.connects == 2,
      str(link and link.connects))
check("...the lost state is cleared", ctl._lost_at == [None] and ctl._slow == [False])
check("...not released: pairing kept", pairing_file() == [A] and ctl.dropped == [])
check("...the lost glyph was shown once (3 blinks)", len(b.glyphs) == 3, str(b.glyphs))

shutil.rmtree(wandboot.TMP, ignore_errors=True)
check.finish("wand boot pairing OK")
