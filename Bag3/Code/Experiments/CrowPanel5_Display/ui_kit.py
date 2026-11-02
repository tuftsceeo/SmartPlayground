"""Widget helpers, screen cache and navigation for the 800x480 teacher tool.

Import only after radio bring-up and display_lvgl.init().
"""

import sys
import time

import lvgl as lv

import ds_tokens as t
import fs_driver

W = 800
H = 480
F12 = lv.font_montserrat_12
F14 = lv.font_montserrat_14
F16 = lv.font_montserrat_16
R = 14
GREY = 0xF4F2FA
OFF_BG = 0xD8D4E6

_fs = None
_scr = {}
_mods = {}
_stack = []
cur = None
_toast = None
_toast_until = 0
_labels = {}   # id(pill or button) -> its label; LVGL objects take no new attributes
_fg = {}       # id(button) -> its label colour when enabled


def fs_init():
    global _fs
    if _fs is None:
        _fs = lv.fs_drv_t()
        fs_driver.fs_register(_fs, "S")


_txt = {}


def st(lb, s):
    """set_text only when the text changes: every set_text redraws and restarts scrolling."""
    if _txt.get(id(lb)) != s:
        _txt[id(lb)] = s
        lb.set_text(s)


_sty = {}


def sty(o, name, hexval, sel=0):
    """set_style_<name>_color only when it changes: every style set invalidates the object."""
    key = (id(o), name, sel)
    if _sty.get(key) != hexval:
        _sty[key] = hexval
        getattr(o, f"set_style_{name}_color")(c(hexval), sel)


def lbl(o):
    return _labels[id(o)]


def c(hexval):
    return lv.color_hex(hexval)


def plain(o):
    o.set_style_pad_all(0, 0)
    o.set_style_shadow_width(0, 0)
    o.set_style_border_width(0, 0)
    o.remove_flag(lv.obj.FLAG.SCROLLABLE)
    return o


def box(parent, x, y, w, h, bg, radius=0, border=None, border_w=2):
    o = plain(lv.obj(parent))
    o.set_pos(x, y)
    o.set_size(w, h)
    o.set_style_radius(radius, 0)
    o.set_style_bg_color(c(bg), 0)
    o.set_style_bg_opa(lv.OPA.COVER, 0)
    if border is not None:
        o.set_style_border_width(border_w, 0)
        o.set_style_border_color(c(border), 0)
    o.remove_flag(lv.obj.FLAG.CLICKABLE)
    return o


def grad(o, a=t.PINK, b=t.PINK_DARK):
    o.set_style_bg_color(c(a), 0)
    o.set_style_bg_grad_color(c(b), 0)
    o.set_style_bg_grad_dir(lv.GRAD_DIR.HOR, 0)


def text(parent, s, color, font=F14, x=0, y=0, align=lv.ALIGN.TOP_LEFT):
    lb = lv.label(parent)
    lb.set_text(s)
    lb.set_style_text_color(c(color), 0)
    lb.set_style_text_font(font, 0)
    lb.align(align, x, y)
    return lb


def slot(parent, x, y, w, color, font=F14, s="", align=lv.ALIGN.TOP_LEFT):
    """Fixed-width label that scrolls when its text is longer than the slot."""
    lb = text(parent, s, color, font, x, y, align)
    lb.set_width(w)
    lb.set_long_mode(lv.label.LONG_MODE.SCROLL_CIRCULAR)
    return lb


_icons = {}


def _icon_src(name):
    """Alpha map from /icons/<name>.a8, loaded once and kept in RAM (no decode on redraw)."""
    if name not in _icons:
        with open(f"/icons/{name}.a8", "rb") as f:
            b = f.read()
        w, h = b[0], b[1]
        px = b[2:]
        d = lv.image_dsc_t({"header": {"magic": lv.IMAGE_HEADER_MAGIC, "cf": lv.COLOR_FORMAT.A8,
                                       "w": w, "h": h, "stride": w},
                            "data_size": len(px), "data": px})
        _icons[name] = (d, px)
    return _icons[name][0]


def icon(parent, name, color, x=0, y=0, align=lv.ALIGN.TOP_LEFT):
    """White-on-alpha icon from /icons, tinted to color."""
    im = lv.image(parent)
    im.set_src(_icon_src(name))
    im.set_style_image_recolor(c(color), 0)
    im.set_style_image_recolor_opa(lv.OPA.COVER, 0)
    im.align(align, x, y)
    return im


def row(parent, gap=8):
    """Content-sized flex row, used for pills, bubbles and button labels."""
    o = plain(lv.obj(parent))
    o.set_size(lv.SIZE_CONTENT, lv.SIZE_CONTENT)
    o.set_style_bg_opa(lv.OPA.TRANSP, 0)
    o.set_flex_flow(lv.FLEX_FLOW.ROW)
    o.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
    o.set_style_pad_column(gap, 0)
    o.remove_flag(lv.obj.FLAG.CLICKABLE)
    return o


def line(parent, place):
    o = row(parent)
    o.set_width(lv.pct(100))
    o.set_flex_align(place, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
    return o


def pill(parent, s, fg, bg, font=F12, px=8, py=4, radius=10):
    p = row(parent)
    p.set_style_bg_color(c(bg), 0)
    p.set_style_bg_opa(lv.OPA.COVER, 0)
    p.set_style_radius(radius, 0)
    p.set_style_pad_hor(px, 0)
    p.set_style_pad_ver(py, 0)
    _labels[id(p)] = text(p, s, fg, font)
    return p


def button(parent, x, y, h, label, fg, ic=None, icon_fg=None, font=F14, px=14, primary=False, w=None):
    """Outline button sized to its label (or w); primary = pink gradient, white text."""
    b = lv.button(parent)
    plain(b)
    b.set_pos(x, y)
    b.set_size(w if w else lv.SIZE_CONTENT, h)
    b.set_style_radius(R, 0)
    b.set_style_pad_hor(px, 0)
    if primary:
        grad(b)
        fg = t.SURFACE
    else:
        b.set_style_bg_color(c(t.SURFACE), 0)
        b.set_style_border_width(2, 0)
        b.set_style_border_color(c(t.BORDER), 0)
    b.set_style_bg_color(c(t.BG if not primary else t.PINK_DARK), lv.STATE.PRESSED)
    b.set_style_bg_color(c(OFF_BG), lv.STATE.DISABLED)
    b.set_style_bg_grad_dir(lv.GRAD_DIR.NONE, lv.STATE.DISABLED)
    b.set_style_border_color(c(OFF_BG), lv.STATE.DISABLED)
    r = row(b)
    r.center()
    if ic:
        icon(r, ic, icon_fg or fg)
    if label:
        _labels[id(b)] = text(r, label, fg, font)
        _fg[id(b)] = fg
    return b


def avatar(parent, x, y, bg, fg, glyph, font=F14, use_grad=False):
    a = box(parent, x, y, 40, 40, bg, t.R_PILL)
    if use_grad:
        grad(a)
    if glyph.startswith("@"):
        icon(a, glyph[1:], fg, align=lv.ALIGN.CENTER)
    else:
        text(a, glyph, fg, font, align=lv.ALIGN.CENTER)
    return a


def bar(parent, x, y, w, h, color=t.PINK):
    b = lv.bar(parent)
    b.set_pos(x, y)
    b.set_size(w, h)
    b.set_range(0, 100)
    b.set_value(0, 0)
    b.set_style_bg_color(c(GREY), 0)
    b.set_style_bg_color(c(color), lv.PART.INDICATOR)
    b.set_style_radius(h // 2, 0)
    b.set_style_radius(h // 2, lv.PART.INDICATOR)
    return b


def safe(fn):
    """Event callback that never raises: an exception in an LVGL callback stops the UI timer."""
    def cb(e):
        try:
            fn()
        except Exception as ex:
            print(f"# ui callback: {type(ex).__name__}: {ex}")
    return cb


def on(o, fn):
    """Click handler. fn runs inside the LVGL task, so it should only queue work."""
    o.add_flag(lv.obj.FLAG.CLICKABLE)
    o.add_event_cb(safe(fn), lv.EVENT.CLICKED, None)


def on_tile(o, tap, hold):
    """Tap and long-press on one object; a long press does not also tap."""
    held = [False]
    o.add_flag(lv.obj.FLAG.CLICKABLE)

    def long_(e):
        held[0] = True
        hold()

    def click(e):
        if held[0]:
            held[0] = False
        else:
            tap()

    o.add_event_cb(safe(lambda: long_(None)), lv.EVENT.LONG_PRESSED, None)
    o.add_event_cb(safe(lambda: click(None)), lv.EVENT.CLICKED, None)


def show_hide(o, on_):
    """Change HIDDEN only when it differs: setting a flag invalidates the object."""
    if on_ == o.has_flag(lv.obj.FLAG.HIDDEN):
        if on_:
            o.remove_flag(lv.obj.FLAG.HIDDEN)
        else:
            o.add_flag(lv.obj.FLAG.HIDDEN)


def set_enabled(o, ok):
    """Disabled buttons get the grey fill and muted label; skips when unchanged."""
    if ok == o.has_state(lv.STATE.DISABLED):
        if ok:
            o.remove_state(lv.STATE.DISABLED)
        else:
            o.add_state(lv.STATE.DISABLED)
    if id(o) in _fg:
        sty(_labels[id(o)], "text", _fg[id(o)] if ok else t.MUTED)


def new_screen():
    scr = plain(lv.obj())
    scr.set_style_bg_color(c(t.BG), 0)
    return scr


def header(scr, title, back_fn=None):
    """White top bar with an optional back button; returns (bar, title_label)."""
    hd = box(scr, 0, 0, W, 64, t.SURFACE)
    box(scr, 0, 63, W, 1, t.BORDER)
    x = 16
    if back_fn:
        b = button(hd, 12, 10, 44, "", t.INK, "back_20", px=12, w=52)
        on(b, back_fn)
        x = 76
    lb = slot(hd, x, 20, 420, t.INK, F16, title)
    return hd, lb


# -- screens and navigation ------------------------------------------------

def go(name, push=True):
    """Show the screen module `name` (module.build() -> screen, module.refresh())."""
    global cur
    m = _mods.get(name)
    if m is None:
        m = _mods[name] = __import__(name)
    if name not in _scr:
        _scr[name] = m.build()
    if push and cur is not None and cur != name:
        _stack.append(cur)
    cur = name
    m.refresh()
    lv.screen_load(_scr[name])


def back():
    if _stack:
        go(_stack.pop(), push=False)
    else:
        go("home", push=False)


def home():
    del _stack[:]
    go("home", push=False)


def refresh():
    """Refresh the current screen, unless another screen (the keyboard) covers it."""
    m = _mods.get(cur)
    kb = sys.modules.get("kbd")
    if m is not None and not (kb and kb.is_open()):
        m.refresh()


# -- toast -----------------------------------------------------------------

def toast(msg, ms=3000):
    global _toast, _toast_until
    if _toast is None:
        top = lv.layer_top()
        _toast = pill(top, msg, t.SURFACE, t.INK, font=F14, px=16, py=10, radius=t.R_PILL)
        _toast.align(lv.ALIGN.BOTTOM_MID, 0, -96)
        _toast.remove_flag(lv.obj.FLAG.CLICKABLE)
    st(lbl(_toast), msg)
    _toast.remove_flag(lv.obj.FLAG.HIDDEN)
    _toast_until = time.ticks_add(time.ticks_ms(), ms)


def tick():
    global _toast_until
    if _toast_until and time.ticks_diff(time.ticks_ms(), _toast_until) >= 0:
        _toast_until = 0
        _toast.add_flag(lv.obj.FLAG.HIDDEN)
