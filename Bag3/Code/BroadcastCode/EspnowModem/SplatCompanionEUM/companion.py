"""
companion.py -- Splat Companion logic: ESP-NOW (via EUM) <-> Splat (BLE)
=======================================================================
Hardware-free. Companion takes an ESP-NOW manager, a SplatLink and a
status-LED object, so the same code runs on the device and in the CPython
simulation (EspnowModem/tests/test_splat_companion.py).

One step() call services, in order:
1. the BLE link state machine (SplatLink.service)
2. splat button events queued by the BLE IRQ
3. keepalive and switch polling
4. the chain player
5. up to ESPNOW_BATCH ESP-NOW messages (mgr.poll)
6. the status LEDs

The longest waits inside step() are the BLE driver's 20 ms write pacing
and a unicast relay waiting for its ESP-NOW ACK (host timeout 300 ms).

Messages in (from wands or a remote):
    {"type": "splat_config", "actions": [[...], ...]}
        chain to play on each splat press; held notes stop on release
    {"type": "splat_cmd", "actions": [[...], ...]}
        play the chain now; notes stop NOTE_HOLD_MS after the last group
    {"type": "splat_cmd", "off": true}
        stop everything on the splat
    {"type": "stop"} or ["stop"]
        clear the config, stop the splat, forget the owner
Messages out:
    {"type": "splat_event", "event": "press" | "release", "splat": "<BLE MAC>"}
        unicast to the owner (the last splat_config / splat_cmd sender),
        broadcast when there is no owner or RELAY_TO_OWNER is False

Action names are the card names used by lib/actions.py: turn* colors,
note_c ... note_c_high, playnote, and the animal sounds.
"""

import time


# ─── Tunables ─────────────────────────────────

GROUP_GAP_MS = 400           # between chain groups
NOTE_HOLD_MS = 400           # splat_cmd notes: noteOff after the last group
KEEPALIVE_MS = 2500
SWITCH_POLL_MS = 150         # readSwitches cadence while ready; 0 = off
ESPNOW_POLL_MS = 5           # idle interval between modem FETCHes
ESPNOW_BATCH = 8             # max messages handled per step
CONNECT_FLASH_MS = 300       # green splat flash on each BLE connect; 0 = off
RELAY_TO_OWNER = True

NOTE_OCTAVE = 4
NOTE_VELOCITY = 127
NOTE_INSTRUMENT = 17
SOUND_VOLUME = 255

# ─── Action maps (card names only) ────────────

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

# Companion status LED colors: (r, g, b), breathe
LED_MODEM_DOWN = ((15, 0, 0), False)
LED_BLE_WAIT = ((0, 0, 15), False)
LED_READY = ((0, 12, 12), True)
LED_CONFIGURED = ((12, 0, 12), True)
LED_PRESSED = ((15, 15, 15), False)

GREEN = (0, 255, 0)


def parse_chain(actions):
    """Parse an action chain into steps.

    actions: list of groups; a group is a list of action names or one name.
    Returns (steps, errors). Each step is (rgb or None, sound id or None,
    (note value, octave) or None). Within a group the last color, sound and
    note named win. Unknown names are reported in errors and skipped.
    """
    steps = []
    errors = []
    if not isinstance(actions, list):
        return steps, ["actions is %s, not a list" % type(actions).__name__]
    for gi, group in enumerate(actions):
        if isinstance(group, str):
            group = [group]
        if not isinstance(group, list):
            errors.append("group %d is %s, not a list" % (gi, type(group).__name__))
            continue
        rgb = sound = note = None
        for a in group:
            if a in COLOR_RGB:
                rgb = COLOR_RGB[a]
            elif a in ANIMAL_SOUNDS:
                sound = ANIMAL_SOUNDS[a]
            elif a in NOTE_VALUES:
                v, dv = NOTE_VALUES[a]
                note = (v, NOTE_OCTAVE + dv)
            else:
                errors.append("group %d: unknown action %r" % (gi, a))
        steps.append((rgb, sound, note))
    return steps, errors


class ChainPlayer:
    """Plays parsed steps one group per GROUP_GAP_MS without blocking."""

    def __init__(self, splat):
        self.splat = splat
        self.steps = []
        self.i = 0
        self.hold = False
        self.next_ms = 0
        self.notes = []          # (value, octave) currently on
        self.notes_off_at = None
        self.write_failures = 0

    @property
    def busy(self):
        return self.i < len(self.steps) or self.notes_off_at is not None

    def start(self, steps, hold, now):
        """hold=True keeps notes on until cancel(); False stops them itself."""
        if self.notes:
            self._notes_off()
        self.steps = steps
        self.i = 0
        self.hold = hold
        self.next_ms = now
        self.notes_off_at = None
        self.service(now)

    def cancel(self):
        """Drop remaining groups. The caller stops the splat's outputs."""
        self.steps = []
        self.i = 0
        self.notes = []
        self.notes_off_at = None

    def service(self, now):
        if self.i < len(self.steps):
            if time.ticks_diff(now, self.next_ms) >= 0:
                self._play(self.steps[self.i])
                self.i += 1
                self.next_ms = time.ticks_add(now, GROUP_GAP_MS)
                if self.i == len(self.steps) and not self.hold and self.notes:
                    self.notes_off_at = time.ticks_add(now, NOTE_HOLD_MS)
        elif (self.notes_off_at is not None and
              time.ticks_diff(now, self.notes_off_at) >= 0):
            self.notes_off_at = None
            self._notes_off()

    def check_write(self, ok, what):
        if not ok:
            self.write_failures += 1
            print("  [ERR] splat %s write failed (failures=%d)"
                  % (what, self.write_failures))

    def _play(self, step):
        rgb, sound, note = step
        # LED first, then sound, then note (order from the Jan 2026 wand-side
        # controller: a note can leave the splat in a sustained state).
        if rgb is not None:
            self.check_write(self.splat.setLEDsON(rgb), "setLEDsON")
        if sound is not None:
            self.check_write(self.splat.playSound(sound, SOUND_VOLUME), "playSound")
        if note is not None:
            v, octave = note
            self.check_write(self.splat.noteOn(v, NOTE_VELOCITY, octave, NOTE_INSTRUMENT),
                        "noteOn")
            self.notes.append(note)

    def _notes_off(self):
        for v, octave in self.notes:
            self.check_write(self.splat.noteOff(v, NOTE_VELOCITY, octave, NOTE_INSTRUMENT),
                        "noteOff")
        self.notes = []


class Companion:
    def __init__(self, mgr, link, leds=None):
        self.mgr = mgr
        self.link = link
        self.leds = leds
        self.player = ChainPlayer(link)
        self.config = None           # parsed steps played on each press
        self.owner = None            # mac_str of the last controller
        self.pressed = False
        now = time.ticks_ms()
        self._next_poll = now
        self._last_ka = now
        self._last_sw = now
        self._leds_off_at = None
        self._events_dropped_seen = 0
        self.counters = {
            "rx": 0, "configs": 0, "cmds": 0, "stops": 0, "ignored": 0,
            "bad_msgs": 0, "presses": 0, "releases": 0, "relays": 0,
            "relay_failures": 0, "cmds_dropped": 0, "ble_up": 0, "ble_down": 0,
        }

    # ─── Loop ─────────────────────────────────

    def step(self):
        now = time.ticks_ms()
        link = self.link
        was_ready = link.ready
        link.service(now)
        if link.ready and not was_ready:
            self._on_ble_up(now)
        elif was_ready and not link.ready:
            self._on_ble_down()

        if link.events_dropped != self._events_dropped_seen:
            print("  [ERR] splat button queue overflow: %d events dropped"
                  % (link.events_dropped - self._events_dropped_seen))
            self._events_dropped_seen = link.events_dropped

        events = link.take_events()
        if link.ready:
            for ev in events:
                self._on_button(ev == 1, time.ticks_ms())
            now = time.ticks_ms()
            self._service_ble(now)
        elif events:
            print("  [WARN] %d splat button events while not ready, dropped"
                  % len(events))

        if time.ticks_diff(now, self._next_poll) >= 0:
            n = 0
            while n < ESPNOW_BATCH:
                msg_type, data, mac = self.mgr.poll()
                if msg_type is None:
                    break
                n += 1
                self.on_message(msg_type, data, mac)
            now = time.ticks_ms()
            self._next_poll = now if n == ESPNOW_BATCH else time.ticks_add(
                now, ESPNOW_POLL_MS)

        if self.leds is not None:
            color, breathe = self._led_state()
            self.leds.show(color, breathe, now)

    def _service_ble(self, now):
        link = self.link
        if time.ticks_diff(now, self._last_ka) >= KEEPALIVE_MS:
            self._last_ka = now
            self.player.check_write(link.keepAlive(), "keepAlive")
        if SWITCH_POLL_MS and time.ticks_diff(now, self._last_sw) >= SWITCH_POLL_MS:
            self._last_sw = now
            self.player.check_write(link.readSwitches(), "readSwitches")
        if (self._leds_off_at is not None and
                time.ticks_diff(now, self._leds_off_at) >= 0):
            self._leds_off_at = None
            if not self.player.busy:
                self.player.check_write(link.allLEDsOff(), "allLEDsOff")
        self.player.service(now)

    def _led_state(self):
        lk = getattr(self.mgr, "_link", None)
        if lk is not None and getattr(lk, "down", False):
            return LED_MODEM_DOWN
        if not self.link.ready:
            return LED_BLE_WAIT
        if self.pressed:
            return LED_PRESSED
        if self.config is not None:
            return LED_CONFIGURED
        return LED_READY

    # ─── BLE side ─────────────────────────────

    def _on_ble_up(self, now):
        self.counters["ble_up"] += 1
        self.pressed = False
        self._last_ka = now
        self._last_sw = now
        if CONNECT_FLASH_MS:
            self.player.check_write(self.link.setLEDsON(GREEN), "setLEDsON")
            self._leds_off_at = time.ticks_add(now, CONNECT_FLASH_MS)

    def _on_ble_down(self):
        self.counters["ble_down"] += 1
        self.player.cancel()
        self._leds_off_at = None
        if self.pressed:
            self.pressed = False
            self._relay("release")
        print("  Companion: BLE down; config %s"
              % ("kept" if self.config is not None else "none"))

    def _on_button(self, pressed, now):
        if pressed == self.pressed:
            return
        self.pressed = pressed
        if pressed:
            self.counters["presses"] += 1
            if self.config:
                self.player.start(self.config, True, now)
            self._relay("press")
        else:
            self.counters["releases"] += 1
            if self.config:
                self.player.cancel()
                self._all_off()
            self._relay("release")

    def _all_off(self):
        # allTasksOff stops notes, sounds and LED sequences in one write
        # (Jan 2026 wand-side finding); static LEDs need allLEDsOff.
        self.player.check_write(self.link.allTasksOff(), "allTasksOff")
        self.player.check_write(self.link.allLEDsOff(), "allLEDsOff")

    def _relay(self, event):
        msg = {"type": "splat_event", "event": event,
               "splat": self.link.mac_address}
        if RELAY_TO_OWNER and self.owner is not None:
            ok = self.mgr.send_to(self.owner, msg)
            dest = self.owner
        else:
            ok = self.mgr.broadcast(msg)
            dest = "broadcast"
        if ok:
            self.counters["relays"] += 1
        else:
            self.counters["relay_failures"] += 1
            print("  [ERR] splat_event %s to %s failed (failures=%d)"
                  % (event, dest, self.counters["relay_failures"]))

    # ─── ESP-NOW side ─────────────────────────

    def on_message(self, msg_type, data, mac):
        self.counters["rx"] += 1
        if msg_type == "splat_config":
            self._on_config(data, mac)
        elif msg_type == "stop":
            self._on_stop(mac)
        elif (msg_type == "raw" and isinstance(data, dict) and
              data.get("type") == "splat_cmd"):
            self._on_cmd(data, mac)
        else:
            self.counters["ignored"] += 1

    def _bad(self, what, mac, errors):
        self.counters["bad_msgs"] += 1
        for e in errors:
            print("  [ERR] %s from %s: %s" % (what, mac, e))

    def _set_owner(self, mac):
        if mac == self.owner or not RELAY_TO_OWNER:
            return
        if self.owner is not None:
            self.mgr.remove_peer(self.owner)
        self.mgr.add_peer(mac)
        self.owner = mac

    def _on_config(self, data, mac):
        steps, errors = parse_chain(data.get("actions"))
        if errors:
            self._bad("splat_config", mac, errors)
        self.counters["configs"] += 1
        self._set_owner(mac)
        self.config = steps if steps else None
        print("  Companion: splat_config from %s, %d groups" % (mac, len(steps)))

    def _on_cmd(self, data, mac):
        self.counters["cmds"] += 1
        self._set_owner(mac)
        if not self.link.ready:
            self.counters["cmds_dropped"] += 1
            print("  [WARN] splat_cmd from %s dropped: splat not connected (%s)"
                  % (mac, self.link.state_name()))
            return
        if data.get("off"):
            self.player.cancel()
            self._all_off()
            return
        if "actions" not in data:
            self._bad("splat_cmd", mac, ["no 'actions' or 'off' key"])
            return
        steps, errors = parse_chain(data["actions"])
        if errors:
            self._bad("splat_cmd", mac, errors)
        if steps:
            self.player.start(steps, False, time.ticks_ms())

    def _on_stop(self, mac):
        self.counters["stops"] += 1
        self.config = None
        self.player.cancel()
        if self.link.ready:
            self._all_off()
        if self.owner is not None:
            self.mgr.remove_peer(self.owner)
            self.owner = None
        print("  Companion: stop from %s" % mac)

    def shutdown(self):
        """Stop the splat, drop BLE, deactivate the modem.

        Peers are removed first: mgr.shutdown() sends stop to every peer,
        which would stop the owner wand's game.
        """
        self.player.cancel()
        if self.link.ready:
            self._all_off()
        self.link.close()
        self.mgr.clear_peers()
        self.owner = None
        self.mgr.shutdown()
