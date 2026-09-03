"""Fake NfcReader — returns canned (cmd, uid) from sim_state.tap_nfc."""

import sim_state
from pn532 import MIFARE_AUTH_A, MIFARE_AUTH_B  # noqa: F401

COMMON_KEYS = [b"\xFF\xFF\xFF\xFF\xFF\xFF"]


def read_ndef_text(nfc, timeout=500, resel_timeout=150):
    return sim_state.consume_nfc()


def _decode_ndef_text(data):
    """Stub for the deprecated raw-MIFARE jumpin.py revisions that still
    import this. Unreachable in the sim: PN532.read_passive_target() always
    returns None, so callers of this (e.g. jumpin.py's _read_tag_text) never
    get past their own None check to reach it. Present only so `from
    nfc_reader import _decode_ndef_text` doesn't raise ImportError."""
    return None


class NfcReader:
    def __init__(self, nfc, commands):
        self.nfc = nfc
        self.commands = set(commands) if commands else set()

    def detect_tag(self, timeout=250):
        cmd, uid = sim_state.consume_nfc()
        if cmd is not None:
            return uid or "sim0001", 0x08
        return None, None

    def read_command(self, timeout=250, on_detect=None, on_progress=None, on_complete=None):
        cmd, uid = sim_state.consume_nfc()
        if cmd is None:
            return None, None
        if on_detect:
            on_detect()
        if on_complete:
            on_complete()
        return cmd, uid
