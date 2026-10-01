"""
splat_api.py -- the `splat` object games receive
==================================================
play(splat, leds, enow, batt=None) games get a SplatGroup instead of the
wand's five hardware objects: there is no NFC, buzzer, motor or
accelerometer here, and the Splats themselves are BLE, not local
peripherals.

SplatGroup drives every Splat this station is configured for (hubtype.py
max_splats / splat_macs; 4 by default) through one SplatAPI per Splat:
color/sound/note/play/off act on all of them, poll() reports a press or
release from any of them with last_index saying which, and unit(i) is one
Splat's own SplatAPI. With one Splat it behaves exactly as that Splat's
SplatAPI.

A game MUST call splat.poll() every loop iteration, exactly as it polls
enow. main.py hands the same SplatGroup to the idle loop (companion.py)
and to each game in turn, so exactly one loop polls it at a time and
nothing else services the BLE links, their keepalives or their button
debounce.

This file is the single source of the action vocabulary below.
ChatBroadcast's js/splat/splatActions.js is generated from it by
ChatBroadcast/tools/sync_splat_actions.py -- run that after editing any of
COLOR_RGB, NOTE_VALUES or ANIMAL_SOUNDS (--check reports drift). The names
are the Bag2 wand's action-card names.
"""

import time


# ─── Action vocabulary (card names) ───────────

COLOR_RGB = {
    "turnred": (255, 0, 0), "turngreen": (0, 255, 0),
    "turnblue": (0, 0, 255), "turnpurple": (160, 0, 200),
    "turnyellow": (255, 180, 0), "turnwhite": (200, 200, 200),
    "turnoff": (0, 0, 0),
}

# name -> (note value, octave offset). Values from the Bag2 companion's
# NOTE_MIDI; the Jan 2026 wand-side controller used different values
# (see README "Drift").
NOTE_VALUES = {
    "note_c": (0, 0), "note_d": (2, 0), "note_e": (4, 0), "note_f": (5, 0),
    "note_g": (7, 0), "note_a": (9, 0), "note_b": (11, 0),
    "note_c_high": (0, 1), "playnote": (0, 0),
}

ANIMAL_SOUNDS = {
    "cat": 19, "chicken": 20, "cow": 21, "dog": 22,
    "pig": 23, "duck": 24, "elephant": 25, "horse": 26, "goat": 28,
}

# ─── Splat write settings ─────────────────────

NOTE_OCTAVE = 4
NOTE_VELOCITY = 127
NOTE_INSTRUMENT = 17
SOUND_VOLUME = 255
KEEPALIVE_MS = 2500
SWITCH_POLL_MS = 150         # readSwitches cadence while ready; 0 = off


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


EVENT_QUEUE_MAX = 16    # SplatGroup press/release events held between polls


class SplatGroup:
    """Every configured Splat, as one `splat` game argument."""

    def __init__(self, hub):
        self.hub = hub
        self.units = [SplatAPI(link) for link in hub.links]
        self.links = hub.links
        self.last_index = None
        self._pending = []           # (index, "press"/"release"), oldest first
        self.events_dropped = 0

    @property
    def count(self):
        """Splats this station is configured for (not how many are up)."""
        return len(self.units)

    @property
    def connected_count(self):
        n = 0
        for u in self.units:
            if u.connected:
                n += 1
        return n

    @property
    def connected(self):
        """True once at least one Splat's BLE link is up."""
        return self.connected_count > 0

    @property
    def write_failures(self):
        return sum(u.write_failures for u in self.units)

    def unit(self, i):
        """One Splat's own SplatAPI, 0-based. IndexError past count."""
        return self.units[i]

    def poll(self):
        """Service every Splat; return "press", "release" or None.

        Events from different Splats are queued and returned one per call,
        oldest first; last_index is the index of the Splat that produced
        the event just returned.
        """
        for i, u in enumerate(self.units):
            ev = u.poll()
            if ev is not None:
                if len(self._pending) >= EVENT_QUEUE_MAX:
                    self.events_dropped += 1
                    print("  [ERR] splat group event queue full: %s from %d dropped"
                          % (ev, i))
                else:
                    self._pending.append((i, ev))
        if not self._pending:
            return None
        i, ev = self._pending.pop(0)
        self.last_index = i
        return ev

    def _each(self, call):
        """call(unit) on every connected unit. True only if at least one is
        connected and every connected unit's write succeeded."""
        any_up = False
        ok = True
        for u in self.units:
            if u.connected:
                any_up = True
                ok = call(u) and ok
        return any_up and ok

    def color(self, name):
        return self._each(lambda u: u.color(name))

    def sound(self, name):
        return self._each(lambda u: u.sound(name))

    def note(self, name):
        return self._each(lambda u: u.note(name))

    def play(self, names):
        return self._each(lambda u: u.play(names))

    def off(self):
        """Stop everything on every Splat, connected or not (each unit's
        off() clears its held-note state either way)."""
        ok = True
        for u in self.units:
            ok = u.off() and ok
        return ok
