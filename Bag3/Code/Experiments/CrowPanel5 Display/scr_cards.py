"""Screen 5 - Write game cards: Game / My own / Read, with the NFC target.

The radio is paused while this screen is open (the reader field is on).
"""

import time

import lvgl as lv

import ds_tokens as t
import nfc_target
import panel
import ui_kit as k
from ui_kit import F12, F14, F16, R

ROWS = 6
_rows = []
HOLD_MS = 1500
_w = {"tab": "game", "gi": 0, "i": 0, "cards": [], "done": set(), "read": None, "custom": ""}


def _leave():
    _w["entered"] = False
    panel.P.nfc_leave()
    k.home()


def build():
    scr = k.new_screen()
    hd, _w["title"] = k.header(scr, "NFC Tags", _leave)
    _w["radio"] = k.slot(hd, 520, 24, 264, t.WARN[0], F12, "Radio paused while writing")
    x = 16
    _w["tabs"] = {}
    for tab, label in (("game", "Game"), ("own", "My own"), ("read", "Read")):
        b = k.button(scr, x, 72, 40, label, t.INK_3, w=116)
        k.on(b, lambda tab=tab: _tab(tab))
        _w["tabs"][tab] = b
        x += 124
    gp = k.button(scr, 16, 120, 36, "<", t.INK, w=44)
    gn = k.button(scr, 452, 120, 36, ">", t.INK, w=44)
    k.on(gp, lambda: _game(-1))
    k.on(gn, lambda: _game(1))
    _w["gp"] = gp
    _w["gn"] = gn
    _w["gname"] = k.slot(scr, 72, 128, 370, t.INK, F16)
    for i in range(ROWS):
        r = k.box(scr, 16, 164 + i * 34, 480, 30, t.SURFACE, 8)
        mark = k.slot(r, 10, 7, 60, t.INK_3, F12)
        lb = k.slot(r, 76, 7, 390, t.INK, F14)
        _rows.append({"row": r, "mark": mark, "label": lb})
    _w["now"] = k.slot(scr, 528, 76, 256, t.INK, F16)
    _w["hint"] = k.slot(scr, 528, 106, 256, t.INK_3, F14)
    _w["prog"] = k.slot(scr, 528, 340, 256, t.PURPLE, F14)
    ft = k.box(scr, 0, 416, k.W, 64, t.SURFACE)
    sk = k.button(ft, 16, 8, 48, "Skip", t.INK_3, w=120, font=F16)
    k.on(sk, _skip)
    _w["edit"] = k.button(ft, 148, 8, 48, "Type text", t.PURPLE, w=150, font=F16)
    k.on(_w["edit"], _type)
    _w["copy"] = k.button(ft, 310, 8, 48, "Copy to tag", t.PURPLE, w=180, font=F16)
    k.on(_w["copy"], _copy)
    dn = k.button(ft, 664, 8, 48, "Done", t.SURFACE, primary=True, w=120, font=F16)
    k.on(dn, _leave)
    _w["edge_l"] = k.box(scr, 0, 64, 6, 0, t.PURPLE)
    _w["edge_b"] = k.box(scr, 0, k.H - 6, 0, 6, t.PURPLE)
    nfc_target.attach(scr)
    return scr


def _tab(tab):
    _w["tab"] = tab
    _load()


def _game(n):
    games = panel.P.lib.games
    _w["gi"] = (_w["gi"] + n) % len(games)
    _load()


def _load():
    P = panel.P
    tab = _w["tab"]
    if tab == "game":
        g = P.lib.games[_w["gi"]]
        _w["cards"] = P.lib.cards(g["slug"])
    elif tab == "own":
        _w["cards"] = [("My text", _w["custom"])] if _w["custom"] else []
    else:
        _w["cards"] = []
    _w["i"] = 0
    _w["done"] = set()
    _w["hold"] = None
    if P.nfc_on:
        k.st(_w["prog"], "Ready")
    _arm()


def _arm():
    """Queue the reader job for the current card, or a read on the Read tab."""
    P = panel.P
    if not P.nfc_on:
        _show()
        return
    if _w["tab"] == "read":
        P.card_job("read", None, "", _result)
        nfc_target.state("waiting", "Tap a tag to read")
    elif _w["i"] < len(_w["cards"]):
        label, text = _w["cards"][_w["i"]]
        P.card_job("write", text, text, _result)
        nfc_target.state("waiting")
    elif _w["cards"]:
        P.job = None
        nfc_target.state("done", "All done")
    else:
        P.job = None
        nfc_target.state("idle", "Type text first")
    _show()


def _result(res, uid, text):
    if res == "busy":
        nfc_target.state("writing")
        k.st(_w["prog"], "Writing... keep holding")
        _edges(50)
        return
    _edges(0)
    if res == "read":
        _w["read"] = text
        k.st(_w["prog"], f"Tag says: {text}")
        nfc_target.state("done", "Read")
        panel.P.card_job("read", None, "", _result)
        _show()
        return
    if res == "empty":
        k.st(_w["prog"], "No text on that tag")
        nfc_target.state("error", "Empty tag")
        panel.P.card_job("read", None, "", _result)
        return
    if res == "failed":
        k.st(_w["prog"], "Write failed - lift and try again")
        nfc_target.state("error", "Try again")
        _hold()
        return
    k.st(_w["prog"], "Already set" if res == "already" else "Written")
    nfc_target.state("done")
    _w["done"].add(_w["i"])
    _w["i"] += 1
    _show()
    _hold()


def _hold():
    """Keep the result on screen for HOLD_MS, then queue the next card."""
    panel.P.job = None
    _w["hold"] = panel.P.wake = time.ticks_add(time.ticks_ms(), HOLD_MS)


def _edges(pct):
    _w["edge_l"].set_height((k.H - 64) * pct // 100)
    _w["edge_b"].set_width(k.W * pct // 100)


def _skip():
    if _w["i"] < len(_w["cards"]):
        _w["i"] += 1
        _arm()


def _type():
    import kbd

    def ok(s):
        _w["custom"] = s
        _w["tab"] = "own"
        _load()
    kbd.open("Text for the tag", _w["custom"], 54, ok)


def _copy():
    if not _w["read"]:
        k.toast("Read a tag first")
        return
    _w["custom"] = _w["read"]
    _w["tab"] = "own"
    _load()


def _show():
    P = panel.P
    tab = _w["tab"]
    for name, b in _w["tabs"].items():
        k.sty(b, "border", t.PINK if name == tab else t.BORDER)
    for b in (_w["gp"], _w["gn"]):
        k.show_hide(b, tab == "game")
    if tab == "game":
        k.st(_w["gname"], P.lib.games[_w["gi"]]["name"])
    elif tab == "own":
        k.st(_w["gname"], "Your own text (54 letters max)")
    elif tab == "read":
        k.st(_w["gname"], "Read a tag, then copy it")
    cards = _w["cards"]
    first = max(0, min(_w["i"] - 2, len(cards) - ROWS))
    for j, r in enumerate(_rows):
        n = first + j
        k.show_hide(r["row"], n < len(cards))
        if n >= len(cards):
            continue
        label, text = cards[n]
        mark = "done" if n in _w["done"] else ("now" if n == _w["i"] else "todo")
        k.st(r["mark"], mark)
        k.sty(r["mark"], "text", t.TEAL_DARK if mark == "done" else (t.PINK if mark == "now" else t.MUTED))
        k.st(r["label"], f"{label}: {text}" if label != text else text)
        k.sty(r["row"], "bg", t.PINK_50 if mark == "now" else t.SURFACE)
    if tab == "read":
        k.st(_w["now"], "Read a tag")
        k.st(_w["hint"], "Hold a tag on the target")
    elif _w["i"] < len(cards):
        k.st(_w["now"], f"Tag {_w['i'] + 1}: {cards[_w['i']][0]}")
        k.st(_w["hint"], "Hold a blank tag on the target")
    else:
        k.st(_w["now"], "No tags to write" if not cards else "All tags written")
        k.st(_w["hint"], "Type text first" if tab == "own" and not cards else "")
    k.set_enabled(_w["copy"], bool(_w["read"]))
    k.show_hide(_w["radio"], P.nfc_on)


def refresh():
    P = panel.P
    h = _w.get("hold")
    if h is not None and time.ticks_diff(time.ticks_ms(), h) >= 0:
        _w["hold"] = None
        if _w.get("entered"):
            _arm()
    if not _w.get("entered"):
        _w["entered"] = True
        nfc_target.attach(k._scr["scr_cards"])
        ok = P.nfc_enter()
        k.st(_w["prog"], "Ready" if ok else P.reader.error)
        _load()
        if not ok:
            nfc_target.state("error", "No reader")
        return
    _show()
