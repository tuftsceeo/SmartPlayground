"""dial_board.py — M5 Dial 2 (StampS3A) hardware constants and construction.

Phase 0 (probe_dial.py, 2026-09-09):
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
"""

from card_writer import NfcWriter

SCREEN_W = 240
SCREEN_H = 240

# Confirmed by probe_dial: internal RFID+RTC+touch bus (Dial / Dial v1.1 pinmap).
I2C_SDA = 11
I2C_SCL = 12
NFC_ADDR = 0x28  # WS1850S (H2); VersionReg read 0x15 on this unit
I2C_FREQ = 100_000

# StickS3 stayed under ~190 to avoid brown-out on battery. Dial 2 has a
# larger enclosure and different power path; start moderate and check on
# battery in Phase 1.
SPEAKER_VOLUME = 180


def make_reader():
    """Construct and init the built-in reader; antenna left off.

    Hardware I2C peripheral (not SoftI2C) on the shared internal bus (also
    touch @ 0x38, RTC @ 0x51). SoftI2C ACKs a bare i2c.scan() of the WS1850S
    at NFC_ADDR just fine, but its bit-banged clock cannot reliably stretch
    for a real register read -- readfrom_mem() times out (ETIMEDOUT) even
    though the chip is present and powered. machine.I2C's hardware
    peripheral does not have that limitation; confirmed live against this
    unit (readfrom_mem(NFC_ADDR, VersionReg) -> 0x15, matching H2's probe).
    Raises whatever NfcWriter/WS1850S raises on a dead bus.
    """
    import machine
    i2c = machine.I2C(
        0, sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=I2C_FREQ)
    nfc = NfcWriter(i2c, NFC_ADDR)
    nfc.init()
    # WS1850S.__init__ leaves the antenna on; idle until a scan says otherwise.
    nfc.antenna_off()
    return nfc
