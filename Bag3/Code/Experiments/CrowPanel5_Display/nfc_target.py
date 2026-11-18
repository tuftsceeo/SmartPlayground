"""NFC tap target: one component at a fixed spot, reparented onto screens 5 and 9.

Drawn as a sign-board arrow whose tip touches the right edge, pointing at the reader mounted
beside the screen. The shape is two alpha maps (icons/tag_arrow_fill, tag_arrow_edge), tinted
per state like the other icons."""

import lvgl as lv

import ds_tokens as t
import ui_kit as k

X = 546
Y = 150
W = 254
H = 180
BODY_W = 164  # the arrow's body (content sits here); the head runs from BODY_W to W

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
_fill = None
_edge = None
_icons = {}
_cap = None


def attach(parent):
    """Move the target onto `parent` (built on first use)."""
    global _box, _fill, _edge, _cap
    if _box is None:
        _box = k.plain(lv.obj(parent))
        _box.set_pos(X, Y)
        _box.set_size(W, H)
        _box.set_style_bg_opa(lv.OPA.TRANSP, 0)
        _box.remove_flag(lv.obj.FLAG.CLICKABLE)
        _fill = k.icon(_box, "tag_arrow_fill", t.PINK_50)
        _edge = k.icon(_box, "tag_arrow_edge", t.PINK)
        grp = k.plain(lv.obj(_box))
        grp.set_size(BODY_W - 16, lv.SIZE_CONTENT)
        grp.set_style_bg_opa(lv.OPA.TRANSP, 0)
        grp.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        grp.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        grp.set_style_pad_row(8, 0)
        grp.align(lv.ALIGN.LEFT_MID, 8, 0)
        for key, name in (("waves", "nfc_waves_56"), ("tick", "check_56"), ("cross", "cross_56")):
            _icons[key] = k.icon(grp, name, t.PINK_DARK)
        _cap = k.text(grp, "", t.PINK_DARK, k.F_BODY)
    else:
        _box.set_parent(parent)
        _box.set_pos(X, Y)
    return _box


def state(name, caption=None):
    border, bg, fg, ic, cap = _LOOK[name]
    _edge.set_style_image_recolor(k.c(border), 0)
    _fill.set_style_image_recolor(k.c(bg), 0)
    for key, im in _icons.items():
        k.show_hide(im, key == ic)
        if key == ic:
            im.set_style_image_recolor(k.c(fg), 0)
    k.sty(_cap, "text", fg)
    k.st(_cap, caption if caption is not None else cap)
