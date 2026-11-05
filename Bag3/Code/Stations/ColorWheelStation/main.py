"""
Color Wheel Station -- daisy-chained NFC colour reader (Bag3)
============================================================
Four XIAO ESP32-C6 boards in a line, each with an M5Stack WS1850S RFID
reader on I2C (SDA=D4/GPIO22, SCL=D5/GPIO23, 0x28). The boards are linked
by soft UART, one direction only:

    [first] --UART--> [middle] --UART--> [middle] --UART--> [last] ==ESP-NOW==>

  * first  (ESP1): a button on D2 triggers a scan. Reads its own tag's NDEF
                   text ("green", "blue", ...) and sends it down the chain.
  * middle (ESP2, ESP3): waits for an upstream line, scans its own tag,
                   appends the colour, forwards the longer line downstream.
  * last   (ESP4): waits for an upstream line, scans its own tag, appends,
                   then broadcasts the full chain over ESP-NOW.

UART wiring is crossed by the cable: each board's D0 (TX) -> next board's
D7 (RX). So every board uses the SAME single-UART setting below
(tx=D0/GPIO0, rx=D7/GPIO17); the first uses only TX, the last only RX.

Memory order (see Bag3/AGENTS.md): only the "last" node uses the radio, and
it brings ESP-NOW up BEFORE importing the NFC modules, so the radio claims
its contiguous DRAM block before anything else fragments the heap. The other
three never import espnow_manager at all.

Flash the same files to all four boards; set ROLE per board.
"""

import time
from machine import Pin, SoftI2C, UART

# ============================================================
# PER-BOARD CONFIG -- set ROLE on each of the four boards
#   "first"  -> ESP1 (button)
#   "middle" -> ESP2, ESP3
#   "last"   -> ESP4 (ESP-NOW broadcast)
# ============================================================
ROLE = "first"

# --- XIAO ESP32-C6 pin positions -> GPIO --------------------
PIN_BUTTON = 2       # D2  -- first node only; button wired to GND
I2C_SDA = 22         # D4
I2C_SCL = 23         # D5
I2C_FREQ = 100000
UART_ID = 1
UART_TX = 0          # D0 -> next board's D7 (RX)
UART_RX = 17         # D7 <- previous board's D0 (TX)
UART_BAUD = 115200

# --- behaviour ----------------------------------------------
SCAN_TIMEOUT_MS = 1000   # how long a node waits for its own tag per trigger
NO_TAG = "?"             # placeholder sent when no readable tag is present
DELIM = ","              # separates colours in the chain message
EOL = "\n"               # line terminator on the UART wire
DEBOUNCE_MS = 40

# The first node's button. On the bench board it reads HIGH when pressed
# (wired to 3V3, with an external pull-down holding GPIO2 low at rest), so
# active-high. Set False for a button wired to GND (uses the internal
# pull-up, reads LOW when pressed).
BUTTON_ACTIVE_HIGH = True


def _build_reader():
    """Bring up the WS1850S on this board's I2C bus. Returns the reader, or
    None if the bus/reader could not be reached (a wiring fault)."""
    from nfc_ws1850s import Ws1850sReader
    i2c = SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=I2C_FREQ)
    try:
        found = i2c.scan()
        print("  [cw] I2C devices: %s" % [hex(a) for a in found])
    except Exception as e:
        print("  [cw] I2C scan failed: %s" % e)
    reader = Ws1850sReader(i2c)
    try:
        ver = reader.begin()
        print("  [cw] WS1850S version: 0x%02X" % ver)
    except Exception as e:
        print("  [cw] reader begin failed: %s" % e)
    return reader


def _scan_colour(reader):
    """Read this node's tag text. Returns the colour string, or NO_TAG if no
    tag is present / no readable NDEF text was found within SCAN_TIMEOUT_MS."""
    from nfc_reader import read_ndef_text
    try:
        text, _uid = read_ndef_text(reader, timeout=SCAN_TIMEOUT_MS)
    except Exception as e:
        print("  [cw] scan error: %s" % e)
        return NO_TAG
    if text:
        return text
    return NO_TAG


def _poll_line(uart, buf):
    """Accumulate UART bytes into buf. Return the next complete line (decoded,
    EOL stripped) when one is available, else None. Non-blocking."""
    data = uart.read()
    if data:
        buf.extend(data)
    idx = bytes(buf).find(b'\n')
    if idx < 0:
        return None
    line = bytes(buf[:idx])
    del buf[:idx + 1]
    try:
        return line.decode('utf-8').strip()
    except Exception:
        return ""


def _append(line, colour):
    """Append this node's colour to the upstream line."""
    if line:
        return line + DELIM + colour
    return colour


def run_first():
    reader = _build_reader()
    uart = UART(UART_ID, baudrate=UART_BAUD, tx=Pin(UART_TX), rx=Pin(UART_RX))
    if BUTTON_ACTIVE_HIGH:
        button = Pin(PIN_BUTTON, Pin.IN, Pin.PULL_DOWN)
        pressed = 1
    else:
        button = Pin(PIN_BUTTON, Pin.IN, Pin.PULL_UP)
        pressed = 0
    print("  [cw] first node ready -- press button to start a scan")
    while True:
        if button.value() == pressed:
            time.sleep_ms(DEBOUNCE_MS)
            if button.value() == pressed:
                colour = _scan_colour(reader)
                uart.write((colour + EOL).encode('utf-8'))
                print("  [cw] started chain: %s" % colour)
                while button.value() == pressed:   # one press = one scan
                    time.sleep_ms(5)
        time.sleep_ms(1)


def run_middle():
    reader = _build_reader()
    uart = UART(UART_ID, baudrate=UART_BAUD, tx=Pin(UART_TX), rx=Pin(UART_RX))
    buf = bytearray()
    print("  [cw] middle node ready -- waiting for upstream")
    while True:
        line = _poll_line(uart, buf)
        if line is not None:
            out = _append(line, _scan_colour(reader))
            uart.write((out + EOL).encode('utf-8'))
            print("  [cw] forwarded: %s" % out)
        time.sleep_ms(1)


def run_last(enow):
    reader = _build_reader()
    uart = UART(UART_ID, baudrate=UART_BAUD, tx=Pin(UART_TX), rx=Pin(UART_RX))
    buf = bytearray()
    print("  [cw] last node ready -- waiting for upstream")
    while True:
        line = _poll_line(uart, buf)
        if line is not None:
            out = _append(line, _scan_colour(reader))
            # Broadcast a bare list of colour names. espnow_manager.poll()
            # classifies a JSON list as msg_type "colors", which is what the
            # color_quest wand game listens for (_colors_from_data filters
            # each entry against its known colours, so a NO_TAG "?" is simply
            # dropped on the wand side).
            colours = out.split(DELIM)
            if enow is not None:
                try:
                    enow.broadcast(colours)
                except Exception as e:
                    print("  [cw] broadcast err: %s" % e)
            print("  [cw] broadcast colors: %s" % colours)
        time.sleep_ms(1)


def main():
    if ROLE == "last":
        # Radio FIRST. Import and bring ESP-NOW up before the NFC modules
        # allocate, so it claims its contiguous DRAM block. See the module
        # docstring and Bag3/AGENTS.md.
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
        run_last(enow)
    elif ROLE == "middle":
        run_middle()
    else:
        run_first()


main()
