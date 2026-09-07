"""
devices.py -- per-hubtype hardware bring-up and the game runtime.

    import devices

    dev = devices.build(commands)
    dev.begin("colorquest", "player", exit_names)
    play(dev)
    dev.end()

build() constructs only the peripherals this hubtype declares in hubtype.CAPS.
A capability this hubtype does not have is absent from the Device, so a role
file that reaches for it fails with an AttributeError naming what it wanted.
Nothing here catches a driver failure: a peripheral this hubtype claims to have
and cannot start is a fault, and stops the device with a traceback.

Device also runs the game loop. A role file is:

    def play(dev):
        while dev.running():
            ev = dev.event()
            ...
            dev.tick()

running() pumps the radio and the card reader, answers capability commands and
consumes system messages, and returns False when the game must end.

Loop pacing comes from the hubtype: idle_ms, idle_poll_ms and game_ms in
HUB_CONFIG. A station with nothing to poll paces on a blocking receive
(idle_poll_ms) rather than a sleep, which is how the Bag2 stations keep the
radio quiet.
"""

import machine
import time

from hubtype import HUB_TYPE, HUB_CONFIG, CAPS
from espnow_manager import ESPNowManager

# Passes between card reads while a game runs. Reading every pass starves the
# rest of the loop; the reader is the slowest thing in it.
NFC_EVERY = 15

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

        self.idle_ms = HUB_CONFIG["idle_ms"]
        self.idle_poll_ms = HUB_CONFIG["idle_poll_ms"]
        self.game_ms = HUB_CONFIG["game_ms"]

        self._events = []
        self._exit = None          # None | "stop" | ("start", slug)
        self._pull = None          # module name a getcode: card asked for
        self._passes = 0
        self._exit_names = ()

    # -- game lifecycle ----------------------------------------------

    def begin(self, slug, role, exit_names=()):
        """Arm the runtime for one game."""
        self.slug = slug
        self.role = role
        self._events = []
        self._exit = None
        self._passes = 0
        self._exit_names = tuple(n for n in exit_names if n != slug)

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
        """("start", slug) if a game switch is queued, else None."""
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

    def idle(self):
        """One pass of the between-games loop, at this hubtype's cadence."""
        self.pump(self.idle_poll_ms)
        if self.cap is not None:
            self.cap.step()
        if self.reader is not None:
            self._read_card()
        if self.idle_ms:
            time.sleep_ms(self.idle_ms)

    def event(self):
        """Next (ev, data, mac) for this game, or None."""
        return self._events.pop(0) if self._events else None

    def tick(self, ms=None):
        """Per-frame sleep. Always yields, so serial and the radio breathe."""
        ms = self.game_ms if ms is None else ms
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

    def _queue_evt(self, data, mac):
        slug = data.get("slug")
        if slug and self.slug and slug != self.slug:
            return
        self._events.append((data.get("ev"), data.get("d"), mac))

    def _read_card(self):
        cmd, _uid = self.reader.read_command(timeout=100)
        if not cmd:
            return
        if cmd.startswith(GETCODE):
            self._pull = cmd[len(GETCODE):]
            self._exit = "stop"
        elif cmd == "stop":
            self._exit = "stop"
        elif cmd in self._exit_names:
            self._exit = ("start", cmd)


def build(commands=()):
    """Construct the Device for this hubtype.

    commands is the set of card texts the reader should recognise -- every
    game name plus the control tags. The caller owns that list.

    Order matters: esp_wifi_init() needs contiguous IDF heap that MicroPython's
    GC carves from and never gives back, so the radio is claimed before any
    driver import fragments it. Only the LED matrix comes first, so the boot
    has something to show.
    """
    dev = Device()

    if "matrix5" in CAPS:
        from leds import Leds
        dev.leds = Leds()

    dev.net.init()

    if "nfc" in CAPS:
        dev.i2c = machine.SoftI2C(sda=machine.Pin(HUB_CONFIG["i2c_sda"]),
                                  scl=machine.Pin(HUB_CONFIG["i2c_scl"]),
                                  freq=HUB_CONFIG["i2c_freq"])

    if HUB_TYPE == "wand":
        from buzzer import Buzzer
        from lis2dw12 import LIS2DW12, RANGE_4G
        from max17048 import MAX17048
        dev.buz = Buzzer(HUB_CONFIG["buzzer_pin"])
        dev.accel = LIS2DW12(dev.i2c)
        dev.accel.init(fs_range=RANGE_4G)
        dev.batt = MAX17048(dev.i2c)
        dev.button = machine.Pin(HUB_CONFIG["button_pin"], machine.Pin.IN,
                                 machine.Pin.PULL_UP)
        dev.motor = machine.Pin(HUB_CONFIG["motor_pin"], machine.Pin.OUT, value=0)
        dev.net.set_status_provider(lambda: dev.batt.soc)

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
        from pn532 import PN532
        from nfc_reader import NfcReader
        dev.nfc = PN532(dev.i2c, addr=HUB_CONFIG["nfc_addr"])
        dev.nfc.begin()
        dev.reader = NfcReader(dev.nfc, commands, prefixes=(GETCODE,))

    return dev
