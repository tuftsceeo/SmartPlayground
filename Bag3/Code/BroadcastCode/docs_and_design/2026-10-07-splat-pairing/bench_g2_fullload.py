"""
bench_g2_fullload.py -- gate G2: full-load memory, 32 KB compile, ESP-NOW + Splat soak
=====================================================================================
Run on a MockWand whose main.py is NOT running (renamed to main.py.bak, board reset).
Needs on the wand, in /m1/: splat_link.py, splat_hub.py, splat_api.py, ble_splat.py
(from SplatCompanion/Companion). N Splats switched on and advertising.

Config is read from builtins so it can be set in the same mpremote call:
    python3 -m mpremote connect $WAND resume \
      exec "import builtins; builtins.G2_N=2; builtins.G2_SOAK_S=120" + run bench_g2_fullload.py
  G2_N       Splats to connect, 1-4 (default 2)
  G2_MACS    list of MAC strings to pin; its length overrides G2_N (default: first found)
  G2_SOAK_S  soak seconds (default 120)
  G2_SRC_KB  generated source size in KB (default 32)

Order: main.py's module-scope imports, game_store sys.path, hardware objects
(LED matrix, I2C, buzzer, pins), ESPNowManager().init() (radio claims its
memory before anything else allocates), NFC reader, BLE, Splat modules, N
Splats READY, compile() of generated source, soak. Each stage prints a RESULT
line with idf_largest. Last line is `G2 {json}`.
Timing: connect wait <= 60 s, soak 120 s, total under 4 min.
"""

import machine
import time
import sys
import json
import gc
import os

# mirrors MockWand/main.py module-scope imports, same order
from hubtype import HUB_TYPE, HUB_CONFIG
from pn532 import PN532
from lis2dw12 import LIS2DW12, RANGE_4G
from max17048 import MAX17048

from leds import (
    Leds, TRIGGER_ORDER, battery_color, WHITE, OFF,
    SHAPE_CHECK, SHAPE_X, RED, GREEN, AMBER, CYAN, BLUE_DIM,
    PURPLE, ORANGE, LIME, SKY, TEAL, MAGENTA, PINK, ROSE, INDIGO, YELLOW,
    SHAPE_BULLSEYE, SHAPE_INNER_3x3, SHAPE_FLAME, SHAPE_MUSIC,
    SHAPE_ARROW_UP, SHAPE_ROW3, SHAPE_SPIRAL, SHAPE_SLASH_L, SHAPE_WIFI,
    SHAPE_WIFI_2, BLUE, ORANGE,
    SHAPE_RAINDROP, SHAPE_DIAMOND, SHAPE_POINTER, SHAPE_EXCLAIM,
    SHAPE_FASTFORWARD,
)
from power_led import PowerLed
from buzzer import Buzzer
from nfc_reader import NfcReader, split_prefixed
from actions import ActionRunner, ACTIONS, ANIMAL_SOUNDS, ACTION_RESOURCE, resolve_and_group, chain_to_str
from battery import show_battery
from espnow_manager import ESPNowManager
from game_tags import GAME_TAGS, CONTROL_TAGS, HIDDEN_TAGS
import brightness
import pull_flag
import game_store
import memprobe

game_store.ensure_dir()
if game_store.GAMES_DIR not in sys.path:
    sys.path.append(game_store.GAMES_DIR)

import builtins
N = getattr(builtins, "G2_N", 2)
MACS = getattr(builtins, "G2_MACS", None)
SOAK_S = getattr(builtins, "G2_SOAK_S", 120)
SRC_KB = getattr(builtins, "G2_SRC_KB", 32)
CONNECT_WAIT_S = 60
SOAK_PERIOD_MS = 100        # one broadcast + one Splat command per period

sys.path.insert(0, "/m1")

_T0 = time.ticks_ms()
summary = {"n": N, "soak_s": SOAK_S, "src_kb": SRC_KB,
           "ext_antenna": sys.modules["espnow_manager"].EXTERNAL_ANTENNA,
           "stages": {}, "ok": False}


def t_s():
    return time.ticks_diff(time.ticks_ms(), _T0) / 1000


def log(s):
    print("[%7.2f] %s" % (t_s(), s))


def step(name, ok=True, note=""):
    memprobe.probe(name)
    free, largest = memprobe._idf_free()
    summary["stages"][name] = largest
    log("RESULT step=%s ok=%s idf_largest=%s idf_free=%s gc_free=%d %s"
        % (name, ok, largest, free, gc.mem_free(), note))


def finish(err=None):
    summary["t_s"] = t_s()
    if err is not None:
        summary["error"] = err
    print("G2 " + json.dumps(summary))


def stats(xs):
    if not xs:
        return None
    xs = sorted(xs)
    n = len(xs)
    return {"n": n, "min": xs[0], "p50": xs[n // 2], "p95": xs[(n * 95) // 100],
            "max": xs[-1], "mean": sum(xs) // n}


step("after-imports")

leds = Leds()
pled = PowerLed()
pled.on()
leds.boot_power()
i2c = machine.SoftI2C(sda=machine.Pin(HUB_CONFIG["i2c_sda"]),
                      scl=machine.Pin(HUB_CONFIG["i2c_scl"]),
                      freq=HUB_CONFIG["i2c_freq"])
buz = Buzzer(HUB_CONFIG["buzzer_pin"])
btn = machine.Pin(HUB_CONFIG["button_pin"], machine.Pin.IN, machine.Pin.PULL_UP)
int1_pin = machine.Pin(HUB_CONFIG["accel_int1_pin"], machine.Pin.IN)
motor = machine.Pin(HUB_CONFIG["motor_pin"], machine.Pin.OUT, value=0)
step("module-objects")

enow = ESPNowManager()
gc.collect()
try:
    enow.init()
    step("post-enow")
except Exception as ex:
    sys.print_exception(ex)
    step("post-enow", ok=False)
    finish("enow.init: %r" % ex)
    raise SystemExit

try:
    nfc = PN532(i2c, HUB_CONFIG["nfc_addr"])
    ic, ver, rev = nfc.begin()
    reader = NfcReader(nfc, list(ACTIONS) + list(GAME_TAGS))
    runner = ActionRunner(leds, buz)
    summary["pn532"] = "%d.%d" % (ver, rev)
    step("nfc")
except Exception as ex:
    sys.print_exception(ex)
    step("nfc", ok=False)
    finish("nfc: %r" % ex)
    raise SystemExit

leds.fill(GREEN)
step("led-matrix")

try:
    import ubluetooth
    ble = ubluetooth.BLE()
    ble.active(True)
    step("ble-active")
    import splat_link
    import splat_hub
    import splat_api
    from splat_hub import SplatHub
    from splat_api import SplatGroup
    step("splat-modules")
except Exception as ex:
    sys.print_exception(ex)
    step("ble-or-splat-modules", ok=False)
    finish("ble: %r" % ex)
    raise SystemExit

hub = SplatHub(count=N, macs=MACS)
group = SplatGroup(hub)
N = len(hub.links)
summary["n"] = N
step("hub-built")


def gen_source(kb):
    """Game-shaped source: functions with branches, string literals, dict lookups."""
    parts = ["import time\nSTATE = {}\n"]
    size = len(parts[0])
    i = 0
    while size < kb * 1024:
        s = ("def handler_%d(splat, leds, enow, n):\n"
             "    msg = {'cmd': 'step', 'i': %d, 'name': 'handler_%d'}\n"
             "    if n %% 3 == 0:\n"
             "        splat.color('turnred')\n"
             "    elif n %% 3 == 1:\n"
             "        splat.color('turngreen')\n"
             "    else:\n"
             "        enow.broadcast(msg)\n"
             "    STATE['last'] = %d\n"
             "    return [x * %d for x in range(n)]\n\n" % (i, i, i, i, i))
        parts.append(s)
        size += len(s)
        i += 1
    return "".join(parts)


try:
    ready_at = [None] * N
    end = time.ticks_add(time.ticks_ms(), CONNECT_WAIT_S * 1000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        group.poll()
        enow.poll()
        for i, link in enumerate(hub.links):
            if ready_at[i] is None and link.state == splat_link.ST_READY:
                ready_at[i] = t_s()
                step("splat%d-ready" % i)
        if None not in ready_at:
            break
        time.sleep_ms(1)
    summary["ready_at"] = ready_at
    summary["splat_macs"] = [l.mac_address for l in hub.links]
    all_ready = None not in ready_at
    step("splats-final", ok=all_ready,
         note="states=%s" % [l.state_name() for l in hub.links])

    # compile with everything loaded
    src = gen_source(SRC_KB)
    summary["src_bytes"] = len(src)
    gc.collect()
    step("pre-compile")
    t0 = time.ticks_ms()
    try:
        code = compile(src, "g2game", "exec")
        summary["compile_ok"] = True
        summary["compile_ms"] = time.ticks_diff(time.ticks_ms(), t0)
        step("post-compile")
        ns = {}
        exec(code, ns)
        summary["exec_ok"] = True
        del ns
        del code
    except MemoryError as ex:
        summary["compile_ok"] = False
        summary["compile_err"] = "MemoryError %r" % ex
        step("post-compile", ok=False, note=repr(ex))
    del src
    gc.collect()
    step("after-compile-free")

    # soak: ESP-NOW broadcast and Splat command alternate every SOAK_PERIOD_MS/2
    bc_ms = []
    sp_ms = []
    bc_fail = 0
    sp_fail = 0
    sp_skip = 0
    colors = ("turnred", "turngreen", "turnblue")
    k = 0
    fail0 = group.write_failures
    connects0 = [l.connects for l in hub.links]
    soak_end = time.ticks_add(time.ticks_ms(), SOAK_S * 1000)
    next_at = time.ticks_ms()
    while time.ticks_diff(soak_end, time.ticks_ms()) > 0:
        group.poll()
        enow.poll()
        if time.ticks_diff(time.ticks_ms(), next_at) >= 0:
            next_at = time.ticks_add(next_at, SOAK_PERIOD_MS // 2)
            if k % 2 == 0:
                t0 = time.ticks_us()
                ok = enow.broadcast({"cmd": "g2", "k": k})
                bc_ms.append(time.ticks_diff(time.ticks_us(), t0) // 100)
                if not ok:
                    bc_fail += 1
            else:
                u = group.unit((k // 2) % N)
                if not u.connected:
                    sp_skip += 1
                else:
                    t0 = time.ticks_us()
                    ok = u.color(colors[(k // 2) % 3])
                    sp_ms.append(time.ticks_diff(time.ticks_us(), t0) // 100)
                    if not ok:
                        sp_fail += 1
            k += 1
        time.sleep_ms(1)
    summary["soak"] = {
        "units": "0.1ms",
        "bcast": stats(bc_ms), "bcast_fail": bc_fail,
        "splat": stats(sp_ms), "splat_fail": sp_fail,
        "splat_skipped_not_connected": sp_skip,
        "write_failures": group.write_failures - fail0,
        "reconnects": [l.connects - c for l, c in zip(hub.links, connects0)],
        "states_end": [l.state_name() for l in hub.links],
    }
    del bc_ms
    del sp_ms
    step("post-soak")
    summary["ok"] = all_ready and summary.get("compile_ok", False)
finally:
    hub.close_all()
    leds.fill(OFF)
    finish()
