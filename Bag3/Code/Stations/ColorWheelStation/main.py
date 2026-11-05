"""
Color Wheel Station -- single-ESP, 4-reader NFC colour reader (Bag3)
===================================================================
One XIAO ESP32-C6 with four M5Stack WS1850S RFID readers, each on its own
bit-banged SoftI2C bus (the readers are all at I2C address 0x28, so they
cannot share a bus). A button triggers a scan of all four readers at once;
each reader's NDEF text -- a colour like "turngreen" -- is collected into a
list and broadcast over ESP-NOW.

The broadcast is a bare list of colour names, which espnow_manager.poll()
classifies as msg_type "colors" -- the shape the color_quest wand game
(Bag3/Code/Wand Module/color_quest.py) listens for. Its valid colours are
the turn-prefixed action names (turnred, turngreen, turnblue, turnpurple,
turnpink, turnyellow, turnwhite, turnoff); the tags must carry those.

Pins are fixed by the breakout board (silk D-number -> GPIO):

    reader 1  SCL D5/GPIO23  SDA D4/GPIO22
    reader 2  SCL D2/GPIO2   SDA D3/GPIO21
    reader 3  SCL D7/GPIO17  SDA D6/GPIO16   <- the C6's UART0 console pins;
                                                verified working here
    reader 4  SCL D0/GPIO0   SDA D1/GPIO1
    button    D8/GPIO19
    NeoPixel  (add later; D3 is now reader 2 -- use a free pin, e.g. D9/D10)

Memory order (Bag3/AGENTS.md): ESP-NOW is brought up FIRST, before the NFC
modules import, so the radio claims its contiguous DRAM block before anything
else fragments the heap. Onboard antenna (espnow_manager EXTERNAL_ANTENNA
= False).
"""

import time
from machine import Pin, SoftI2C

# --- reader buses: (scl_gpio, sda_gpio), in output order -----
READER_PINS = (
    (23, 22),   # reader 1  -- D5 / D4
    (2, 21),    # reader 2  -- D2 / D3
    (17, 16),   # reader 3  -- D7 / D6  (C6 UART0 console pins; works in test)
    (0, 1),     # reader 4  -- D0 / D1
)
I2C_FREQ = 100000

# --- button (D8 / GPIO19) -----------------------------------
PIN_BUTTON = 19
# Bench board was active-high (wired to 3V3 + external pull-down). Set False
# for a button wired to GND (internal pull-up, reads LOW when pressed).
BUTTON_ACTIVE_HIGH = True
DEBOUNCE_MS = 40

# --- NeoPixel status strip (optional, add later) ------------
# D3/GPIO21 is now reader 2's SDA; a free pin like D9/GPIO20 or D10/GPIO18.
# NEOPIXEL_PIN = 20

# --- behaviour ----------------------------------------------
SCAN_TIMEOUT_MS = 1000   # how long each reader waits for its tag
NO_TAG = "?"             # placeholder when a reader has no readable tag


def _build_readers():
    """Bring up a SoftI2C WS1850S on each pin pair. Returns a list aligned
    with READER_PINS; a failed reader is None (so one dead bus doesn't take
    the whole station down)."""
    from nfc_ws1850s import Ws1850sReader
    readers = []
    for i, (scl, sda) in enumerate(READER_PINS):
        try:
            bus = SoftI2C(scl=Pin(scl), sda=Pin(sda), freq=I2C_FREQ)
            found = bus.scan()
            reader = Ws1850sReader(bus)
            ver = reader.begin()
            print("  [cw] reader %d (scl=%d sda=%d): addrs=%s ver=0x%02X"
                  % (i + 1, scl, sda, [hex(a) for a in found], ver))
            readers.append(reader)
        except Exception as e:
            print("  [cw] reader %d (scl=%d sda=%d) FAILED: %s"
                  % (i + 1, scl, sda, e))
            readers.append(None)
    return readers


def _scan_colour(reader):
    """Read one reader's tag text. Returns the colour string, or NO_TAG if no
    tag / no readable NDEF text within SCAN_TIMEOUT_MS, or the bus is dead."""
    if reader is None:
        return NO_TAG
    from nfc_reader import read_ndef_text
    try:
        text, _uid = read_ndef_text(reader, timeout=SCAN_TIMEOUT_MS)
    except Exception as e:
        print("  [cw] scan error: %s" % e)
        return NO_TAG
    return text if text else NO_TAG


def _scan_all(readers):
    return [_scan_colour(r) for r in readers]


def main():
    # ── 1. Radio first (memory order; see module docstring). ──
    from espnow_manager import ESPNowManager
    enow = ESPNowManager()
    try:
        enow.init()
        print("  [cw] ESP-NOW ready")
    except Exception as e:
        enow = None
        print("  [cw] ESP-NOW init failed:")
        import sys
        sys.print_exception(e)

    # ── 2. Readers (after the radio has its memory). ──
    readers = _build_readers()

    # ── 3. Button. ──
    if BUTTON_ACTIVE_HIGH:
        button = Pin(PIN_BUTTON, Pin.IN, Pin.PULL_DOWN)
        pressed = 1
    else:
        button = Pin(PIN_BUTTON, Pin.IN, Pin.PULL_UP)
        pressed = 0

    print("  [cw] ready -- press button to scan the 4 readers")
    while True:
        if button.value() == pressed:
            time.sleep_ms(DEBOUNCE_MS)
            if button.value() == pressed:
                colours = _scan_all(readers)
                if enow is not None:
                    try:
                        enow.broadcast(colours)
                    except Exception as e:
                        print("  [cw] broadcast err: %s" % e)
                print("  [cw] broadcast colors: %s" % colours)
                while button.value() == pressed:   # one press = one scan
                    time.sleep_ms(5)
        time.sleep_ms(1)


main()
