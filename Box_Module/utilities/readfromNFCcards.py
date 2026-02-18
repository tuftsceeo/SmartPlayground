"""
PlaygroundV5 - PN532 NFC Tag Reader (Fixed Protocol)
=====================================================
Board: Seeed XIAO ESP32-C6
NFC: PN532 on shared I2C bus (SDA=GPIO22, SCL=GPIO23)
PN532 I2C address: 0x24

Fixed: Proper I2C ACK/response frame handling for reliable
MIFARE Classic auth + read and NTAG page reads.
"""

import machine
import time
import struct

# ─────────────────────────────────────────────
# PIN CONFIG
# ─────────────────────────────────────────────
I2C_SDA = 22
I2C_SCL = 23
PN532_ADDR = 0x24

# ─────────────────────────────────────────────
# PN532 CONSTANTS
# ─────────────────────────────────────────────
TFI_HOST2PN532 = 0xD4
TFI_PN5322HOST = 0xD5

CMD_GETFIRMWAREVERSION  = 0x02
CMD_SAMCONFIGURATION    = 0x14
CMD_INLISTPASSIVETARGET = 0x4A
CMD_INDATAEXCHANGE      = 0x40

MIFARE_CMD_AUTH_A = 0x60
MIFARE_CMD_AUTH_B = 0x61
MIFARE_CMD_READ   = 0x30

TAG_TYPES = {
    (0x0004, 0x08): "MIFARE Classic 1K",
    (0x0002, 0x08): "MIFARE Classic 1K",
    (0x0044, 0x08): "MIFARE Classic 1K",
    (0x0004, 0x18): "MIFARE Classic 4K",
    (0x0002, 0x18): "MIFARE Classic 4K",
    (0x0044, 0x00): "MIFARE Ultralight / NTAG2xx",
    (0x0004, 0x00): "MIFARE Ultralight / NTAG2xx",
    (0x0004, 0x20): "MIFARE Plus / NTAG",
    (0x0044, 0x20): "MIFARE DESFire",
}


class PN532:
    def __init__(self, i2c, addr=0x24):
        self.i2c = i2c
        self.addr = addr
        self.debug = False  # set True to see raw frames

    # ─── LOW LEVEL I2C PROTOCOL ───

    def _wait_ready(self, timeout=1000):
        """Poll PN532 until it signals ready (first byte = 0x01)."""
        start = time.ticks_ms()
        while True:
            try:
                status = self.i2c.readfrom(self.addr, 1)
                if status[0] == 0x01:
                    return True
            except OSError:
                pass
            if time.ticks_diff(time.ticks_ms(), start) > timeout:
                return False
            time.sleep_ms(10)

    def _write_command(self, cmd, params=b''):
        """Build and send a command frame to PN532."""
        payload = bytes([TFI_HOST2PN532, cmd]) + bytes(params)
        length = len(payload)
        lcs = (~length + 1) & 0xFF

        frame = bytearray([
            0x00, 0x00, 0xFF,   # preamble + start codes
            length, lcs,        # length + length checksum
        ])
        frame.extend(payload)
        dcs = (~sum(payload) + 1) & 0xFF
        frame.append(dcs)
        frame.append(0x00)      # postamble

        if self.debug:
            print(f"    >> TX: {' '.join(f'{b:02X}' for b in frame)}")

        self.i2c.writeto(self.addr, frame)

    def _read_ack(self, timeout=500):
        """Read and verify the ACK frame from PN532."""
        if not self._wait_ready(timeout):
            raise RuntimeError("Timeout waiting for ACK ready")

        # Read ACK: ready_byte + 00 00 FF 00 FF 00
        ack = self.i2c.readfrom(self.addr, 7)
        if self.debug:
            print(f"    << ACK: {' '.join(f'{b:02X}' for b in ack)}")

        # Check for ACK pattern (skip ready byte at index 0)
        # ACK = 00 00 FF 00 FF 00
        # But ready byte might or might not be at start
        ack_pattern = bytes([0x00, 0x00, 0xFF, 0x00, 0xFF, 0x00])
        if ack_pattern in bytes(ack):
            return True

        # Some PN532 boards send slightly different ACKs
        # Accept if we see 00 FF 00 FF anywhere
        raw = bytes(ack)
        for i in range(len(raw) - 3):
            if raw[i] == 0x00 and raw[i+1] == 0xFF and raw[i+2] == 0x00 and raw[i+3] == 0xFF:
                return True

        raise RuntimeError(f"Bad ACK: {' '.join(f'{b:02X}' for b in ack)}")

    def _read_response(self, timeout=1000):
        """Read a response frame from PN532. Returns payload bytes."""
        if not self._wait_ready(timeout):
            raise RuntimeError("Timeout waiting for response ready")

        # Read a generous chunk — ready_byte + frame
        # Max response ~64 bytes for most commands
        buf = self.i2c.readfrom(self.addr, 64)
        if self.debug:
            print(f"    << RX: {' '.join(f'{b:02X}' for b in buf[:32])}...")

        # Find frame start: look for 00 FF after the ready byte
        raw = bytes(buf)
        offset = -1
        for i in range(len(raw) - 4):
            if raw[i] == 0x00 and raw[i+1] == 0xFF:
                # Make sure this isn't the 00 FF 00 FF ACK pattern
                if i + 2 < len(raw) and raw[i+2] != 0x00:
                    offset = i
                    break
                elif i + 2 < len(raw) and raw[i+2] == 0x00 and i + 3 < len(raw) and raw[i+3] != 0xFF:
                    offset = i
                    break

        if offset < 0:
            raise RuntimeError(f"No frame start found in response")

        frame_len = raw[offset + 2]
        lcs = raw[offset + 3]
        if ((frame_len + lcs) & 0xFF) != 0:
            raise RuntimeError(f"Length checksum error: len={frame_len} lcs={lcs}")

        data_start = offset + 4
        data = raw[data_start: data_start + frame_len]

        if len(data) < frame_len:
            raise RuntimeError(f"Short response: got {len(data)}, expected {frame_len}")

        # Verify data checksum
        dcs = raw[data_start + frame_len]
        if ((sum(data) + dcs) & 0xFF) != 0:
            raise RuntimeError("Data checksum error")

        return data

    def _send_command(self, cmd, params=b'', timeout=1000):
        """Send command, read ACK, read response, return payload."""
        self._write_command(cmd, params)
        time.sleep_ms(5)
        self._read_ack(timeout=timeout)
        resp = self._read_response(timeout=timeout)

        # Validate TFI and response code
        if len(resp) < 2:
            raise RuntimeError(f"Response too short: {len(resp)} bytes")
        if resp[0] != TFI_PN5322HOST:
            raise RuntimeError(f"Bad TFI: 0x{resp[0]:02X}")
        if resp[1] != (cmd + 1):
            raise RuntimeError(f"Bad response code: 0x{resp[1]:02X} (expected 0x{(cmd+1):02X})")

        return resp[2:]

    # ─── HIGH LEVEL COMMANDS ───

    def get_firmware_version(self):
        resp = self._send_command(CMD_GETFIRMWAREVERSION)
        return {
            'ic': resp[0], 'ver': resp[1],
            'rev': resp[2], 'support': resp[3],
        }

    def sam_config(self):
        self._send_command(CMD_SAMCONFIGURATION, b'\x01\x00\x00')

    def read_passive_target(self, baud=0x00, timeout=1000):
        """Detect ISO14443A tag. Returns dict or None."""
        try:
            resp = self._send_command(
                CMD_INLISTPASSIVETARGET,
                bytes([0x01, baud]),
                timeout=timeout
            )
        except RuntimeError:
            return None

        if len(resp) < 6 or resp[0] == 0:
            return None

        tg = resp[1]
        atqa = (resp[2] << 8) | resp[3]
        sak = resp[4]
        uid_len = resp[5]
        uid = resp[6:6 + uid_len]

        return {
            'uid': uid,
            'uid_hex': ':'.join(f'{b:02X}' for b in uid),
            'uid_len': uid_len,
            'atqa': atqa,
            'sak': sak,
            'tag_type': TAG_TYPES.get((atqa, sak), f"Unknown (ATQA=0x{atqa:04X} SAK=0x{sak:02X})"),
            'target': tg,
        }

    def mifare_auth_block(self, uid, block, key=b'\xFF\xFF\xFF\xFF\xFF\xFF', key_type=MIFARE_CMD_AUTH_A):
        """Authenticate a MIFARE Classic block. Returns True on success."""
        # InDataExchange: [Tg=1, AuthCmd, Block, Key(6), UID(4)]
        params = bytes([0x01, key_type, block]) + bytes(key) + bytes(uid[:4])
        try:
            resp = self._send_command(CMD_INDATAEXCHANGE, params, timeout=1000)
            if self.debug:
                print(f"    Auth block {block}: status=0x{resp[0]:02X}")
            return (resp[0] & 0x3F) == 0x00  # mask error bits
        except RuntimeError as e:
            if self.debug:
                print(f"    Auth block {block} error: {e}")
            return False

    def mifare_read_block(self, block):
        """Read 16 bytes from authenticated MIFARE Classic block."""
        params = bytes([0x01, MIFARE_CMD_READ, block])
        resp = self._send_command(CMD_INDATAEXCHANGE, params, timeout=1000)
        status = resp[0] & 0x3F
        if status != 0x00:
            raise RuntimeError(f"Read status: 0x{status:02X}")
        if len(resp) < 17:
            raise RuntimeError(f"Short read: {len(resp)-1} bytes")
        return resp[1:17]

    def ntag_read_page(self, page):
        """Read 4 bytes from NTAG/Ultralight page."""
        params = bytes([0x01, MIFARE_CMD_READ, page])
        resp = self._send_command(CMD_INDATAEXCHANGE, params, timeout=1000)
        status = resp[0] & 0x3F
        if status != 0x00:
            raise RuntimeError(f"Read status: 0x{status:02X}")
        return resp[1:5]


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def section(title):
    print("\n" + "=" * 55)
    print(f"  {title}")
    print("=" * 55)

# ─────────────────────────────────────────────
# MIFARE CLASSIC READ
# ─────────────────────────────────────────────
def read_mifare_classic(nfc, tag):
    print("\n  Reading MIFARE Classic (trying keys A & B):")
    print(f"  {'Block':>5} | {'Hex Data':48} | ASCII")
    print(f"  {'─'*5}─┼─{'─'*48}─┼─{'─'*16}")

    common_keys = [
        b'\xFF\xFF\xFF\xFF\xFF\xFF',  # factory default
        b'\xA0\xA1\xA2\xA3\xA4\xA5',  # MAD key A
        b'\xB0\xB1\xB2\xB3\xB4\xB5',  # common key B
        b'\xD3\xF7\xD3\xF7\xD3\xF7',  # NFC Forum public key
        b'\x00\x00\x00\x00\x00\x00',  # blank key
    ]

    sectors_to_read = 4
    total_read = 0
    total_fail = 0

    for sector in range(sectors_to_read):
        first_block = sector * 4
        authed = False

        # Try each key until one works
        for key in common_keys:
            for key_type in [MIFARE_CMD_AUTH_A, MIFARE_CMD_AUTH_B]:
                # Must re-select tag before each auth attempt
                resel = nfc.read_passive_target(timeout=300)
                if resel is None:
                    continue

                if nfc.mifare_auth_block(tag['uid'], first_block, key, key_type):
                    kt = 'A' if key_type == MIFARE_CMD_AUTH_A else 'B'
                    key_hex = ''.join(f'{b:02X}' for b in key)

                    # Read all 4 blocks in this sector
                    for block in range(first_block, first_block + 4):
                        try:
                            data = nfc.mifare_read_block(block)
                            hex_str = ' '.join(f'{b:02X}' for b in data)
                            asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)

                            label = ""
                            if block == 0:
                                label = " <- Manufacturer"
                            elif block % 4 == 3:
                                label = f" <- Trailer (Key{kt}:{key_hex})"

                            print(f"  {block:>5} | {hex_str} | {asc}{label}")
                            total_read += 1
                        except RuntimeError as e:
                            print(f"  {block:>5} | (read error: {e})")
                            total_fail += 1

                    authed = True
                    break
            if authed:
                break

        if not authed:
            print(f"  Sector {sector} (blocks {first_block}-{first_block+3}): "
                  f"Auth failed with all keys")
            total_fail += 4

    print(f"\n  Summary: {total_read} blocks read, {total_fail} failed")

# ─────────────────────────────────────────────
# NTAG / ULTRALIGHT READ
# ─────────────────────────────────────────────
def read_ntag(nfc, tag):
    print("\n  Reading NTAG / Ultralight pages:")
    print(f"  {'Page':>5} | {'Hex Data':14} | ASCII")
    print(f"  {'─'*5}─┼─{'─'*14}─┼─{'─'*4}")

    max_pages = 45  # NTAG213=45, try up to this
    ndef_data = bytearray()
    pages_read = 0

    for page in range(max_pages):
        try:
            data = nfc.ntag_read_page(page)
            hex_str = ' '.join(f'{b:02X}' for b in data)
            asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)

            labels = {0: " <- UID", 1: " <- UID", 2: " <- Lock", 3: " <- CC", 4: " <- NDEF start"}
            label = labels.get(page, "")
            print(f"  {page:>5} | {hex_str} | {asc}{label}")
            pages_read += 1

            if page >= 4:
                ndef_data.extend(data)

        except Exception:
            print(f"  {page:>5} | (end of readable area)")
            break

    print(f"\n  Pages read: {pages_read}")

    if ndef_data:
        decode_ndef(ndef_data)


def decode_ndef(data):
    print("\n  NDEF Decode:")
    try:
        i = 0
        while i < len(data):
            t = data[i]
            if t == 0x00:
                i += 1; continue
            elif t == 0xFE:
                break
            elif t == 0x03:
                length = data[i + 1]
                off = i + 2
                if length == 0xFF:
                    length = (data[i + 2] << 8) | data[i + 3]
                    off = i + 4
                ndef = data[off: off + length]

                if len(ndef) > 3:
                    flags = ndef[0]
                    type_len = ndef[1]
                    sr = flags & 0x10  # short record
                    pl = ndef[2] if sr else (ndef[2] << 24 | ndef[3] << 16 | ndef[4] << 8 | ndef[5])
                    ho = 3 if sr else 6
                    rec_type = bytes(ndef[ho:ho + type_len])
                    payload = bytes(ndef[ho + type_len:ho + type_len + pl])
                    ts = rec_type.decode('ascii', 'replace')
                    print(f"    Type: '{ts}' ({pl} bytes)")

                    if ts == 'T':
                        ll = payload[0] & 0x3F
                        lang = payload[1:1+ll].decode('ascii', 'replace')
                        text = payload[1+ll:].decode('utf-8', 'replace')
                        print(f"    Lang: {lang}")
                        print(f"    Text: \"{text}\"")
                    elif ts == 'U':
                        prefixes = ["", "http://www.", "https://www.", "http://", "https://",
                                    "tel:", "mailto:", "ftp://anonymous:anonymous@", "ftp://ftp."]
                        pre = prefixes[payload[0]] if payload[0] < len(prefixes) else ""
                        uri = pre + payload[1:].decode('utf-8', 'replace')
                        print(f"    URI: {uri}")
                    else:
                        print(f"    Payload: {payload[:50]}")
                break
            else:
                i += 2 + data[i + 1]; continue
            i += 1
    except Exception as e:
        print(f"    Decode error: {e}")


# ─────────────────────────────────────────────
# UID-ONLY MODE (guaranteed to work)
# ─────────────────────────────────────────────
def read_uid_only(nfc):
    """Simple mode — just reads and logs UIDs without reading blocks."""
    section("UID-Only Mode — Tap tags to log UIDs")
    print("  Press Ctrl+C to stop\n")

    seen = {}
    last_uid = None

    while True:
        try:
            tag = nfc.read_passive_target(timeout=500)
            if tag is None:
                if last_uid:
                    print("  --- removed ---\n")
                    last_uid = None
                time.sleep_ms(200)
                continue

            uid = tag['uid_hex']
            if uid != last_uid:
                last_uid = uid
                count = seen.get(uid, 0) + 1
                seen[uid] = count

                print(f"  Tag: {uid}  |  {tag['tag_type']}  |  "
                      f"seen {count}x  |  total unique: {len(seen)}")

            time.sleep_ms(300)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"  [ERR] {e}")
            time.sleep_ms(500)

    print(f"\n  Unique tags: {len(seen)}")
    for uid, cnt in seen.items():
        print(f"    {uid} — {cnt} reads")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "*" * 55)
    print("  PlaygroundV5 — PN532 NFC Tag Reader")
    print("  Board: XIAO ESP32-C6")
    print("*" * 55)

    i2c = machine.SoftI2C(
        sda=machine.Pin(I2C_SDA),
        scl=machine.Pin(I2C_SCL),
        freq=100_000
    )

    devices = i2c.scan()
    print(f"\n  I2C devices: {['0x{:02X}'.format(d) for d in devices]}")

    if PN532_ADDR not in devices:
        print(f"  [FAIL] PN532 not found at 0x{PN532_ADDR:02X}")
        return

    nfc = PN532(i2c, PN532_ADDR)
    # nfc.debug = True  # uncomment to see raw I2C frames

    section("PN532 Init")
    try:
        fw = nfc.get_firmware_version()
        print(f"  IC: PN5{fw['ic']:02X}")
        print(f"  Firmware: {fw['ver']}.{fw['rev']}")
        print(f"  Supports: 0x{fw['support']:02X}")
        nfc.sam_config()
        print("  SAM configured")
    except Exception as e:
        print(f"  [FAIL] Init error: {e}")
        return

    # Main tag reading loop
    section("Scanning — Hold a tag near the reader")
    print("  Press Ctrl+C to stop\n")

    last_uid = None
    tag_count = 0

    while True:
        try:
            tag = nfc.read_passive_target(timeout=500)

            if tag is None:
                if last_uid is not None:
                    print("  --- Tag removed ---\n")
                    last_uid = None
                time.sleep_ms(200)
                continue

            if tag['uid_hex'] != last_uid:
                tag_count += 1
                last_uid = tag['uid_hex']

                print(f"  ┌─ Tag #{tag_count} ──────────────────────")
                print(f"  │ UID:  {tag['uid_hex']} ({tag['uid_len']} bytes)")
                print(f"  │ Type: {tag['tag_type']}")
                print(f"  │ ATQA: 0x{tag['atqa']:04X}  SAK: 0x{tag['sak']:02X}")
                print(f"  └────────────────────────────────────")

                try:
                    if 'Classic' in tag['tag_type']:
                        read_mifare_classic(nfc, tag)
                    elif 'Ultralight' in tag['tag_type'] or 'NTAG' in tag['tag_type']:
                        read_ntag(nfc, tag)
                    else:
                        print("  (Tag type not supported for data read)")
                        print(f"  UID logged: {tag['uid_hex']}")
                except Exception as e:
                    print(f"  [WARN] Data read failed: {e}")
                    print(f"  UID was still captured: {tag['uid_hex']}")

                print()


            time.sleep_ms(300)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"  [ERR] {e}")
            time.sleep_ms(500)

    section("Done")
    print(f"  Total tags read: {tag_count}")


if __name__ == "__main__":
    main()
    # To use UID-only mode (skip block reads), comment out main() and uncomment:
    # read_uid_only(nfc)