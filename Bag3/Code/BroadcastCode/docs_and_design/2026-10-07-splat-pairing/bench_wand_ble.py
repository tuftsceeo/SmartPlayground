"""
bench_wand_ble.py -- BLE bring-up and 2 Splats after MockWand main.py's import load
====================================================================================
Run on a MockWand whose main.py is NOT running (renamed to main.py.bak, board reset):
    python3 -m mpremote connect $WAND resume run bench_wand_ble.py
Needs on the wand, in /m1/: splat_link.py, splat_hub.py, splat_api.py, ble_splat.py
(from SplatCompanion/Companion). Both Splats switched on and advertising.

Steps, in main.py's order: module-scope imports, game_store/sys.path, (optional)
hardware objects, ESPNowManager().init(), BLE().active(True), the four Splat
modules, SplatHub(macs=SPLAT_MACS) and SplatGroup serviced until both links are READY.
Each step prints a RESULT line with idf_largest, and memprobe.probe()/frag().
"""

import machine
import time
import sys
import json
import gc
import os

# ── mirrors MockWand/main.py lines 16-49, same order ──
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

# ── mirrors main.py lines 56-58 ──
game_store.ensure_dir()
if game_store.GAMES_DIR not in sys.path:
    sys.path.append(game_store.GAMES_DIR)

# ─── bench constants ───
SPLAT_MACS = ["AB:42:00:00:20:60", "AB:42:00:00:6D:27"]
CONNECT_WAIT_S = 90
BUILD_MODULE_OBJECTS = True   # main.py lines 303-312: Leds, PowerLed, SoftI2C, Buzzer, pins
EXTERNAL_ANTENNA_NOTE = "espnow_manager.EXTERNAL_ANTENNA=%s" % sys.modules["espnow_manager"].EXTERNAL_ANTENNA

sys.path.insert(0, '/m1')

_T0 = time.ticks_ms()


def t_s():
    return time.ticks_diff(time.ticks_ms(), _T0) / 1000


def log(s):
    print("[%7.2f] %s" % (t_s(), s))


def step(name, ok=True, note=""):
    """memprobe lines, then one RESULT line carrying idf_largest."""
    memprobe.probe(name)
    memprobe.frag(name)
    free, largest = memprobe._idf_free()
    log("RESULT step=%s t=%.2f ok=%s idf_largest=%s idf_free=%s gc_free=%d %s"
        % (name, t_s(), ok, largest, free, gc.mem_free(), note))


step("after-imports", note=EXTERNAL_ANTENNA_NOTE)

objs = None
if BUILD_MODULE_OBJECTS:
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

# ── main(): pull_flag.is_pending() then enow.init(), as main.py ──
enow = ESPNowManager()
step("pre-enow")
try:
    enow.init()
    step("post-enow")
except Exception as ex:
    sys.print_exception(ex)
    step("post-enow", ok=False, note="enow.init raised %r" % ex)
    raise SystemExit

# ── SPEC section 4 step 4 ──
try:
    import ubluetooth
    ble = ubluetooth.BLE()
    ble.active(True)
    step("ble-active")
except Exception as ex:
    sys.print_exception(ex)
    step("ble-active", ok=False, note="raised %r" % ex)
    raise SystemExit

try:
    import splat_link
    import splat_hub
    import splat_api
    from splat_hub import SplatHub
    from splat_api import SplatGroup
    step("splat-modules")
except Exception as ex:
    sys.print_exception(ex)
    step("splat-modules", ok=False, note="raised %r" % ex)
    raise SystemExit

hub = SplatHub(macs=SPLAT_MACS)
group = SplatGroup(hub)
step("hub-built")

ready_at = [None] * len(hub.links)
end = time.ticks_add(time.ticks_ms(), CONNECT_WAIT_S * 1000)
try:
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        group.poll()
        for i, link in enumerate(hub.links):
            if ready_at[i] is None and link.state == splat_link.ST_READY:
                ready_at[i] = t_s()
                step("splat%d-ready" % i)
        if None not in ready_at:
            break
        time.sleep_ms(1)
    both = None not in ready_at
    states = [l.state_name() for l in hub.links]
    step("final", ok=both,
         note="ready_at=%s states=%s connects=%s attempts=%s misrouted=%d"
         % (ready_at, states, [l.connects for l in hub.links],
            [l.attempts for l in hub.links], hub.misrouted))
    if both:
        for _ in range(3):
            group.color("turnblue")
            time.sleep_ms(300)
            group.color("turngreen")
            time.sleep_ms(300)
        step("after-writes", note="write_failures=%d" % group.write_failures)
finally:
    hub.close_all()
    log("DONE")
