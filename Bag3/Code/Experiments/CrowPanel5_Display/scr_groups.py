"""Screen 1H - Manage groups, from the menu (1F).

The saved groups with their wand and station counts. Edit opens 2B (screen 2 in edit mode) and
Save comes back here; Delete deletes at once (no confirm) and stays here, with Undo in 1G.
New group opens screen 2.
"""

import lvgl as lv

import ds_tokens as t
import panel
import side
import ui_kit as k
from ui_kit import F14, F16

ROWS = 5
RH = 68
GAP = 8
Y0 = 76
_w = {"names": [None] * ROWS}


def _pick(i, fn):
    name = _w["names"][i]
    if name is not None:
        P = panel.P
        P.act(getattr(P, fn), name)


def _row(scr, i):
    r = k.box(scr, 16, Y0 + i * (RH + GAP), k.W - 32, RH, t.SURFACE, k.R)
    av = k.box(r, 12, 14, 40, 40, t.PURPLE_50, t.R_PILL)
    letter = k.text(av, "", t.PURPLE, F16, align=lv.ALIGN.CENTER)
    name = k.slot(r, 64, 12, 420, t.INK, F16)
    k.icon(r, "wand_18", t.TEAL_DARK, 64, 38)
    nw = k.text(r, "", t.TEAL_DARK, F14, 86, 38)
    si = k.icon(r, "station_face_20", t.INK_3, 120, 37)
    ns = k.text(r, "", t.INK_3, F14, 144, 38)
    dl = k.button(r, k.W - 32 - 10 - 48, 10, 48, "", t.DANGER[0], "trash_18", px=12, w=48)
    dl.set_style_border_color(k.c(0xF3C5C0), 0)
    ed = k.button(r, k.W - 32 - 10 - 48 - 10 - 100, 10, 48, "Edit", t.INK_3, "pencil_20", w=100)
    k.on(ed, lambda: _pick(i, "edit_group"))
    k.on(dl, lambda: _pick(i, "delete_group"))
    return {"row": r, "letter": letter, "name": name, "nw": nw, "si": si, "ns": ns}


def build():
    scr = k.new_screen()
    hd, _, _w["sub"] = k.header(scr, "Groups", k.back, "", 480)
    nb = k.button(hd, k.W - 16 - 150, 10, 44, "New group", t.PURPLE, "plus_16", w=150)
    k.on(nb, side.new_group)
    _w["rows"] = [_row(scr, i) for i in range(ROWS)]
    _w["empty"] = k.text(scr, "No groups yet.", t.INK_3, F14, 0, 0, lv.ALIGN.CENTER)
    return scr


def refresh():
    P = panel.P
    groups = sorted(P.store.groups.items())
    n = len(groups)
    k.st(_w["sub"], f"{n} group" if n == 1 else f"{n} groups")
    k.show_hide(_w["empty"], n == 0)
    for i, r in enumerate(_w["rows"]):
        g = groups[i] if i < n else None
        _w["names"][i] = g[0] if g else None
        k.show_hide(r["row"], g is not None)
        if g is None:
            continue
        name, macs = g
        w, s = P.group_counts(macs)
        k.st(r["letter"], name[:1].upper())
        k.st(r["name"], name)
        k.st(r["nw"], str(w))
        k.st(r["ns"], str(s))
        k.show_hide(r["si"], s > 0)
        k.show_hide(r["ns"], s > 0)
