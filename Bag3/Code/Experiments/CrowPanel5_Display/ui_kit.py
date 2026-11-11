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
# Font roles: the boards use Nunito 11-32 px; until it is on the panel each role maps to a built-in size.
F_TITLE = F16
F_HEAD = F16
F_BODY = F14
F_SMALL = F12
# The built-in fonts are ASCII only; with Nunito these become "·", "→" and "…".
DOT = " - "
ARROW = " >"
R = 14
GREY = 0xF4F2FA
INK3 = t.INK_3
OFF_BG = 0xD8D4E6

_fs = None
_scr = {}
_mods = {}
_stack = []
cur = None
_toast = None
_toast_until = 0
_labels = {}   # id(pill or button) -> its label; LVGL objects take no new attributes
_fg = {}       # id(button) -> its label color when enabled
_prim = set()  # id(button) of primary (filled) buttons
_PRIMARY = {"pink": (t.PINK, t.PINK_DARK), "teal": (t.TEAL, t.TEAL_DARK), "purple": (t.PURPLE, t.PURPLE)}


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
        try:
            with open(f"/icons/{name}.a8", "rb") as f:
                b = f.read()
        except OSError:
            print(f"# icon missing: {name}")
            return _icon_src("sparkle_14") if name != "sparkle_14" else None
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
    """Outline button sized to its label (or w); primary = filled, white text: True or "pink", "teal", "purple"."""
    b = lv.button(parent)
    plain(b)
    b.set_pos(x, y)
    b.set_size(w if w else lv.SIZE_CONTENT, h)
    b.set_style_radius(R, 0)
    b.set_style_pad_hor(px, 0)
    if primary:
        ca, cb = _PRIMARY["pink" if primary is True else primary]
        grad(b, ca, cb)
        fg = t.SURFACE
        _prim.add(id(b))
    else:
        b.set_style_bg_color(c(t.SURFACE), 0)
        b.set_style_border_width(2, 0)
        b.set_style_border_color(c(t.BORDER), 0)
    b.set_style_bg_color(c(t.BG if not primary else cb), lv.STATE.PRESSED)
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
    """Disabled buttons get the grey fill and a muted (outline) or white (primary) label; skips when unchanged."""
    if ok == o.has_state(lv.STATE.DISABLED):
        if ok:
            o.remove_state(lv.STATE.DISABLED)
        else:
            o.add_state(lv.STATE.DISABLED)
    if id(o) in _fg:
        sty(_labels[id(o)], "text", _fg[id(o)] if ok or id(o) in _prim else t.MUTED)


def new_screen():
    scr = plain(lv.obj())
    scr.set_style_bg_color(c(t.BG), 0)
    return scr


def header(scr, title, back_fn=None, sub=None, w=420):
    """White top bar with an optional back button; returns (bar, title_label), or
    (bar, title_label, sub_label) when sub is given (title on top, sub line below)."""
    hd = box(scr, 0, 0, W, 64, t.SURFACE)
    box(scr, 0, 63, W, 1, t.BORDER)
    x = 16
    if back_fn:
        b = button(hd, 12, 10, 44, "", t.INK, "back_20", px=12, w=44)
        on(b, back_fn)
        x = 68
    if sub is None:
        return hd, slot(hd, x, 22, w, t.INK, F_HEAD, title)
    lb = slot(hd, x, 12, w, t.INK, F_HEAD, title)
    return hd, lb, slot(hd, x, 36, w, t.INK_3, F_SMALL, sub)


def seg(parent, x, y, items, pick, iw=100, ih=40):
    """Segmented switch: grey track, the active item white with pink text.
    items = ((key, label), ...); pick(key) on tap. Returns (track, set_active(key), {key: label})."""
    tr = box(parent, x, y, len(items) * iw + 8, ih + 8, GREY, 20)
    parts = {}
    for i, (key, label) in enumerate(items):
        b = box(tr, 4 + i * iw, 4, iw, ih, GREY, 16)
        lb = text(b, label, t.INK_3, F14, align=lv.ALIGN.CENTER)
        on(b, lambda key=key: pick(key))
        parts[key] = (b, lb)

    def set_active(key):
        for kk, (b, lb) in parts.items():
            sty(b, "bg", t.SURFACE if kk == key else GREY)
            sty(lb, "text", t.PINK_DARK if kk == key else t.INK_3)
    return tr, set_active, {kk: v[1] for kk, v in parts.items()}


def rail(parent, x, y, h, on_up, on_down):
    """52 px paging rail: up and down arrows with a track between (no free scrolling).
    Returns set(page, pages); the rail hides when there is one page."""
    up = button(parent, x, y, 52, lv.SYMBOL.UP, INK3, px=0, w=52)
    dn = button(parent, x, y + h - 52, 52, lv.SYMBOL.DOWN, INK3, px=0, w=52)
    tr = box(parent, x + 19, y + 60, 14, h - 120, GREY, 7)
    th = box(tr, 0, 0, 14, h - 120, t.WAIT_DOT, 7)
    on(up, on_up)
    on(dn, on_down)
    last = [None]

    def set_page(page, pages):
        many = pages > 1
        for o in (up, dn, tr):
            show_hide(o, many)
        if not many or last[0] == (page, pages):
            return
        last[0] = (page, pages)
        full = h - 120
        th.set_height(max(20, full // pages))
        th.set_y(full * page // pages)
        set_enabled(up, page > 0)
        set_enabled(dn, page < pages - 1)
    return set_page


# edge state -> (fill color, track color or None, percent)
_EDGE = {"ready": (t.PURPLE, None, 0), "writing": (t.PURPLE, t.PURPLE_50, 60),
         "done": (t.TEAL, None, 100), "error": (t.DANGER[0], t.DANGER[1], 40)}


def edges(parent, top=0):
    """10 px bars on the left (fills upward) and bottom edges of an NFC screen; returns set(state)."""
    bars = (bar(parent, 0, top, 10, H - top), bar(parent, 0, H - 10, W, 10))
    for b in bars:
        b.set_style_radius(0, 0)
        b.set_style_radius(0, lv.PART.INDICATOR)
        b.set_style_bg_opa(lv.OPA.TRANSP, 0)
    cur_ = [None]

    def set_state(state):
        if cur_[0] == state:
            return
        cur_[0] = state
        fill, track, v = _EDGE[state]
        for b in bars:
            b.set_style_bg_color(c(fill), lv.PART.INDICATOR)
            b.set_style_bg_opa(lv.OPA.COVER if track else lv.OPA.TRANSP, 0)
            if track:
                b.set_style_bg_color(c(track), 0)
            b.set_value(v, 0)
    set_state("ready")
    return set_state


def radio_icon(parent, x, y):
    """Radio on / paused icon pair; returns set(on)."""
    ion = icon(parent, "radio_on_20", t.TEAL_DARK, x, y)
    ioff = icon(parent, "radio_off_20", t.PURPLE, x, y)

    def set_on(on_):
        show_hide(ion, on_)
        show_hide(ioff, not on_)
    return set_on


def signal_level(rssi):
    """0 (unknown) to 4 bars."""
    if rssi is None:
        return 0
    return 4 if rssi > -60 else (3 if rssi > -70 else (2 if rssi > -80 else 1))


def sig_bars(parent, x, y):
    """Four rising bars (the boards' signal glyph); returns set(level, color)."""
    bs = [box(parent, x + i * 5, y + 9 - 3 * i, 3, 4 + 3 * i, t.BORDER, 1) for i in range(4)]

    def set_level(level, col):
        for i, b in enumerate(bs):
            sty(b, "bg", col if i < level else t.BORDER)
    return set_level


def bubble(parent, mine=False):
    """Chat bubble in a full-width row: right and pink-filled when mine, else left and white.
    Returns (row, text_label, sub_label)."""
    ln = line(parent, lv.FLEX_ALIGN.END if mine else lv.FLEX_ALIGN.START)
    col = plain(lv.obj(ln))
    col.set_size(lv.SIZE_CONTENT, lv.SIZE_CONTENT)
    col.set_style_bg_opa(lv.OPA.TRANSP, 0)
    col.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    col.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.END if mine else lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START)
    col.set_style_pad_row(4, 0)
    b = row(col, 8)
    b.set_style_bg_opa(lv.OPA.COVER, 0)
    b.set_style_radius(R, 0)
    b.set_style_pad_hor(14, 0)
    b.set_style_pad_ver(10, 0)
    if mine:
        grad(b)
    else:
        b.set_style_bg_color(c(t.SURFACE), 0)
        b.set_style_border_width(2, 0)
        b.set_style_border_color(c(t.BORDER), 0)
    lb = text(b, "", t.SURFACE if mine else t.INK, F14)
    sub = text(col, "", t.INK_3, F12)
    return ln, lb, sub


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
