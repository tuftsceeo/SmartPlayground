"""
NFC Reader — Tag scanning and command extraction
==================================================
Wraps PN532 driver with NDEF text decoding,
raw-bytes fallback, gesture tag detection,
and Splat Companion (SC:) tag passthrough.

Supports two-phase reading: detect tag presence first,
then read data (allows animation during the slow read).

Gesture tags: If block 4 of a MIFARE Classic tag starts
with b'G:', it's a gesture tag. The reader loads the centroid
into the GestureEngine and returns "gesture:<name>" as the command.

SC tags: If NDEF text starts with "sc:", it's a Splat Companion
tag. The full text (e.g. "sc:b4:3a:45:86:1c:8c") is returned
as the command — the caller handles MAC parsing.

Usage:
    from nfc_reader import NfcReader

    reader = NfcReader(nfc, commands)
    reader.gesture_engine = ge  # optional: enable gesture tag support

    cmd, uid = reader.read_command(
        on_detect=my_start_fn,
        on_progress=my_frame_fn,
        on_complete=my_done_fn,
    )
    # cmd might be "gesture:triangle" for gesture tags
    # cmd might be "sc:b4:3a:45:86:1c:8c" for SC tags
"""

import sys
import time
from pn532 import MIFARE_AUTH_A, MIFARE_AUTH_B

COMMON_KEYS = [
    b'\xFF\xFF\xFF\xFF\xFF\xFF',
    b'\xD3\xF7\xD3\xF7\xD3\xF7',
    b'\xA0\xA1\xA2\xA3\xA4\xA5',
    b'\xB0\xB1\xB2\xB3\xB4\xB5',
    b'\x00\x00\x00\x00\x00\x00',
]

GESTURE_MARKER = b'G:'
SC_PREFIX = "sc:"


class NfcReader:
    def __init__(self, nfc, commands):
        """
        Args:
            nfc: PN532 driver instance
            commands: set of all valid command strings to recognize
        """
        self.nfc = nfc
        self.commands = commands
        self.gesture_engine = None  # set externally to enable gesture tags

    def detect_tag(self, timeout=250):
        """
        Quick check for tag presence. Returns (uid_hex, sak) or (None, None).
        Does NOT read NDEF data.
        """
        tag = self.nfc.read_passive_target(timeout=timeout)
        if tag is None:
            return None, None
        return tag['uid_hex'], tag['sak']

    def read_command(self, timeout=250, on_detect=None, on_progress=None, on_complete=None):
        """
        Scan for a tag and try to extract a command string.

        Recognition order:
          1. Gesture tags (block 4 starts with "G:")
          2. SC tags (NDEF text starts with "sc:")
          3. Known commands from self.commands
          4. Raw bytes fallback search

        Returns:
            (command, uid_hex) if tag found.
            command is a string from self.commands, "gesture:<name>",
            "sc:<mac>", or None if unrecognized.
            uid_hex is None if no tag detected.
        """
        # Phase 1: Detect tag presence (fast)
        tag = self.nfc.read_passive_target(timeout=timeout)
        if tag is None:
            return None, None

        sak = tag['sak']
        uid_hex = tag['uid_hex']

        # Notify: tag detected
        if on_detect:
            on_detect(uid_hex, sak)

        # Phase 2: Read NDEF data (slow — animate during this)
        ndef_data = bytearray()
        try:
            if sak in (0x08, 0x18):
                ndef_data = self._read_mifare_classic(tag, on_progress)
            else:
                ndef_data = self._read_ntag(on_progress)
        except Exception as e:
            sys.print_exception(e)

        # ── Check for gesture tag ──
        if (self.gesture_engine and sak in (0x08, 0x18)
                and len(ndef_data) >= 16
                and ndef_data[0:2] == GESTURE_MARKER):
            gesture = self.gesture_engine.read_gesture_tag(self.nfc, tag)
            if gesture:
                self.gesture_engine.load_gesture(gesture['name'], gesture['centroid'])
                command = "gesture:%s" % gesture['name']
                print("  [Gesture tag: '%s' loaded]" % gesture['name'])
                if on_complete:
                    on_complete(command)
                return command, uid_hex
            else:
                print("  [Gesture tag detected but read failed]")
                if on_complete:
                    on_complete(None)
                return None, uid_hex

        # ── Decode NDEF text ──
        text = _decode_ndef_text(ndef_data)

        # ── Check for SC tag ──
        if text and text.startswith(SC_PREFIX) and len(text) > len(SC_PREFIX):
            command = text  # pass through full "sc:b4:3a:45:86:1c:8c"
            print("  [SC tag: %s]" % text)
            if on_complete:
                on_complete(command)
            return command, uid_hex

        # ── Standard command lookup ──
        command = None
        if text and text in self.commands:
            command = text
        else:
            # Also check raw bytes for known commands
            command = self._find_in_raw(ndef_data)

        # Notify: read complete
        if on_complete:
            on_complete(command)

        return command, uid_hex

    # ── MIFARE Classic reading ──

    def _read_mifare_classic(self, tag, on_progress=None):
        ndef_data = bytearray()
        frame = 0
        for sector in (1, 2):
            first_block = sector * 4
            authed = False
            for key in COMMON_KEYS:
                for key_type in [MIFARE_AUTH_A, MIFARE_AUTH_B]:
                    if on_progress:
                        on_progress(frame); frame += 1

                    resel = self.nfc.read_passive_target(timeout=150)
                    if resel is None:
                        continue
                    if self.nfc.mifare_auth_block(resel['uid'], first_block, key, key_type):
                        for blk in range(first_block, first_block + 3):
                            if on_progress:
                                on_progress(frame); frame += 1
                            try:
                                ndef_data.extend(self.nfc.mifare_read_block(blk))
                            except Exception:
                                ndef_data.extend(b'\x00' * 16)
                        authed = True
                        break
                if authed:
                    break
            if not authed:
                ndef_data.extend(b'\x00' * 48)
        return ndef_data

    # ── NTAG / Ultralight reading ──

    def _read_ntag(self, on_progress=None):
        ndef_data = bytearray()
        frame = 0
        for page in range(4, 20):
            if on_progress:
                on_progress(frame); frame += 1
            try:
                ndef_data.extend(self.nfc.ntag_read_page(page))
            except Exception:
                break
        return ndef_data

    # ── Raw bytes fallback ──

    def _find_in_raw(self, data):
        if not data:
            return None
        try:
            raw_str = bytes(data).decode('ascii', 'replace').lower()
        except Exception:
            return None

        # Check for SC prefix in raw data too
        sc_idx = raw_str.find(SC_PREFIX)
        if sc_idx >= 0:
            # Try to extract the full SC:MAC string
            # MAC is 17 chars: AA:BB:CC:DD:EE:FF
            sc_end = sc_idx + len(SC_PREFIX) + 17
            if sc_end <= len(raw_str):
                candidate = raw_str[sc_idx:sc_end]
                # Validate it looks like a MAC
                parts = candidate[len(SC_PREFIX):].split(':')
                if len(parts) == 6 and all(len(p) == 2 for p in parts):
                    return candidate

        for cmd in self.commands:
            if cmd in raw_str:
                return cmd
        return None


# ─────────────────────────────────────────────
# NDEF TEXT DECODE (module-level)
# ─────────────────────────────────────────────

def _decode_ndef_text(data):
    """Parse NDEF TLV data and extract text or URI payload as lowercase string."""
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
                flags = ndef[0]; type_len = ndef[1]
                sr = flags & 0x10
                if sr:
                    pl = ndef[2]; ho = 3
                else:
                    if len(ndef) < 6: break
                    pl = (ndef[2] << 24) | (ndef[3] << 16) | (ndef[4] << 8) | ndef[5]
                    ho = 6
                rec_type = ndef[ho:ho + type_len]
                payload = ndef[ho + type_len:ho + type_len + pl]
                if bytes(rec_type) == b'T' and len(payload) > 1:
                    lang_len = payload[0] & 0x3F
                    return bytes(payload[1 + lang_len:]).decode('utf-8', 'replace').strip().lower()
                elif bytes(rec_type) == b'U' and len(payload) > 1:
                    prefixes = [
                        "", "http://www.", "https://www.", "http://",
                        "https://", "tel:", "mailto:",
                    ]
                    pre = prefixes[payload[0]] if payload[0] < len(prefixes) else ""
                    return (pre + bytes(payload[1:]).decode('utf-8', 'replace')).strip().lower()
            break
        else:
            if i + 1 < len(data):
                i += 2 + data[i + 1]
            else:
                break
            
    return None