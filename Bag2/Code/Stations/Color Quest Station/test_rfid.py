"""
test_rfid.py — RFID read test for Color Quest Station
Supports MIFARE Classic 1K/4K and NTAG / Ultralight cards.
Run directly on the ESP32-C6 via REPL, or rename to main.py temporarily.
"""

import time
from machine import Pin, SoftI2C
from ws1850s import WS1850S

SDA = 22
SCL = 23

_COMMON_KEYS = [
    b'\xFF\xFF\xFF\xFF\xFF\xFF',
    b'\xD3\xF7\xD3\xF7\xD3\xF7',
    b'\xA0\xA1\xA2\xA3\xA4\xA5',
    b'\xB0\xB1\xB2\xB3\xB4\xB5',
    b'\x00\x00\x00\x00\x00\x00',
]


# ─── NDEF decode ──────────────────────────────────────────────────────────────

def _decode_ndef_text(data):
    if not data or len(data) < 4:
        return None
    i = 0
    while i < len(data):
        t = data[i]
        if t == 0x00:
            i += 1; continue
        if t == 0xFE:
            break
        if t == 0x03:
            if i + 1 >= len(data): break
            length = data[i + 1]
            off = i + 2
            if length == 0xFF:
                if i + 3 >= len(data): break
                length = (data[i + 2] << 8) | data[i + 3]
                off = i + 4
            ndef = data[off:off + length]
            if len(ndef) > 3:
                flags    = ndef[0]
                type_len = ndef[1]
                sr       = flags & 0x10
                if not sr and len(ndef) < 6: break
                pl  = ndef[2] if sr else (ndef[2] << 24 | ndef[3] << 16 | ndef[4] << 8 | ndef[5])
                ho  = 3 if sr else 6
                rec_type = ndef[ho:ho + type_len]
                payload  = ndef[ho + type_len:ho + type_len + pl]
                if bytes(rec_type) == b'T' and len(payload) > 1:
                    lang_len = payload[0] & 0x3F
                    return bytes(payload[1 + lang_len:]).decode('utf-8', 'replace').strip().lower()
                if bytes(rec_type) == b'U' and len(payload) > 1:
                    prefixes = ["", "http://www.", "https://www.", "http://",
                                "https://", "tel:", "mailto:"]
                    pre = prefixes[payload[0]] if payload[0] < len(prefixes) else ""
                    return (pre + bytes(payload[1:]).decode('utf-8', 'replace')).strip().lower()
            break
        else:
            i += 2 + data[i + 1] if i + 1 < len(data) else len(data)
    return None


# ─── Card type detection ───────────────────────────────────────────────────────

def detect_card(rfid):
    """
    Returns (uid_bytes, uid_str, sak, card_type) or (None, None, None, None).
    Handles single-cascade (4-byte, MIFARE Classic) and double-cascade
    (7-byte, NTAG / Ultralight) cards.
    """
    status, _ = rfid.request(WS1850S.PICC_REQIDL)
    if status != WS1850S.MI_OK:
        return None, None, None, None

    # Level-1 anticollision (SEL = 0x93)
    status, back = rfid.anticoll()
    if status != WS1850S.MI_OK or len(back) < 5:
        return None, None, None, None

    sak = rfid.select_tag(back)

    if not (sak & 0x04):
        # Single cascade complete — 4-byte UID
        uid = bytes(back[:4])
    else:
        # Double cascade — back[0] = CT (0x88), real bytes in back[1:4]
        uid_part1 = bytes(back[1:4])

        # Level-2 anticollision (SEL = 0x95)
        rfid._w(rfid.BitFramingReg, 0x00)
        st2, back2, _ = rfid._to_card(rfid.PCD_TRANSCEIVE, [0x95, 0x20])
        if st2 != rfid.MI_OK or len(back2) < 5:
            return None, None, None, None

        # Level-2 select
        sel2 = [0x95, 0x70] + list(back2[:5])
        sel2 += rfid._calc_crc(sel2)
        st3, back3, _ = rfid._to_card(rfid.PCD_TRANSCEIVE, sel2)
        if st3 != rfid.MI_OK or not back3:
            return None, None, None, None

        sak  = back3[0]
        uid  = uid_part1 + bytes(back2[:4])   # 7-byte UID

    uid_str = ":".join("%02X" % b for b in uid)

    if sak in (0x08, 0x18):
        card_type = "mifare_classic"
    elif sak == 0x00:
        card_type = "ntag_ultralight"
    else:
        card_type = "unknown"

    return uid, uid_str, sak, card_type


# ─── MIFARE Classic read ───────────────────────────────────────────────────────

def read_mifare_classic(rfid, uid):
    """Auth sectors 1 & 2, read blocks 4-6 and 8-10. Returns raw bytes."""
    nd = bytearray()
    for sector in (1, 2):
        fb = sector * 4
        authed = False
        for key in _COMMON_KEYS:
            for mode in (WS1850S.PICC_AUTHENT1A, WS1850S.PICC_AUTHENT1B):
                st = rfid.auth(mode, fb, key, uid)
                if st == WS1850S.MI_OK:
                    for blk in range(fb, fb + 3):
                        st2, data = rfid.read_block(blk)
                        nd.extend(data if (st2 == WS1850S.MI_OK and data) else b'\x00' * 16)
                    rfid.stop_crypto1()
                    authed = True
                    break
                rfid.stop_crypto1()
            if authed:
                break
        if not authed:
            nd.extend(b'\x00' * 48)
    rfid.halt()
    return nd


# ─── NTAG / Ultralight read ────────────────────────────────────────────────────

def read_ntag(rfid):
    """
    Read user pages 4-19 without auth. Each read_block() call returns 16 bytes
    (4 pages), so we step by 4. Returns raw bytes or empty bytearray on failure.
    """
    nd = bytearray()
    for page in range(4, 20, 4):
        st, data = rfid.read_block(page)
        if st == WS1850S.MI_OK and data:
            nd.extend(data)
        else:
            break
    rfid.halt()
    return nd


# ─── Hex dump helper ───────────────────────────────────────────────────────────

def hexdump(data, label="raw"):
    if not data:
        print("  %s: (empty)" % label)
        return
    print("  %s (%d bytes):" % (label, len(data)))
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        hex_part = " ".join("%02X" % b for b in chunk)
        asc_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print("    %04X  %-47s  %s" % (i, hex_part, asc_part))


# ─── Main loop ────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 44)
    print("  Color Quest Station — RFID Test")
    print("  SDA=%d  SCL=%d" % (SDA, SCL))
    print("  Tap any card. Ctrl-C to stop.")
    print("=" * 44 + "\n")

    i2c  = SoftI2C(sda=Pin(SDA), scl=Pin(SCL), freq=100_000)
    rfid = WS1850S(i2c)

    ver = rfid.version()
    print("WS1850S version reg: 0x%02X" % ver)
    if ver in (0x00, 0xFF):
        print("  WARNING: unexpected version — check wiring\n")
    else:
        print("  Looks good.\n")

    last_uid = None

    while True:
        uid, uid_str, sak, card_type = detect_card(rfid)

        if uid is None:
            if last_uid is not None:
                print("  [card removed]\n")
                last_uid = None
            time.sleep_ms(150)
            continue

        if uid_str == last_uid:
            time.sleep_ms(150)
            continue

        last_uid = uid_str
        print("UID  : %s" % uid_str)
        print("SAK  : 0x%02X  (%s)" % (sak, card_type))

        raw = bytearray()

        if card_type == "mifare_classic":
            print("Mode : MIFARE Classic — authenticating sectors 1 & 2")
            raw = read_mifare_classic(rfid, uid)
        elif card_type == "ntag_ultralight":
            print("Mode : NTAG / Ultralight — reading pages 4-19")
            raw = read_ntag(rfid)
        else:
            print("Mode : Unknown card type — no NDEF attempt")
            rfid.halt()

        text = _decode_ndef_text(raw) if raw else None

        if text:
            print("Text : %s" % text)
        elif raw:
            print("Text : (no NDEF text found)")
            hexdump(raw, "data")
        print()

        time.sleep_ms(150)


main()
