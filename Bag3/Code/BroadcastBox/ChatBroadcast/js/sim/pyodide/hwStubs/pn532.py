"""Browser stub for PN532 NFC driver."""

MIFARE_AUTH_A = 0x60
MIFARE_AUTH_B = 0x61
MIFARE_READ = 0x30


class PN532:
    def __init__(self, i2c, addr=0x24):
        self.i2c = i2c
        self.addr = addr

    def begin(self):
        return (0x32, 1, 6)

    def read_passive_target(self, baud=0x00, timeout=500):
        from sim_bootstrap import input_state
        pending = input_state.get("nfc_pending")
        if pending:
            cmd, uid = pending
            input_state["nfc_pending"] = None
            return {"uid": b"\x00" * 4, "uid_hex": uid or "sim", "atqa": 0, "sak": 0x08, "uid_len": 4}
        return None

    def mifare_auth_block(self, uid, block, key, key_type):
        return True

    def mifare_read_block(self, block):
        return b"\x00" * 16

    def ntag_read_page(self, page):
        return b"\x00" * 4
