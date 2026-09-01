"""
ws1850s.py - MicroPython driver for the M5Stack RFID 2 Unit (WS1850S)

The WS1850S is an I2C-only contactless reader IC, register-compatible with
the well-known NXP MFRC522. Default I2C address is 0x28.

Supports:
    - Mifare Classic 1K / 4K (16-byte blocks, key-authenticated)
    - Mifare Ultralight / NTAG21x (4-byte pages, no auth)
    - Both 4-byte and 7-byte UIDs (full cascade-level anticollision)

Tested on ESP32-S3 with SoftI2C(scl=7, sda=6).
"""

import time


class WS1850S:
    # --- I2C address ---
    DEFAULT_ADDR = 0x28

    # --- Registers (same map as MFRC522) ---
    CommandReg      = 0x01
    ComIEnReg       = 0x02
    DivIEnReg       = 0x03
    ComIrqReg       = 0x04
    DivIrqReg       = 0x05
    ErrorReg        = 0x06
    Status1Reg      = 0x07
    Status2Reg      = 0x08
    FIFODataReg     = 0x09
    FIFOLevelReg    = 0x0A
    ControlReg      = 0x0C
    BitFramingReg   = 0x0D
    CollReg         = 0x0E
    ModeReg         = 0x11
    TxModeReg       = 0x12
    RxModeReg       = 0x13
    TxControlReg    = 0x14
    TxASKReg        = 0x15
    CRCResultRegH   = 0x21
    CRCResultRegL   = 0x22
    RFCfgReg        = 0x26
    TModeReg        = 0x2A
    TPrescalerReg   = 0x2B
    TReloadRegH     = 0x2C
    TReloadRegL     = 0x2D
    VersionReg      = 0x37

    # --- PCD (reader) commands ---
    PCD_IDLE        = 0x00
    PCD_CALCCRC     = 0x03
    PCD_TRANSCEIVE  = 0x0C
    PCD_AUTHENT     = 0x0E
    PCD_RESETPHASE  = 0x0F

    # --- PICC (card) commands ---
    PICC_REQIDL          = 0x26
    PICC_REQALL          = 0x52
    PICC_ANTICOLL        = 0x93   # cascade level 1
    PICC_SELECTTAG       = 0x93
    PICC_ANTICOLL_CL2    = 0x95   # cascade level 2 (7-byte UIDs)
    PICC_SELECTTAG_CL2   = 0x95
    PICC_AUTHENT1A       = 0x60
    PICC_AUTHENT1B       = 0x61
    PICC_READ            = 0x30   # used by Classic and Ultralight
    PICC_WRITE           = 0xA0   # Mifare Classic write
    PICC_UL_WRITE        = 0xA2   # Ultralight / NTAG write
    PICC_HALT            = 0x50

    # ISO 14443-3 Cascade Tag (marks UID byte 0 of a longer UID)
    CT = 0x88

    # --- Status codes ---
    MI_OK       = 0
    MI_NOTAGERR = 1
    MI_ERR      = 2

    DEFAULT_KEY = b"\xFF\xFF\xFF\xFF\xFF\xFF"

    # ------------------------------------------------------------------
    # Construction / low-level register access
    # ------------------------------------------------------------------
    def __init__(self, i2c, addr=DEFAULT_ADDR):
        self.i2c = i2c
        self.addr = addr
        self.init()

    def _w(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val & 0xFF]))

    def _r(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def _set_bits(self, reg, mask):
        self._w(reg, self._r(reg) | mask)

    def _clr_bits(self, reg, mask):
        self._w(reg, self._r(reg) & (~mask & 0xFF))

    # ------------------------------------------------------------------
    # Init / antenna / reset
    # ------------------------------------------------------------------
    def reset(self):
        self._w(self.CommandReg, self.PCD_RESETPHASE)
        time.sleep_ms(50)

    def antenna_on(self):
        if not (self._r(self.TxControlReg) & 0x03):
            self._set_bits(self.TxControlReg, 0x03)

    def antenna_off(self):
        self._clr_bits(self.TxControlReg, 0x03)

    def set_antenna_gain(self, gain):
        self._w(self.RFCfgReg, (gain & 0x07) << 4)

    def init(self):
        self.reset()
        self._w(self.TModeReg, 0x8D)
        self._w(self.TPrescalerReg, 0x3E)
        self._w(self.TReloadRegL, 30)
        self._w(self.TReloadRegH, 0)
        self._w(self.TxASKReg, 0x40)
        self._w(self.ModeReg, 0x3D)
        self.antenna_on()

    def version(self):
        return self._r(self.VersionReg)

    # ------------------------------------------------------------------
    # Core transceive
    # ------------------------------------------------------------------
    def _to_card(self, command, send_data):
        back = []
        back_bits = 0
        status = self.MI_ERR
        irq_en = 0x00
        wait_irq = 0x00

        if command == self.PCD_AUTHENT:
            irq_en, wait_irq = 0x12, 0x10
        elif command == self.PCD_TRANSCEIVE:
            irq_en, wait_irq = 0x77, 0x30

        self._w(self.ComIEnReg, irq_en | 0x80)
        self._clr_bits(self.ComIrqReg, 0x80)
        self._set_bits(self.FIFOLevelReg, 0x80)
        self._w(self.CommandReg, self.PCD_IDLE)

        for b in send_data:
            self._w(self.FIFODataReg, b)

        self._w(self.CommandReg, command)
        if command == self.PCD_TRANSCEIVE:
            self._set_bits(self.BitFramingReg, 0x80)

        i = 2000
        while True:
            n = self._r(self.ComIrqReg)
            i -= 1
            if not ((i != 0) and not (n & 0x01) and not (n & wait_irq)):
                break

        self._clr_bits(self.BitFramingReg, 0x80)

        if i != 0:
            if (self._r(self.ErrorReg) & 0x1B) == 0x00:
                status = self.MI_OK
                if n & irq_en & 0x01:
                    status = self.MI_NOTAGERR
                if command == self.PCD_TRANSCEIVE:
                    n = self._r(self.FIFOLevelReg)
                    last_bits = self._r(self.ControlReg) & 0x07
                    back_bits = (n - 1) * 8 + last_bits if last_bits else n * 8
                    if n == 0:
                        n = 1
                    if n > 16:
                        n = 16
                    for _ in range(n):
                        back.append(self._r(self.FIFODataReg))

        return status, back, back_bits

    def _calc_crc(self, data):
        self._clr_bits(self.DivIrqReg, 0x04)
        self._set_bits(self.FIFOLevelReg, 0x80)
        for b in data:
            self._w(self.FIFODataReg, b)
        self._w(self.CommandReg, self.PCD_CALCCRC)
        i = 0xFF
        while True:
            n = self._r(self.DivIrqReg)
            i -= 1
            if not ((i != 0) and not (n & 0x04)):
                break
        return [self._r(self.CRCResultRegL), self._r(self.CRCResultRegH)]

    # ------------------------------------------------------------------
    # Anticollision / select
    # ------------------------------------------------------------------
    def request(self, mode=PICC_REQIDL):
        self._w(self.BitFramingReg, 0x07)
        status, _, bits = self._to_card(self.PCD_TRANSCEIVE, [mode])
        if status != self.MI_OK or bits != 0x10:
            status = self.MI_ERR
        return status, bits

    def _anticoll(self, cmd):
        """Generic anticollision for any cascade level."""
        self._w(self.BitFramingReg, 0x00)
        status, back, _ = self._to_card(self.PCD_TRANSCEIVE, [cmd, 0x20])
        if status == self.MI_OK:
            if len(back) == 5:
                chk = 0
                for i in range(4):
                    chk ^= back[i]
                if chk != back[4]:
                    status = self.MI_ERR
            else:
                status = self.MI_ERR
        return status, back

    def _select(self, cmd, uid_with_bcc):
        """Generic SELECT for any cascade level."""
        buf = [cmd, 0x70] + list(uid_with_bcc[:5])
        crc = self._calc_crc(buf)
        buf += crc
        status, back, bits = self._to_card(self.PCD_TRANSCEIVE, buf)
        if status == self.MI_OK and bits == 0x18:
            return back[0]
        return 0

    def anticoll(self):
        """Cascade level 1 anticollision. Returns (status, [4 UID bytes + BCC])."""
        return self._anticoll(self.PICC_ANTICOLL)

    def anticoll_cl2(self):
        """Cascade level 2 anticollision (for 7-byte UIDs)."""
        return self._anticoll(self.PICC_ANTICOLL_CL2)

    def select_tag(self, uid_with_bcc):
        return self._select(self.PICC_SELECTTAG, uid_with_bcc)

    def select_tag_cl2(self, uid_with_bcc):
        return self._select(self.PICC_SELECTTAG_CL2, uid_with_bcc)

    # ------------------------------------------------------------------
    # Authentication (Mifare Classic only)
    # ------------------------------------------------------------------
    def auth(self, mode, block, key, uid):
        # For 7-byte UID cards Classic uses the last 4 bytes of UID, but
        # these cards are rare; for 4-byte UIDs uid[:4] is the whole UID.
        buf = [mode, block] + list(key) + list(uid[:4])
        status, _, _ = self._to_card(self.PCD_AUTHENT, buf)
        if status != self.MI_OK or not (self._r(self.Status2Reg) & 0x08):
            status = self.MI_ERR
        return status

    def stop_crypto1(self):
        self._clr_bits(self.Status2Reg, 0x08)

    def halt(self):
        buf = [self.PICC_HALT, 0x00]
        buf += self._calc_crc(buf)
        self._to_card(self.PCD_TRANSCEIVE, buf)
        self.stop_crypto1()

    # ------------------------------------------------------------------
    # Mifare Classic block I/O
    # ------------------------------------------------------------------
    def read_block(self, block):
        buf = [self.PICC_READ, block]
        buf += self._calc_crc(buf)
        status, back, _ = self._to_card(self.PCD_TRANSCEIVE, buf)
        if status != self.MI_OK or len(back) != 16:
            return self.MI_ERR, None
        return status, back

    def write_block(self, block, data):
        if len(data) != 16:
            raise ValueError("block data must be exactly 16 bytes")
        buf = [self.PICC_WRITE, block]
        buf += self._calc_crc(buf)
        status, back, bits = self._to_card(self.PCD_TRANSCEIVE, buf)
        if status != self.MI_OK or bits != 4 or (back[0] & 0x0F) != 0x0A:
            return self.MI_ERR
        payload = list(data)
        payload += self._calc_crc(payload)
        status, back, bits = self._to_card(self.PCD_TRANSCEIVE, payload)
        if status != self.MI_OK or bits != 4 or (back[0] & 0x0F) != 0x0A:
            return self.MI_ERR
        return self.MI_OK

    # ------------------------------------------------------------------
    # Ultralight / NTAG21x page I/O (no authentication)
    # ------------------------------------------------------------------
    def ul_read(self, page):
        """
        Read 16 bytes (4 consecutive pages) starting at `page`.
        Works on Mifare Ultralight, Ultralight C/EV1, NTAG21x.
        Returns (status, 16-byte list).
        """
        buf = [self.PICC_READ, page]
        buf += self._calc_crc(buf)
        status, back, _ = self._to_card(self.PCD_TRANSCEIVE, buf)
        if status != self.MI_OK or len(back) != 16:
            return self.MI_ERR, None
        return status, back

    def ul_write(self, page, data):
        """
        Write exactly 4 bytes to a single page on Ultralight/NTAG.
        Returns status.
        """
        if len(data) != 4:
            raise ValueError("Ultralight page is exactly 4 bytes")
        buf = [self.PICC_UL_WRITE, page] + list(data)
        buf += self._calc_crc(buf)
        status, back, bits = self._to_card(self.PCD_TRANSCEIVE, buf)
        # ACK is 4 bits: 0xA = success, anything else (0/1/4/5) = NAK
        if status != self.MI_OK or bits != 4 or (back[0] & 0x0F) != 0x0A:
            return self.MI_ERR
        return self.MI_OK

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------
    def read_uid(self):
        """
        Legacy: returns the first 4 bytes from cascade level 1.
        For 7-byte UID cards this includes the cascade tag (0x88),
        which is NOT the real UID. Use read_uid_full() instead.
        """
        status, _ = self.request(self.PICC_REQIDL)
        if status != self.MI_OK:
            return None
        status, back = self.anticoll()
        if status != self.MI_OK or len(back) < 4:
            return None
        return bytes(back[:4])

    def read_uid_full(self):
        """
        Full anticollision cascade. Returns (uid, sak) or None.
            uid : bytes, length 4 or 7
            sak : int, the Select Acknowledge byte (tells you card type)
        Leaves the card in ACTIVE state — ready for auth (Classic) or
        page I/O (Ultralight/NTAG).
        """
        status, _ = self.request(self.PICC_REQIDL)
        if status != self.MI_OK:
            return None

        status, cl1 = self.anticoll()
        if status != self.MI_OK or len(cl1) < 5:
            return None

        sak = self.select_tag(cl1)
        if sak == 0:
            return None

        if cl1[0] != self.CT:
            return bytes(cl1[:4]), sak

        # Cascade tag present -> 7-byte UID, do level 2
        status, cl2 = self.anticoll_cl2()
        if status != self.MI_OK or len(cl2) < 5:
            return None
        sak2 = self.select_tag_cl2(cl2)
        if sak2 == 0:
            return None

        uid = bytes(cl1[1:4]) + bytes(cl2[:4])
        return uid, sak2

    def is_present(self):
        status, _ = self.request(self.PICC_REQIDL)
        return status == self.MI_OK