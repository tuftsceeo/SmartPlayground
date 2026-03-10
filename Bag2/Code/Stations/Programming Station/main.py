"""
Programming Station — 4x PN532 NFC readers, broadcasts via ESP-NOW
====================================================================
Board: Seeed XIAO ESP32-C6
Requires hubtype.txt containing: programming_station
Requires /lib/: hubtype.py, espnow_manager.py, leds.py, pn532.py, nfc_reader.py
"""

import machine
import time
import json

from hubtype import HUB_TYPE, HUB_CONFIG
from leds import Leds
from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
from nfc_reader import _decode_ndef_text, COMMON_KEYS
from espnow_manager import ESPNowManager

# ─────────────────────────────────────────────
# CONFIG FROM HUBTYPE
# ─────────────────────────────────────────────
I2C_SDA       = HUB_CONFIG["i2c_sda"]
I2C_SCL       = HUB_CONFIG["i2c_scl"]
I2C_FREQ      = HUB_CONFIG["i2c_freq"]
BTN_PIN       = HUB_CONFIG["button_pin"]
MUX_RST_PIN   = HUB_CONFIG["mux_rst_pin"]
PN532_RST_PIN = HUB_CONFIG["pn532_rst_pin"]

MUX_ADDR      = 0x70
PN532_ADDR    = 0x24
NUM_READERS   = 4
MAX_RETRIES   = 3

TAG_COLOR = {
    "turnred": (50, 0, 0), "turngreen": (0, 50, 0),
    "turnblue": (0, 0, 50), "turnpurple": (50, 0, 50),
    "turnyellow": (50, 35, 0), "turnwhite": (30, 30, 30),
}

# ─────────────────────────────────────────────
# MUX + RESET HELPERS
# ─────────────────────────────────────────────
def mux_select(i2c, ch):
    i2c.writeto(MUX_ADDR, bytes([1 << ch if 0 <= ch < 4 else 0]))

def mux_disable(i2c):
    i2c.writeto(MUX_ADDR, bytes([0]))

def mux_reset(rst):
    rst.value(0); time.sleep_ms(10); rst.value(1); time.sleep_ms(50)

def pn532_hard_reset(rst):
    rst.value(0); time.sleep_ms(100); rst.value(1); time.sleep_ms(500)

def init_reader(nfc):
    ic, ver, rev = nfc.begin()
    print("  PN5%02X fw %d.%d" % (ic, ver, rev))
    nfc._send_command(0x32, b'\x05\x01\x01\x02')
    return True

def reinit_reader(nfc):
    try: nfc.i2c.writeto(nfc.addr, bytes([0x55]))
    except OSError: pass
    time.sleep_ms(100)
    try:
        nfc._send_command(0x14, b'\x01\x00\x00', timeout=300)
        nfc._send_command(0x32, b'\x05\x01\x01\x02', timeout=300)
    except Exception: pass

# ─────────────────────────────────────────────
# READ NDEF
# ─────────────────────────────────────────────
def read_tag_text(nfc):
    try: tag = nfc.read_passive_target(timeout=500)
    except Exception: return None
    if tag is None or tag['sak'] not in (0x08, 0x18): return None

    nd = bytearray()
    try:
        for sector in (1, 2):
            fb = sector * 4; authed = False
            for key in COMMON_KEYS:
                for kt in [MIFARE_AUTH_A, MIFARE_AUTH_B]:
                    try: resel = nfc.read_passive_target(timeout=200)
                    except Exception: continue
                    if resel is None: continue
                    try:
                        if nfc.mifare_auth_block(resel['uid'], fb, key, kt):
                            for blk in range(fb, fb + 3):
                                try: nd.extend(nfc.mifare_read_block(blk))
                                except Exception: nd.extend(b'\x00' * 16)
                            authed = True; break
                    except Exception: continue
                if authed: break
            if not authed: nd.extend(b'\x00' * 48)
    except Exception: pass
    return _decode_ndef_text(nd) if nd else None

# ─────────────────────────────────────────────
# LED STRIP FEEDBACK
# ─────────────────────────────────────────────
def strip_blink_colors(leds, commands):
    colors = [TAG_COLOR.get(cmd, (30, 30, 30)) for cmd in commands if cmd in TAG_COLOR]
    if not colors: colors = [(0, 40, 0)]

    for color in colors:
        leds.solid(*color); time.sleep_ms(300)
        leds.off(); time.sleep_ms(100)

    for _ in range(3):
        for offset in range(leds.num):
            for i in range(leds.num):
                c = colors[(i + offset) % len(colors)]
                leds.np[i] = c
            leds.np.write(); time.sleep_ms(40)
    leds.off()

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "=" * 50)
    print("  Programming Station — 4x NFC Reader Hub")
    print("  Hub type: %s" % HUB_TYPE)
    print("=" * 50)

    i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=I2C_FREQ)
    btn_pin = machine.Pin(BTN_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    mux_rst = machine.Pin(MUX_RST_PIN, machine.Pin.OUT, value=1)
    pn532_rst = machine.Pin(PN532_RST_PIN, machine.Pin.OUT, value=1)
    leds = Leds()
    leds.off()

    mux_reset(mux_rst); pn532_hard_reset(pn532_rst)
    print("  I2C: %s" % str([hex(a) for a in i2c.scan()]))

    nfc = PN532(i2c, PN532_ADDR)
    ok_readers = []
    for ch in range(NUM_READERS):
        print("  Init reader #%d..." % ch)
        mux_select(i2c, ch); time.sleep_ms(20)
        try: init_reader(nfc); ok_readers.append(ch)
        except Exception as e: print("    Failed: %s" % str(e))
    mux_disable(i2c)

    mgr = ESPNowManager()
    mgr.init()

    print("\n  %d/%d readers ready. Press button.\n" % (len(ok_readers), NUM_READERS))

    last_btn = 1
    while True:
        cur = btn_pin.value()
        if last_btn == 1 and cur == 0:
            time.sleep_ms(30)
            if btn_pin.value() == 0:
                try:
                    print("— Scanning all readers —")
                    mux_reset(mux_rst); pn532_hard_reset(pn532_rst)
                    for ch in ok_readers:
                        mux_select(i2c, ch); time.sleep_ms(30); reinit_reader(nfc)

                    commands = []
                    for ch in ok_readers:
                        text = None
                        for _ in range(MAX_RETRIES):
                            try:
                                mux_select(i2c, ch); time.sleep_ms(30)
                                reinit_reader(nfc); time.sleep_ms(20)
                                text = read_tag_text(nfc)
                            except Exception: text = None
                            if text: break
                            time.sleep_ms(50)
                        if text:
                            commands.append(text)
                            print("  #%d: \"%s\"" % (ch, text))
                        else:
                            print("  #%d: no tag" % ch)

                    try: mux_disable(i2c)
                    except Exception: pass

                    if commands:
                        print("  Broadcasting: %s" % str(commands))
                        mgr.broadcast(commands)
                        strip_blink_colors(leds, commands)
                    else:
                        print("  No tags found")

                except Exception as ex:
                    print("  [ERR] %s" % str(ex))
                    try: mux_disable(i2c)
                    except Exception: pass
                print()
        last_btn = cur
        time.sleep_ms(10)

if __name__ == "__main__":
    main()