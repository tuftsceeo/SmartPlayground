"""
eum_classify.py -- message classification on the modem
======================================================
Port of the poll() classification in
Bag3/Code/BroadcastCode/MockWand/lib/espnow_manager.py. A new message type
added there must be added here and to CODE_NAMES in eum_proto.py.

Pure Python so it can be tested under CPython.
"""

import json

from eum_proto import (
    C_DROP, C_RAW_BYTES, C_RAW_JSON, C_COLORS, C_STOP, C_BATTERY,
    C_SPLAT_CONFIG, C_SCORE, C_SCAN_REQUEST, C_START_GAME, C_FIND_DEVICE,
    C_STATUS_POLL, C_STATUS_REPORT,
)

_DICT_CODES = {
    "stop": C_STOP,
    "splat_config": C_SPLAT_CONFIG,
    "score": C_SCORE,
    "scan_request": C_SCAN_REQUEST,
    "status_poll": C_STATUS_POLL,
    "status_report": C_STATUS_REPORT,
}


def classify(msg, own_mac_hex):
    """Return the classification code for one received payload.

    own_mac_hex: this modem's MAC as 12 uppercase hex digits, no colons.
    find_device aimed at another MAC returns C_DROP.
    """
    try:
        data = json.loads(msg)
    except (ValueError, UnicodeError):
        return C_RAW_BYTES

    if isinstance(data, list):
        if "stop" in data:
            return C_STOP
        if "battery" in data:
            return C_BATTERY
        return C_COLORS

    if isinstance(data, dict):
        mt = data.get("type")
        code = _DICT_CODES.get(mt)
        if code is not None:
            return code
        if mt == "start_game":
            name = data.get("name")
            if isinstance(name, str) and name:
                return C_START_GAME
            return C_RAW_JSON
        if mt == "find_device":
            target = data.get("mac")
            if target is None:
                return C_FIND_DEVICE
            if not isinstance(target, str):
                return C_DROP
            if target.replace(":", "").upper() == own_mac_hex:
                return C_FIND_DEVICE
            return C_DROP
        return C_RAW_JSON

    return C_RAW_JSON
