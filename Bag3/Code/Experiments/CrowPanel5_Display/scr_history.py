"""Screen 1G - History / Undo, from the menu (1F).

Changes made since the panel turned on, newest first: deleted groups, changed groups and renamed
devices (panel.history), each with Undo. An undone row stays, greyed, marked Undone. Sends and
games aren't listed. Kept in memory only: shutdown or a reset clears it.
"""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12, F14, F16, GREY

ROWS = 5            # panel.HIST_MAX
RH = 64
GAP = 8
Y0 = 76
FOOT_H = 48
_w = {}


def _row(scr, i):
    r = k.box(scr, 16, Y0 + i * (RH + GAP), k.W - 32, RH, t.SURFACE, k.R)
    tile = k.box(r, 12, 12, 40, 40, t.PURPLE_50, 12)
    ics = {n: k.icon(tile, n, t.PURPLE, align=lv.ALIGN.CENTER) for n in ("trash_18", "pencil_20")}
    title = k.slot(r, 64, 12, 470, t.INK, F16)
    sub = k.text(r, "", t.INK_3, F12, 64, 36)
    age = k.text(r, "", t.INK_3, F12, -136, 0, lv.ALIGN.RIGHT_MID)
    undo = k.button(r, k.W - 32 - 10 - 110, 10, 44, "Undo", t.PURPLE, "undo_16", w=110)
    k.on(undo, lambda: panel.P.act(panel.P.undo, i))
    done = k.text(r, "Undone", t.TEAL_DARK, F14, -40, 0, lv.ALIGN.RIGHT_MID)
    return {"row": r, "tile": tile, "ics": ics, "title": title, "sub": sub, "age": age,
            "undo": undo, "done": done, "look": None}


def build():
    scr = k.new_screen()
    k.header(scr, "History", k.back, "Since the panel turned on", 600)
    _w["rows"] = [_row(scr, i) for i in range(ROWS)]
    _w["empty"] = k.text(scr, "Nothing to undo yet.", t.INK_3, F14, 0, -10, lv.ALIGN.CENTER)
    ft = k.box(scr, 0, k.H - FOOT_H, k.W, FOOT_H, t.SURFACE)
    k.box(scr, 0, k.H - FOOT_H, k.W, 1, t.BORDER)
    k.icon(ft, "power_16", t.INK_3, 16, 16)
    k.text(ft, "Cleared when the panel shuts down", t.INK_3, F14, 40, 14)
    return scr


def refresh():
    hist = panel.P.history
    k.show_hide(_w["empty"], not hist)
    for i, r in enumerate(_w["rows"]):
        h = hist[i] if i < len(hist) else None
        k.show_hide(r["row"], h is not None)
        if h is None:
            continue
        done = h["done"]
        k.st(r["title"], h["title"])
        k.st(r["sub"], h["sub"])
        k.st(r["age"], panel.ago(h["t"]))
        k.show_hide(r["undo"], not done)
        k.show_hide(r["done"], done)
        k.sty(r["row"], "bg", GREY if done else t.SURFACE)
        k.sty(r["title"], "text", t.INK_3 if done else t.INK)
        dl = h["kind"] == "del"
        if r["look"] != dl:
            r["look"] = dl
            k.sty(r["tile"], "bg", t.DANGER[1] if dl else t.PURPLE_50)
            for name, im in r["ics"].items():
                k.show_hide(im, (name == "trash_18") == dl)
                im.set_style_image_recolor(k.c(t.DANGER[0] if dl else t.PURPLE), 0)
