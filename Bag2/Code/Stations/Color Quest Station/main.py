"""
Color Quest Station — ESP32-C6 + WS1850S RFID reader
=====================================================
One of four identical nodes. Each reads its local tag and, on receiving
an ESP-NOW scan_request, unicasts its position and scanned color back to
the requesting wand. Supports MIFARE Classic 1K/4K and NTAG/Ultralight.

Deploy:
  - Copy ws1850s.py and espnow_manager.py to /lib/ on each board.
  - Edit config.json: set "position" to 0, 1, 2, or 3.
  - Flash main.py to the board root.

config.json keys:
  position  — 0..3, the physical slot this board occupies
  i2c_sda   — SDA GPIO (default 22, ESP32-C6)
  i2c_scl   — SCL GPIO (default 23, ESP32-C6)
  i2c_freq  — I2C frequency in Hz (default 100000)

ESP-NOW message types (received):
  scan_request  — wand asks for this station's current color

ESP-NOW message types (sent):
  color_station_reply — {"type": "color_station_reply",
                          "position": N, "color": "turnred"}
  If no tag is present the "color" field is null.
"""

import json
import time
from machine import Pin, SoftI2C

from ws1850s import WS1850S
from espnow_manager import ESPNowManager

# ─── Config ──────────────────────────────────────────────────────────────────

def _load_config():
    try:
        with open("config.json") as f:
            return json.load(f)
    except Exception as e:
        print("[config] Failed to load config.json: %s — using defaults" % e)
        return {}

_cfg = _load_config()

POSITION  = int(_cfg.get("position", 0))
I2C_SDA   = int(_cfg.get("i2c_sda", 22))
I2C_SCL   = int(_cfg.get("i2c_scl", 23))
I2C_FREQ  = int(_cfg.get("i2c_freq", 100_000))

# ─── NDEF reading ─────────────────────────────────────────────────────────────

_COMMON_KEYS = [
    b'\xFF\xFF\xFF\xFF\xFF\xFF',
    b'\xD3\xF7\xD3\xF7\xD3\xF7',
    b'\xA0\xA1\xA2\xA3\xA4\xA5',
    b'\xB0\xB1\xB2\xB3\xB4\xB5',
    b'\x00\x00\x00\x00\x00\x00',
]


def _decode_ndef_text(data):
    """Extract the text payload from NDEF TLV bytes. Returns lowercase str or None."""
    if not data or len(data) < 4:
        return None
    i = 0
    while i < len(data):
        t = data[i]
        if t == 0x00:
            i += 1
            continue
        if t == 0xFE:
            break
        if t == 0x03:
            if i + 1 >= len(data):
                break
            length = data[i + 1]
            off = i + 2
            if length == 0xFF:
                if i + 3 >= len(data):
                    break
                length = (data[i + 2] << 8) | data[i + 3]
                off = i + 4
            ndef = data[off:off + length]
            if len(ndef) > 3:
                flags    = ndef[0]
                type_len = ndef[1]
                sr       = flags & 0x10
                if sr:
                    pl  = ndef[2]
                    ho  = 3
                else:
                    if len(ndef) < 6:
                        break
                    pl = (ndef[2] << 24) | (ndef[3] << 16) | (ndef[4] << 8) | ndef[5]
                    ho = 6
                rec_type = ndef[ho:ho + type_len]
                payload  = ndef[ho + type_len:ho + type_len + pl]
                if bytes(rec_type) == b'T' and len(payload) > 1:
                    lang_len = payload[0] & 0x3F
                    return bytes(payload[1 + lang_len:]).decode('utf-8', 'replace').strip().lower()
            break
        else:
            if i + 1 < len(data):
                i += 2 + data[i + 1]
            else:
                break
    return None


def _detect_card(rfid):
    """
    Returns (uid_bytes, sak) or (None, None).

    Handles both single-cascade (4-byte UID, MIFARE Classic) and
    double-cascade (7-byte UID, NTAG / Ultralight) cards.

    When the level-1 SAK has bit 2 set (0x04) it means the card has
    more UID bytes; we run a level-2 anticollision (SEL=0x95) to
    complete selection before reading.
    """
    status, _ = rfid.request(WS1850S.PICC_REQIDL)
    if status != WS1850S.MI_OK:
        return None, None

    # Level-1 anticollision (SEL = 0x93)
    status, back = rfid.anticoll()
    if status != WS1850S.MI_OK or len(back) < 5:
        return None, None

    sak = rfid.select_tag(back)

    if not (sak & 0x04):
        # Single cascade complete — 4-byte UID
        return bytes(back[:4]), sak

    # Double cascade — first 3 real UID bytes are back[1:4] (back[0] = CT 0x88)
    uid_part1 = bytes(back[1:4])

    # Level-2 anticollision (SEL = 0x95)
    rfid._w(rfid.BitFramingReg, 0x00)
    st2, back2, _ = rfid._to_card(rfid.PCD_TRANSCEIVE, [0x95, 0x20])
    if st2 != rfid.MI_OK or len(back2) < 5:
        return None, None

    # Level-2 select
    sel2 = [0x95, 0x70] + list(back2[:5])
    sel2 += rfid._calc_crc(sel2)
    st3, back3, _ = rfid._to_card(rfid.PCD_TRANSCEIVE, sel2)
    if st3 != rfid.MI_OK or not back3:
        return None, None

    sak2    = back3[0]
    uid     = uid_part1 + bytes(back2[:4])   # 3 + 4 = 7-byte UID
    return uid, sak2


def _read_mifare_classic(rfid, uid):
    """Auth sectors 1 & 2, read blocks 4-6 and 8-10."""
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


def _read_ntag(rfid):
    """Read user pages 4-19 without auth (NTAG / Ultralight)."""
    nd = bytearray()
    for page in range(4, 20, 4):
        st, data = rfid.read_block(page)
        if st == WS1850S.MI_OK and data:
            nd.extend(data)
        else:
            break
    rfid.halt()
    return nd


def read_tag_ndef(rfid):
    """
    Detect card type via SAK, read NDEF text from MIFARE Classic or NTAG/Ultralight.
    Returns the decoded lowercase string, or None if no tag / unreadable.
    """
    uid, sak = _detect_card(rfid)
    if uid is None:
        return None

    if sak in (0x08, 0x18):
        nd = _read_mifare_classic(rfid, uid)
    else:
        nd = _read_ntag(rfid)

    return _decode_ndef_text(nd)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 50)
    print("  Color Quest Station  (position %d)" % POSITION)
    print("  SDA=%d  SCL=%d  freq=%d" % (I2C_SDA, I2C_SCL, I2C_FREQ))
    print("=" * 50)

    i2c  = SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=I2C_FREQ)
    rfid = WS1850S(i2c)
    print("  WS1850S version: 0x%02X" % rfid.version())

    mgr = ESPNowManager()
    mgr.init()

    print("  Ready — waiting for scan_request\n")

    while True:
        try:
            msg_type, data, mac_str = mgr.poll(timeout_ms=50)
        except Exception as e:
            print("  [poll err] %s" % e)
            time.sleep_ms(100)
            continue

        if msg_type != "scan_request" or not mac_str:
            continue

        print("— scan_request from %s —" % mac_str)

        color = read_tag_ndef(rfid)
        print("  tag: %s" % (color or "none"))

        reply = {
            "type":     "color_station_reply",
            "position": POSITION,
            "color":    color,
        }

        mgr.add_peer(mac_str)
        ok = mgr.send_to(mac_str, reply)
        print("  %s reply to %s: pos=%d color=%s\n" % (
            "Sent" if ok else "SEND FAILED",
            mac_str, POSITION, color
        ))


if __name__ == "__main__":
    main()
