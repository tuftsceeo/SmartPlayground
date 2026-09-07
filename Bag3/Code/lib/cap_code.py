"""
cap_code.py -- code_station capability: a row of NFC slots read as a sequence.

Verbs, over ESP-NOW "cap" messages addressed to hubtype code_station:

    scan            read every slot and report the sequence
    slot  {n, c}    light slot n in colour name c
    clear           return the slots to the ready colour

A finished scan reports evt "seq" with one entry per slot, in slot order, and
"?" for a slot holding a card this station does not recognise.

Four PN532 readers share address 0x24 behind an I2C mux; only one channel is
live at a time. A scan is stepped one reader at a time from the station loop:
each reader needs a reset and can take a few hundred ms to answer, and doing
all four in one call left the radio unserviced for seconds.
"""

import time

import neopixel
from machine import Pin

from hubtype import HUB_CONFIG
from nfc_reader import read_ndef_text
from pn532 import PN532

READY = (100, 100, 100)
UNKNOWN = "?"

COLORS = {
    "red":    (255, 0, 0),
    "green":  (0, 255, 0),
    "blue":   (0, 0, 255),
    "purple": (40, 0, 200),
    "yellow": (255, 255, 0),
    "white":  (30, 30, 30),
    "pink":   (200, 0, 200),
    "off":    (0, 0, 0),
}

MAX_TRIES = 3

# Reset timings from the Bag2 station; the readers need them to answer.
RESET_LOW_MS = 100
RESET_HIGH_MS = 500
CHANNEL_SETTLE_MS = 30
REINIT_SETTLE_MS = 20

RESET_LOW, RESET_HIGH, READ = range(3)


class CodeSlots:

    def __init__(self, i2c):
        self.i2c = i2c
        self.slot_leds = HUB_CONFIG["slot_leds"]
        self.mux_addr = HUB_CONFIG["mux_addr"]
        self.strip = neopixel.NeoPixel(Pin(HUB_CONFIG["led_pin"]),
                                       HUB_CONFIG["num_leds"])
        self.mux_rst = Pin(HUB_CONFIG["mux_rst_pin"], Pin.OUT, value=1)
        self.pn532_rst = Pin(HUB_CONFIG["pn532_rst_pin"], Pin.OUT, value=1)
        self.nfc = PN532(i2c, addr=HUB_CONFIG["nfc_addr"])
        self._phase = None
        self._due = 0
        self._slot = 0
        self._tries = 0
        self._found = []
        self.off()

    # -- capability interface ----------------------------------------

    def handle(self, op, args):
        if op == "scan":
            self.scan()
        elif op == "slot":
            self.light(args["n"], args["c"])
        elif op == "clear":
            self.off()
        else:
            raise ValueError("code_station: unknown op %r" % op)

    def step(self):
        """Advance a running scan. Returns ("seq", [...]) when it finishes."""
        if self._phase is None:
            return None
        if time.ticks_diff(time.ticks_ms(), self._due) < 0:
            return None

        if self._phase == RESET_LOW:
            self.pn532_rst.value(0)
            self._wait(RESET_LOW_MS)
            self._phase = RESET_HIGH
            return None

        if self._phase == RESET_HIGH:
            self.pn532_rst.value(1)
            self._wait(RESET_HIGH_MS)
            self._phase = READ
            return None

        return self._read_slot()

    def off(self):
        self._phase = None
        for pair in self.slot_leds:
            for i in pair:
                self.strip[i] = READY
        self.strip.write()

    # -- verbs -------------------------------------------------------

    def scan(self):
        """Begin a scan. step() drives it and reports the result."""
        self.off()
        self._mux_reset()
        self._slot = 0
        self._tries = 0
        self._found = []
        self._phase = RESET_LOW
        self._due = time.ticks_ms()

    def light(self, slot, colour):
        if not 0 <= slot < len(self.slot_leds):
            raise ValueError("code_station: no slot %r" % slot)
        if colour not in COLORS:
            raise ValueError("code_station: unknown colour %r" % colour)
        for i in self.slot_leds[slot]:
            self.strip[i] = COLORS[colour]
        self.strip.write()

    # -- scanning ----------------------------------------------------

    def _read_slot(self):
        """One attempt at the current slot. Advances, or ends the scan."""
        self._select(self._slot)
        text = read_ndef_text(self.nfc, timeout=500)
        self._tries += 1

        if text is None and self._tries < MAX_TRIES:
            self._wait(CHANNEL_SETTLE_MS)
            return None

        if text is None:
            self._found.append(None)
        elif text in COLORS:
            self._found.append(text)
            self.light(self._slot, text)
        else:
            print("  code_station: slot %d holds %r" % (self._slot, text))
            self._found.append(UNKNOWN)
            self.light(self._slot, "red")

        self._slot += 1
        self._tries = 0
        if self._slot < len(self.slot_leds):
            self._wait(CHANNEL_SETTLE_MS)
            return None

        self._mux_disable()
        self._phase = None
        return ("seq", [c for c in self._found if c is not None])

    def _select(self, channel):
        self.i2c.writeto(self.mux_addr, bytes([1 << channel]))
        time.sleep_ms(CHANNEL_SETTLE_MS)
        self._reinit()
        time.sleep_ms(REINIT_SETTLE_MS)

    def _reinit(self):
        """Wake the reader on the live channel and re-arm its RF config."""
        self.nfc.i2c.writeto(self.nfc.addr, bytes([0x55]))
        time.sleep_ms(CHANNEL_SETTLE_MS)
        self.nfc._send_command(0x14, b'\x01\x00\x00', timeout=300)
        self.nfc._send_command(0x32, b'\x05\x01\x01\x02', timeout=300)

    def _mux_reset(self):
        self.mux_rst.value(0)
        time.sleep_ms(10)
        self.mux_rst.value(1)
        time.sleep_ms(50)

    def _mux_disable(self):
        self.i2c.writeto(self.mux_addr, bytes([0]))

    def _wait(self, ms):
        self._due = time.ticks_add(time.ticks_ms(), ms)
