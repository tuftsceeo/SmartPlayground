"""Screen 1B - Group chat: the home layout, with the group's last roll call under its name.
The pencil opens 2B (Edit group: change its devices, or Delete group).

Opening a group (side._open_chat) runs a roll call and Find for its devices (panel.open_group).
"""

import ds_tokens as t
import feed
import home
import panel
import side
import ui_kit as k
from ui_kit import F12, F16, H

_w = {}


def build():
    scr = k.new_screen()
    _w["side"] = side.build(scr, "msg")
    x0 = home.SIDE_W
    hd = k.box(scr, x0, 0, home.MAIN_W, home.HEAD_H, t.SURFACE)
    k.box(scr, x0, home.HEAD_H - 1, home.MAIN_W, 1, t.BORDER)
    _w["title"] = k.slot(hd, 16, 10, home.MAIN_W - 150, t.INK, F16)
    _w["wand"] = k.icon(hd, "wand_18", t.TEAL_DARK, 16, 36)
    _w["n"] = k.text(hd, "", t.TEAL_DARK, k.F_BODY, 38, 36)
    _w["age"] = k.text(hd, "", t.INK_3, F12, 64, 38)
    rc = k.button(hd, home.MAIN_W - 16 - 44, 10, 44, "", t.TEAL_DARK, "roll_call_18", px=12, w=44)
    k.on(rc, lambda: panel.P.act(panel.P.open_group))
    _w["rc"] = rc
    ed = k.button(hd, home.MAIN_W - 16 - 44 - 12 - 44, 10, 44, "", t.INK_3, "pencil_20", px=12, w=44)
    k.on(ed, lambda: panel.P.act(panel.P.edit_group))
    _w["slots"] = feed.build(scr, x0, home.HEAD_H, home.MAIN_W, H - home.HEAD_H - home.FOOT_H)
    _w["foot"] = home.footer(scr)
    return scr


def refresh():
    P = panel.P
    side.refresh(_w["side"])
    k.st(_w["title"], P.target["name"])
    c = P.calls.get(P.key())
    k.show_hide(_w["wand"], c is not None)
    k.st(_w["n"], "" if c is None else str(c[1]))
    k.st(_w["age"], "" if c is None else panel.short_ago(c[0]))
    x = 38 + 10 * len(_w["n"].get_text()) + 6
    if _w.get("ax") != x:
        _w["ax"] = x
        _w["age"].set_x(x)
    feed.fill(_w["slots"], P.log())
    k.busy(_w["rc"], P.rolling(P.key()))
    home.dim_footer(_w["foot"])
