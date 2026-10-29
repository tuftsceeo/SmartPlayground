"""
NFC Reader — fast opcode tag scanning
=====================================
Every wand card stores a 4-byte opcode at page/block 5 (see opcodes.py).
Reading a card is therefore a single page read (NTAG) or one auth + one
block read (MIFARE Classic) — no NDEF TLV parsing, no multi-page scan.
The decoded command is a plain string ("colorquest", "note_c", "stop", …),
exactly the vocabulary the games already use.

Supported tag types:
  • MIFARE Classic 1K (SAK 0x08 / 0x18)  — auth block 5, read block 5
  • NTAG / MIFARE Ultralight             — unauthenticated read of page 5

Usage:
    # For game code that only needs the command + UID of any tag:
    from nfc_reader import read_tag_command
    cmd, uid = read_tag_command(nfc)

    # For the main command-dispatch loop:
    from nfc_reader import NfcReader
    reader = NfcReader(nfc, commands)
    cmd, uid = reader.read_command(
        on_detect=my_start_fn,
        on_progress=my_frame_fn,
        on_complete=my_done_fn,
    )
"""

import sys
import time
from pn532 import MIFARE_AUTH_A, MIFARE_AUTH_B
from opcodes import decode, CARD_PAGE

# All cards are (re)written with the factory key, but a blank/re-keyed
# MIFARE Classic card can carry other common keys — try them in order.
COMMON_KEYS = [
    b'\xFF\xFF\xFF\xFF\xFF\xFF',
    b'\xD3\xF7\xD3\xF7\xD3\xF7',
    b'\xA0\xA1\xA2\xA3\xA4\xA5',
    b'\xB0\xB1\xB2\xB3\xB4\xB5',
    b'\x00\x00\x00\x00\x00\x00',
]

# Number of synthetic frames to emit through on_progress so callers that
# animate during the (now near-instant) read still get a brief scan effect.
_SCAN_FRAMES = 6


# ─────────────────────────────────────────────
# LOW-LEVEL: read the 4 opcode bytes off page 5
# ─────────────────────────────────────────────

def _read_opcode_bytes(nfc, sak, resel_timeout=150):
    """Return the 4 opcode bytes at page/block 5, or None on failure.

    NTAG / Ultralight: one unauthenticated page read.
    MIFARE Classic:    auth the sector holding block 5, then read it.
    """
    if sak in (0x08, 0x18):
        # MIFARE Classic — must auth before reading. Re-select before each
        # auth attempt: the PN532 needs the card selected, and a failed
        # auth drops it.
        for key in COMMON_KEYS:
            for kt in (MIFARE_AUTH_A, MIFARE_AUTH_B):
                resel = nfc.read_passive_target(timeout=resel_timeout)
                if resel is None:
                    continue
                if nfc.mifare_auth_block(resel['uid'], CARD_PAGE, key, kt):
                    try:
                        return bytes(nfc.mifare_read_block(CARD_PAGE)[:4])
                    except Exception:
                        return None
        return None
    else:
        # NTAG / Ultralight — no auth needed.
        try:
            return bytes(nfc.ntag_read_page(CARD_PAGE)[:4])
        except Exception:
            return None


# ─────────────────────────────────────────────
# TOP-LEVEL HELPER: read any supported tag type
# ─────────────────────────────────────────────

def read_tag_command(nfc, timeout=500, resel_timeout=150):
    """Detect a tag and decode its opcode. Returns (command, uid_hex).

    command is a known command string, or None if the tag carries no valid
    opcode (blank, non-opcode, or misread). uid_hex is None only when no tag
    was detected within `timeout`.
    """
    tag = nfc.read_passive_target(timeout=timeout)
    if tag is None:
        return None, None

    uid_hex = tag['uid_hex']
    data = None
    try:
        data = _read_opcode_bytes(nfc, tag['sak'], resel_timeout)
    except Exception as e:
        sys.print_exception(e)

    return decode(data), uid_hex


# Backward-compatible alias for callers that still import the old name.
read_ndef_text = read_tag_command


# ─────────────────────────────────────────────
# NFC READER CLASS (command dispatch)
# ─────────────────────────────────────────────

class NfcReader:
    def __init__(self, nfc, commands):
        """
        Args:
            nfc: PN532 driver instance
            commands: set of valid command strings this caller recognizes.
                      A decoded command outside this set is reported as None
                      (same contract as before).
        """
        self.nfc = nfc
        self.commands = commands

    def detect_tag(self, timeout=250):
        """
        Quick check for tag presence. Returns (uid_hex, sak) or (None, None).
        Does NOT read the opcode.
        """
        tag = self.nfc.read_passive_target(timeout=timeout)
        if tag is None:
            return None, None
        return tag['uid_hex'], tag['sak']

    def read_command(self, timeout=250, on_detect=None, on_progress=None, on_complete=None):
        """
        Scan for a tag and decode its command.

        Returns:
            (command, uid_hex) if a tag is found; command is a string from
            self.commands, or None if the tag is unrecognized.
            (None, None) if no tag detected.
        """
        # Phase 1: detect tag presence (fast)
        tag = self.nfc.read_passive_target(timeout=timeout)
        if tag is None:
            return None, None

        sak = tag['sak']
        uid_hex = tag['uid_hex']

        if on_detect:
            on_detect(uid_hex, sak)

        # Phase 2: read the opcode. A quick synthetic animation keeps the
        # scan-feedback callbacks meaningful now that the read is instant.
        if on_progress:
            for f in range(_SCAN_FRAMES):
                on_progress(f)
                time.sleep_ms(15)

        data = None
        try:
            data = _read_opcode_bytes(self.nfc, sak)
        except Exception as e:
            sys.print_exception(e)

        name = decode(data)
        command = name if (name and name in self.commands) else None

        if on_complete:
            on_complete(command)

        return command, uid_hex
