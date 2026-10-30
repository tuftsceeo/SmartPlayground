"""Screen 7 - Plugged into a computer: shown from the first identify until ChatBroadcast links."""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12, F14, F16


def build():
    scr = k.new_screen()
    tile = k.box(scr, 56, 130, 220, 220, t.TEAL_50, 24)
    k.icon(tile, "computer_link_120", t.TEAL_DARK, align=lv.ALIGN.CENTER)
    x = 316
    k.text(scr, "Plugged into a computer", t.TEAL_DARK, F14, x, 146)
    k.text(scr, "Link to ChatBroadcast", t.INK, F16, x, 174)
    k.slot(scr, x, 206, 428, t.INK_3, F14, "Send code or open this device in ChatBroadcast.")
    k.box(scr, x, 242, 10, 10, t.TEAL, t.R_PILL)
    k.text(scr, "Waiting...", t.INK_3, F12, x + 20, 240)
    ch = k.button(scr, x, 278, 52, "Just charge", t.INK, font=F14, w=160)
    k.on(ch, lambda: panel.P.act(panel.P.host.release))
    return scr


def refresh():
    pass
