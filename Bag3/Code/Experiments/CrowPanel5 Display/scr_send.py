"""Screen 4 - Sending code to wands: per-device progress, Pause, Retry, Start."""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12, F14, F16, R

ROWS = 8
_rows = []
_w = {}
_WORDS = {"has": ("Has it", t.SERVE[0]), "send": ("Sending", t.PURPLE),
          "wait": ("Waiting", t.INK_3), "fail": ("No answer", t.DANGER[0])}


def build():
    scr = k.new_screen()
    hd, _w["title"] = k.header(scr, "", panel.P.leave_send)
    _w["busy"] = k.slot(hd, 520, 24, 264, t.WARN[0], F12, "Radio busy - games paused")
    bub = k.box(scr, 16, 76, 360, 52, t.WRITE[1], R)
    _w["bubble"] = k.slot(bub, 14, 16, 330, t.PURPLE, F16)
    _w["count"] = k.slot(scr, 16, 142, 360, t.INK, F16)
    _w["bar"] = k.bar(scr, 16, 172, 360, 12, t.TEAL)
    k.text(scr, "Keep wands near the panel", t.INK_3, F14, 16, 200)
    for i in range(ROWS):
        y = 76 + i * 44
        r = k.box(scr, 392, y, 392, 40, t.SURFACE, 10)
        nm = k.slot(r, 12, 11, 150, t.INK, F14)
        st = k.slot(r, 170, 11, 100, t.INK_3, F14)
        b = k.button(r, 286, 2, 36, "Retry", t.DANGER[0], font=F12, w=96)
        d = {"row": r, "name": nm, "st": st, "retry": b, "mac": None}
        k.on(b, lambda d=d: d["mac"] and panel.P.act(panel.P.retry_code, d["mac"]))
        _rows.append(d)
    ft = k.box(scr, 0, 416, k.W, 64, t.SURFACE)
    _w["pause"] = k.button(ft, 16, 8, 48, "Pause", t.INK, w=140, font=F16)
    k.on(_w["pause"], lambda: panel.P.act(panel.P.pause))
    _w["stop"] = k.button(ft, 168, 8, 48, "Stop sending", t.DANGER[0], w=180, font=F16)
    k.on(_w["stop"], lambda: panel.P.act(_stop))
    _w["start"] = k.button(ft, 560, 8, 48, "Start", t.SURFACE, "play_20", primary=True, w=224, font=F16)
    k.on(_w["start"], lambda: panel.P.act(panel.P.start_sent))
    return scr


def _stop():
    P = panel.P
    if P.dist and P.fleet is not None:
        P.dist["stopped"] = True
        P.fleet.cancel("stopped")
        P.dirty = True


def refresh():
    P = panel.P
    d = P.dist
    if not d:
        return
    st = d["state"]
    has = sum(1 for s in st.values() if s == "has")
    k.st(_w["title"], f"Sending code - {d['name']}")
    k.st(_w["bubble"], f"Send code: {d['name']}")
    stopped = d.get("stopped")
    k.st(_w["count"], f"Stopped - {has} of {len(st)}" if stopped else f"{has} of {len(st)} wands have it")
    _w["bar"].set_value(100 * has // max(1, len(st)), 0)
    k.show_hide(_w["busy"], not d["done"])
    paused = P.fleet is not None and P.fleet.paused
    k.st(k.lbl(_w["pause"]), "Resume" if paused else "Pause")
    busy = any(s in ("send", "wait") for s in st.values())
    fail = any(s == "fail" for s in st.values())
    k.set_enabled(_w["start"], not busy)
    k.show_hide(_w["pause"], busy)
    k.show_hide(_w["stop"], busy)
    k.st(k.lbl(_w["start"]), "Start anyway" if fail and not busy else f"Start {d['name']}")
    macs = d["macs"][:ROWS]
    for i, r in enumerate(_rows):
        mac = macs[i] if i < len(macs) else None
        r["mac"] = mac
        k.show_hide(r["row"], mac is not None)
        if mac is None:
            continue
        word, col = _WORDS[st.get(mac, "wait")]
        if stopped and st.get(mac) == "fail":
            word, col = "Not sent", t.INK_3
        k.st(r["name"], P.roster.name(mac))
        k.st(r["st"], word)
        k.sty(r["st"], "text", col)
        k.show_hide(r["retry"], st.get(mac) == "fail")
