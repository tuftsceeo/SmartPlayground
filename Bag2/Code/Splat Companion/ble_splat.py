"""
ble_splat_ctrl.py — Direct Splat BLE Controller for Wand
==========================================================
Manages BLE connections from the wand directly to Splat devices,
bypassing the Splat Companion. Handles connection lifecycle,
action execution, radio management (ESP-NOW/BLE coexistence),
and idle signaling.

Requires ble_splat.py in root or /lib/.

Usage:
    from ble_splat_ctrl import (
        sp_connect, sp_disconnect_all, sp_keepalive_all,
        sp_poll_switches_all, sp_process_pending_all,
        sp_reconnect_lost, sp_has_connections, sp_signal_idle,
        espnow_pause, espnow_resume, espnow_quick_check,
        is_sp_trigger, parse_sp_mac,
    )
"""

import time
import network


# ─────────────────────────────────────────────
# SP TAG HELPERS
# ─────────────────────────────────────────────
def is_sp_trigger(name):
    return name is not None and name.startswith("SP:")

def parse_sp_mac(name):
    if not is_sp_trigger(name):
        return None
    return name[3:]


# ─────────────────────────────────────────────
# ESP-NOW / BLE RADIO MANAGEMENT
# ─────────────────────────────────────────────
# The ESP32-C6 shares a single 2.4GHz antenna between
# WiFi (ESP-NOW) and BLE. Time-slicing causes unreliable
# BLE writes when ESP-NOW is active. We pause ESP-NOW
# during BLE-heavy operations.

def espnow_pause(mgr):
    """Pause ESP-NOW to free the radio for BLE."""
    if mgr and mgr.is_active:
        try:
            mgr.enow.active(False)
        except Exception:
            pass
        print("  Radio: ESP-NOW paused for BLE")

def espnow_resume(mgr):
    """Resume ESP-NOW after BLE operations."""
    if mgr and mgr.enow is not None:
        try:
            mgr.enow.active(True)
        except Exception:
            pass
        print("  Radio: ESP-NOW resumed")

def espnow_quick_check(mgr, check_broadcast_fn, batt_ref, leds_ref, buz_ref):
    """
    Briefly enable ESP-NOW, poll for stop/battery, then disable.
    check_broadcast_fn: the check_broadcast function from main.
    Returns "stop", "battery", or None.
    """
    if mgr is None or mgr.enow is None:
        return None
    try:
        mgr.enow.active(True)
        time.sleep_ms(5)
        result = check_broadcast_fn(mgr, batt_ref, leds_ref, buz_ref)
        mgr.enow.active(False)
        return result
    except Exception:
        return None


# ─────────────────────────────────────────────
# ACTION MAPS (Splat command parameters)
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


# ─────────────────────────────────────────────
# ACTION PARSER
# ─────────────────────────────────────────────
def _parse_sp_actions(chain):
    """Parse action chain into color/note/sound lists for Splat."""
    colors, notes, sounds = [], [], []
    for group in chain:
        gc, gn, gs = None, None, None
        for a in group:
            if a in SP_COLOR_RGB:
                gc = a
            elif a in SP_NOTE_MAP:
                gn = a
            elif a in SP_ANIMAL_SOUNDS:
                gs = a
        colors.append(gc)
        notes.append(gn)
        sounds.append(gs)
    return colors, notes, sounds


# ─────────────────────────────────────────────
# DIRECT SPLAT CONTROLLER
# ─────────────────────────────────────────────
class DirectSplatController:
    """
    Manages a direct BLE connection from the wand to a Splat.

    IMPORTANT: on_press/on_release are called from the BLE IRQ
    context (notification handler). You CANNOT do gattc_write from
    inside an IRQ — it silently fails. Instead we set a pending
    flag and the main loop calls process_pending() to execute
    the actual BLE commands.
    """
    def __init__(self, splat):
        self.splat = splat
        self.colors = []
        self.notes = []
        self.sounds = []
        self.configured = False
        self.active_notes = []
        self._pending_press = False
        self._pending_release = False
        self._has_notes = False
        self._was_pressed = False

    def set_config(self, chain):
        self.colors, self.notes, self.sounds = _parse_sp_actions(chain)
        self.configured = True
        self.active_notes = []
        self._pending_press = False
        self._pending_release = False
        self._has_notes = any(n is not None for n in self.notes)
        if self._has_notes:
            # Splat button notifications corrupt the note engine.
            # Disable callbacks — wand button will be used instead.
            print("  SP: Notes detected — use wand button to trigger")
            self.splat.on_splat_pressed = None
            self.splat.on_splat_released = None
        else:
            self.splat.on_splat_pressed = self.on_press
            self.splat.on_splat_released = self.on_release
        print("  SP Config: %d groups (has_notes=%s)" % (len(chain), self._has_notes))

    def clear_config(self):
        self.colors = []; self.notes = []; self.sounds = []
        self.configured = False
        self._pending_press = False
        self._pending_release = False
        if self.splat.connected:
            for mn in self.active_notes:
                try:
                    self.splat.noteOff(mn, SP_DEFAULT_VELOCITY, SP_DEFAULT_OCTAVE, SP_DEFAULT_INSTRUMENT)
                except Exception:
                    pass
            try:
                self.splat.allLEDsOff()
            except Exception:
                pass
        self.active_notes = []

    def on_press(self):
        """Called from BLE IRQ — just set flag, don't do BLE writes."""
        if not self.configured:
            return
        self._pending_press = True
        self._pending_release = False

    def on_release(self):
        """Called from BLE IRQ — just set flag, don't do BLE writes."""
        if not self.configured:
            return
        self._pending_release = True

    def process_pending(self):
        """
        Called from main loop. Processes pending press/release from callbacks.
        For note configs, use wand_button_event() instead.
        """
        if self._has_notes:
            # Handled by wand_button_event() from sp_loop
            return False
        if self._pending_press:
            self._pending_press = False
            self._do_press()
            return True
        if self._pending_release:
            self._pending_release = False
            self._do_release()
            return True
        return False

    def wand_button_event(self, pressed):
        """
        Called from sp_loop when wand physical button changes state.
        Used when notes are in the config since Splat button notifications
        corrupt the note engine.
        """
        if not self.configured or not self.splat.connected:
            return
        if pressed:
            self._do_press()
        else:
            self._do_release()

    def _do_press(self):
        if not self.splat.connected:
            return
        print("  SP PRESSED")
        self.active_notes = []
        for i in range(len(self.colors)):
            c, n, s = self.colors[i], self.notes[i], self.sounds[i]
            # LED first — most visible, least likely to block
            if c and c in SP_COLOR_RGB:
                try:
                    self.splat.setLEDsON(SP_COLOR_RGB[c])
                except Exception as e:
                    print("    SP LED err: %s" % str(e))
                time.sleep_ms(30)
            # Sound second — fire-and-forget
            if s and s in SP_ANIMAL_SOUNDS:
                try:
                    self.splat.playSound(SP_ANIMAL_SOUNDS[s], SP_DEFAULT_SOUND_VOL)
                except Exception as e:
                    print("    SP Sound err: %s" % str(e))
                time.sleep_ms(30)
            # Note last — can put Splat in sustained state
            if n and n in SP_NOTE_MAP:
                mn = SP_NOTE_MAP[n]
                print("    SP Note: %s -> val=%d, oct=%d, vel=%d, inst=%d" % (n, mn, SP_DEFAULT_OCTAVE, SP_DEFAULT_VELOCITY, SP_DEFAULT_INSTRUMENT))
                try:
                    self.splat.noteOn(mn, SP_DEFAULT_VELOCITY, SP_DEFAULT_OCTAVE, SP_DEFAULT_INSTRUMENT)
                    self.active_notes.append(mn)
                except Exception as e:
                    print("    SP Note err: %s" % str(e))
                time.sleep_ms(30)
            if i < len(self.colors) - 1:
                time.sleep_ms(400)

    def _do_release(self):
        if not self.splat.connected:
            return
        print("  SP RELEASED")
        self._stop_all()

    def _stop_all(self):
        if not self.splat.connected:
            return
        # allTasksOff is a nuclear reset — stops notes, sounds,
        # LED sequences, everything in one command. Much more
        # reliable than 3 separate writes that can collide.
        try:
            self.splat.allTasksOff()
        except Exception:
            pass
        self.active_notes = []


# ─────────────────────────────────────────────
# CONNECTION MANAGER
# ─────────────────────────────────────────────
_sp_connections = {}   # { "SP:<MAC>": { "splat": OpenSplat, "ctrl": DirectSplatController } }


def sp_connect(sp_mac, leds, mgr=None):
    """
    Connect to a Splat device via BLE.
    sp_mac: BLE MAC string like "AB:42:00:00:7E:B6"
    leds: Leds instance for status feedback.
    mgr: ESPNowManager — will be paused during BLE connect.
    Returns (OpenSplat, DirectSplatController) or (None, None).
    """
    from ble_splat import OpenSplat

    key = "SP:" + sp_mac
    if key in _sp_connections:
        entry = _sp_connections[key]
        if entry["splat"].connected:
            return entry["splat"], entry["ctrl"]
        else:
            print("  SP: stale connection for %s, reconnecting..." % sp_mac)
            try:
                entry["splat"].disconnect()
            except Exception:
                pass

    print("  SP: Connecting to Splat %s via BLE..." % sp_mac)
    leds.solid(0, 0, 15)

    espnow_pause(mgr)

    splat = OpenSplat(mac_address=sp_mac, verbose=False)
    ctrl = DirectSplatController(splat)
    splat.on_splat_pressed = ctrl.on_press
    splat.on_splat_released = ctrl.on_release

    ok = splat.connect(timeout=15)
    if not ok:
        print("  SP: First attempt failed, retrying...")
        leds.flash(15, 8, 0, times=3, on_ms=80, off_ms=60)
        ok = splat.connect(timeout=15)

    if not ok:
        print("  SP: [FAIL] Could not connect to Splat %s" % sp_mac)
        leds.flash(15, 0, 0, times=5, on_ms=80, off_ms=60)
        espnow_resume(mgr)
        return None, None

    print("  SP: BLE connected to %s!" % sp_mac)
    leds.flash(0, 15, 0, times=3, on_ms=80, off_ms=60)

    # NOTE: Do NOT call identifySplat() here — it starts an LED
    # sequence on the Splat that blocks subsequent setLEDsON commands.

    _sp_connections[key] = {"splat": splat, "ctrl": ctrl}
    return splat, ctrl


def sp_signal_idle(entry):
    """Flash an LED pattern on the Splat to indicate idle/disconnected."""
    splat = entry["splat"]
    if not splat.connected:
        return
    try:
        splat.soundOff()
        time.sleep_ms(30)
        splat.allLEDsOff()
        time.sleep_ms(50)
        # Flash orange 3 times
        for _ in range(3):
            splat.setLEDsON((255, 80, 0))
            time.sleep_ms(200)
            splat.allLEDsOff()
            time.sleep_ms(150)
    except Exception as e:
        print("  SP idle signal err: %s" % str(e))


def sp_disconnect_all(mgr=None):
    """Signal idle on all Splats, then disconnect."""
    for key in list(_sp_connections.keys()):
        entry = _sp_connections[key]
        try:
            entry["ctrl"].clear_config()
        except Exception:
            pass
        sp_signal_idle(entry)
        try:
            entry["splat"].disconnect()
        except Exception:
            pass
        print("  SP: Disconnected %s" % key)
    _sp_connections.clear()
    espnow_resume(mgr)


def sp_keepalive_all():
    """Send keepalive to all connected Splats."""
    for key, entry in _sp_connections.items():
        if entry["splat"].connected:
            try:
                entry["splat"].keepAlive()
            except Exception:
                pass


def sp_poll_switches_all():
    """No longer needed — Splat sends button notifications via interrupt.
    Kept as no-op for compatibility in case sp_loop.py calls it."""
    pass


def sp_process_pending_all():
    """Process any pending press/release actions from BLE IRQ callbacks."""
    for key, entry in _sp_connections.items():
        entry["ctrl"].process_pending()


def sp_reconnect_lost(leds, mgr=None):
    """Check for lost connections and attempt reconnect."""
    for key in list(_sp_connections.keys()):
        entry = _sp_connections[key]
        if not entry["splat"].connected:
            sp_mac = key[3:]
            print("  SP: [WARN] BLE lost for %s — reconnecting..." % sp_mac)
            leds.solid(0, 0, 15)
            espnow_pause(mgr)
            ok = entry["splat"].connect(timeout=10)
            if ok:
                print("  SP: Reconnected %s!" % sp_mac)
                leds.flash(0, 15, 0, times=2, on_ms=80, off_ms=60)
            else:
                print("  SP: Reconnect failed for %s" % sp_mac)


def sp_has_connections():
    """Check if any SP connections exist."""
    return len(_sp_connections) > 0


def sp_has_notes():
    """Check if any SP connection has notes configured."""
    for key, entry in _sp_connections.items():
        if entry["ctrl"]._has_notes:
            return True
    return False


def sp_wand_button_event(pressed):
    """Forward wand button event to all SP controllers with notes."""
    for key, entry in _sp_connections.items():
        if entry["ctrl"]._has_notes:
            entry["ctrl"].wand_button_event(pressed)


def sp_get_connections():
    """Return the connections dict (for cleanup in main)."""
    return _sp_connections