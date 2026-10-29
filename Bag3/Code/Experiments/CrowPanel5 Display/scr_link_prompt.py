"""Screen 7 - Plugged in: link to ChatBroadcast?"""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F14, F16


def build():
    scr = k.new_screen()
    card = k.box(scr, 150, 60, 500, 360, t.SURFACE, 24, t.BORDER)
    k.icon(card, "computer_link_120", t.PURPLE, align=lv.ALIGN.TOP_MID, y=20)
    k.text(card, "ChatBroadcast is asking to link", t.INK, F16, 0, 160, lv.ALIGN.TOP_MID)
    k.text(card, "The computer takes over. Wands keep answering.", t.INK_3, F14, 0, 192, lv.ALIGN.TOP_MID)
    ln = k.button(card, 40, 260, 64, "Link", t.SURFACE, "plug_22", font=F16, primary=True, w=200)
    ch = k.button(card, 260, 260, 64, "Just charge", t.INK_3, font=F16, w=200)
    k.on(ln, lambda: panel.P.act(panel.P.host.link))
    k.on(ch, lambda: panel.P.act(panel.P.host.just_charge))
    return scr


def refresh():
    pass
