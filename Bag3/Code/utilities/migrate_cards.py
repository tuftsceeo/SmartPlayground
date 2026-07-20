"""
Migrate NFC cards: old NDEF text  ->  new 4-byte opcode (page/block 5)
=====================================================================
Board: Seeed XIAO ESP32-C6 (Bag3 wand)

Reads the old NDEF-text card format (what the wand used before opcodes),
maps the text to a command name, and rewrites the card in place as a
compact opcode (see lib/opcodes.py). Tap each card once:

  • already-migrated cards (valid opcode on page 5)  -> skipped (blue)
  • old NDEF card with a known command               -> rewritten (green)
  • unreadable / unknown text                         -> left alone (red)

Idempotent: re-tapping a migrated card just skips it, so you can sweep a
whole pile without tracking which you've done.

Requires on the device: ws1850s.py, opcodes.py, and writetoNFCcards.py
(this reuses that file's WS1850S adapter + LED/buzzer feedback).

Run from the REPL:   import migrate_cards; migrate_cards.main()
"""

import machine
import time

from writetoNFCcards import (
    NfcWriter, LEDAnimator, Beeper, COMMON_KEYS,
    MIFARE_AUTH_A, MIFARE_AUTH_B,
    I2C_SDA, I2C_SCL, NEOPIXEL, BUZZER, NFC_ADDR, NUM_LEDS,
)
from opcodes import encode, decode, CARD_PAGE

# Old tag texts that were renamed under the opcode scheme. Everything else
# kept its name (the old NDEF text WAS the command name), so no entry needed.
ALIASES = {
    "notec": "note_c", "noted": "note_d", "notee": "note_e",
    "notef": "note_f", "noteg": "note_g", "notea": "note_a",
    "noteb": "note_b",
}


# ─────────────────────────────────────────────
# OLD FORMAT: read NDEF text off a card
# ─────────────────────────────────────────────
def _read_ndef_bytes(nfc, tag):
    """Read the raw NDEF region: pages 4-19 (NTAG) or sectors 1-2 (Classic)."""
    nd = bytearray()
    if tag['is_classic']:
        for sector in (1, 2):
            fb = sector * 4
            authed = False
            for key in COMMON_KEYS:
                for kt in (MIFARE_AUTH_A, MIFARE_AUTH_B):
                    resel = nfc.detect_tag(timeout=150)
                    if resel is None:
                        continue
                    if nfc.mifare_auth(tag['uid'], fb, key, kt):
                        for blk in range(fb, fb + 3):
                            try:
                                nd.extend(nfc.mifare_read(blk))
                            except Exception:
                                nd.extend(b'\x00' * 16)
                        authed = True
                        break
                if authed:
                    break
            if not authed:
                nd.extend(b'\x00' * 48)
    else:
        for page in range(4, 20):
            try:
                nd.extend(nfc.ntag_read_page(page))
            except Exception:
                break
    return nd


def _decode_ndef_text(data):
    """Parse an NDEF TLV and return the Text/URI payload, lowercased."""
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
                flags = ndef[0]; type_len = ndef[1]
                sr = flags & 0x10
                if sr:
                    pl = ndef[2]; ho = 3
                else:
                    if len(ndef) < 6:
                        break
                    pl = (ndef[2] << 24) | (ndef[3] << 16) | (ndef[4] << 8) | ndef[5]
                    ho = 6
                rec_type = ndef[ho:ho + type_len]
                payload = ndef[ho + type_len:ho + type_len + pl]
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


# ─────────────────────────────────────────────
# NEW FORMAT: read / write the opcode at page 5
# ─────────────────────────────────────────────
def _read_page5(nfc, tag):
    """Return the 4 bytes at page/block 5, or None."""
    try:
        if tag['is_ntag']:
            return bytes(nfc.ntag_read_page(CARD_PAGE)[:4])
        # Classic: re-select, auth the sector, read the block.
        if nfc.detect_tag(timeout=300) is None:
            return None
        for key in COMMON_KEYS:
            for kt in (MIFARE_AUTH_A, MIFARE_AUTH_B):
                if nfc.mifare_auth(tag['uid'], CARD_PAGE, key, kt):
                    return bytes(nfc.mifare_read(CARD_PAGE)[:4])
        return None
    except Exception:
        return None


def _write_page5(nfc, tag, payload):
    """Write the 4-byte opcode to page/block 5. Returns True on success."""
    try:
        if tag['is_ntag']:
            nfc.ntag_write_page(CARD_PAGE, payload)
            return True
        # Classic: re-select, auth, 16-byte block write (opcode + zero pad).
        if nfc.detect_tag(timeout=300) is None:
            return False
        authed = False
        for key in COMMON_KEYS:
            for kt in (MIFARE_AUTH_A, MIFARE_AUTH_B):
                if nfc.mifare_auth(tag['uid'], CARD_PAGE, key, kt):
                    authed = True
                    break
            if authed:
                break
        if not authed:
            print("  auth failed — cannot write")
            return False
        block16 = bytearray(16)
        block16[0:4] = payload
        nfc.mifare_write(CARD_PAGE, block16)
        return True
    except Exception as e:
        print("  write error: %s" % e)
        return False


# ─────────────────────────────────────────────
# MIGRATE ONE CARD
# ─────────────────────────────────────────────
def migrate_card(nfc, tag):
    """Returns 'skip', 'ok', 'unknown', or 'fail'."""
    # Already in the new format?
    existing = _read_page5(nfc, tag)
    already = decode(existing) if existing else None
    if already is not None:
        print("  already opcode: \"%s\" — skipping" % already)
        return "skip"

    # Read the old NDEF text (must happen before we overwrite block 5).
    text = _decode_ndef_text(_read_ndef_bytes(nfc, tag))
    if not text:
        print("  no readable NDEF text — cannot migrate")
        return "fail"

    name = ALIASES.get(text, text)
    payload = encode(name)
    if payload is None:
        print("  \"%s\" is not a known command — leaving as-is" % text)
        return "unknown"

    if not _write_page5(nfc, tag, payload):
        return "fail"

    # Verify by reading page 5 back and decoding it.
    rb = _read_page5(nfc, tag)
    if rb is not None and decode(rb) == name:
        extra = "" if name == text else " (renamed from \"%s\")" % text
        print("  migrated \"%s\" -> opcode + verified%s" % (name, extra))
        return "ok"
    print("  verify failed — card may not have persisted")
    return "fail"


# ─────────────────────────────────────────────
# MAIN — sweep loop
# ─────────────────────────────────────────────
def main():
    print("\n" + "*" * 55)
    print("  NFC Card Migration — NDEF text  ->  opcode")
    print("  Tap each old card once. Ctrl+C to stop.")
    print("*" * 55 + "\n")

    i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=400_000)
    led = LEDAnimator(NEOPIXEL, NUM_LEDS)
    beep = Beeper(BUZZER)
    led.clear()

    nfc = NfcWriter(i2c, NFC_ADDR)
    nfc.init()
    print("  WS1850S ready — waiting for cards\n")

    counts = {"ok": 0, "skip": 0, "unknown": 0, "fail": 0}
    last_uid = None
    frame = 0

    try:
        while True:
            tag = nfc.detect_tag(timeout=200)

            if tag is None:
                if last_uid is not None:
                    last_uid = None
                    led.clear()
                led.idle_pulse(frame)
                frame += 1
                time.sleep_ms(40)
                continue

            # Debounce: one action per physical placement.
            if tag['uid_hex'] == last_uid:
                time.sleep_ms(100)
                continue
            last_uid = tag['uid_hex']

            print("  Card %s (%s)" % (tag['uid_hex'], tag['tag_type']))
            beep.click()
            led.fill((0, 0, 20))  # blue = working

            result = migrate_card(nfc, tag)
            counts[result] = counts.get(result, 0) + 1

            if result == "ok":
                led.success(); beep.success()
            elif result == "skip":
                led.fill((0, 0, 40)); time.sleep_ms(400)   # blue = already done
            else:  # unknown / fail
                led.failure(); beep.fail()

            print("  totals: %d migrated, %d skipped, %d unknown, %d failed\n"
                  % (counts["ok"], counts["skip"], counts["unknown"], counts["fail"]))
            led.clear()

    except KeyboardInterrupt:
        led.clear()
        print("\n  Done. %d migrated, %d skipped, %d unknown, %d failed."
              % (counts["ok"], counts["skip"], counts["unknown"], counts["fail"]))


if __name__ == "__main__":
    main()
