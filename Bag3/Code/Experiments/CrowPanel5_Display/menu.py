"""1F Menu: the hamburger at the top of the Messages column opens it over the screen.

Roll call (Everyone's), Manage groups (1H), History / Undo (1G) and, set apart, Shutdown.
A dark close button sits where the hamburger was; tapping the scrim also closes it, and so does
leaving the screen (ui_kit.go).
"""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12, F16

_root = None
_open = [False]
# (key, title, sub, icon, tile bg, icon/title colour)
_ITEMS = (("roll", "Roll call", "Check which devices answer", "roll_call_22", t.TEAL_50, t.TEAL_DARK),
          ("groups", "Manage groups", "Edit or delete groups", "everyone_20", t.PURPLE_50, t.PURPLE),
          ("hist", "History / Undo", "Undo group and name changes", "undo_22", t.PURPLE_50, t.PURPLE),
          ("off", "Shutdown", "Turn the panel off", "power_22", t.DANGER[1], t.DANGER[0]))
ROW_H = 64


def _build():
    global _root
    _root = k.plain(lv.obj(lv.layer_top()))
    _root.set_pos(0, 0)
    _root.set_size(k.W, k.H)
    _root.set_style_bg_color(k.c(t.INK), 0)
    _root.set_style_bg_opa(89, 0)       # 35%
    k.on(_root, close)
    x = k.box(_root, 178, 16, 44, 44, t.INK, k.R)       # over the hamburger (side.py)
    k.text(x, lv.SYMBOL.CLOSE, t.SURFACE, F16, align=lv.ALIGN.CENTER)
    k.on(x, close)
    h = 6 + 4 * (ROW_H + 2) + 9 + 6
    card = k.box(_root, 10, 68, 300, h, t.SURFACE, 16)
    card.add_flag(lv.obj.FLAG.CLICKABLE)     # a tap between rows doesn't close the menu
    card.set_style_shadow_width(34, 0)
    card.set_style_shadow_offset_y(14, 0)
    card.set_style_shadow_color(k.c(t.INK), 0)
    card.set_style_shadow_opa(70, 0)
    y = 6
    for key, title, sub, ic, bg, fg in _ITEMS:
        if key == "off":
            k.box(card, 14, y + 3, 272, 1, t.BORDER)
            y += 9
        r = k.box(card, 6, y, 288, ROW_H, t.SURFACE, 12)
        r.set_style_bg_color(k.c(t.BG), lv.STATE.PRESSED)
        tile = k.box(r, 12, 12, 40, 40, bg, 12)
        k.icon(tile, ic, fg, align=lv.ALIGN.CENTER)
        k.text(r, title, t.DANGER[0] if key == "off" else t.INK, F16, 64, 12)
        k.text(r, sub, t.INK_3, F12, 64, 36)
        k.on(r, lambda key=key: _pick(key))
        y += ROW_H + 2


def _pick(key):
    close()
    P = panel.P
    if key == "roll":
        import side
        side.roll_everyone()
    elif key == "groups":
        k.go("scr_groups")
    elif key == "hist":
        k.go("scr_history")
    else:
        P.act(P.shutdown)


def open():
    if _root is None:
        _build()
    _open[0] = True
    _root.move_foreground()
    k.show_hide(_root, True)


def close():
    if _open[0]:
        _open[0] = False
        k.show_hide(_root, False)


def is_open():
    return _open[0]
