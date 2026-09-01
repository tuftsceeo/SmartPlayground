"""Browser stub for NFC reader — returns sim button-tapped tag commands."""

import time
from pn532 import MIFARE_AUTH_A, MIFARE_AUTH_B

COMMON_KEYS = [b"\xFF\xFF\xFF\xFF\xFF\xFF"]


def _decode_ndef_text(data):
    return None


def read_ndef_text(nfc, timeout=500, resel_timeout=150):
    from sim_bootstrap import input_state
    pending = input_state.get("nfc_pending")
    if pending:
        cmd, uid = pending
        input_state["nfc_pending"] = None
        return cmd, uid
    return None, None


class NfcReader:
    def __init__(self, nfc, commands):
        self.nfc = nfc
        self.commands = set(commands) if commands else set()

    def detect_tag(self, timeout=250):
        from sim_bootstrap import input_state
        pending = input_state.get("nfc_pending")
        if pending:
            return pending[1] or "sim", 0x08
        return None, None

    def read_command(self, timeout=250, on_detect=None, on_progress=None, on_complete=None):
        from sim_bootstrap import input_state
        pending = input_state.get("nfc_pending")
        if pending:
            cmd, uid = pending
            input_state["nfc_pending"] = None
            if on_detect:
                on_detect()
            if on_complete:
                on_complete()
            return cmd, uid
        return None, None
