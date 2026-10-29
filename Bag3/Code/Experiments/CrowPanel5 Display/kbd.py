"""On-screen keyboard on its own screen, so typing redraws only the keyboard: open(title, initial, max_bytes, on_ok)."""

import lvgl as lv

import ds_tokens as t
import ui_kit as k
from ui_kit import F14, F16

_root = None
_prev = None
_w = {}


def _build():
    global _root
    _root = k.new_screen()
    _root.set_style_bg_color(k.c(t.SURFACE), 0)
    _w["title"] = k.slot(_root, 16, 16, 400, t.INK, F16)
    ta = lv.textarea(_root)
    ta.set_pos(16, 48)
    ta.set_size(560, 52)
    ta.set_one_line(True)
    ta.set_style_text_font(F16, 0)
    _w["ta"] = ta
    _w["count"] = k.slot(_root, 590, 64, 80, t.INK_3, F14)
    ok = k.button(_root, 680, 48, 52, "OK", t.SURFACE, primary=True, w=104)
    cancel = k.button(_root, 680, 4, 40, "Cancel", t.INK_3, w=104)
    k.on(ok, _ok)
    k.on(cancel, close)
    kb = lv.keyboard(_root)
    kb.set_size(k.W, 360)
    kb.align(lv.ALIGN.BOTTOM_MID, 0, 0)
    kb.set_textarea(ta)
    kb.set_mode(lv.keyboard.MODE.TEXT_LOWER)
    kb.add_event_cb(k.safe(_ok), lv.EVENT.READY, None)
    kb.add_event_cb(k.safe(close), lv.EVENT.CANCEL, None)
    ta.add_event_cb(k.safe(_count), lv.EVENT.VALUE_CHANGED, None)


def _count():
    if "max" not in _w:
        return
    n = len(_w["ta"].get_text().encode())
    k.st(_w["count"], f"{n}/{_w['max']}")
    k.sty(_w["count"], "text", t.DANGER[0] if n > _w["max"] else t.INK_3)


def _ok():
    s = _w["ta"].get_text().strip()
    if len(s.encode()) > _w["max"]:
        k.toast(f"Too long - at most {_w['max']} letters")
        return
    if any(ord(ch) > 126 for ch in s):
        k.toast("Letters and numbers only")
        return
    close()
    _w["cb"](s)


def is_open():
    return _prev is not None


def open(title, initial, max_bytes, on_ok):
    global _prev
    if _root is None:
        _build()
    _w["max"] = max_bytes
    _w["cb"] = on_ok
    k.st(_w["title"], title)
    _w["ta"].set_text(initial or "")
    _count()
    if _prev is None:
        _prev = lv.screen_active()
        lv.screen_load(_root)


def close():
    global _prev
    if _prev is not None:
        lv.screen_load(_prev)
        _prev = None
