"""Screen 3 - Pick a game: bottom sheet on the top layer, over home or screen 6."""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12, F14, F16, R

SHEET_Y = 96
COLS = 4
TW = 180
TH = 92
_tiles = []
_w = {"tab": "ready", "page": 0, "sel": None}
_root = None


def _build():
    global _root
    _root = k.box(lv.layer_top(), 0, 0, k.W, k.H, t.INK)
    _root.set_style_bg_opa(120, 0)
    _root.add_flag(lv.obj.FLAG.CLICKABLE)
    sh = k.box(_root, 0, SHEET_Y, k.W, k.H - SHEET_Y, t.SURFACE, 24)
    sh.add_flag(lv.obj.FLAG.CLICKABLE)
    k.text(sh, "Pick a game", t.INK, F16, 16, 16)
    _w["to"] = k.slot(sh, 16, 40, 300, t.INK_3, F12)
    x = 400
    _w["tabs"] = {}
    for tab, label in (("ready", "Ready"), ("new", "New")):
        b = k.button(sh, x, 12, 40, label, t.INK_3, w=100)
        k.on(b, lambda tab=tab: _tab(tab))
        _w["tabs"][tab] = b
        x += 108
    p = k.button(sh, 620, 12, 40, "<", t.INK, w=52)
    n = k.button(sh, 680, 12, 40, ">", t.INK, w=52)
    k.on(p, lambda: _page(-1))
    k.on(n, lambda: _page(1))
    for i in range(COLS * 2):
        x = 16 + (i % COLS) * (TW + 12)
        y = 66 + (i // COLS) * (TH + 10)
        b = k.box(sh, x, y, TW, TH, t.SURFACE, R, t.BORDER)
        sw = k.box(b, 12, 12, 28, 28, 0xBF75C9, 8)
        k.icon(sw, "music_note_16", t.SURFACE, align=lv.ALIGN.CENTER)
        nm = k.slot(b, 12, 46, TW - 24, t.INK, F14)
        sub = k.slot(b, 12, 68, TW - 24, t.INK_3, F12)
        d = {"box": b, "sw": sw, "name": nm, "sub": sub, "slug": None}
        k.on(b, lambda d=d: _select(d))
        _tiles.append(d)
    _w["msg"] = k.slot(sh, 16, 284, 380, t.INK_3, F14)
    st = k.button(sh, 410, 272, 52, "Start", t.SURFACE, "play_20", font=F16, primary=True, w=120)
    sc = k.button(sh, 540, 272, 52, "Send code", t.PURPLE, "code_20", font=F16, w=140)
    ny = k.button(sh, 690, 272, 52, "Not yet", t.INK_3, w=94)
    k.on(st, lambda: _go("start"))
    k.on(sc, lambda: _go("code"))
    k.on(ny, close)
    _w["start"] = st
    _w["code"] = sc


def _tab(tab):
    _w["tab"] = tab
    _w["page"] = 0
    _w["sel"] = None
    refresh()


def _page(n):
    _w["page"] = max(0, _w["page"] + n)
    refresh()


def _select(d):
    if d["slug"]:
        _w["sel"] = d["slug"]
        refresh()


def _go(what):
    slug = _w["sel"]
    if slug is None:
        k.toast("Pick a game first")
        return
    P = panel.P
    g = P.lib.get(slug)
    if what == "code" and not g["flash"]:
        k.toast("Built-in game - wands already have it")
        return
    close()
    P.act(P.start_game if what == "start" else P.send_code, slug)


def open(mode="start"):
    if _root is None:
        _build()
    _w["sel"] = None
    _w["tab"] = "new" if mode == "code" else "ready"
    _w["page"] = 0
    k.show_hide(_root, True)
    refresh()


def close():
    if _root is not None:
        k.show_hide(_root, False)


def _games():
    P = panel.P
    macs = set(P.macs())
    out = []
    for g in P.lib.games:
        sent = P.sent.get(g["slug"], set())
        ready = not g["flash"] or (macs and macs <= sent)
        if (_w["tab"] == "ready") == bool(ready):
            out.append(g)
    return out


def _sub(g):
    P = panel.P
    macs = P.macs()
    playing = sum(1 for m in macs if P.playing.get(m) == g["slug"])
    if macs and playing == len(macs):
        return "Playing now"
    if g["flash"]:
        n = len(P.sent.get(g["slug"], set()) & set(macs))
        return f"on {n} of {len(macs)}" if n else "New"
    return "Built in"


def refresh():
    if _root is None:
        return
    P = panel.P
    k.st(_w["to"], f"To: {P.target['name']} - {len(P.macs())} devices")
    for tab, b in _w["tabs"].items():
        k.sty(b, "border", t.PINK if tab == _w["tab"] else t.BORDER)
    games = _games()
    per = COLS * 2
    pages = max(1, (len(games) + per - 1) // per)
    _w["page"] = min(_w["page"], pages - 1)
    games = games[_w["page"] * per:(_w["page"] + 1) * per]
    for i, d in enumerate(_tiles):
        g = games[i] if i < len(games) else None
        k.show_hide(d["box"], g is not None)
        d["slug"] = g["slug"] if g else None
        if g is None:
            continue
        k.sty(d["sw"], "bg", g["color"])
        k.st(d["name"], g["name"])
        k.st(d["sub"], _sub(g))
        sel = g["slug"] == _w["sel"]
        k.sty(d["box"], "border", t.PINK if sel else t.BORDER)
    sel = P.lib.get(_w["sel"]) if _w["sel"] else None
    if sel is None:
        k.st(_w["msg"], "Tap a game." if games else "No games here.")
    elif sel["flash"] and not P.sent.get(sel["slug"]):
        k.st(_w["msg"], f"{sel['name']} needs its code first.")
    else:
        k.st(_w["msg"], sel["name"])
    k.set_enabled(_w["code"], sel is not None and sel["flash"])
