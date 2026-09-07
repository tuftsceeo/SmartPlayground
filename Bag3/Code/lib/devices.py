"""
devices.py -- per-hubtype hardware bring-up and the game runtime.

    import devices

    dev = devices.build()
    dev.begin("colorquest", "player", exit_names)
    play(dev)
    dev.end()

build() constructs only the peripherals this hubtype declares in hubtype.CAPS.
A capability this hubtype does not have is absent from the Device, so a role
file that reaches for it fails with an AttributeError naming what it wanted. A
capability whose driver fails to start is set to None and printed as [FAIL].

Device also runs the game loop. A role file is:

    def play(dev):
        while dev.running():
            ev = dev.event()
            ...
            dev.tick(20)

running() pumps the radio and the card reader, answers capability commands and
consumes system messages, and returns False when the game must end.
"""

import time

from hubtype import HUB_TYPE, HUB_CONFIG, CAPS
from espnow_manager import ESPNowManager

# How often running() reads the card reader, in calls. Reading every pass
# starves everything else; the reader is the slowest thing in the loop.
NFC_EVERY = 15

# Queued events a game has not read yet. Oldest are dropped -- a game that
# is not reading its events is not going to want the backlog.
EVENT_QUEUE_MAX = 8

GETCODE = "getcode:"


class Device:

    def __init__(self):
        self.hub_type = HUB_TYPE
        self.config = HUB_CONFIG
        self.caps = CAPS
        self.slug = None
        self.role = None
        self.net = ESPNowManager()
        self.cap = None            # station capability handler, if any
        self.reader = None         # NfcReader, if this hubtype has nfc

        self._events = []
        self._exit = None          # None | "stop" | ("start", slug)
        self._pull = None          # module name a getcode: card asked for
        self._passes = 0
        self._exit_names = ()

    # -- game lifecycle ----------------------------------------------

    def begin(self, slug, role, exit_names=()):
        """Arm the runtime for one game. Called by the launcher."""
        self.slug = slug
        self.role = role
        self._events = []
        self._exit = None
        self._passes = 0
        self._exit_names = tuple(n for n in exit_names if n != slug)

    def end(self):
        """Restore outputs after a game returns."""
        for name in ("leds", "cap"):
            obj = getattr(self, name, None)
            if obj is not None:
                try:
                    obj.off()
                except AttributeError:
                    pass
                except Exception as e:
                    print("  [FAIL] %s.off(): %s" % (name, str(e)))
        self.slug = None
        self.role = None
        self._events = []

    def pending(self):
        """What to do after play() returns: ("start", slug) or None."""
        return self._exit if isinstance(self._exit, tuple) else None

    def pending_pull(self):
        """Module name a getcode: card asked for, or None."""
        return self._pull

    # -- the loop ----------------------------------------------------

    def running(self):
        """Pump the device. False when the running game must end."""
        self.pump()
        self._passes += 1
        if self.reader is not None and self._passes % NFC_EVERY == 0:
            self._read_card()
        return self._exit is None

    def pump(self):
        """Service the radio once. Safe to call outside a game."""
        while True:
            kind, data, mac = self.net.poll()
            if kind is None:
                return
            if kind == "sys":
                self._handle_sys(data)
            elif kind == "cap":
                self._handle_cap(data)
            elif kind == "evt":
                self._queue_evt(data, mac)

    def event(self):
        """Next (ev, data, mac) for this game, or None."""
        return self._events.pop(0) if self._events else None

    def tick(self, ms=20):
        """Per-frame sleep. Always yields, so serial and the radio breathe."""
        time.sleep_ms(ms if ms > 0 else 1)

    def stop(self):
        """End the running game from inside it."""
        self._exit = "stop"

    # -- message handling --------------------------------------------

    def _handle_sys(self, data):
        op = data.get("op")
        if op == "stop":
            self._exit = "stop"
        elif op == "start":
            slug = data.get("slug")
            if slug and slug != self.slug:
                self._exit = ("start", slug)
        elif op == "ident":
            self._events.append(("ident", data, None))

    def _handle_cap(self, data):
        """Run a capability command. Already filtered to this hubtype."""
        if self.cap is None:
            return
        op = data.get("op")
        try:
            self.cap.handle(op, data.get("a") or {})
        except Exception as e:
            print("  [FAIL] cap %s: %s" % (op, str(e)))

    def _queue_evt(self, data, mac):
        slug = data.get("slug")
        if slug and self.slug and slug != self.slug:
            return
        if len(self._events) >= EVENT_QUEUE_MAX:
            self._events.pop(0)
        self._events.append((data.get("ev"), data.get("d"), mac))

    def _read_card(self):
        try:
            cmd, _uid = self.reader.read_command(timeout=100)
        except Exception as e:
            print("  [FAIL] card read: %s" % str(e))
            return
        if not cmd:
            return
        if cmd.startswith(GETCODE):
            self._pull = cmd[len(GETCODE):]
            self._exit = "stop"
        elif cmd == "stop" or cmd in self._exit_names:
            self._exit = "stop" if cmd == "stop" else ("start", cmd)


def _fail(name, exc):
    print("  [FAIL] %s: %s" % (name, str(exc)))
    return None


def _build_i2c():
    import machine
    return machine.SoftI2C(sda=machine.Pin(HUB_CONFIG["i2c_sda"]),
                           scl=machine.Pin(HUB_CONFIG["i2c_scl"]),
                           freq=HUB_CONFIG["i2c_freq"])


def _attach_nfc(dev, commands):
    from pn532 import PN532
    from nfc_reader import NfcReader
    nfc = PN532(dev.i2c, addr=HUB_CONFIG["nfc_addr"])
    nfc.begin()
    dev.nfc = nfc
    dev.reader = NfcReader(nfc, commands, prefixes=(GETCODE,))


def build(commands=()):
    """Construct the Device for this hubtype.

    commands is the set of card texts the reader should recognise -- every
    game name plus the control tags. The launcher owns that list.
    """
    dev = Device()

    if "nfc" in CAPS:
        dev.i2c = _build_i2c()

    if HUB_TYPE == "wand":
        from leds import Leds
        from buzzer import Buzzer
        dev.leds = Leds()
        dev.buz = Buzzer(HUB_CONFIG["buzzer_pin"])
        try:
            from lis2dw12 import LIS2DW12, RANGE_4G
            accel = LIS2DW12(dev.i2c)
            accel.init(fs_range=RANGE_4G)
            dev.accel = accel
        except Exception as e:
            dev.accel = _fail("accel", e)
        try:
            from max17048 import MAX17048
            dev.batt = MAX17048(dev.i2c)
        except Exception as e:
            dev.batt = _fail("battery", e)
        import machine
        dev.button = machine.Pin(HUB_CONFIG["button_pin"], machine.Pin.IN,
                                 machine.Pin.PULL_UP)
        dev.motor = machine.Pin(HUB_CONFIG["motor_pin"], machine.Pin.OUT, value=0)

    elif HUB_TYPE == "code_station":
        from cap_code import CodeSlots
        dev.cap = dev.slots = CodeSlots(dev.i2c)

    elif HUB_TYPE == "score_station":
        from cap_score import ScoreBars
        dev.cap = dev.bars = ScoreBars()

    elif HUB_TYPE == "icon_station":
        from cap_icon import IconPanel
        dev.cap = dev.icon = IconPanel()

    elif HUB_TYPE == "dial_station":
        from cap_dial import DialAudio
        dev.cap = dev.dial = DialAudio()

    if "nfc" in CAPS:
        try:
            _attach_nfc(dev, commands)
        except Exception as e:
            dev.nfc = _fail("nfc", e)

    dev.net.init()
    if getattr(dev, "batt", None) is not None:
        dev.net.set_status_provider(lambda: dev.batt.soc)
    return dev
