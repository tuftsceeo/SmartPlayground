"""Screen 8 - Connected: mirroring the computer. Status card, devices while sending, Stop all.

When the computer goes quiet (host.lost) the header turns yellow and reads "Disconnected";
Stop all stays, and a tap on the header goes home.
"""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12

DEV = 7
TOP = 72
FOOT_Y = 440
CARD_W = 504
AX = 536
AW = 250
_w = {"stopped": False}
_DOTS = {"has": t.TEAL, "recv": t.PINK, "wait": t.WAIT_DOT, "fail": t.DANGER[0]}


def _stop_all():
    panel.P.stop_all()
    _w["stopped"] = True


def _home():
    P = panel.P
    if P.host is not None and P.host.lost:
        P.host.drop()


def build():
    scr = k.new_screen()
    hd = k.box(scr, 0, 0, k.W, 56, t.TEAL_50)
    k.box(scr, 0, 55, k.W, 1, t.BORDER)
    _w["hd"] = hd
    _w["plug"] = k.icon(hd, "plug_22", t.TEAL_DARK, 16, 17)
    _w["head"] = k.slot(hd, 48, 19, 560, t.TEAL_DARK, k.F_HEAD, "Connected")
    k.on(hd, lambda: panel.P.act(_home))
    stop = k.button(hd, k.W - 16 - 130, 6, 44, "Stop all", t.INK, "stop_18", t.DANGER[0], k.F_BODY, w=130)
    k.on(stop, lambda: panel.P.act(_stop_all))
    _w["stop"] = stop

    st = k.box(scr, 16, TOP, CARD_W, FOOT_Y - TOP - 16, t.SURFACE, 16, t.BORDER, 1)
    _w["card"] = st
    k.text(st, "STATUS", t.INK_3, F12, 20, 18)
    _w["now"] = k.slot(st, 20, 44, CARD_W - 40, t.INK, k.F_TITLE)
    _w["bar"] = k.bar(st, 20, 82, CARD_W - 40, 12, t.TEAL)
    _w["sub"] = k.slot(st, 20, 106, CARD_W - 40, t.INK_3, k.F_BODY)

    a = k.box(scr, AX, TOP, AW, FOOT_Y - TOP - 16, t.SURFACE, 16, t.BORDER, 1)
    _w["aside"] = a
    k.text(a, "Devices", t.INK, k.F_HEAD, 14, 14)
    _w["heard"] = k.slot(a, AW - 14 - 100, 16, 100, t.INK_3, F12)
    _w["heard"].set_style_text_align(lv.TEXT_ALIGN.RIGHT, 0)
    _w["dev"] = []
    for i in range(DEV):
        y = 48 + i * 36
        dot = k.box(a, 14, y + 6, 10, 10, t.WAIT_DOT, t.R_PILL)
        nm = k.slot(a, 32, y + 1, AW - 46, t.INK, k.F_BODY)
        _w["dev"].append((dot, nm))
    for i, (word, col) in enumerate((("Updated", t.TEAL), ("Working", t.PINK),
                                     ("Not heard", t.DANGER[0]), ("Skipped", t.WAIT_DOT))):
        x, y = 14 + (i % 2) * 112, 300 + (i // 2) * 22
        k.box(a, x, y + 4, 8, 8, col, t.R_PILL)
        k.text(a, word, t.INK_3, F12, x + 14, y)

    ft = k.box(scr, 0, FOOT_Y, k.W, k.H - FOOT_Y, t.SURFACE)
    k.box(scr, 0, FOOT_Y, k.W, 1, t.BORDER)
    _w["radio"] = k.radio_icon(ft, 16, 10)
    return scr


def _status(P):
    """(headline, sub, bar percent, sending)."""
    d = P.dist
    if d:
        has = sum(1 for s in d["state"].values() if s == "has")
        busy = any(s in ("recv", "wait") for s in d["state"].values())
        if busy:
            _w["stopped"] = False
            pct = 100 * has // max(1, len(d["state"]))
            return f"Sending {d['name']}", f"{has} of {len(d['state'])} have it", pct, True
    slugs = [s for s in P.playing.values() if s]
    if slugs:
        _w["stopped"] = False
        g = P.lib.get(slugs[0])
        return f"Playing {g['name'] if g else slugs[0]}", "", None, False
    if _w["stopped"]:
        return "Stopped all", "", None, False
    return "Waiting", "", None, False


def refresh():
    P = panel.P
    lost = P.host is not None and P.host.lost
    head, sub, pct, sending = _status(P)
    running = sending or head.startswith("Playing")
    k.sty(_w["hd"], "bg", t.WARN[1] if lost else t.TEAL_50)
    k.sty(_w["head"], "text", t.WARN[0] if lost else t.TEAL_DARK)
    _w["plug"].set_style_image_recolor(k.c(t.WARN[0] if lost else t.TEAL_DARK), 0)
    k.st(_w["head"], "Disconnected" if lost else "Connected")
    k.show_hide(_w["stop"], running or lost)
    k.st(_w["now"], head)
    k.st(_w["sub"], sub)
    k.show_hide(_w["sub"], sending)
    k.show_hide(_w["bar"], sending)
    if pct is not None:
        _w["bar"].set_value(pct, 0)
    k.show_hide(_w["aside"], sending)
    if sending:
        d = P.dist
        k.st(_w["heard"], f"{len(P.roster.d)} heard")
        macs = d["macs"][:DEV]
        for i, (dot, nm) in enumerate(_w["dev"]):
            mac = macs[i] if i < len(macs) else None
            k.show_hide(dot, mac is not None)
            k.st(nm, P.roster.name(mac) if mac else "")
            if mac is not None:
                k.sty(dot, "bg", _DOTS[d["state"].get(mac, "wait")])
    _w["radio"](P.radio)
