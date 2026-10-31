"""NFC tap target: one component at a fixed spot, reparented onto screens 5 and 9."""

import lvgl as lv

import ds_tokens as t
import ui_kit as k

X = 528
Y = 150
W = 240
H = 180

_COLORS = {"waiting": t.PINK, "writing": t.PURPLE, "done": t.TEAL, "error": t.DANGER[0], "idle": t.MUTED_2}
_CAPTION = {"waiting": "Tap a tag here", "writing": "Writing...", "done": "Done", "error": "", "idle": ""}

_box = None
_waves = None
_tick = None
_cap = None


def attach(parent):
    """Move the target onto `parent` (built on first use)."""
    global _box, _waves, _tick, _cap
    if _box is None:
        _box = k.box(parent, X, Y, W, H, t.SURFACE, 20, t.PURPLE, 4)
        _waves = k.icon(_box, "nfc_waves_64", t.PURPLE, align=lv.ALIGN.CENTER, y=-20)
        _tick = k.icon(_box, "check_56", t.TEAL, align=lv.ALIGN.CENTER, y=-20)
        k.show_hide(_tick, False)
        _cap = k.slot(_box, 12, H - 44, W - 32, t.INK_3, k.F14, "", lv.ALIGN.TOP_MID)
        _cap.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    else:
        _box.set_parent(parent)
        _box.set_pos(X, Y)
    return _box


def state(name, caption=None):
    col = _COLORS[name]
    k.sty(_box, "border", col)
    _waves.set_style_image_recolor(k.c(col), 0)
    k.show_hide(_waves, name != "done")
    k.show_hide(_tick, name == "done")
    k.st(_cap, caption if caption is not None else _CAPTION[name])
