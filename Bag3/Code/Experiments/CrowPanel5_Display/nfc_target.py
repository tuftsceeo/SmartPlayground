"""NFC tap target: one component at a fixed spot, reparented onto screens 5 and 9."""

import lvgl as lv

import ds_tokens as t
import ui_kit as k

X = 528
Y = 150
W = 240
H = 180

# state -> (border, background, foreground, icon, caption)
_LOOK = {
    "waiting": (t.PINK, t.PINK_50, t.PINK_DARK, "waves", "Tap tag here"),
    "writing": (t.PURPLE, t.PURPLE_50, t.PURPLE, "waves", "Writing..."),
    "done": (t.TEAL, t.TEAL_50, t.TEAL_DARK, "tick", "Done"),
    "error": (t.DANGER[0], t.DANGER[1], t.DANGER[0], "cross", "Try again"),
    "idle": (t.BORDER, t.BG, t.IDLE_FG, "waves", "Not in use"),
    "read_wait": (t.PURPLE, t.PURPLE_50, t.PURPLE, "waves", "Tap tag to read"),
    "read": (t.TEAL, t.TEAL_50, t.TEAL_DARK, "tick", "Read"),
}

_box = None
_icons = {}
_cap = None


def attach(parent):
    """Move the target onto `parent` (built on first use)."""
    global _box, _cap
    if _box is None:
        _box = k.box(parent, X, Y, W, H, t.PINK_50, 16, t.PINK, 2)
        grp = k.plain(lv.obj(_box))
        grp.set_size(W - 16, lv.SIZE_CONTENT)
        grp.set_style_bg_opa(lv.OPA.TRANSP, 0)
        grp.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        grp.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        grp.set_style_pad_row(8, 0)
        grp.center()
        for key, name in (("waves", "nfc_waves_56"), ("tick", "check_56"), ("cross", "cross_56")):
            _icons[key] = k.icon(grp, name, t.PINK_DARK)
        _cap = k.text(grp, "", t.PINK_DARK, k.F_BODY)
    else:
        _box.set_parent(parent)
        _box.set_pos(X, Y)
    return _box


def state(name, caption=None):
    border, bg, fg, ic, cap = _LOOK[name]
    k.sty(_box, "border", border)
    k.sty(_box, "bg", bg)
    for key, im in _icons.items():
        k.show_hide(im, key == ic)
        if key == ic:
            im.set_style_image_recolor(k.c(fg), 0)
    k.sty(_cap, "text", fg)
    k.st(_cap, caption if caption is not None else cap)
