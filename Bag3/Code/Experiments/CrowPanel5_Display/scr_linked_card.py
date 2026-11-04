"""Screen 9 - Linked: the computer asks for a tag. Uses the shared NFC target and edge bars."""

import lvgl as lv

import ds_tokens as t
import nfc_target
import panel
import ui_kit as k
from ui_kit import F12

_w = {}
_HINT = {"waiting": "Hold until the beep", "writing": "Hold until the beep", "error": "Hold until the beep"}


def build():
    scr = k.new_screen()
    hd = k.box(scr, 0, 0, k.W, 56, t.TEAL_50)
    k.box(scr, 0, 55, k.W, 1, t.BORDER)
    k.icon(hd, "plug_22", t.TEAL_DARK, 16, 17)
    k.slot(hd, 48, 19, 300, t.TEAL_DARK, k.F_HEAD, "Connected")
    pill = k.box(hd, k.W - 16 - 44, 8, 44, 40, t.PURPLE_50, t.R_PILL)
    k.icon(pill, "radio_off_20", t.PURPLE, align=lv.ALIGN.CENTER)

    _w["kicker"] = k.slot(scr, 40, 130, 440, t.PURPLE, F12)
    title = k.text(scr, "", t.INK, k.F_TITLE, 40, 156)
    title.set_width(440)
    title.set_long_mode(lv.label.LONG_MODE.WRAP)
    _w["title"] = title
    hint = k.text(scr, "", t.INK_3, k.F_BODY, 40, 220)
    hint.set_width(440)
    hint.set_long_mode(lv.label.LONG_MODE.WRAP)
    _w["hint"] = hint

    nfc_target.attach(scr)
    _w["edges"] = k.edges(scr, 56)
    return scr


def refresh():
    P = panel.P
    c = P.host.card
    if c is None:
        if P.host.shown is not None:
            nfc_target.attach(k._scr["scr_linked_card"])
            _show(P, P.host.shown)
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
    n, m, game = c.get("index"), c.get("total"), c.get("game")
    if c.get("set_done") and m:
        k.st(_w["kicker"], f"{game}{k.DOT}{m} of {m}" if game else "")
        k.st(_w["title"], f"All {m} written")
        k.st(_w["hint"], "")
        _w["edges"]("ready")
        nfc_target.state("idle")
        return
    k.st(_w["kicker"], f"{game}{k.DOT}tag {n} of {m}" if game and n and m else "")
    k.st(_w["title"], c["label"])
    k.st(_w["hint"], _HINT.get(st, ""))
    _w["edges"]("ready" if st == "waiting" else st)
    nfc_target.state(st)
