"""
gamelib.py -- the shared wiring for loading and running game files.

This is the one thing every device does the same way. Boot, hardware setup and
the idle loop belong to each device's own main.py; this module only covers how
a game file is found, run, switched and unloaded.

A game file is identical on every device:

    def play(dev):
        while dev.running():
            ev = dev.event()
            ...
            dev.tick(20)

main.py builds the Device, hangs its own hardware on it, and launches:

    dev = gamelib.Device(net, builtins=GAME_MODULES)
    dev.leds = leds
    dev.reader = reader
    ...
    dev.launch("colorquest")

running() pumps the radio and the card reader and returns False on stop, on a
start for another game, or on an exit tag -- so a game cannot forget to poll
and become unstoppable.

Pulled games live in /games/<module>.py, which is on sys.path, so a pulled game
imports by bare name exactly the way a built-in does.
"""

import gc
import sys
import time

import game_store

# Passes between card reads while a game runs. Reading every pass starves the
# rest of the loop; the reader is the slowest thing in it. A game that reads
# cards as part of play can lower its own dev.nfc_every.
NFC_EVERY = 15

# A card sitting on the reader reads over and over. The same uid is ignored
# until it has been away for a pass or this long has gone by.
REPEAT_MS = 1200

GETCODE = "getcode:"
CONTROL_TAGS = ("stop", "start")

game_store.ensure_dir()
if game_store.GAMES_DIR not in sys.path:
    sys.path.append(game_store.GAMES_DIR)


class Device:
    """What a game receives. main.py fills in the hardware it has."""

    def __init__(self, net, builtins=None):
        self.net = net
        self.builtins = builtins or {}
        self.cap = None            # station hardware handler, if any
        self.reader = None         # NfcReader, if this device has one
        self.slug = None
        self.role = None

        self._events = []
        self._exit = None          # None | "stop" | ("start", slug)
        self._pull = None          # module a getcode: card asked for
        self._passes = 0
        self._exit_names = ()
        self._last_uid = None
        self._last_read = 0
        self.nfc_every = NFC_EVERY

    # -- games -------------------------------------------------------

    def resolve(self, slug):
        """Module name for a game, or None.

        Built-ins win: a pulled file can never shadow one. Otherwise the
        filesystem is the index -- <slug>.py, or the single <slug>_<role>.py
        this device holds for that game.
        """
        if slug in self.builtins:
            return self.builtins[slug]
        return game_store.module_for(slug)

    def is_game(self, slug):
        return self.resolve(slug) is not None

    def card_commands(self):
        """Card texts the reader should answer to."""
        return set(self.builtins) | set(CONTROL_TAGS) | set(game_store.slugs())

    def launch(self, slug, on_load=None):
        """Run a game, chaining a force-switch without returning to idle.

        on_load(slug), if given, is called just before the blocking import --
        it is how a device shows that a tap was seen. Raises if a module will
        not import or has no play(); the caller decides what that looks like,
        because the indication is device-specific.
        """
        while self.is_game(slug):
            module = self.resolve(slug)
            if on_load:
                on_load(slug)
            play = getattr(__import__(module), "play")
            self.begin(slug)
            play(self)
            self.end()
            play = None
            self._unload(module)
            nxt = self.pending()
            if not nxt:
                return
            slug = nxt

    def _unload(self, module):
        """Drop a finished game so the next starts from a cleaner heap.

        Safe only because no game may keep a callback or a reference into
        itself. Interned strings are never reclaimed, so each distinct game
        loaded in one boot leaves a small permanent residual.
        """
        if module in sys.modules:
            del sys.modules[module]
        gc.collect()

    # -- game lifecycle ----------------------------------------------

    def begin(self, slug):
        self.slug = slug
        self.nfc_every = NFC_EVERY
        self.role = game_store.role_of(self.resolve(slug))
        self._events = []
        self._exit = None
        self._passes = 0
        self._exit_names = tuple(n for n in self.card_commands() if n != slug)
        self._last_uid = None

    def end(self):
        """Restore outputs after a game returns."""
        leds = getattr(self, "leds", None)
        if leds is not None:
            leds.off()
        if self.cap is not None:
            self.cap.off()
        self.slug = None
        self.role = None
        self._events = []

    def pending(self):
        """Game slug to switch to, or None."""
        return self._exit[1] if isinstance(self._exit, tuple) else None

    def take_exit(self):
        """Read and clear what ended the game: None, "stop", or ("start", slug).

        Cleared on read so a stop seen while idle is acted on once and does not
        linger into the next game.
        """
        pending, self._exit = self._exit, None
        return pending

    def pending_pull(self):
        """Module a getcode: card asked for, or None."""
        return self._pull

    # -- the loop ----------------------------------------------------

    def running(self):
        """Pump the device. False when the running game must end."""
        self.pump()
        self.step_cap()
        self._passes += 1
        if self.reader is not None and self._passes % self.nfc_every == 0:
            self.read_card()
        return self._exit is None

    def pump(self, timeout_ms=0):
        """Service the radio: one wait of timeout_ms, then drain."""
        kind, data, mac = self.net.poll(timeout_ms)
        while kind is not None:
            if kind == "sys":
                self._handle_sys(data)
            elif kind == "cap":
                self.cap.handle(data.get("op"), data.get("a") or {})
            elif kind == "evt":
                self._queue_evt(data, mac)
            kind, data, mac = self.net.poll(0)

    def step_cap(self):
        """Advance the station's hardware and report what it finishes.

        A handler never touches the radio: step() returns (ev, data) when
        something completes and this puts it on the air.
        """
        if self.cap is None:
            return
        done = self.cap.step()
        if done:
            self.net.broadcast_evt(done[0], done[1], slug=self.slug)

    def event(self):
        """Next (ev, data, mac) for this game, or None."""
        return self._events.pop(0) if self._events else None

    def tick(self, ms=20):
        """Per-frame sleep. Always yields, so serial and the radio breathe."""
        time.sleep_ms(ms if ms > 0 else 1)

    def stop(self):
        """End the running game from inside it."""
        self._exit = "stop"

    def read_card(self):
        """Read one card and act on stop / a game tag / a getcode: card."""
        cmd, uid = self.reader.read_command(timeout=100)
        if uid is None:
            self._last_uid = None
            return
        now = time.ticks_ms()
        if uid == self._last_uid and time.ticks_diff(now, self._last_read) < REPEAT_MS:
            return
        self._last_uid = uid
        self._last_read = now
        if not cmd:
            return
        if cmd.startswith(GETCODE):
            self._pull = cmd[len(GETCODE):]
            self._exit = "stop"
        elif cmd == "stop":
            self._exit = "stop"
        elif cmd in self._exit_names and self.is_game(cmd):
            self._exit = ("start", cmd)
        else:
            # A card this game reads itself -- note_c, tomato, caller. It
            # arrives as an event so the game does not touch the reader; the
            # third field is the card uid.
            self._events.append(("tag", cmd, uid))

    # -- message handling --------------------------------------------

    def _handle_sys(self, data):
        op = data.get("op")
        if op == "stop":
            self._exit = "stop"
        elif op == "start":
            slug = data.get("slug")
            if slug and slug != self.slug and self.is_game(slug):
                self._exit = ("start", slug)
        elif op in ("ident", "battery"):
            self._events.append((op, data, None))

    def _queue_evt(self, data, mac):
        slug = data.get("slug")
        if slug and self.slug and slug != self.slug:
            return
        self._events.append((data.get("ev"), data.get("d"), mac))
