# LVGL helpers for the Waveshare 1.9 mockup (170x320). Copied in spirit from
# Experiments/CrowPanel5_Display/ui_kit.py, cut down to what these screens use.
# Import only after hw_display.init().
import lvgl as lv
import tokens as t
import fake_data as fake

W = 170
H = 320
F14 = lv.font_montserrat_14
F16 = lv.font_montserrat_16
F_BIG = getattr(lv, "font_montserrat_24", F16)
RADIUS = 12

_screens = {}
_builders = {}
_state = {"tag": 0}


def c(h):
    return lv.color_hex(h)


def plain(o):
    o.set_style_pad_all(0, 0)
    o.set_style_border_width(0, 0)
    o.set_style_radius(0, 0)
    o.set_style_bg_opa(0, 0)
    o.remove_flag(lv.obj.FLAG.SCROLLABLE)


def box(parent, x, y, w, h, bg, border=None, radius=RADIUS):
    o = lv.obj(parent)
    plain(o)
    o.set_pos(x, y)
    o.set_size(w, h)
    o.set_style_radius(radius, 0)
    o.set_style_bg_color(c(bg), 0)
    o.set_style_bg_opa(255, 0)
    if border is not None:
        o.set_style_border_color(c(border), 0)
        o.set_style_border_width(2, 0)
    return o


def label(parent, s, color=t.INK, font=F14, x=0, y=0, w=None, center=False):
    lb = lv.label(parent)
    lb.set_text(s)
    lb.set_style_text_color(c(color), 0)
    lb.set_style_text_font(font, 0)
    if w is not None:
        lb.set_width(w)
    if center:
        lb.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    lb.set_pos(x, y)
    return lb


def on_tap(o, fn):
    o.add_flag(lv.obj.FLAG.CLICKABLE)
    o.add_event_cb(lambda e: fn(), lv.EVENT.CLICKED, None)


def button(parent, x, y, w, h, text, kind="plain", fn=None, font=F16):
    fill, fg, border = {
        "primary": (t.PINK, 0xFFFFFF, t.PINK),
        "danger": (t.SURFACE, t.DANGER, t.DANGER),
        "plain": (t.SURFACE, t.INK, t.BORDER),
    }[kind]
    b = box(parent, x, y, w, h, fill, border)
    lb = label(b, text, fg, font)
    lb.center()
    if fn:
        on_tap(b, fn)
    return b


def row(parent, y, text, right=None, selected=False, dot=None, fn=None):
    fg = t.PURPLE if selected else t.INK
    r = box(parent, 8, y, W - 16, 44, t.PURPLE_50 if selected else t.SURFACE,
            t.PURPLE if selected else t.BORDER)
    x = 10
    if dot is not None:
        d = box(r, 10, 12, 10, 10, dot, radius=5)
        x = 28
    lb = label(r, text, fg, F14, x=x, y=9)
    if right is not None:
        rl = label(r, right, t.INK_3, F14)
        rl.align(lv.ALIGN.RIGHT_MID, -8, 0)
    if fn:
        on_tap(r, fn)
    return r


def screen(name):
    """Plain 170x320 screen with the status strip on top."""
    s = lv.obj()
    plain(s)
    s.set_size(W, H)
    s.set_style_bg_color(c(t.BG), 0)
    s.set_style_bg_opa(255, 0)
    strip = box(s, 0, 0, W, 32, t.SURFACE, radius=0)
    box(strip, 0, 31, W, 1, t.BORDER, radius=0)
    box(strip, 8, 12, 8, 8, t.TEAL, radius=4)
    label(strip, "Linked", t.INK, F14, x=22, y=7)
    if name in ("home", "games", "tags", "serve"):
        p = box(strip, 78, 6, 54, 20, t.TEAL_50, radius=10)
        label(p, "Serving", t.TEAL, F14).center()
    bl = label(strip, "%d%%" % fake.BATTERY, t.INK_3, F14)
    bl.align(lv.ALIGN.RIGHT_MID, -6, 0)
    return s


def header(s, title, back="home"):
    b = box(s, 0, 32, 44, 44, t.BG, radius=0)
    label(b, lv.SYMBOL.LEFT, t.INK_3, F16).center()
    on_tap(b, lambda: go(back))
    label(s, title, t.INK, F16, x=44, y=45)


def register(name, builder):
    _builders[name] = builder


def go(name):
    """Build the screen on first use, then load it."""
    if name not in _screens:
        _screens[name] = _builders[name]()
    lv.screen_load(_screens[name])


def rebuild(name):
    """Drop a screen so the next go() builds it with current state."""
    _screens.pop(name, None)


def state():
    return _state
