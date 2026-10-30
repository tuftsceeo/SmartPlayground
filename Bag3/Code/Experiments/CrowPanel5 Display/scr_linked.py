"""Screen 8 - Linked: mirroring the computer. Happening now, recent feed, device grid, Stop all."""

import time

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12, F14, F16

FEED = 6
DEV = 12
TOP = 70            # body top: 56 px header + 14 px gap
FOOT = 440          # footer top
AX = 534            # devices panel x
AW = 250
COL = 106
_w = {}
_DOTS = {"has": t.TEAL, "send": t.PINK, "wait": t.MUTED_2, "fail": t.DANGER[0]}


def build():
    scr = k.new_screen()
    hd = k.box(scr, 0, 0, k.W, 56, t.TEAL_50)
    k.box(scr, 0, 55, k.W, 1, t.BORDER)
    k.icon(hd, "plug_22", t.TEAL_DARK, 16, 17)
    k.slot(hd, 48, 19, 420, t.TEAL_DARK, F16, "Linked to ChatBroadcast")
    stop = k.button(hd, 654, 6, 44, "Stop all", t.INK, "stop_18", t.DANGER[0], F14, w=130)
    k.on(stop, lambda: panel.P.act(panel.P.stop_all))
    _w["stop"] = stop

    now = k.box(scr, 16, TOP, 504, 118, t.SURFACE, 16, t.BORDER, 1)
    k.text(now, "HAPPENING NOW", t.INK_3, F12, 16, 14)
    _w["now"] = k.slot(now, 16, 36, 472, t.INK, F16)
    _w["bar"] = k.bar(now, 16, 64, 472, 12, t.TEAL)
    _w["sub"] = k.slot(now, 16, 86, 472, t.INK_3, F14)

    k.text(scr, "RECENT", t.INK_3, F12, 16, 202)
    _w["feed"] = []
    for i in range(FEED):
        y = 222 + i * 30
        tm = k.slot(scr, 16, y + 6, 40, t.INK_3, F12)
        tx = k.slot(scr, 62, y + 5, 458, t.INK, F14)
        k.box(scr, 16, y + 29, 504, 1, k.GREY)
        _w["feed"].append((tm, tx))

    a = k.box(scr, AX, TOP, AW, FOOT - 14 - TOP, t.SURFACE, 16, t.BORDER, 1)
    k.text(a, "Devices", t.INK, F16, 14, 12)
    _w["heard"] = k.slot(a, 120, 15, 114, t.INK_3, F12)
    _w["heard"].set_style_text_align(lv.TEXT_ALIGN.RIGHT, 0)
    _w["dev"] = []
    for i in range(DEV):
        x = 14 + (i % 2) * (COL + 10)
        y = 46 + (i // 2) * 30
        dot = k.box(a, x, y + 7, 9, 9, t.MUTED_2, t.R_PILL)
        nm = k.slot(a, x + 15, y + 3, COL - 15, t.INK, F12)
        _w["dev"].append((dot, nm))
    x = 14
    for col, word in ((t.TEAL, "Updated"), (t.PINK, "Working"), (t.DANGER[0], "Not heard")):
        k.box(a, x, 334, 8, 8, col, t.R_PILL)
        k.text(a, word, t.INK_3, F12, x + 12, 330)
        x += 74

    ft = k.box(scr, 0, FOOT, k.W, 40, t.SURFACE)
    k.box(scr, 0, FOOT, k.W, 1, t.BORDER)
    k.text(ft, "Unplug to use on its own", t.INK_3, F12, 16, 13)
    _w["radio"] = k.slot(ft, 584, 13, 200, t.INK_3, F12)
    _w["radio"].set_style_text_align(lv.TEXT_ALIGN.RIGHT, 0)
    return scr


def _ago(ms):
    s = time.ticks_diff(time.ticks_ms(), ms) // 1000
    if s < 60:
        return "now"
    if s < 3600:
        return f"{s // 60}m"
    return f"{s // 3600}h"


def _dot(P, e):
    if P.dist and e["mac"] in P.dist["state"]:
        return _DOTS[P.dist["state"][e["mac"]]]
    if e["seen"] is None:
        return t.DANGER[0]
    return t.PINK if P.playing.get(e["mac"]) else t.TEAL


def refresh():
    P = panel.P
    d = P.dist
    k.st(_w["now"], P.happening or "Nothing running")
    k.show_hide(_w["bar"], bool(d))
    if d:
        has = sum(1 for s in d["state"].values() if s == "has")
        _w["bar"].set_value(100 * has // max(1, len(d["state"])), 0)
        k.st(_w["sub"], f"{has} of {len(d['state'])} have it")
    else:
        playing = sum(1 for g in P.playing.values() if g)
        k.st(_w["sub"], f"Playing on {playing} devices" if playing else "")
    k.show_hide(_w["stop"], bool(P.happening))
    feed = P.feed[-FEED:]
    for i, (tm, tx) in enumerate(_w["feed"]):
        f = feed[len(feed) - 1 - i] if i < len(feed) else None
        k.st(tm, _ago(f[0]) if f else "")
        k.st(tx, f[1] if f else "")
    items = P.roster.items()
    k.st(_w["heard"], f"{sum(1 for e in items if e['seen'] is not None)} heard")
    for i, (dot, nm) in enumerate(_w["dev"]):
        e = items[i] if i < len(items) else None
        k.show_hide(dot, e is not None)
        k.st(nm, P.roster.name(e["mac"]) if e else "")
        if e is not None:
            k.sty(dot, "bg", _dot(P, e))
    k.st(_w["radio"], "Radio on" if P.radio else "Radio off")
