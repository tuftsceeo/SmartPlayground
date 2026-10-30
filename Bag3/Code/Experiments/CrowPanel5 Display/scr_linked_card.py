"""Screen 9 - Linked: the computer asks for a card. Uses the shared NFC target and edge bars."""

import lvgl as lv

import ds_tokens as t
import nfc_target
import panel
import ui_kit as k
from ui_kit import F12, F14, F16

_w = {}
# card state -> (status text, text colour, slot colour, bars full)
_SLOT = {"waiting": ("Ready", t.INK_3, k.GREY, False),
         "writing": ("Writing...", t.PURPLE, t.PURPLE_50, True),
         "done": ("Done", t.TEAL_DARK, t.TEAL_50, True),
         "error": ("Lift and tap again", t.DANGER[0], t.DANGER[1], False)}
_HINT = {"waiting": "Hold a blank card on the target. Wait for the beep.",
         "writing": "Keep the card still until the beep."}


def _cancel():
    h = panel.P.host
    if h.card is not None:
        h.card_done("write_failed", None)


def build():
    scr = k.new_screen()
    hd = k.box(scr, 0, 0, k.W, 56, t.TEAL_50)
    k.box(scr, 0, 55, k.W, 1, t.BORDER)
    k.icon(hd, "plug_22", t.TEAL_DARK, 16, 17)
    k.slot(hd, 48, 19, 300, t.TEAL_DARK, F16, "Linked to ChatBroadcast")
    k.pill(hd, "Radio paused", t.PURPLE, t.PURPLE_50, F14, 12, 6, t.R_PILL).set_pos(510, 13)
    cancel = k.button(hd, 664, 6, 44, "Cancel", t.INK_3, w=120)
    k.on(cancel, lambda: panel.P.act(_cancel))

    k.text(scr, "THE COMPUTER ASKS FOR A CARD", t.INK_3, F12, 40, 124)
    _w["title"] = k.slot(scr, 40, 148, 440, t.INK, F16)
    _w["hint"] = k.slot(scr, 40, 180, 440, t.INK_3, F14)
    chip = k.box(scr, 40, 210, 440, 32, k.GREY, 8, t.BORDER, 1)
    _w["text"] = k.slot(chip, 10, 8, 418, t.INK_2, F12)
    _w["slot"] = k.box(scr, 40, 258, 440, 60, k.GREY, 12)
    _w["status"] = k.slot(_w["slot"], 10, 8, 420, t.INK_3, F14)
    _w["sbar"] = k.bar(_w["slot"], 10, 36, 420, 12, t.PURPLE)
    _w["sbar"].set_style_bg_color(k.c(t.SURFACE), 0)

    ft = k.box(scr, 0, 430, k.W, 40, t.SURFACE)
    k.box(scr, 0, 430, k.W, 1, t.BORDER)
    _w["last"] = k.slot(ft, 16, 13, 480, t.INK_3, F12)

    nfc_target.attach(scr)
    _w["left"] = k.bar(scr, 0, 56, 10, 414, t.PURPLE)
    _w["bottom"] = k.bar(scr, 0, 470, k.W, 10, t.PURPLE)
    for b in (_w["left"], _w["bottom"]):
        b.set_style_radius(0, 0)
        b.set_style_radius(0, lv.PART.INDICATOR)
    return scr


def refresh():
    P = panel.P
    c = P.host.card
    if c is None:
        return
    nfc_target.attach(k._scr["scr_linked_card"])
    if not P.nfc_on:
        if not P.nfc_enter():
            c["state"] = "error"
            c["msg"] = P.reader.error
            _show(P, c)
            P.host.card_done("write_failed", None)
            return
        P.card_job("write", c["text"], c["label"], P.host.card_result)
    _show(P, c)


def _show(P, c):
    st = c["state"]
    word, fg, bg, full = _SLOT[st]
    k.st(_w["title"], f"Card: {c['label']}")
    k.st(_w["hint"], _HINT.get(st, c["msg"]))
    k.st(_w["text"], c["text"])
    k.st(_w["status"], word)
    k.sty(_w["status"], "text", fg)
    k.sty(_w["slot"], "bg", bg)
    v = 100 if full else 0
    _w["sbar"].set_value(v, 0)
    for b in (_w["left"], _w["bottom"]):
        b.set_value(v, 0)
        k.sty(b, "bg", t.PURPLE_50 if full else t.BG)
    last = P.host.last_card
    k.st(_w["last"], f"Last card: {last[0]} - {'written' if last[1] else 'not written'}" if last else "")
    nfc_target.state(st, c["msg"])
