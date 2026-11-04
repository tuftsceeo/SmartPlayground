"""Screen 3 - Start a game: bottom sheet on the top layer, over home or screen 6."""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12, R

SHEET_Y = 60
COLS = 4
TW = 181
TH = 128
_tiles = []
_w = {"tab": "all", "page": 0, "sel": None, "mode": "start"}
_root = None


def _build():
    global _root
    _root = k.box(lv.layer_top(), 0, 0, k.W, k.H, t.INK)
    _root.set_style_bg_opa(89, 0)
    _root.add_flag(lv.obj.FLAG.CLICKABLE)
    sh = k.box(_root, 0, SHEET_Y, k.W, k.H - SHEET_Y + 20, t.SURFACE, 20)
    sh.add_flag(lv.obj.FLAG.CLICKABLE)
    _w["head"] = k.slot(sh, 20, 14, 230, t.INK, k.F_HEAD)
    _w["to"] = k.slot(sh, 20, 38, 230, t.INK_3, F12)
    ny = k.button(sh, k.W - 20 - 110, 12, 44, "Not yet", t.INK_3, w=110)
    k.on(ny, close)
    _w["seg_tr"], _w["seg"], _ = k.seg(sh, k.W - 20 - 110 - 12 - 296, 10,
                             (("ready", "On wands"), ("new", "New"), ("all", "All")), _tab, 96)
    p = k.button(sh, 262, 12, 44, "<", t.INK, w=40)
    n = k.button(sh, 310, 12, 44, ">", t.INK, w=40)
    k.on(p, lambda: _page(-1))
    k.on(n, lambda: _page(1))
    _w["pager"] = (p, n)
    for i in range(COLS * 2):
        x = 20 + (i % COLS) * (TW + 12)
        y = 72 + (i // COLS) * (TH + 12)
        b = k.box(sh, x, y, TW, TH, t.SURFACE, R, t.BORDER)
        sw = k.box(b, 14, 14, 40, 40, 0xBF75C9, 10)
        nm = k.slot(b, 14, 66, TW - 28, t.INK, k.F_BODY)
        sub = k.slot(b, 14, 92, TW - 28, t.INK_3, F12)
        d = {"box": b, "sw": sw, "name": nm, "sub": sub, "slug": None}
        k.on(b, lambda d=d: _select(d))
        _tiles.append(d)
    _w["msg"] = k.slot(sh, 20, 368, 350, t.INK_3, k.F_BODY)
    # one action per sheet: Start in start mode, Send code in code mode, same spot
    sc = k.button(sh, 570, 352, 52, f"Send code{k.ARROW}", t.SURFACE, "code_20", font=k.F_HEAD,
                  primary="purple", w=210)
    st = k.button(sh, 570, 352, 52, f"Start{k.ARROW}", t.SURFACE, "play_20", font=k.F_HEAD, primary=True, w=210)
    k.on(st, lambda: _go("start"))
    k.on(sc, lambda: _go("code"))
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
        return
    P = panel.P
    close()
    P.act(P.start_game if what == "start" else P.send_code, slug)


def open(mode="start"):
    if _root is None:
        _build()
    _w["sel"] = None
    _w["mode"] = mode
    _w["tab"] = "all"
    _w["page"] = 0
    k.show_hide(_root, True)
    refresh()


def close():
    if _root is not None:
        k.show_hide(_root, False)


def _ready(g, macs):
    return not g["flash"] or (macs and macs <= panel.P.sent.get(g["slug"], set()))


def _games():
    P = panel.P
    macs = set(P.macs())
    if _w["mode"] == "code":
        return P.lib.flash_games()      # built-in games are already on every wand
    tab = _w["tab"]
    return [g for g in P.lib.games if tab == "all" or (tab == "ready") == bool(_ready(g, macs))]


def _sub(g):
    """(meta text, color) for a game tile."""
    P = panel.P
    macs = P.macs()
    m = len(macs)
    playing = sum(1 for x in macs if P.playing.get(x) == g["slug"])
    if macs and playing == m:
        return "Playing now", t.TEAL_DARK
    if not g["flash"]:
        return (f"On all {m}" if m else "On all"), t.INK_3
    n = len(P.sent.get(g["slug"], set()) & set(macs))
    if n == 0:
        return f"New{k.DOT}on 0 of {m}", t.PINK_DARK
    if n < m:
        return f"On {n} of {m}", t.WARN[0]
    return f"On all {m}", t.INK_3


def refresh():
    if _root is None:
        return
    P = panel.P
    code = _w["mode"] == "code"
    k.st(_w["head"], "Send code" if code else "Start a game")
    k.show_hide(_w["seg_tr"], not code)
    k.show_hide(_w["start"], not code)
    k.show_hide(_w["code"], code)
    n = len(P.macs())
    k.st(_w["to"], f"To: {P.target['name']}" if P.target["kind"] == "one"
         else f"To: {P.target['name']}{k.DOT}{n} device{'' if n == 1 else 's'}")
    _w["seg"](_w["tab"])
    games = _games()
    per = COLS * 2
    pages = max(1, (len(games) + per - 1) // per)
    _w["page"] = min(_w["page"], pages - 1)
    for b in _w["pager"]:
        k.show_hide(b, pages > 1)
    games = games[_w["page"] * per:(_w["page"] + 1) * per]
    for i, d in enumerate(_tiles):
        g = games[i] if i < len(games) else None
        k.show_hide(d["box"], g is not None)
        d["slug"] = g["slug"] if g else None
        if g is None:
            continue
        k.sty(d["sw"], "bg", g["color"])
        k.st(d["name"], g["name"])
        word, col = _sub(g)
        sel = g["slug"] == _w["sel"]
        k.st(d["sub"], word)
        k.sty(d["sub"], "text", t.PINK_DARK if sel else col)
        k.sty(d["box"], "border", t.PINK if sel else t.BORDER)
        k.sty(d["box"], "bg", t.PINK_50 if sel else t.SURFACE)
    sel = P.lib.get(_w["sel"]) if _w["sel"] else None
    # the design's only message: a game no wand is on yet
    new = sel is not None and not code and _sub(sel)[0].startswith("New")
    k.st(_w["msg"], f"{sel['name']} needs its code first." if new else "")
    # Start is never held back: the panel's record of what each wand has is lost on restart
    k.set_enabled(_w["code"], sel is not None)
    k.set_enabled(_w["start"], sel is not None)
