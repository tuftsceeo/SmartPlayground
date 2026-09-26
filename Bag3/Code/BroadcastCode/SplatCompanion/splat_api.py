"""
splat_api.py -- the `splat` object games receive
==================================================
play(splat, leds, enow, batt=None) games get a SplatAPI instance instead of
the wand's five hardware objects: there is no NFC, buzzer, motor or
accelerometer here, and the Splat itself is BLE, not a local peripheral.

A game MUST call splat.poll() every loop iteration, exactly as it polls
enow. While a game runs, main.py's bridge (companion.py) is not running, so
nothing else services the BLE link, its keepalive or its button debounce --
poll() is what does all three.

Action names are the card names from lib/actions.py (colors, note_c ...
note_c_high, the animal sounds) -- see knowledge/splat_companion.py.
"""

import time

from companion import (
    COLOR_RGB, NOTE_VALUES, ANIMAL_SOUNDS,
    NOTE_OCTAVE, NOTE_VELOCITY, NOTE_INSTRUMENT, SOUND_VOLUME,
    KEEPALIVE_MS, SWITCH_POLL_MS,
)


class SplatAPI:
    def __init__(self, link):
        self.link = link
        self.write_failures = 0
        self._active_note = None       # (value, octave), or None
        now = time.ticks_ms()
        self._last_ka = now
        self._last_sw = now

    @property
    def connected(self):
        return self.link.ready

    def poll(self):
        """Service the BLE link; return "press", "release", or None.

        Only the most recent debounced edge is reported when more than one
        arrived since the last poll() -- a game loop that polls every
        `time.sleep_ms(1)` iteration never falls behind enough for that to
        matter in practice.
        """
        now = time.ticks_ms()
        self.link.service(now)
        if not self.link.ready:
            return None
        if time.ticks_diff(now, self._last_ka) >= KEEPALIVE_MS:
            self._last_ka = now
            self._check(self.link.keepAlive(), "keepAlive")
        if SWITCH_POLL_MS and time.ticks_diff(now, self._last_sw) >= SWITCH_POLL_MS:
            self._last_sw = now
            self._check(self.link.readSwitches(), "readSwitches")
        events = self.link.take_events()
        if not events:
            return None
        return "press" if events[-1] == 1 else "release"

    def _check(self, ok, what):
        if not ok:
            self.write_failures += 1
            print("  [ERR] splat.%s write failed (failures=%d)"
                  % (what, self.write_failures))
        return ok

    def color(self, name):
        """Set the Splat's LEDs to a card color name, e.g. "turnred"."""
        if not self.link.ready:
            return False
        rgb = COLOR_RGB.get(name)
        if rgb is None:
            print("  [ERR] splat.color: unknown name %r" % name)
            return False
        return self._check(self.link.setLEDsON(rgb), "color")

    def sound(self, name):
        """Play an animal sound card name, e.g. "cat"."""
        if not self.link.ready:
            return False
        idx = ANIMAL_SOUNDS.get(name)
        if idx is None:
            print("  [ERR] splat.sound: unknown name %r" % name)
            return False
        return self._check(self.link.playSound(idx, SOUND_VOLUME), "sound")

    def note(self, name):
        """Play a note card name, e.g. "note_c". Replaces any note already
        held -- only one note plays at a time through this call."""
        if not self.link.ready:
            return False
        v = NOTE_VALUES.get(name)
        if v is None:
            print("  [ERR] splat.note: unknown name %r" % name)
            return False
        self._note_off()
        value, octave_offset = v
        octave = NOTE_OCTAVE + octave_offset
        ok = self._check(
            self.link.noteOn(value, NOTE_VELOCITY, octave, NOTE_INSTRUMENT),
            "note")
        if ok:
            self._active_note = (value, octave)
        return ok

    def _note_off(self):
        if self._active_note is None:
            return
        value, octave = self._active_note
        self._active_note = None
        self._check(
            self.link.noteOff(value, NOTE_VELOCITY, octave, NOTE_INSTRUMENT),
            "note_off")

    def play(self, names):
        """Play a group of card action names together: colors, notes and
        sounds may all be named in one call, same as one AND-group in a
        wand action chain. Unknown names print [ERR] and are skipped;
        returns True only if every write in the group succeeded."""
        ok = True
        for name in names:
            if name in COLOR_RGB:
                ok = self.color(name) and ok
            elif name in ANIMAL_SOUNDS:
                ok = self.sound(name) and ok
            elif name in NOTE_VALUES:
                ok = self.note(name) and ok
            else:
                print("  [ERR] splat.play: unknown action %r" % name)
                ok = False
        return ok

    def off(self):
        """Stop everything: the held note (if any), then allTasksOff and
        allLEDsOff (allTasksOff alone can leave a static color lit)."""
        self._note_off()
        if not self.link.ready:
            return False
        a = self._check(self.link.allTasksOff(), "off(allTasksOff)")
        b = self._check(self.link.allLEDsOff(), "off(allLEDsOff)")
        return a and b
