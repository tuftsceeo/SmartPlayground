"""
Splat Companion — ESP-NOW ↔ BLE Bridge
========================================
Board: Seeed XIAO ESP32-C6
Requires hubtype.txt containing: splat_companion
Requires /lib/ and ble_splat.py in root
"""

import machine
import time

from hubtype import HUB_TYPE, HUB_CONFIG
from leds import Leds
from max17048 import MAX17048
from battery import show_battery
from espnow_manager import ESPNowManager
from ble_splat import OpenSplat

# ─────────────────────────────────────────────
# COLOR / NOTE / SOUND MAPS
# ─────────────────────────────────────────────
COLOR_RGB = {
    "turnred": (255, 0, 0), "turngreen": (0, 255, 0),
    "turnblue": (0, 0, 255), "turnpurple": (160, 0, 200),
    "turnyellow": (255, 180, 0), "turnwhite": (200, 200, 200),
    "turnoff": (0, 0, 0),
}

NOTE_MIDI = {
    "notec": 0, "noted": 2, "notee": 4, "notef": 5,
    "noteg": 7, "notea": 9, "noteb": 11, "playnote": 0,
}

ANIMAL_SOUNDS = {
    "cat": 19, "chicken": 20, "cow": 21, "dog": 22,
    "pig": 23, "duck": 24, "elephant": 25, "horse": 26, "goat": 28,
}

DEFAULT_OCTAVE = 4
DEFAULT_VELOCITY = 127
DEFAULT_INSTRUMENT = 17
DEFAULT_SOUND_VOL = 255

# Status colors
S_BLE_CONN = (0, 0, 15)
S_BLE_OK   = (0, 15, 0)
S_READY    = (0, 15, 15)
S_CONFIG   = (15, 0, 15)
S_ERROR    = (15, 0, 0)


# ─────────────────────────────────────────────
# ACTION PARSER
# ─────────────────────────────────────────────
def parse_actions(chain):
    colors, notes, sounds = [], [], []
    for group in chain:
        gc, gn, gs = None, None, None
        for a in group:
            if a in COLOR_RGB: gc = a
            elif a in NOTE_MIDI: gn = a
            elif a in ANIMAL_SOUNDS: gs = a
        colors.append(gc); notes.append(gn); sounds.append(gs)
    return colors, notes, sounds


# ─────────────────────────────────────────────
# SPLAT CONTROLLER
# ─────────────────────────────────────────────
class SplatController:
    def __init__(self, splat):
        self.splat = splat
        self.colors = []
        self.notes = []
        self.sounds = []
        self.configured = False
        self.active_notes = []

    def set_config(self, chain):
        self.colors, self.notes, self.sounds = parse_actions(chain)
        self.configured = True
        self.active_notes = []
        print("  Config: %d groups" % len(chain))

    def clear_config(self):
        self.colors = []; self.notes = []; self.sounds = []
        self.configured = False
        self._stop_all()

    def on_press(self):
        if not self.configured or not self.splat.connected: return
        print("  PRESSED")
        self.active_notes = []
        for i in range(len(self.colors)):
            c, n, s = self.colors[i], self.notes[i], self.sounds[i]
            if c and c in COLOR_RGB:
                try: self.splat.setLEDsON(COLOR_RGB[c])
                except Exception as e: print("    LED err: %s" % str(e))
            if n and n in NOTE_MIDI:
                mn = NOTE_MIDI[n]
                try:
                    self.splat.noteOn(mn, DEFAULT_VELOCITY, DEFAULT_OCTAVE, DEFAULT_INSTRUMENT)
                    self.active_notes.append(mn)
                except Exception as e: print("    Note err: %s" % str(e))
            if s and s in ANIMAL_SOUNDS:
                try: self.splat.playSound(ANIMAL_SOUNDS[s], DEFAULT_SOUND_VOL)
                except Exception as e: print("    Sound err: %s" % str(e))
            if i < len(self.colors) - 1:
                time.sleep_ms(400)

    def on_release(self):
        if not self.configured or not self.splat.connected: return
        print("  RELEASED")
        self._stop_all()

    def _stop_all(self):
        if not self.splat.connected: return
        for mn in self.active_notes:
            try: self.splat.noteOff(mn, DEFAULT_VELOCITY, DEFAULT_OCTAVE, DEFAULT_INSTRUMENT)
            except Exception: pass
        self.active_notes = []
        try: self.splat.allLEDsOff()
        except Exception: pass
        try: self.splat.soundOff()
        except Exception: pass


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "=" * 50)
    print("  Splat Companion — BLE/ESP-NOW Bridge")
    print("  Hub type: %s" % HUB_TYPE)
    print("=" * 50)

    leds = Leds()

    # Battery
    i2c = machine.SoftI2C(
        sda=machine.Pin(HUB_CONFIG["i2c_sda"]),
        scl=machine.Pin(HUB_CONFIG["i2c_scl"]),
        freq=HUB_CONFIG["i2c_freq"],
    )
    batt = None
    if HUB_CONFIG.get("has_battery"):
        try:
            batt = MAX17048(i2c)
            v, s = batt.read_all()
            print("  Battery: %.2fV, %.1f%%" % (v, s))
        except Exception:
            batt = None; print("  [WARN] No battery gauge")

    # ── BLE connect ──
    print("\n  Phase 1: BLE connect...")
    leds.solid(*S_BLE_CONN)

    splat = OpenSplat(verbose=False)
    ctrl = SplatController(splat)
    splat.on_splat_pressed = ctrl.on_press
    splat.on_splat_released = ctrl.on_release

    mac = splat.scanSplat(timeout=10)
    if mac: print("  Found: %s" % mac)

    ok = splat.connect(timeout=30)
    if not ok:
        leds.flash(*S_ERROR, times=5); time.sleep(5)
        ok = splat.connect(timeout=30)
        if not ok:
            print("  [FAIL] BLE failed. Reboot.")
            leds.solid(*S_ERROR)
            while True: time.sleep(1)

    print("  BLE connected!")
    leds.flash(*S_BLE_OK, times=3)
    try: splat.identifySplat()
    except Exception: pass

    # ── ESP-NOW ──
    print("\n  Phase 2: ESP-NOW...")
    mgr = ESPNowManager()
    mgr.init()
    leds.solid(*S_READY)
    print("  Ready\n")

    # ── Main loop ──
    last_ka = time.ticks_ms()
    last_sw = time.ticks_ms()
    frame = 0

    while True:
        try:
            now = time.ticks_ms()

            if time.ticks_diff(now, last_ka) >= 2500:
                if splat.connected:
                    try: splat.keepAlive()
                    except Exception: pass
                last_ka = now

            if ctrl.configured and splat.connected and time.ticks_diff(now, last_sw) >= 150:
                try: splat.readSwitches()
                except Exception: pass
                last_sw = now

            if not splat.connected:
                print("  [WARN] BLE lost — reconnecting...")
                leds.solid(*S_BLE_CONN); ctrl.clear_config()
                if splat.connect(timeout=15):
                    print("  Reconnected!")
                    leds.solid(*S_READY)
                else:
                    leds.flash(*S_ERROR, times=2); time.sleep(2); continue

            # ESP-NOW
            msg_type, data, mac_str = mgr.poll()

            if msg_type == "splat_config":
                actions = data.get("actions")
                if actions:
                    ctrl.set_config(actions)
                    leds.flash(0, 15, 15, times=2, on_ms=100, off_ms=60)
                    leds.solid(*S_CONFIG)
                    print("  Listening...\n")

            elif msg_type == "stop":
                ctrl.clear_config()
                leds.flash(15, 8, 0, times=2, on_ms=100, off_ms=60)
                leds.solid(*S_READY)
                print("  Stopped\n")

            elif msg_type == "battery":
                show_battery(batt, leds, None)
                leds.solid(S_CONFIG if ctrl.configured else S_READY)

            # Status animation
            if msg_type is None:
                if ctrl.configured:
                    leds.breathe(15, 0, 15, frame)
                elif frame % 5 == 0:
                    leds.breathe(0, 10, 10, frame)
            frame += 1

        except KeyboardInterrupt:
            ctrl.clear_config(); splat.disconnect(); leds.off(); mgr.shutdown(); break
        except Exception as e:
            print("  [ERR] %s" % str(e)); time.sleep_ms(500)


if __name__ == "__main__":
    main()