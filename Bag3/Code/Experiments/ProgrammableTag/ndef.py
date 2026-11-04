"""
ndef.py - NDEF text record build/decode for NTAG-style tags.

build_ndef_text and decode_ndef_text are copied from
BroadcastBox/BBoxFirmware/card_writer.py (build_ndef_text,
_decode_ndef_text). Text records only; decode returns the text as written
(no lowercasing).
"""


def build_ndef_text(text):
    """Complete TLV (03 len record FE) holding one NDEF text record."""
    lang = b'en'
    payload = bytes([len(lang)]) + lang + text.encode('utf-8')
    flags = 0xD1  # MB|ME|SR, TNF=0x01 (well-known)
    record = bytes([flags, 1, len(payload)]) + b'T' + payload
    return bytes([0x03, len(record)]) + record + bytes([0xFE])


def decode_ndef_text(data):
    """Return the text of the first NDEF text record in a TLV area, or None."""
    i = 0
    while data and i < len(data):
        t = data[i]
        if t == 0x00:
            i += 1
            continue
        if t == 0xFE:
            return None
        if i + 1 >= len(data):
            return None
        if t != 0x03:
            i += 2 + data[i + 1]
            continue
        length = data[i + 1]
        off = i + 2
        ndef = data[off:off + length]
        if len(ndef) < 4 or not (ndef[0] & 0x10):
            return None
        type_len = ndef[1]
        pl = ndef[2]
        rec_type = ndef[3:3 + type_len]
        payload = ndef[3 + type_len:3 + type_len + pl]
        if bytes(rec_type) == b'T' and len(payload) > 1:
            lang_len = payload[0] & 0x3F
            return bytes(payload[1 + lang_len:]).decode('utf-8', 'replace')
        return None
    return None
