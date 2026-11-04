"""Bare LVGL stub for host imports.

Only present so dial_ui.py imports cleanly under CPython. The one thing
evaluated at import time is a default argument (lv.ALIGN.TOP_MID in
_label()); everything else here is touched only inside methods the host
devtests never call, and is filled in only far enough to satisfy attribute
lookups, not behaviour.
"""

font_montserrat_14 = None
font_montserrat_16 = None
font_montserrat_24 = None


class SYMBOL:
    RIGHT = "right"
    LEFT = "left"
    SD_CARD = "sd_card"
    WIFI = "wifi"
    OK = "ok"
    CLOSE = "close"
    WARNING = "warning"
    USB = "usb"
    REFRESH = "refresh"
    STOP = "stop"
    BATTERY_FULL = "battery_full"
    EYE_OPEN = "eye_open"


class ALIGN:
    TOP_MID = "top_mid"
    TOP_LEFT = "top_left"
    CENTER = "center"


class TEXT_ALIGN:
    CENTER = "center"
    LEFT = "left"


class EVENT:
    CLICKED = "clicked"


class PART:
    SELECTED = "selected"


class ANIM:
    OFF = "off"


class _RollerMode:
    NORMAL = "normal"
    INFINITE = "infinite"


class roller:
    MODE = _RollerMode


def color_hex(v):
    return v


class _Flag:
    CLICKABLE = "clickable"
    HIDDEN = "hidden"


class obj:
    FLAG = _Flag

    def __init__(self, *a, **k):
        pass
