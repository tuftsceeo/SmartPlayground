"""Screen 8 - Connected: mirroring the computer. Status, device grid, Stop all."""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12, F14, F16

DEV = 14
TOP = 70            # body top: 56 px header + 14 px gap
BOT = 464
AX = 372            # devices panel x
AW = 412
COL = 186
_w = {"stopped": False}
_DOTS = {"has": t.TEAL, "send": t.PINK, "wait": t.MUTED_2, "fail": t.DANGER[0]}


def _stop_all():
    panel.P.stop_all()
    _w["stopped"] = True


def build():
    scr = k.new_screen()
    hd = k.box(scr, 0, 0, k.W, 56, t.TEAL_50)
    k.box(scr, 0, 55, k.W, 1, t.BORDER)
    k.icon(hd, "plug_22", t.TEAL_DARK, 16, 17)
    k.slot(hd, 48, 19, 420, t.TEAL_DARK, F16, "Connected")
    stop = k.button(hd, 654, 6, 44, "Stop all", t.INK, "stop_18", t.DANGER[0], F14, w=130)
    k.on(stop, lambda: panel.P.act(_stop_all))

    st = k.box(scr, 16, TOP, AX - 32, BOT - TOP, t.SURFACE, 16, t.BORDER, 1)
    k.text(st, "STATUS", t.INK_3, F12, 16, 14)
    _w["now"] = k.slot(st, 16, 40, AX - 64, t.INK, F16)
    _w["bar"] = k.bar(st, 16, 72, AX - 64, 12, t.TEAL)
    _w["sub"] = k.slot(st, 16, 96, AX - 64, t.INK_3, F14)

    a = k.box(scr, AX, TOP, AW, BOT - TOP, t.SURFACE, 16, t.BORDER, 1)
    k.text(a, "Devices", t.INK, F16, 14, 12)
    _w["heard"] = k.slot(a, 260, 15, 136, t.INK_3, F12)
    _w["heard"].set_style_text_align(lv.TEXT_ALIGN.RIGHT, 0)
    _w["dev"] = []
    for i in range(DEV):
        x = 14 + (i % 2) * (COL + 10)
        y = 48 + (i // 2) * 38
        dot = k.box(a, x, y + 8, 10, 10, t.MUTED_2, t.R_PILL)
        nm = k.slot(a, x + 18, y + 3, COL - 18, t.INK, F14)
        _w["dev"].append((dot, nm))
    x = 14
    for col, word in ((t.TEAL, "Updated"), (t.PINK, "Working"), (t.DANGER[0], "Not heard"), (t.MUTED_2, "Skipped")):
        k.box(a, x, 352, 8, 8, col, t.R_PILL)
        k.text(a, word, t.INK_3, F12, x + 12, 348)
        x += 96
    return scr


def _dot(P, e):
    if P.dist and e["mac"] in P.dist["state"]:
        return _DOTS[P.dist["state"][e["mac"]]]
    if e["seen"] is None:
        return t.DANGER[0]
    return t.PINK if P.playing.get(e["mac"]) else t.TEAL


def _status(P):
    """(headline, sub, bar percent or None)."""
    d = P.dist
    if d:
        has = sum(1 for s in d["state"].values() if s == "has")
        busy = any(s in ("send", "wait") for s in d["state"].values())
        pct = 100 * has // max(1, len(d["state"]))
        if busy:
            _w["stopped"] = False
            return f"Sending {d['name']}", f"{has} of {len(d['state'])} have it", pct
    slugs = [s for s in P.playing.values() if s]
    if slugs:
        _w["stopped"] = False
        g = P.lib.get(slugs[0])
        n = len(slugs)
        return f"Playing {g['name'] if g else slugs[0]}", f"On {n} device" + ("" if n == 1 else "s"), None
    if _w["stopped"]:
        return "Stopped all", "", None
    if d:
        return f"Sent {d['name']}", f"{has} of {len(d['state'])} have it", pct
    return "Waiting", "Nothing running", None


def refresh():
    P = panel.P
    head, sub, pct = _status(P)
    k.st(_w["now"], head)
    k.st(_w["sub"], sub)
    k.show_hide(_w["bar"], pct is not None)
    if pct is not None:
        _w["bar"].set_value(pct, 0)
    items = P.roster.ranked(playing=P.playing)
    k.st(_w["heard"], f"{sum(1 for e in items if e['seen'] is not None)} heard")
    for i, (dot, nm) in enumerate(_w["dev"]):
        e = items[i] if i < len(items) else None
        k.show_hide(dot, e is not None)
        k.st(nm, P.roster.name(e["mac"]) if e else "")
        if e is not None:
            k.sty(dot, "bg", _dot(P, e))
