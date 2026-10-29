"""dial_board.py — M5 Dial 2 (StampS3A) hardware constants and construction.

Phase 0 (tools/probe_dial.py, 2026-09-09):
  H1 PASS — UIFlow2, 240x240, Rotary, m5ui, BtnA+BtnB APIs present
  H2 PASS — WS1850S-class at 0x28, VersionReg=0x15
  H3 PASS for pins — sda=11 scl=12; same bus also has touch @ 0x38 and
       RTC8563 @ 0x51. SoftI2C's version() (a bare register read) worked
       during this probe, but that was misleading: SoftI2C ACKs an
       i2c.scan() of the WS1850S fine, yet its bit-banged clock cannot
       reliably stretch for a real readfrom_mem() -- intermittent
       ETIMEDOUT once real traffic (UI loop, vendor RFID driver) hit the
       bus. Switched to the hardware machine.I2C peripheral on these same
       pins post-Phase-0 (2026-09-09 field debugging); confirmed live:
       readfrom_mem(NFC_ADDR, VersionReg) -> 0x15, matching this line.
  H5 FAIL as probed — SoftAP OOM with 8 LVGL pages resident (~40 kB free).
       Real firmware must keep screen budget tight / free before arming AP.
  H4/H6/H7 — incomplete on first run (H7 crashed after H5 OOM).

make_reader() raises loudly rather than returning None — a broken reader
must be a crash, matching buttons.py's stance on the Box.

EXTERNAL READER: the built-in reader's antenna sits under the LCD, sharing
the enclosure with the touch controller, RTC, encoder assembly, speaker
and battery -- detuning the coil and causing the poor read/write
reliability reported against the Box's external M5Stack RFID 2 Grove unit
(same WS1850S chip, its own antenna, off on a cable away from other
components). Confirmed on real hardware 2026-09-22: an external Grove
RFID2 unit wired to the Dial's Port A header (sda=13 scl=15, ACKs 0x28 --
probe_dial.run(stages=[4])) reads/writes noticeably better than the
built-in reader. make_reader() now prefers that external unit whenever one
is attached, and falls back to the built-in reader when it isn't -- a
missing external unit must not brick a Dial that has none wired up.
"""

from card_writer import NfcWriter

SCREEN_W = 240
SCREEN_H = 240

# Confirmed by probe_dial: internal RFID+RTC+touch bus (Dial / Dial v1.1 pinmap).
I2C_SDA = 11
I2C_SCL = 12
NFC_ADDR = 0x28  # WS1850S (H2); VersionReg read 0x15 on this unit
I2C_FREQ = 100_000

# External Grove RFID2 (WS1850S) on the Dial's Port A header -- see the
# EXTERNAL READER note above. Pins confirmed live 2026-09-22 via
# probe_dial.run(stages=[4]) on a real unit wired to Port A: sda=13 scl=15
# ACKs a device at 0x28 (WS1850S), matching the internal chip's address on
# a separate bus -- no address conflict either way.
EXT_I2C_SDA = 13
EXT_I2C_SCL = 15


# StickS3 stayed under ~190 to avoid brown-out on battery. Dial 2 has a
# larger enclosure and different power path; start moderate and check on
# battery in Phase 1.
SPEAKER_VOLUME = 180


def make_reader():
    """Construct and init the reader; antenna left off.

    Prefers the external Grove unit on Port A (see EXTERNAL READER above);
    falls back to the built-in reader when nothing acks at NFC_ADDR on that
    bus. WS1850S.__init__ writes registers immediately, so a bus with
    nothing listening raises there (OSError, no ACK) -- that's exactly the
    signal used to detect "no external unit attached", not an error to
    surface.

    Hardware I2C peripheral (not SoftI2C) either way -- SoftI2C ACKs a bare
    i2c.scan() of the WS1850S fine, but its bit-banged clock cannot reliably
    stretch for a real register read (readfrom_mem() -- ETIMEDOUT) even
    though the chip is present and powered; machine.I2C's hardware
    peripheral does not have that limitation. Confirmed live on both buses
    (readfrom_mem(NFC_ADDR, VersionReg) -> 0x15 on each).

    Raises whatever NfcWriter/WS1850S raises if BOTH buses are dead -- a
    fully broken reader must still be a crash, matching buttons.py's stance
    on the Box.
    """
    import machine
    try:
        i2c = machine.I2C(
            0, sda=machine.Pin(EXT_I2C_SDA), scl=machine.Pin(EXT_I2C_SCL),
            freq=I2C_FREQ)
        nfc = NfcWriter(i2c, NFC_ADDR)
        print("# nfc: external reader on Port A (sda=%d scl=%d)"
              % (EXT_I2C_SDA, EXT_I2C_SCL))
    except Exception as e:
        print("# nfc: no external reader on Port A (%s) -- using built-in"
              % str(e))
        i2c = machine.I2C(
            0, sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL),
            freq=I2C_FREQ)
        nfc = NfcWriter(i2c, NFC_ADDR)
    nfc.init()
    # WS1850S.__init__ leaves the antenna on; idle until a scan says otherwise.
    nfc.antenna_off()
    return nfc
