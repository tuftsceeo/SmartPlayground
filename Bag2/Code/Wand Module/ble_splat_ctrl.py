"""
ble_splat_ctrl.py — Direct Splat BLE Controller for Wand (v4)
================================================================
Split from the working unified main.py.
IMPORTANT: After copying to device, verify version prints on boot.
"""

_VERSION = "v4"

import time
import network


# ─────────────────────────────────────────────
# SP TAG HELPERS
# ─────────────────────────────────────────────
def is_sp_trigger(name):
    return name is not None and name.startswith("SP:")

def parse_sp_mac(name):
    if not is_sp_trigger(name): return None
    return name[3:]


# ─────────────────────────────────────────────
# ESP-NOW / BLE RADIO MANAGEMENT
# ─────────────────────────────────────────────
def espnow_pause(mgr):
    if mgr and mgr.is_active:
        try: mgr.enow.active(False)
        except Exception: pass
        print("  Radio: ESP-NOW paused for BLE")

def espnow_resume(mgr):
    if mgr and mgr.enow is not None:
        try: mgr.enow.active(True)
        except Exception: pass
        print("  Radio: ESP-NOW resumed")

def espnow_quick_check(mgr, check_broadcast_fn, batt_ref, leds_ref, buz_ref):
    if mgr is None or mgr.enow is None: return None
    try:
        mgr.enow.active(True)
        time.sleep_ms(5)
        result = check_broadcast_fn(mgr, batt_ref, leds_ref, buz_ref)
        mgr.enow.active(False)
        return result
    except Exception: return None


# ─────────────────────────────────────────────
# ACTION MAPS
# ─────────────────────────────────────────────
SP_COLOR_RGB = {
    "turnred": (255, 0, 0), "turngreen": (0, 255, 0),
    "turnblue": (0, 0, 255), "turnpurple": (160, 0, 200),
    "turnyellow": (255, 180, 0), "turnwhite": (200, 200, 200),
    "turnoff": (0, 0, 0),
}

SP_NOTE_MAP = {
    "notec": 1, "noted": 3, "notee": 6, "notef": 7,
    "noteg": 10, "notea": 13, "noteb": 15, "playnote": 1,
}

SP_ANIMAL_SOUNDS = {
    "cat": 19, "chicken": 20, "cow": 21, "dog": 22,
    "pig": 23, "duck": 24, "elephant": 25, "horse": 26, "goat": 28,
}

SP_DEFAULT_OCTAVE = 4
SP_DEFAULT_VELOCITY = 255
SP_DEFAULT_INSTRUMENT = 16
SP_DEFAULT_SOUND_VOL = 255


def _parse_sp_actions(chain):
    colors, notes, sounds = [], [], []
    for group in chain:
        gc, gn, gs = None, None, None
        for a in group:
            if a in SP_COLOR_RGB: gc = a
            elif a in SP_NOTE_MAP: gn = a
            elif a in SP_ANIMAL_SOUNDS: gs = a
        colors.append(gc); notes.append(gn); sounds.append(gs)
    return colors, notes, sounds


# ─────────────────────────────────────────────
# DIRECT SPLAT CONTROLLER
# ─────────────────────────────────────────────
class DirectSplatController:
    def __init__(self, splat):
        self.splat = splat
        self.colors = []
        self.notes = []
        self.sounds = []
        self.configured = False
        self.active_notes = []
        self._pending_press = False
        self._pending_release = False

    def set_config(self, chain):
        self.colors, self.notes, self.sounds = _parse_sp_actions(chain)
        self.configured = True
        self.active_notes = []
        self._pending_press = False
        self._pending_release = False
        self.splat.on_splat_pressed = self.on_press
        self.splat.on_splat_released = self.on_release
        self.splat.splat_pressed = False
        self.splat._last_raw_state = False
        self.splat._last_button_change_ms = 0
        print("  SP Config: %d groups" % len(chain))

    def clear_config(self):
        self.colors = []; self.notes = []; self.sounds = []
        self.configured = False
        self._pending_press = False
        self._pending_release = False
        self.active_notes = []
        if self.splat.connected:
            try: self.splat.allLEDsOff()
            except Exception: pass

    def on_press(self):
        if not self.configured: return
        self._pending_press = True
        self._pending_release = False

    def on_release(self):
        if not self.configured: return
        self._pending_release = True

    def process_pending(self):
        if self._pending_press:
            self._pending_press = False
            self._do_press()
            return True
        if self._pending_release:
            self._pending_release = False
            self._do_release()
            return True
        return False

    def _do_press(self):
        if not self.splat.connected: return
        print("  SP PRESSED")
        self.active_notes = []
        for i in range(len(self.colors)):
            c, n, s = self.colors[i], self.notes[i], self.sounds[i]
            if c and c in SP_COLOR_RGB:
                rgb = SP_COLOR_RGB[c]
                try:
                    self.splat._ble.gattc_write(
                        self.splat._conn_handle, self.splat._tx_char_handle,
                        bytearray([0x01, 0x50, 0xFF, 0x3F, rgb[0], rgb[1], rgb[2]]))
                except Exception as e:
                    print("    LED err: %s" % str(e))
                time.sleep_ms(30)
            if s and s in SP_ANIMAL_SOUNDS:
                try:
                    self.splat._ble.gattc_write(
                        self.splat._conn_handle, self.splat._tx_char_handle,
                        bytearray([0x00, 0x20, SP_ANIMAL_SOUNDS[s], SP_DEFAULT_SOUND_VOL]))
                except Exception as e:
                    print("    Sound err: %s" % str(e))
                time.sleep_ms(30)
            if n and n in SP_NOTE_MAP:
                mn = SP_NOTE_MAP[n]
                try:
                    self.splat._ble.gattc_write(
                        self.splat._conn_handle, self.splat._tx_char_handle,
                        bytearray([0, 64, mn, SP_DEFAULT_OCTAVE, SP_DEFAULT_VELOCITY, SP_DEFAULT_INSTRUMENT]))
                    self.active_notes.append(mn)
                except Exception as e:
                    print("    Note err: %s" % str(e))
                time.sleep_ms(30)
            if i < len(self.colors) - 1:
                time.sleep_ms(400)

    def _do_release(self):
        if not self.splat.connected: return
        print("  SP RELEASED")
        for mn in self.active_notes:
            try:
                self.splat._ble.gattc_write(
                    self.splat._conn_handle, self.splat._tx_char_handle,
                    bytearray([1, 64, mn, SP_DEFAULT_OCTAVE, SP_DEFAULT_VELOCITY, SP_DEFAULT_INSTRUMENT]))
            except Exception: pass
        self.active_notes = []
        try:
            self.splat._ble.gattc_write(
                self.splat._conn_handle, self.splat._tx_char_handle,
                bytearray([0x03, 0x00]))
        except Exception: pass


# ─────────────────────────────────────────────
# CONNECTION MANAGER
# ─────────────────────────────────────────────
_sp_connections = {}


def sp_connect(sp_mac, leds, mgr=None):
    from ble_splat import OpenSplat
    key = "SP:" + sp_mac
    if key in _sp_connections:
        entry = _sp_connections[key]
        if entry["splat"].connected:
            return entry["splat"], entry["ctrl"]
        try: entry["splat"].disconnect()
        except Exception: pass

    print("  SP: Connecting to Splat %s via BLE..." % sp_mac)
    leds.solid(0, 0, 15)
    espnow_pause(mgr)

    splat = OpenSplat(mac_address=sp_mac, verbose=False)
    ctrl = DirectSplatController(splat)

    ok = splat.connect(timeout=15)
    if not ok:
        leds.flash(15, 8, 0, times=3, on_ms=80, off_ms=60)
        ok = splat.connect(timeout=15)
    if not ok:
        print("  SP: [FAIL] Could not connect to %s" % sp_mac)
        leds.flash(15, 0, 0, times=5, on_ms=80, off_ms=60)
        espnow_resume(mgr)
        return None, None

    print("  SP: BLE connected to %s!" % sp_mac)
    leds.flash(0, 15, 0, times=3, on_ms=80, off_ms=60)
    _sp_connections[key] = {"splat": splat, "ctrl": ctrl}
    return splat, ctrl


def sp_signal_idle(entry):
    splat = entry["splat"]
    if not splat.connected: return
    try:
        splat.allLEDsOff()
        time.sleep_ms(50)
        for _ in range(3):
            splat.setLEDsON((255, 80, 0))
            time.sleep_ms(200)
            splat.allLEDsOff()
            time.sleep_ms(150)
    except Exception: pass


def sp_disconnect_all(leds, mgr=None):
    for key in list(_sp_connections.keys()):
        entry = _sp_connections[key]
        try: entry["ctrl"].clear_config()
        except Exception: pass
        sp_signal_idle(entry)
        try: entry["splat"].disconnect()
        except Exception: pass
    _sp_connections.clear()
    espnow_resume(mgr)


def sp_keepalive_all():
    for key, entry in _sp_connections.items():
        if entry["splat"].connected:
            try: entry["splat"].keepAlive()
            except Exception: pass


def sp_process_pending_all():
    for key, entry in _sp_connections.items():
        entry["ctrl"].process_pending()


def sp_get_connections():
    return _sp_connections


print("[ble_splat_ctrl %s loaded]" % _VERSION)