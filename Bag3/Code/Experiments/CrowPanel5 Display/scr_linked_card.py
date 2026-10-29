"""Screen 9 - Linked: the computer asks for a card. Uses the shared NFC target."""

import lvgl as lv

import ds_tokens as t
import nfc_target
import panel
import ui_kit as k
from ui_kit import F14, F16, R

_w = {}


def _cancel():
    h = panel.P.host
    if h.card is not None:
        h.card_done("write_failed", None)


def build():
    scr = k.new_screen()
    k.header(scr, "The computer asks for a card")
    box = k.box(scr, 16, 84, 480, 120, t.WRITE[1], R)
    k.text(box, "Write this card", t.PURPLE, F14, 16, 14)
    _w["text"] = k.slot(box, 16, 44, 448, t.INK, F16)
    _w["msg"] = k.slot(scr, 16, 230, 480, t.INK_3, F16)
    k.text(scr, "Radio paused while writing", t.WARN[0], F14, 16, 270)
    cancel = k.button(scr, 16, 410, 56, "Cancel", t.INK_3, w=160, font=F16)
    k.on(cancel, lambda: panel.P.act(_cancel))
    nfc_target.attach(scr)
    return scr


def refresh():
    P = panel.P
    c = P.host.card
    if c is None:
        return
    nfc_target.attach(k._scr["scr_linked_card"])
    if not P.nfc_on:
        if not P.nfc_enter():
            nfc_target.state("error", "No reader")
            k.st(_w["text"], c["text"])
            k.st(_w["msg"], P.reader.error)
            P.host.card_done("write_failed", None)
            return
        P.card_job("write", c["text"], c["label"], P.host.card_result)
    k.st(_w["text"], c["text"])
    k.st(_w["msg"], c["msg"])
    nfc_target.state(c["state"], c["msg"])
