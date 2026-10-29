"""Screen 8 - Linked: mirroring the computer. Happening now, recent feed, devices, Stop all."""

import lvgl as lv

import ds_tokens as t
import panel
import roster
import ui_kit as k
from ui_kit import F12, F14, F16, R

DEV = 7
FEED = 6
_w = {}


def build():
    scr = k.new_screen()
    hd, title = k.header(scr, "Linked to ChatBroadcast", k.home)
    k.icon(hd, "plug_22", t.SERVE[0], x=-24, y=20, align=lv.ALIGN.TOP_RIGHT)
    now = k.box(scr, 16, 76, 470, 84, t.SERVE[1], R)
    k.text(now, "Happening now", t.SERVE[0], F12, 14, 10)
    _w["now"] = k.slot(now, 14, 34, 440, t.INK, F16)
    _w["bar"] = k.bar(now, 14, 64, 440, 8, t.TEAL)
    k.text(scr, "Recent", t.INK, F16, 16, 172)
    _w["feed"] = [k.slot(scr, 16, 200 + i * 30, 470, t.INK_3, F14) for i in range(FEED)]
    k.text(scr, "Devices", t.INK, F16, 504, 80)
    _w["dev"] = []
    for i in range(DEV):
        r = k.box(scr, 504, 108 + i * 42, 280, 38, t.SURFACE, 10)
        nm = k.slot(r, 10, 10, 130, t.INK, F14)
        st = k.slot(r, 146, 11, 126, t.INK_3, F12)
        _w["dev"].append((r, nm, st))
    stop = k.button(scr, 504, 416, 56, "Stop all", t.INK, "stop_20", t.DANGER[0], F16, w=280)
    k.on(stop, lambda: panel.P.act(panel.P.stop_all))
    return scr


def refresh():
    P = panel.P
    k.st(_w["now"], P.happening or "Nothing running")
    d = P.dist
    if d:
        has = sum(1 for s in d["state"].values() if s == "has")
        _w["bar"].set_value(100 * has // max(1, len(d["state"])), lv.ANIM.OFF)
    k.show_hide(_w["bar"], bool(d))
    feed = P.feed[-FEED:]
    for i, lb in enumerate(_w["feed"]):
        k.st(lb, feed[len(feed) - 1 - i] if i < len(feed) else "")
    items = P.roster.items()
    for i, (r, nm, st) in enumerate(_w["dev"]):
        e = items[i] if i < len(items) else None
        k.show_hide(r, e is not None)
        if e is None:
            continue
        k.st(nm, P.roster.name(e["mac"]))
        s = P.dist["state"].get(e["mac"]) if P.dist else None
        word = {"has": "Has it", "send": "Sending", "wait": "Waiting", "fail": "No answer"}.get(s)
        g = P.playing.get(e["mac"])
        k.st(st, word or (f"Playing {g}" if g else P.roster.age(e)))
