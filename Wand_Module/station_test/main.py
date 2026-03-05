"""
4x PN532 NFC readers on PCA9546 I2C mux — ESP32-C6 MicroPython
Reads NDEF text from Mifare Classic 1K, broadcasts via ESP-NOW.
18-LED strip on GPIO21 blinks scanned colors after send.

Requires /lib/pn532.py and /lib/nfc_reader.py

Wiring:
  ESP32-C6  GPIO22 (SDA) -> PCA9546 SDA  (+ 4.7k pull-up)
  ESP32-C6  GPIO23 (SCL) -> PCA9546 SCL  (+ 4.7k pull-up)
  ESP32-C6  GPIO1        -> PCA9546 RESET
  ESP32-C6  GPIO2        -> All PN532 RSTPDN pins
  ESP32-C6  GPIO21       -> LED strip DIN (18 LEDs)
  PCA9546 CH0-CH3        -> PN532 #0-#3
  GPIO0                  -> Button -> GND (internal pull-up)
"""

import machine
import network
import espnow
import time
import json
from neopixel import NeoPixel

from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
from nfc_reader import _decode_ndef_text, COMMON_KEYS

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
I2C_SDA       = 22
I2C_SCL       = 23
I2C_FREQ      = 100_000
BTN_PIN       = 0
MUX_RST_PIN   = 1
PN532_RST_PIN = 2
LED_PIN       = 21
NUM_STRIP     = 18

MUX_ADDR      = 0x70
PN532_ADDR    = 0x24
NUM_READERS   = 4
MAX_RETRIES   = 3

BROADCAST = b'\xFF\xFF\xFF\xFF\xFF\xFF'

TAG_COLOR = {
    "turnred":    (50, 0, 0),
    "turngreen":  (0, 50, 0),
    "turnblue":   (0, 0, 50),
    "turnpurple": (50, 0, 50),
    "turnyellow": (50, 35, 0),
    "turnwhite":  (30, 30, 30),
}

# ─────────────────────────────────────────────
# PCA9546 MUX + RESET HELPERS
# ─────────────────────────────────────────────
def mux_select(i2c, ch):
    i2c.writeto(MUX_ADDR, bytes([1 << ch if 0 <= ch < 4 else 0]))

def mux_disable(i2c):
    i2c.writeto(MUX_ADDR, bytes([0]))

def mux_reset(rst_pin):
    rst_pin.value(0)
    time.sleep_ms(10)
    rst_pin.value(1)
    time.sleep_ms(50)

def pn532_hard_reset(rst_pin):
    rst_pin.value(0)
    time.sleep_ms(100)
    rst_pin.value(1)
    time.sleep_ms(500)

# ─────────────────────────────────────────────
# PER-CHANNEL PN532 INIT
# ─────────────────────────────────────────────
def init_reader(nfc):
    ic, ver, rev = nfc.begin()
    print("  PN5%02X fw %d.%d" % (ic, ver, rev))
    nfc._send_command(0x32, b'\x05\x01\x01\x02')
    return True

def reinit_reader(nfc):
    try:
        nfc.i2c.writeto(nfc.addr, bytes([0x55]))
    except OSError:
        pass
    time.sleep_ms(100)
    nfc._send_command(0x14, b'\x01\x00\x00', timeout=300)
    nfc._send_command(0x32, b'\x05\x01\x01\x02', timeout=300)

# ─────────────────────────────────────────────
# READ NDEF TEXT FROM CURRENT MUX CHANNEL
# ─────────────────────────────────────────────
def read_tag_text(nfc):
    tag = nfc.read_passive_target(timeout=500)
    if tag is None:
        return None
    if tag['sak'] not in (0x08, 0x18):
        return None

    ndef_data = bytearray()
    for sector in (1, 2):
        first_block = sector * 4
        authed = False
        for key in COMMON_KEYS:
            for key_type in [MIFARE_AUTH_A, MIFARE_AUTH_B]:
                resel = nfc.read_passive_target(timeout=200)
                if resel is None:
                    continue
                if nfc.mifare_auth_block(resel['uid'], first_block, key, key_type):
                    for blk in range(first_block, first_block + 3):
                        try:
                            ndef_data.extend(nfc.mifare_read_block(blk))
                        except Exception:
                            ndef_data.extend(b'\x00' * 16)
                    authed = True
                    break
            if authed:
                break
        if not authed:
            ndef_data.extend(b'\x00' * 48)

    return _decode_ndef_text(ndef_data)

# ─────────────────────────────────────────────
# LED STRIP HELPERS
# ─────────────────────────────────────────────
def strip_off(np):
    for i in range(NUM_STRIP):
        np[i] = (0, 0, 0)
    np.write()

def strip_blink_colors(np, commands):
    colors = [TAG_COLOR.get(cmd, (30, 30, 30)) for cmd in commands]
    if not colors:
        colors = [(0, 40, 0)]

    # Flash all LEDs in each color
    for color in colors:
        for i in range(NUM_STRIP):
            np[i] = color
        np.write()
        time.sleep_ms(300)
        strip_off(np)
        time.sleep_ms(100)

    # Chase the colors around the strip
    for _ in range(3):
        for offset in range(NUM_STRIP):
            for i in range(NUM_STRIP):
                cidx = (i + offset) % len(colors)
                np[i] = colors[cidx]
            np.write()
            time.sleep_ms(40)

    strip_off(np)

# ─────────────────────────────────────────────
# ESP-NOW SETUP
# ─────────────────────────────────────────────
def espnow_init():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.disconnect()
    e = espnow.ESPNow()
    e.active(True)
    e.add_peer(BROADCAST)
    print("ESP-NOW ready")
    return e

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=I2C_FREQ)
    btn = machine.Pin(BTN_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    mux_rst = machine.Pin(MUX_RST_PIN, machine.Pin.OUT, value=1)
    pn532_rst = machine.Pin(PN532_RST_PIN, machine.Pin.OUT, value=1)
    np = NeoPixel(machine.Pin(LED_PIN), NUM_STRIP)
    strip_off(np)

    mux_reset(mux_rst)
    pn532_hard_reset(pn532_rst)

    print("Scanning I2C bus:", [hex(a) for a in i2c.scan()])

    nfc = PN532(i2c, PN532_ADDR)

    ok_readers = []
    for ch in range(NUM_READERS):
        print("Init reader #%d..." % ch)
        mux_select(i2c, ch)
        time.sleep_ms(20)
        try:
            init_reader(nfc)
            ok_readers.append(ch)
        except Exception as e:
            print("  Reader #%d — failed: %s" % (ch, str(e)))
    mux_disable(i2c)

    enow = espnow_init()

    print("\n%d/%d readers ready. Press button on GPIO%d.\n" % (
        len(ok_readers), NUM_READERS, BTN_PIN))

    last_btn = 1
    while True:
        cur = btn.value()
        if last_btn == 1 and cur == 0:
            time.sleep_ms(30)
            if btn.value() == 0:
                print("— Button pressed, scanning all readers —")

                mux_reset(mux_rst)
                pn532_hard_reset(pn532_rst)

                for ch in ok_readers:
                    mux_select(i2c, ch)
                    time.sleep_ms(30)
                    reinit_reader(nfc)

                commands = []
                for ch in ok_readers:
                    text = None
                    for attempt in range(MAX_RETRIES):
                        mux_select(i2c, ch)
                        time.sleep_ms(30)
                        reinit_reader(nfc)
                        time.sleep_ms(20)
                        text = read_tag_text(nfc)
                        if text:
                            break
                        time.sleep_ms(50)
                    if text:
                        commands.append(text)
                        print("  Reader #%d: \"%s\"" % (ch, text))
                    else:
                        print("  Reader #%d: no tag / unreadable" % ch)
                mux_disable(i2c)

                print("  Commands: %s" % str(commands))
                msg = json.dumps(commands)
                try:
                    enow.send(BROADCAST, msg)
                    print("  ESP-NOW sent: %s" % msg)
                    strip_blink_colors(np, commands)
                except Exception as ex:
                    print("  ESP-NOW error: %s" % str(ex))
                print()
        last_btn = cur
        time.sleep_ms(10)

if __name__ == "__main__":
    main()