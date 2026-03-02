"""
NFC Reader — Tag scanning and command extraction
==================================================
Wraps PN532 driver with NDEF text decoding and
raw-bytes fallback for command recognition.

Supports two-phase reading: detect tag presence first,
then read data (allows animation during the slow read).

Usage:
    from nfc_reader import NfcReader

    reader = NfcReader(nfc, commands)

    # Simple (no animation):
    cmd, uid = reader.read_command()

    # With animation callbacks:
    cmd, uid = reader.read_command(
        on_detect=my_start_fn,
        on_progress=my_frame_fn,
        on_complete=my_done_fn,
    )
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


class NfcReader:
    def __init__(self, nfc, commands):
        """
        Args:
            nfc: PN532 driver instance
            commands: set of all valid command strings to recognize
        """
        self.nfc = nfc
        self.commands = commands

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

        Args:
            timeout: ms to wait for tag detection
            on_detect: called when tag first detected, before data read.
                       signature: on_detect(uid_hex, sak)
            on_progress: called repeatedly during data read for animation.
                         signature: on_progress(frame)  frame=0,1,2,...
            on_complete: called after data read finishes (success or fail).
                         signature: on_complete(command_or_none)

        Returns:
            (command, uid_hex) if tag found.
            command is a string from self.commands, or None if unrecognized.
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

        # Parse command from data
        command = None
        text = _decode_ndef_text(ndef_data)
        if text and text in self.commands:
            command = text
        else:
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