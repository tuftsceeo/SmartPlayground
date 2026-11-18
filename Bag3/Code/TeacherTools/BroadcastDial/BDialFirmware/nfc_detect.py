"""nfc_detect.py -- what is on the Dial's Port A, and the reader to use.

Imported lazily by dial_board.make_reader(), after the radio prewarm --
dial_board itself is imported before it, so nothing here may move there.

One i2c.scan() of Port A (sda=13 scl=15):

  0x24  PN532 (pn532_writer.py)          reader on Port A, no tag
  0x28  WS1850S / Grove RFID2             reader on Port A, no tag
  0x55  MIKROE NFC Tag 2 Click (NT3H2111) the Click is the "card" a wand
        taps (tag_emulator.py); Read uses the built-in WS1850S
  none  built-in WS1850S                  reader on the internal bus

The reader takes hardware I2C(0) either way (SoftI2C cannot clock-stretch
for the WS1850S -- see dial_board). In Click mode the Click goes on
SoftI2C on Port A: it is a plain EEPROM, and this leaves the internal
bus's hardware controller to the reader.

Returns (reader, tag, kind): tag is an NT3H2111 or None; kind is
"pn532", "ws1850s", "click" or "internal". A reader that fails to come up
raises, as before.
"""

import machine

from dial_board import (I2C_SDA, I2C_SCL, EXT_I2C_SDA, EXT_I2C_SCL,
                        NFC_ADDR, I2C_FREQ)

PN532_ADDR = 0x24
TAG_ADDR = 0x55


def _internal():
    from card_writer import NfcWriter
    i2c = machine.I2C(0, sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL),
                      freq=I2C_FREQ)
    return NfcWriter(i2c, NFC_ADDR)


def make_reader():
    ext = machine.I2C(0, sda=machine.Pin(EXT_I2C_SDA),
                      scl=machine.Pin(EXT_I2C_SCL), freq=I2C_FREQ)
    try:
        found = ext.scan()
    except OSError:
        found = []
    print("# nfc: Port A scan %s" % [hex(a) for a in found])
    tag = None
    if PN532_ADDR in found:
        from pn532_writer import Pn532Writer
        nfc = Pn532Writer(ext, PN532_ADDR)
        kind = "pn532"
    elif NFC_ADDR in found:
        from card_writer import NfcWriter
        nfc = NfcWriter(ext, NFC_ADDR)
        kind = "ws1850s"
    elif TAG_ADDR in found:
        from nt3h2111 import NT3H2111
        nfc = _internal()       # re-creates I2C(0) on the internal pins
        soft = machine.SoftI2C(sda=machine.Pin(EXT_I2C_SDA),
                               scl=machine.Pin(EXT_I2C_SCL), freq=I2C_FREQ)
        tag = NT3H2111(soft, TAG_ADDR)
        kind = "click"
    else:
        nfc = _internal()
        kind = "internal"
    print("# nfc: %s" % kind)
    nfc.init()
    nfc.antenna_off()   # idle until a scan says otherwise
    return nfc, tag, kind
