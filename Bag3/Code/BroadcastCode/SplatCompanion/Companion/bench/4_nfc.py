"""
4_nfc.py -- bench stage 4: PN532 card reader on I2C
====================================================
Run on the hub: mpremote connect $HUB resume run bench/4_nfc.py
Needs on the hub: /hubtype.txt, /lib/hubtype.py, /lib/pn532.py,
/lib/nfc_reader.py, /lib/splat_tags.py.

Scans the bus (expects nfc_addr, 0x24), starts the PN532 and prints its
firmware (PASS), then for TAP_S prints each tapped card's command.
"""

import time
import machine
from hubtype import HUB_CONFIG
from splat_tags import GAME_TAGS, CONTROL_TAGS

TAP_S = 60

i2c = machine.SoftI2C(sda=machine.Pin(HUB_CONFIG["i2c_sda"]),
                      scl=machine.Pin(HUB_CONFIG["i2c_scl"]),
                      freq=HUB_CONFIG["i2c_freq"])
addr = HUB_CONFIG.get("nfc_addr", 0x24)
found = i2c.scan()
print("bench 4: sda=%d scl=%d found %s" % (HUB_CONFIG["i2c_sda"],
      HUB_CONFIG["i2c_scl"], [hex(a) for a in found]))
if addr not in found:
    print("FAIL: PN532 not at 0x%02X -- check wiring and the PN532's I2C mode switch" % addr)
    raise SystemExit

from pn532 import PN532
from nfc_reader import NfcReader

nfc = PN532(i2c, addr)
ic, ver, rev = nfc.begin()
print("PASS: PN532 firmware %d.%d (IC 0x%02X) -- tap cards now (%d s)" % (ver, rev, ic, TAP_S))
reader = NfcReader(nfc, GAME_TAGS | CONTROL_TAGS, prefixes={"getcode"})

end = time.ticks_add(time.ticks_ms(), TAP_S * 1000)
last_uid = None
while time.ticks_diff(end, time.ticks_ms()) > 0:
    uid, sak = reader.detect_tag()
    if uid is None:
        last_uid = None
    elif uid != last_uid:
        cmd, uid = reader.read_command()
        last_uid = uid
        print("card %s -> %r" % (uid, cmd))
    time.sleep_ms(1)
print("DONE")
