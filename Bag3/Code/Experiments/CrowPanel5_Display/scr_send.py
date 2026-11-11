"""Screen 4 - Sending code to wands.

The list shows only wands that are receiving the code or have it: "N have it - M receiving",
no total and no progress bar. Each wand starts the game as soon as it has it, so there is no
Start button; when the send is complete the panel goes back to the chat (panel._send_check, 4.5). Code is pushed one wand after another (unicast, fleet.py). For
Everyone a scan runs alongside and each wand that answers joins the queue (dist "scan").
4.2, 4.3 and 4.6 (paused, retry, stopped) are not redrawn yet; their Start anyway buttons are gone.
"""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12, R

ROWS = 12
CARD_X = 120
CARD_Y = 146
CARD_W = 560
CARD_H = 262
_rows = []
_w = {"page": 0}
_WORDS = {"has": ("Has it", t.TEAL_DARK, t.TEAL), "recv": ("Receiving", t.PINK_DARK, t.PINK)}


def build():
    scr = k.new_screen()
    hd, _w["title"] = k.header(scr, "", panel.P.leave_send)
    bub = k.box(scr, k.W - 16 - 360, 76, 360, 48, t.PURPLE, R)
    k.icon(bub, "code_20", t.SURFACE, 14, 14)
    _w["bubble"] = k.slot(bub, 44, 15, 230, t.SURFACE, k.F_BODY)
    _w["when"] = k.slot(bub, 280, 17, 70, t.SURFACE, F12)
    cd = k.box(scr, CARD_X, CARD_Y, CARD_W, CARD_H, t.SURFACE, R, t.BORDER)
    _w["head"] = k.slot(cd, 16, 20, 380, t.INK, k.F_HEAD)
    _w["pause"] = k.button(cd, CARD_W - 16 - 100, 12, 40, "Pause", t.INK_3, font=F12, w=100)
    k.on(_w["pause"], lambda: panel.P.act(panel.P.pause))
    cw = (CARD_W - 32 - 52 - 12 - 16) // 2
    for i in range(ROWS):
        x = 16 + (i // 6) * (cw + 16)
        y = 64 + (i % 6) * 30
        dot = k.box(cd, x, y + 7, 10, 10, t.WAIT_DOT, 5)
        nm = k.slot(cd, x + 18, y + 2, cw - 100, t.INK, k.F_BODY)
        st = k.slot(cd, x + cw - 76, y + 3, 76, t.INK_3, F12)
        _rows.append({"dot": dot, "name": nm, "st": st})
    _w["rail"] = k.rail(cd, CARD_W - 16 - 52, 60, CARD_H - 72, lambda: _page(-1), lambda: _page(1))
    ft = k.box(scr, 0, 406, k.W, 74, t.SURFACE)
    k.box(scr, 0, 406, k.W, 1, t.BORDER)
    _w["right"] = k.button(ft, k.W - 16 - 230, 11, 52, "Send to the rest", t.SURFACE, primary="purple", w=230,
                           font=k.F_BODY)
    k.on(_w["right"], lambda: panel.P.act(_right))
    _w["left"] = k.button(ft, k.W - 16 - 170, 11, 52, "Stop sending", t.DANGER[0], font=k.F_BODY, w=170)
    k.on(_w["left"], lambda: panel.P.act(_left))
    return scr


def _page(n):
    _w["page"] = max(0, _w["page"] + n)
    refresh()


def _counts(st):
    n = {"has": 0, "recv": 0, "wait": 0, "fail": 0}
    for s in st.values():
        n[s] = n.get(s, 0) + 1
    return n


def _mode(P):
    d = P.dist
    n = _counts(d["state"])
    if d.get("stopped"):
        return "stopped", n
    if n["recv"] or n["wait"] or d.get("scan"):
        return ("paused" if P.fleet is not None and P.fleet.paused else "sending"), n
    return ("failed" if n["fail"] else "done"), n


def _stop():
    P = panel.P
    if P.dist and P.fleet is not None:
        P.dist["stopped"] = True
        P.fleet.cancel("stopped")
        P.dirty = True


def _left():
    P = panel.P
    if not P.dist:
        return
    mode, _ = _mode(P)
    if mode == "stopped":
        P.leave_send()
    elif mode in ("sending", "paused"):
        _stop()
    elif mode == "failed":
        P.retry_failed()


def _right():
    P = panel.P
    if not P.dist:
        return
    mode, _ = _mode(P)
    if mode == "stopped":
        P.send_rest()


def refresh():
    P = panel.P
    d = P.dist
    if not d:
        return
    st = d["state"]
    mode, n = _mode(P)
    has = n["has"]
    k.st(_w["title"], P.target["name"])
    k.st(_w["bubble"], f"Send code: {d['name']}")
    when = panel.ago(d.get("ts"))
    k.st(_w["when"], when[:1].upper() + when[1:])
    summary = f"{has} have it{k.DOT}{n['recv']} receiving"
    if mode == "stopped":
        head = f"Stopped{k.DOT}{has} have it"
    elif mode == "paused":
        head = f"Paused{k.DOT}{summary}"
    elif mode in ("done", "failed"):
        head = f"{has} have it"
    else:
        head = summary
    k.st(_w["head"], head)
    k.sty(_w["head"], "text", t.TEAL_DARK if mode == "done" else t.INK)
    k.show_hide(_w["pause"], mode in ("sending", "paused"))
    k.st(k.lbl(_w["pause"]), "Resume" if mode == "paused" else "Pause")
    macs = [m for m in (d["macs"] or list(st)) if st.get(m) in _WORDS]
    pages = max(1, (len(macs) + ROWS - 1) // ROWS)
    _w["page"] = min(_w["page"], pages - 1)
    _w["rail"](_w["page"], pages)
    macs = macs[_w["page"] * ROWS:(_w["page"] + 1) * ROWS]
    for i, r in enumerate(_rows):
        mac = macs[i] if i < len(macs) else None
        for o in (r["dot"], r["name"], r["st"]):
            k.show_hide(o, mac is not None)
        if mac is None:
            continue
        word, c, dot = _WORDS[st[mac]]
        k.st(r["name"], P.roster.name(mac))
        k.st(r["st"], word)
        k.sty(r["st"], "text", c)
        k.sty(r["dot"], "bg", dot)
    left, right = _w["left"], _w["right"]
    rest = len(st) - has
    if mode in ("sending", "paused"):
        k.st(k.lbl(left), "Stop sending")
        k.sty(k.lbl(left), "text", t.DANGER[0])
    elif mode == "failed":
        fails = [m for m, s in st.items() if s == "fail"]
        k.st(k.lbl(left), f"Retry {P.roster.name(fails[0])}" if len(fails) == 1 else f"Retry {len(fails)} wands")
        k.sty(k.lbl(left), "text", t.INK)
    elif mode == "stopped":
        k.st(k.lbl(left), "Back to chat")
        k.sty(k.lbl(left), "text", t.INK)
        k.st(k.lbl(right), f"Send to the other {rest}")
    k.show_hide(left, mode != "done")
    k.show_hide(right, mode == "stopped" and rest > 0)
    x = k.W - 16 - 170 - (240 if mode == "stopped" and rest > 0 else 0)
    if _w.get("lx") != x:
        _w["lx"] = x
        left.set_x(x)
