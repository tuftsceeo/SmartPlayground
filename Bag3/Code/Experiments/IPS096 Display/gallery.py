"""Design-system component gallery for the 160x80 landscape screen.

Each page is built on its own screen and loaded by show(index).
"""

import lvgl as lv

import display_lvgl
import ds_tokens as t

W = 160
H = 80

F12 = lv.font_montserrat_12
F14 = lv.font_montserrat_14
F16 = lv.font_montserrat_16


def _c(hexval):
    return display_lvgl.color(hexval)


def _screen():
    scr = lv.obj()
    scr.set_style_bg_color(_c(t.BG), 0)
    scr.set_style_pad_all(0, 0)
    scr.remove_flag(lv.obj.FLAG.SCROLLABLE)
    return scr


def _box(parent, x, y, w, h, bg, radius, border=None, border_w=1):
    o = lv.obj(parent)
    o.set_pos(x, y)
    o.set_size(w, h)
    o.set_style_pad_all(0, 0)
    o.set_style_radius(radius, 0)
    o.set_style_bg_color(_c(bg), 0)
    o.set_style_bg_opa(lv.OPA.COVER, 0)
    o.set_style_shadow_width(0, 0)
    if border is None:
        o.set_style_border_width(0, 0)
    else:
        o.set_style_border_width(border_w, 0)
        o.set_style_border_color(_c(border), 0)
    o.remove_flag(lv.obj.FLAG.SCROLLABLE)
    return o


def _text(parent, text, color, font=F12, align=lv.ALIGN.CENTER, x=0, y=0):
    lb = lv.label(parent)
    lb.set_text(text)
    lb.set_style_text_color(_c(color), 0)
    lb.set_style_text_font(font, 0)
    lb.align(align, x, y)
    return lb


def _title(scr, n, name):
    _text(scr, f"{n}/{len(PAGES)} {name}", t.MUTED, F12, lv.ALIGN.TOP_LEFT, 4, 2)


def _buttons(scr):
    _box(scr, 6, 20, 70, 24, t.PINK, t.R_PILL)
    _text(scr, "Send", t.SURFACE, F14, lv.ALIGN.TOP_LEFT, 23, 24)
    _box(scr, 84, 20, 70, 24, t.TEAL, t.R_PILL)
    _text(scr, "Serve", t.SURFACE, F14, lv.ALIGN.TOP_LEFT, 99, 24)
    _box(scr, 6, 50, 70, 24, t.DISABLED, t.R_PILL)
    _text(scr, "Send", t.MUTED_2, F14, lv.ALIGN.TOP_LEFT, 23, 54)
    _box(scr, 84, 50, 70, 24, t.SURFACE, t.R_PILL, t.BORDER, 2)
    _text(scr, "Not yet", t.INK_3, F12, lv.ALIGN.TOP_LEFT, 96, 55)


def _chips(scr):
    x = 6
    for label, active in (("All", True), ("Sound", False), ("Light", False)):
        w = 12 + len(label) * 8
        if active:
            _box(scr, x, 22, w, 20, t.PINK_50, t.R_PILL, t.PINK, 1)
            _text(scr, label, t.PINK_DARK, F12, lv.ALIGN.TOP_LEFT, x + 6, 25)
        else:
            _box(scr, x, 22, w, 20, t.SURFACE, t.R_PILL, t.BORDER, 1)
            _text(scr, label, t.INK_3, F12, lv.ALIGN.TOP_LEFT, x + 6, 25)
        x += w + 4
    _box(scr, 6, 50, 70, 22, t.PURPLE, t.R_PILL)
    _text(scr, "Play", t.SURFACE, F12, lv.ALIGN.TOP_LEFT, 28, 54)
    _box(scr, 84, 50, 70, 22, t.PURPLE_50, t.R_PILL)
    _text(scr, "Code", t.PURPLE, F12, lv.ALIGN.TOP_LEFT, 104, 54)


def _toast(scr):
    _box(scr, 10, 26, 140, 30, t.INK, t.R_PILL)
    _text(scr, "Sent - 3 wands", t.SURFACE, F12, lv.ALIGN.TOP_LEFT, 27, 33)


def _status(scr):
    items = (("Serving", t.SERVE), ("Writing", t.WRITE), ("Low batt", t.WARN), ("No wand", t.DANGER))
    for i, (label, (fg, bg)) in enumerate(items):
        x = 6 + (i % 2) * 76
        y = 20 + (i // 2) * 30
        _box(scr, x, y, 72, 26, bg, t.R_MD, fg, 1)
        _box(scr, x + 6, y + 10, 6, 6, fg, t.R_PILL)
        _text(scr, label, fg, F12, lv.ALIGN.TOP_LEFT, x + 16, y + 6)


def _field(scr):
    _box(scr, 6, 20, 148, 24, t.SURFACE, t.R_MD, t.BORDER, 2)
    _text(scr, "Name your game", t.MUTED, F12, lv.ALIGN.TOP_LEFT, 12, 25)
    _box(scr, 6, 50, 148, 24, t.SURFACE, t.R_MD, t.PINK, 2)
    _text(scr, "rainbow tag", t.INK, F12, lv.ALIGN.TOP_LEFT, 12, 55)
    _box(scr, 88, 55, 1, 14, t.PINK, 0)


def _header(scr):
    _box(scr, 0, 18, W, 30, t.PINK, 0)  # flat: gradients band on this panel
    _box(scr, 6, 23, 20, 20, t.SURFACE, t.R_PILL)
    _box(scr, 11, 28, 10, 10, t.YELLOW, t.R_PILL)
    _text(scr, "Smart Playground", t.SURFACE, F12, lv.ALIGN.TOP_LEFT, 32, 26)
    _text(scr, "Box - ready", t.INK_3, F12, lv.ALIGN.TOP_LEFT, 6, 58)


def _palette(scr):
    rows = (
        (t.PINK, t.PURPLE, t.TEAL, t.YELLOW, t.INK, t.MUTED),
        (t.LED_RED, t.LED_GREEN, t.LED_BLUE, t.LED_YELLOW, t.LED_PURPLE, t.LED_PINK),
    )
    for r, row in enumerate(rows):
        for i, col in enumerate(row):
            _box(scr, 6 + i * 25, 20 + r * 30, 22, 26, col, t.R_SM)


def _levels(scr):
    # Calibration: R, G, B and grey rows at all 32 levels (5 px each), black page.
    # Raw colours, not panel-corrected, so a photo of this page can rebuild the lookup.
    scr.set_style_bg_color(lv.color_hex(0x000000), 0)
    for i in range(4):
        _box(scr, 40 * i + 39, 14, 1, 2, t.SURFACE, 0)  # ticks every 8 levels
    for r, (mr, mg, mb) in enumerate(((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1))):
        for i in range(32):
            v = i * 8 + 4
            o = _box(scr, i * 5, 16 + r * 16, 5, 16, 0, 0)
            o.set_style_bg_color(lv.color_hex((v * mr << 16) | (v * mg << 8) | v * mb), 0)


def _ref(scr):
    # Calibration: per channel, 32 flat levels (10 px) above dithers of only levels 0 and full
    # in 2x2 blocks, giving 1/8, 1/4, 1/2 and full light (12 px). Raw colours, not corrected.
    h = 66
    buf = bytearray(W * h * 2)
    _bufs.append(buf)
    cv = lv.canvas(scr)
    cv.set_pos(0, 14)
    cv.set_buffer(buf, W, h, lv.COLOR_FORMAT.RGB565)
    for r, (shift, full) in enumerate(((11, 31), (5, 63), (0, 31))):
        y0 = r * 22
        on = full << shift
        for x in range(W):
            i = x // 5
            flat = (2 * i + 1 if shift == 5 else i) << shift  # same levels as the Levels page
            patch = x // 40
            bx = x // 2
            for y in range(y0, y0 + 22):
                if y < y0 + 10:
                    v = flat
                else:
                    by = (y - y0 - 10) // 2
                    if patch == 0:
                        lit = bx % 4 == 0 and by % 2 == 0
                    elif patch == 1:
                        lit = bx % 2 == 0 and by % 2 == 0
                    elif patch == 2:
                        lit = (bx + by) % 2 == 0
                    else:
                        lit = True
                    v = on if lit else 0
                o = (y * W + x) * 2
                buf[o] = v & 0xFF
                buf[o + 1] = v >> 8
    cv.invalidate()


PAGES = (
    ("Ref", _ref),
    ("Levels", _levels),
    ("Button", _buttons),
    ("Chip", _chips),
    ("Toast", _toast),
    ("Status", _status),
    ("Field", _field),
    ("Header", _header),
    ("Palette", _palette),
)

_screens = {}
_bufs = []


def show(index):
    """Load page index (wraps). Returns the page name."""
    index %= len(PAGES)
    name, build = PAGES[index]
    scr = _screens.get(index)
    if scr is None:
        scr = _screen()
        _title(scr, index + 1, name)
        build(scr)
        _screens[index] = scr
    lv.screen_load(scr)
    return name
