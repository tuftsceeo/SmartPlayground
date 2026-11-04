"""Screen 4 - Sending code to wands: per-device progress, Pause, Retry, Start."""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12, R

ROWS = 12
CARD_X = 120
CARD_Y = 146
CARD_W = 560
_rows = []
_w = {}
_WORDS = {"has": ("Has it", t.TEAL_DARK), "send": ("Sending", t.PINK_DARK),
          "wait": ("Waiting", t.INK_3), "fail": ("No answer", t.DANGER[0])}


def _why(s):
    """A wand's refusal reason in short words, or None when it just didn't answer."""
    if not s:
        return None
    if s.startswith("busy"):
        return "Busy"
    if s.startswith("too large"):
        return "Too big"
    if s.startswith("does not compile"):
        return "Won't run"
    if s in ("timeout", "no_ack", "stopped", "cancelled", "pushed"):
        return None
    return "Didn't finish"


def build():
    scr = k.new_screen()
    hd, _w["title"], _w["sub"] = k.header(scr, "", panel.P.leave_send, "")
    bub = k.box(scr, k.W - 16 - 360, 76, 360, 48, t.PURPLE, R)
    k.icon(bub, "code_20", t.SURFACE, 14, 14)
    _w["bubble"] = k.slot(bub, 44, 15, 300, t.SURFACE, k.F_BODY)
    _w["when"] = k.slot(scr, k.W - 16 - 200, 127, 200, t.INK_3, F12)
    _w["when"].set_style_text_align(lv.TEXT_ALIGN.RIGHT, 0)
    cd = k.box(scr, CARD_X, CARD_Y, CARD_W, 262, t.SURFACE, R, t.BORDER)
    _w["head"] = k.slot(cd, 16, 16, 400, t.INK, k.F_HEAD)
    _w["pause"] = k.button(cd, CARD_W - 16 - 100, 8, 36, "Pause", t.INK, font=F12, w=100)
    k.on(_w["pause"], lambda: panel.P.act(panel.P.pause))
    _w["bar"] = k.bar(cd, 16, 52, CARD_W - 32, 10, t.TEAL)
    cw = (CARD_W - 44) // 2
    for i in range(ROWS):
        x = 16 + (i // 6) * (cw + 12)
        y = 76 + (i % 6) * 30
        dot = k.box(cd, x, y + 7, 10, 10, t.WAIT_DOT, 5)
        nm = k.slot(cd, x + 18, y + 2, 120, t.INK, k.F_BODY)
        st = k.slot(cd, x + 140, y + 3, cw - 140, t.INK_3, F12)
        _rows.append({"dot": dot, "name": nm, "st": st})
    ft = k.box(scr, 0, 416, k.W, 64, t.SURFACE)
    k.box(scr, 0, 416, k.W, 1, t.BORDER)
    _w["left"] = k.button(ft, 16, 8, 48, "Stop sending", t.DANGER[0], font=k.F_HEAD, w=220)
    k.on(_w["left"], lambda: panel.P.act(_left))
    _w["right"] = k.button(ft, k.W - 16 - 300, 8, 48, "Start", t.SURFACE, "play_20", primary=True,
                           w=300, font=k.F_HEAD)
    k.on(_w["right"], lambda: panel.P.act(_right))
    return scr


def _counts(st):
    n = {"has": 0, "send": 0, "wait": 0, "fail": 0}
    for s in st.values():
        n[s] = n.get(s, 0) + 1
    return n


def _mode(P):
    d = P.dist
    n = _counts(d["state"])
    if d.get("stopped"):
        return "stopped", n
    if n["send"] or n["wait"]:
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
    if mode in ("sending", "paused"):
        _stop()
    elif mode == "failed":
        P.retry_failed()
    elif mode == "stopped":
        P.leave_send()


def _right():
    P = panel.P
    if not P.dist:
        return
    mode, _ = _mode(P)
    if mode == "stopped":
        P.send_rest()
    elif mode in ("failed", "done"):
        P.start_sent()


def refresh():
    P = panel.P
    d = P.dist
    if not d:
        return
    st = d["state"]
    total = len(st)
    mode, n = _mode(P)
    es = [P.roster.d[m] for m in P.macs() if m in P.roster.d]
    nw = sum(1 for e in es if P.roster.is_wand(e))
    ns = len(es) - nw
    k.st(_w["title"], P.target["name"])
    k.st(_w["sub"], f"{nw} wand{'' if nw == 1 else 's'}{k.DOT}{ns} station{'' if ns == 1 else 's'}")
    k.st(_w["bubble"], f"Send code: {d['name']}")
    when = panel.ago(d.get("ts"))
    k.st(_w["when"], when[:1].upper() + when[1:])
    has = n["has"]
    if mode == "stopped":
        head = f"Stopped{k.DOT}{has} of {total} have it"
    elif mode == "paused":
        head = f"Paused{k.DOT}{has} of {total} have it"
    elif mode == "sending":
        head = f"{has} of {total} wands have it"
    elif mode == "failed":
        head = f"{has} of {total} wands have it"
    else:
        head = f"All {total} wands have it"
    k.st(_w["head"], head)
    _w["bar"].set_value(100 * has // max(1, total), 0)
    col = t.WAIT_DOT if mode == "stopped" else (t.WARN_DOT if mode == "paused" else t.TEAL)
    _w["bar"].set_style_bg_color(k.c(col), lv.PART.INDICATOR)
    k.show_hide(_w["pause"], mode in ("sending", "paused"))
    k.st(k.lbl(_w["pause"]), "Resume" if mode == "paused" else "Pause")
    why = d.get("why", {})
    macs = d["macs"][:ROWS]
    for i, r in enumerate(_rows):
        mac = macs[i] if i < len(macs) else None
        for o in (r["dot"], r["name"], r["st"]):
            k.show_hide(o, mac is not None)
        if mac is None:
            continue
        s = st.get(mac, "wait")
        word, c = _WORDS[s]
        if s == "fail":
            short = _why(why.get(mac))
            if short:
                word = short
            elif mode == "stopped":
                word, c = "Not sent", t.INK_3
        k.st(r["name"], P.roster.name(mac))
        k.st(r["st"], word)
        k.sty(r["st"], "text", c)
        k.sty(r["dot"], "bg", t.WAIT_DOT if c == t.INK_3 else c)
    left, right = _w["left"], _w["right"]
    if mode in ("sending", "paused"):
        k.st(k.lbl(left), "Stop sending")
        k.sty(k.lbl(left), "text", t.DANGER[0])
        k.st(k.lbl(right), f"Start {d['name']}{k.ARROW}")
    elif mode == "failed":
        fails = [m for m, s in st.items() if s == "fail"]
        k.st(k.lbl(left), f"Retry {P.roster.name(fails[0])}" if len(fails) == 1 else f"Retry {len(fails)} wands")
        k.sty(k.lbl(left), "text", t.INK)
        k.st(k.lbl(right), f"Start anyway{k.ARROW}")
    elif mode == "done":
        k.st(k.lbl(right), f"Start {d['name']}{k.ARROW}")
    else:
        k.st(k.lbl(left), "Back to chat")
        k.sty(k.lbl(left), "text", t.INK)
        rest = total - has
        k.st(k.lbl(right), f"Send to the other {rest}")
    k.show_hide(left, mode != "done")
    k.set_enabled(right, (mode in ("failed", "done") and has > 0) or (mode == "stopped" and total - has > 0))
