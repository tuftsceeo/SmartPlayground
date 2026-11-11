"""Keyboard sheet (5.8): open(title, initial, max_bytes, on_ok).

Covers everything below the 64 px header on the top layer, so the screen's header (Back, the
Games / Write / Read toggle) stays live; leaving the screen closes it. A text field with "Use this
text", then four rows of keys: QWERTY, shift, backspace, 123, "-", a wide "_", ":" and ".".
title is unused (the artboard has none); kept for the callers.
"""

import lvgl as lv

import ds_tokens as t
import ui_kit as k
from ui_kit import F16, GREY

TOP = 64
_root = None
_open = [False]
_w = {"shift": False, "nums": False}
_BS = lv.SYMBOL.BACKSPACE
_SH = lv.SYMBOL.UP
_GAP = " "      # hidden spacer key, centers the shorter rows as on the artboard


def _rows(nums, shift):
    if nums:
        r1, r2, r3 = "1234567890", "!?'/()&@#", "+=*%,;\""
    else:
        r1, r2, r3 = "qwertyuiop", "asdfghjkl", "zxcvbnm"
        if shift:
            r1, r2, r3 = r1.upper(), r2.upper(), r3.upper()
    # (label, width units); a 60 px key is 2 units, every row 22
    return ([(_GAP, 1)] + [(c, 2) for c in r1] + [(_GAP, 1)],
            [(_GAP, 2)] + [(c, 2) for c in r2] + [(_GAP, 2)],
            [(_GAP, 1), (_SH if not nums else _GAP, 3)] + [(c, 2) for c in r3] +
            ([(_GAP, 2)] * (7 - len(r3))) + [(_BS, 3), (_GAP, 1)],
            [("abc" if nums else "123", 3), ("-", 2), ("_", 13), (":", 2), (".", 2)])


def _map():
    labels = []
    ctrl = []
    for i, row in enumerate(_rows(_w["nums"], _w["shift"])):
        if i:
            labels.append("\n")
        for lb, u in row:
            labels.append(lb)
            c = u
            if lb == _GAP:
                c |= lv.buttonmatrix.CTRL.HIDDEN
            elif lb == _SH and _w["shift"]:
                c |= lv.buttonmatrix.CTRL.CHECKED
            ctrl.append(c)
    labels.append("")
    _w["map"] = labels      # buttonmatrix keeps a pointer to the list
    _w["bm"].set_map(labels)
    _w["bm"].set_ctrl_map(ctrl)


def _build():
    global _root
    _root = k.box(lv.layer_top(), 0, TOP, k.W, k.H - TOP, t.BG)
    _root.add_flag(lv.obj.FLAG.CLICKABLE)
    ta = lv.textarea(_root)
    ta.set_pos(16, 14)
    ta.set_size(k.W - 32 - 10 - 170, 52)
    ta.set_one_line(True)
    ta.set_style_text_font(F16, 0)
    ta.set_style_text_color(k.c(t.INK), 0)
    ta.set_style_bg_color(k.c(t.SURFACE), 0)
    ta.set_style_border_color(k.c(t.PURPLE), 0)
    ta.set_style_border_width(2, 0)
    ta.set_style_radius(12, 0)
    ta.set_style_pad_hor(14, 0)
    ta.set_style_pad_top(16, 0)
    ta.set_style_bg_color(k.c(t.PURPLE), lv.PART.CURSOR | lv.STATE.FOCUSED)
    ta.add_state(lv.STATE.FOCUSED)      # shows the cursor without a group
    ta.remove_flag(lv.obj.FLAG.CLICK_FOCUSABLE)
    _w["ta"] = ta
    ok = k.button(_root, k.W - 16 - 170, 14, 52, "Use this text", t.SURFACE, primary=True, w=170,
                  font=k.F_HEAD)
    k.on(ok, _ok)
    pad = k.box(_root, 16, 76, k.W - 32, k.H - TOP - 76 - 12, t.SURFACE, 16, t.BORDER, 2)
    bm = lv.buttonmatrix(pad)
    k.plain(bm)
    bm.set_size(k.W - 32 - 24, k.H - TOP - 76 - 12 - 24)
    bm.set_pos(10, 10)
    bm.set_style_bg_opa(lv.OPA.TRANSP, 0)
    bm.set_style_pad_all(0, 0)
    bm.set_style_pad_row(8, 0)
    bm.set_style_pad_column(8, 0)
    bm.set_style_bg_color(k.c(GREY), lv.PART.ITEMS)
    bm.set_style_bg_opa(lv.OPA.COVER, lv.PART.ITEMS)
    bm.set_style_bg_color(k.c(t.PURPLE_50), lv.PART.ITEMS | lv.STATE.PRESSED)
    bm.set_style_bg_color(k.c(t.PURPLE_50), lv.PART.ITEMS | lv.STATE.CHECKED)
    bm.set_style_radius(10, lv.PART.ITEMS)
    bm.set_style_border_width(0, lv.PART.ITEMS)
    bm.set_style_shadow_width(0, lv.PART.ITEMS)
    bm.set_style_text_font(F16, lv.PART.ITEMS)
    bm.set_style_text_color(k.c(t.INK), lv.PART.ITEMS)
    bm.add_event_cb(k.safe(_key), lv.EVENT.VALUE_CHANGED, None)
    _w["bm"] = bm
    _map()
    ta.add_event_cb(k.safe(_limit), lv.EVENT.VALUE_CHANGED, None)


def _key():
    bm = _w["bm"]
    i = bm.get_selected_button()
    if i >= 0xFFFF:                 # LV_BUTTONMATRIX_BUTTON_NONE
        return
    s = bm.get_button_text(i)
    ta = _w["ta"]
    if s == _BS:
        ta.delete_char()
    elif s == _SH:
        _w["shift"] = not _w["shift"]
        _map()
    elif s in ("123", "abc"):
        _w["nums"] = s == "123"
        _map()
    elif s and s != _GAP:
        ta.add_text(s)
        if _w["shift"]:             # one capital, then back to lower case
            _w["shift"] = False
            _map()


def _limit():
    """Text too long: drop the last letter with the fail beep, as the Dial's keyboard does."""
    if "max" not in _w:
        return
    ta = _w["ta"]
    if len(ta.get_text().encode()) > _w["max"]:
        ta.delete_char()
        import beep
        beep.fail()


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
    return _open[0]


def open(title, initial, max_bytes, on_ok):
    if _root is None:
        _build()
    _w["max"] = max_bytes
    _w["cb"] = on_ok
    _w["ta"].set_text(initial or "")
    if _w["shift"] or _w["nums"]:
        _w["shift"] = _w["nums"] = False
        _map()
    _open[0] = True
    k.show_hide(_root, True)


def close():
    if _open[0]:
        _open[0] = False
        k.show_hide(_root, False)
