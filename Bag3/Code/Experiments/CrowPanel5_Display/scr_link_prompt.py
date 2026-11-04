"""Screen 7 - Connecting: shown from the first identify until ChatBroadcast links."""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12


def build():
    scr = k.new_screen()
    tile = k.box(scr, 56, 130, 220, 220, t.TEAL_50, 24)
    k.icon(tile, "computer_link_120", t.TEAL_DARK, align=lv.ALIGN.CENTER)
    x = 316
    k.text(scr, "Connecting", t.INK, k.F_TITLE, x, 174)
    k.slot(scr, x, 206, 428, t.INK_3, k.F_BODY, "On the computer: Connect via USB")
    k.box(scr, x, 244, 10, 10, t.TEAL, t.R_PILL)
    k.text(scr, "Waiting...", t.INK_3, F12, x + 20, 242)
    # quiet way back to the panel's own screens when the computer keeps talking
    ch = k.button(scr, x, 286, 48, "Just charge", t.INK_3, font=k.F_BODY, w=160)
    k.on(ch, lambda: panel.P.act(panel.P.host.release))
    return scr


def refresh():
    pass
