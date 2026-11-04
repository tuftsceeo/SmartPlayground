"""Design-system component gallery for the 800x480 CrowPanel.

Each page is built on its own screen, cached, and loaded by show(index).
Prev / Next buttons along the bottom switch pages.
"""

import lvgl as lv

import ds_tokens as t

W = 800
H = 480
NAV_H = 72

F12 = lv.font_montserrat_12
F14 = lv.font_montserrat_14
F16 = lv.font_montserrat_16


def _c(hexval):
    return lv.color_hex(hexval)


def _screen():
    scr = lv.obj()
    scr.set_style_bg_color(_c(t.BG), 0)
    scr.set_style_pad_all(0, 0)
    scr.remove_flag(lv.obj.FLAG.SCROLLABLE)
    return scr


def _box(parent, x, y, w, h, bg, radius, border=None, border_w=2):
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
    o.remove_flag(lv.obj.FLAG.CLICKABLE)
    return o


def _text(parent, text, color, font=F16, align=lv.ALIGN.CENTER, x=0, y=0):
    lb = lv.label(parent)
    lb.set_text(text)
    lb.set_style_text_color(_c(color), 0)
    lb.set_style_text_font(font, 0)
    lb.align(align, x, y)
    return lb


def _button(parent, x, y, w, h, bg, fg, text, border=None):
    b = lv.button(parent)
    b.set_pos(x, y)
    b.set_size(w, h)
    b.set_style_radius(t.R_PILL, 0)
    b.set_style_bg_color(_c(bg), 0)
    b.set_style_shadow_width(0, 0)
    if border is None:
        b.set_style_border_width(0, 0)
    else:
        b.set_style_border_width(2, 0)
        b.set_style_border_color(_c(border), 0)
    _text(b, text, fg, F16)
    return b


def _title(scr, n, name):
    _text(scr, f"{n}/{len(PAGES)}  {name}", t.INK_3, F16, lv.ALIGN.TOP_LEFT, 24, 18)


def _nav(scr, index):
    _box(scr, 0, H - NAV_H, W, NAV_H, t.SURFACE, 0, t.BORDER, 2)
    prev = _button(scr, 24, H - NAV_H + 12, 180, 48, t.SURFACE, t.INK, "< Prev", t.BORDER)
    nxt = _button(scr, W - 204, H - NAV_H + 12, 180, 48, t.PINK, t.SURFACE, "Next >")
    prev.add_event_cb(lambda e: show(index - 1), lv.EVENT.CLICKED, None)
    nxt.add_event_cb(lambda e: show(index + 1), lv.EVENT.CLICKED, None)


def _buttons(scr):
    _button(scr, 60, 90, 300, 72, t.PINK, t.SURFACE, "Send to Box")
    _button(scr, 440, 90, 300, 72, t.TEAL, t.SURFACE, "Serve")
    b = _button(scr, 60, 200, 300, 72, t.DISABLED, t.MUTED_2, "Send to Box")
    b.remove_flag(lv.obj.FLAG.CLICKABLE)
    _button(scr, 440, 200, 300, 72, t.SURFACE, t.INK_3, "Not yet", t.BORDER)
    _text(scr, "Primary, secondary, disabled, ghost - tap to see pressed state",
          t.MUTED, F14, lv.ALIGN.TOP_LEFT, 60, 310)


def _chips(scr):
    x = 60
    for label, active in (("All", True), ("Sound", False), ("Light", False), ("Motion", False)):
        w = 40 + len(label) * 12
        if active:
            _box(scr, x, 100, w, 48, t.PINK_50, t.R_PILL, t.PINK)
            _text(scr, label, t.PINK_DARK, F16, lv.ALIGN.TOP_LEFT, x + 20, 115)
        else:
            _box(scr, x, 100, w, 48, t.SURFACE, t.R_PILL, t.BORDER)
            _text(scr, label, t.INK_3, F16, lv.ALIGN.TOP_LEFT, x + 20, 115)
        x += w + 16
    _box(scr, 60, 200, 160, 48, t.PURPLE, t.R_PILL)
    _text(scr, "Play", t.SURFACE, F16, lv.ALIGN.TOP_LEFT, 120, 215)
    _box(scr, 240, 200, 160, 48, t.PURPLE_50, t.R_PILL)
    _text(scr, "Code", t.PURPLE, F16, lv.ALIGN.TOP_LEFT, 298, 215)


def _toast(scr):
    _box(scr, 200, 170, 400, 64, t.INK, t.R_PILL)
    _box(scr, 232, 194, 16, 16, t.TEAL, t.R_PILL)
    _text(scr, "Sent - 3 wands", t.SURFACE, F16, lv.ALIGN.TOP_LEFT, 266, 193)


def _status(scr):
    items = (("Serving", t.SERVE), ("Writing", t.WRITE), ("Low battery", t.WARN), ("No wand", t.DANGER))
    for i, (label, (fg, bg)) in enumerate(items):
        x = 60 + (i % 2) * 360
        y = 90 + (i // 2) * 110
        _box(scr, x, y, 320, 80, bg, t.R_MD, fg)
        _box(scr, x + 24, y + 32, 16, 16, fg, t.R_PILL)
        _text(scr, label, fg, F16, lv.ALIGN.TOP_LEFT, x + 56, y + 31)


def _field(scr):
    _text(scr, "Game name", t.INK_3, F14, lv.ALIGN.TOP_LEFT, 60, 80)
    _box(scr, 60, 104, 680, 64, t.SURFACE, t.R_MD, t.BORDER)
    _text(scr, "Name your game", t.MUTED, F16, lv.ALIGN.TOP_LEFT, 84, 127)
    _text(scr, "Focused", t.INK_3, F14, lv.ALIGN.TOP_LEFT, 60, 200)
    _box(scr, 60, 224, 680, 64, t.SURFACE, t.R_MD, t.PINK, 3)
    lb = _text(scr, "rainbow tag", t.INK, F16, lv.ALIGN.TOP_LEFT, 84, 247)
    lb.update_layout()
    _box(scr, 88 + lb.get_width(), 240, 2, 32, t.PINK, 0)


def _header(scr):
    hd = _box(scr, 0, 60, W, 96, t.PINK, 0)
    hd.set_style_bg_grad_color(_c(t.PINK_DARK), 0)
    hd.set_style_bg_grad_dir(lv.GRAD_DIR.HOR, 0)
    _box(scr, 24, 80, 56, 56, t.SURFACE, t.R_PILL)
    _box(scr, 38, 94, 28, 28, t.YELLOW, t.R_PILL)
    _text(scr, "Smart Playground", t.SURFACE, F16, lv.ALIGN.TOP_LEFT, 100, 99)
    gem = _box(scr, 0, 180, W, 60, t.PINK, 0)
    gem.set_style_bg_grad_color(_c(t.PURPLE), 0)
    gem.set_style_bg_grad_dir(lv.GRAD_DIR.HOR, 0)
    _text(scr, "Gradient pink to purple (grad-gem)", t.SURFACE, F14, lv.ALIGN.TOP_LEFT, 24, 202)
    _text(scr, "Box - ready", t.INK_3, F16, lv.ALIGN.TOP_LEFT, 24, 270)


def _palette(scr):
    rows = (
        (("pink", t.PINK), ("purple", t.PURPLE), ("teal", t.TEAL), ("yellow", t.YELLOW), ("ink", t.INK), ("muted", t.MUTED)),
        (("red", t.LED_RED), ("green", t.LED_GREEN), ("blue", t.LED_BLUE), ("yellow", t.LED_YELLOW), ("purple", t.LED_PURPLE), ("pink", t.LED_PINK)),
    )
    for r, row in enumerate(rows):
        for i, (name, col) in enumerate(row):
            x = 40 + i * 124
            y = 70 + r * 170
            _box(scr, x, y, 108, 108, col, t.R_MD)
            _text(scr, name, t.INK_3, F14, lv.ALIGN.TOP_LEFT, x, y + 116)
    _text(scr, "Top: brand.  Bottom: wand LEDs.", t.MUTED, F14, lv.ALIGN.TOP_RIGHT, -24, 20)


def _levels(scr):
    # Calibration: R, G, B and grey rows at all 32 levels (25 px each), black page.
    # Raw colours, not corrected.
    scr.set_style_bg_color(_c(0x000000), 0)
    for i in range(1, 4):
        _box(scr, 200 * i - 1, 56, 2, 8, t.SURFACE, 0)  # ticks every 8 levels
    for r, (mr, mg, mb) in enumerate(((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1))):
        for i in range(32):
            v = i * 8 + 4
            _box(scr, i * 25, 64 + r * 84, 25, 80, (v * mr << 16) | (v * mg << 8) | v * mb, 0)


PAGES = (
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


def show(index):
    """Load page index (wraps). Returns the page name."""
    index %= len(PAGES)
    name, build = PAGES[index]
    scr = _screens.get(index)
    if scr is None:
        scr = _screen()
        build(scr)
        _title(scr, index + 1, name)
        _nav(scr, index)
        _screens[index] = scr
    lv.screen_load(scr)
    print(f"page {index + 1} {name}")
    return name
