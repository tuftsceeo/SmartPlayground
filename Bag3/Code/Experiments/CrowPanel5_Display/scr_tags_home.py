"""NFC Tags home: Games / Write / Read tiles. The radio stays on here; it pauses once a mode opens."""

import lvgl as lv

import ds_tokens as t
import ui_kit as k

TW = 240
TH = 260
_TILES = (("games", "Games", "Write the tags for a game", "gamepad_88", t.PINK_DARK, t.PINK_50),
          ("write", "Write", "Write your own words on a tag", "pencil_88", t.PURPLE, t.PURPLE_50),
          ("read", "Read", "See what a tag says", "nfc_waves_88", t.TEAL_DARK, t.TEAL_50))
def _open(mode):
    import scr_cards
    scr_cards.start(mode)
    k.go("scr_cards")
    scr_cards.opened()


def build():
    scr = k.new_screen()
    k.header(scr, "NFC Tags", k.back)
    for i, (mode, title, sub, ic, fg, bg) in enumerate(_TILES):
        b = k.box(scr, 28 + i * (TW + 16), 100, TW, TH, t.SURFACE, 20, t.BORDER)
        sq = k.box(b, (TW - 120) // 2 - 2, 28, 120, 120, bg, 24)
        k.icon(sq, ic, fg, 16, 16)
        k.text(b, title, t.INK, k.F_TITLE, 0, 170, lv.ALIGN.TOP_MID)
        k.text(b, sub, t.INK_3, k.F_BODY, 0, 200, lv.ALIGN.TOP_MID)
        k.on(b, lambda mode=mode: _open(mode))
    return scr


def refresh():
    pass
