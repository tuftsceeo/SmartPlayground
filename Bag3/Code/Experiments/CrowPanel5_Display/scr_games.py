"""Screens 3 and 3b - Start a game / Send code: bottom sheet on the top layer.

Start shows Custom (games from the computer) and Examples (built into every wand), each under a
header that opens and closes it. Send code shows Custom only, with no header. Tapping a game
starts it (or sends it) at once. Grid = 6 columns of 84 px tiles, list = 3 columns of 52 px rows;
both use the same tile pool. The rail pages the list; there is no free scrolling.
"""

import lvgl as lv

import ds_tokens as t
import library
import panel
import ui_kit as k
from ui_kit import F12, R

SHEET_Y = 40
AREA_X = 20
AREA_Y = 64
AREA_W = k.W - AREA_X - 12 - 52 - 12
AREA_H = 440 - AREA_Y - 76
GAP = 8
POOL = 18
_VIEW = {"grid": (6, 84), "list": (3, 52)}
_tiles = []
_heads = []
_w = {"mode": "start", "view": "grid", "page": 0, "open": {"custom": True, "examples": True}}
_root = None


def _build():
    global _root
    _root = k.box(lv.layer_top(), 0, 0, k.W, k.H, t.INK)
    _root.set_style_bg_opa(89, 0)
    _root.add_flag(lv.obj.FLAG.CLICKABLE)
    sh = k.box(_root, 0, SHEET_Y, k.W, k.H - SHEET_Y + 20, t.SURFACE, 20)
    sh.add_flag(lv.obj.FLAG.CLICKABLE)
    _w["head"] = k.slot(sh, 20, 12, 400, t.INK, k.F_HEAD)
    _w["to"] = k.slot(sh, 20, 36, 400, t.PINK_DARK, F12)
    _, _w["seg"], _ = k.seg(sh, k.W - 20 - 104, 8, (("grid", "Grid"), ("list", lv.SYMBOL.LIST)), _view, 48)
    for _ in range(2):
        b = k.box(sh, AREA_X, 0, AREA_W, 56, t.BG, 12)
        chev = k.box(b, 4, 4, 48, 48, t.SURFACE, 12, t.BORDER, 2)
        mark = k.text(chev, lv.SYMBOL.DOWN, t.INK_3, k.F16, align=lv.ALIGN.CENTER)
        title = k.text(b, "", t.INK, k.F16, 62, 18)
        n = k.text(b, "", t.INK_3, F12, -12, 0, lv.ALIGN.RIGHT_MID)
        h = {"box": b, "mark": mark, "title": title, "n": n, "key": None, "y": None}
        k.on(b, lambda h=h: h["key"] and _fold(h["key"]))
        _heads.append(h)
    for _ in range(POOL):
        b = k.box(sh, 0, 0, 10, 10, t.SURFACE, R, t.BORDER, 2)
        b.set_style_bg_color(k.c(t.PINK_50), lv.STATE.PRESSED)
        sw = k.box(b, 8, 8, 36, 36, 0xBF75C9, 10)
        nm = k.slot(b, 8, 56, 90, t.INK, F12)
        d = {"box": b, "sw": sw, "name": nm, "slug": None, "geo": None}
        k.on(b, lambda d=d: d["slug"] and _tap(d["slug"]))
        _tiles.append(d)
    _w["rail"] = k.rail(sh, k.W - 12 - 52, AREA_Y + 4, AREA_H - 8, lambda: _page(-1), lambda: _page(1))
    k.box(sh, 0, 440 - 76, k.W, 1, k.GREY)
    cancel = k.button(sh, k.W - 20 - 130, 440 - 66, 52, "Cancel", t.INK_3, font=k.F_BODY, w=130)
    k.on(cancel, close)


def _view(v):
    _w["view"] = v
    _w["page"] = 0
    refresh()


def _fold(key):
    _w["open"][key] = not _w["open"][key]
    refresh()


def _page(n):
    _w["page"] = max(0, _w["page"] + n)
    refresh()


def _tap(slug):
    P = panel.P
    close()
    P.act(P.start_game if _w["mode"] == "start" else P.send_code, slug)


def open(mode="start"):
    if _root is None:
        _build()
    _w["mode"] = mode
    _w["page"] = 0
    k.show_hide(_root, True)
    refresh()


def close():
    if _root is not None:
        k.show_hide(_root, False)


def _lines():
    """The sheet as lines: ("h", key, title, count) headers and ("g", [games]) tile rows."""
    P = panel.P
    cols = _VIEW[_w["view"]][0]
    sections = [("custom", "Custom", P.lib.flash_games())]
    if _w["mode"] == "start":
        sections.append(("examples", "Examples", [g for g in P.lib.games if g["slug"] in _BUILTIN]))
    out = []
    for key, title, games in sections:
        if _w["mode"] == "start":
            out.append(("h", key, title, len(games)))
            if not _w["open"][key]:
                continue
        for i in range(0, len(games), cols):
            out.append(("g", games[i:i + cols]))
    return out


_BUILTIN = set(s for s, _ in library.BUILTIN)


def _pages(lines):
    """Start index of each page: as many lines as fit in the area."""
    th = _VIEW[_w["view"]][1]
    starts = [0]
    y = 0
    for i, ln in enumerate(lines):
        h = 56 if ln[0] == "h" else th
        if y and y + h > AREA_H:
            starts.append(i)
            y = 0
        y += h + GAP
    return starts


def _place(o, cache, key, x, y, w=None, h=None):
    if cache.get(key) != (x, y, w, h):
        cache[key] = (x, y, w, h)
        o.set_pos(x, AREA_Y + y)
        if w is not None:
            o.set_size(w, h)


def refresh():
    if _root is None:
        return
    P = panel.P
    code = _w["mode"] == "code"
    k.st(_w["head"], "Send code" if code else "Start a game")
    k.st(_w["to"], f"To: {P.target['name']}")
    _w["seg"](_w["view"])
    cols, th = _VIEW[_w["view"]]
    tw = (AREA_W - (cols - 1) * GAP) // cols
    lines = _lines()
    starts = _pages(lines)
    _w["page"] = min(_w["page"], len(starts) - 1)
    first = starts[_w["page"]]
    last = starts[_w["page"] + 1] if _w["page"] + 1 < len(starts) else len(lines)
    _w["rail"](_w["page"], len(starts))
    y = 0
    hi = ti = 0
    for ln in lines[first:last]:
        if ln[0] == "h":
            h = _heads[hi]
            hi += 1
            h["key"] = ln[1]
            k.show_hide(h["box"], True)
            _place(h["box"], h, "geo", AREA_X, y)
            k.st(h["title"], ln[2])
            k.st(h["n"], str(ln[3]))
            k.st(h["mark"], lv.SYMBOL.DOWN if _w["open"][ln[1]] else lv.SYMBOL.RIGHT)
            y += 56 + GAP
            continue
        for c, g in enumerate(ln[1]):
            if ti >= POOL:
                break
            d = _tiles[ti]
            ti += 1
            d["slug"] = g["slug"]
            k.show_hide(d["box"], True)
            _place(d["box"], d, "geo", AREA_X + c * (tw + GAP), y, tw, th)
            geo = (8, 56, tw - 16) if _w["view"] == "grid" else (52, 17, tw - 60)
            if d.get("ngeo") != geo:
                d["ngeo"] = geo
                d["name"].set_pos(geo[0], geo[1])
                d["name"].set_width(geo[2])
            k.sty(d["sw"], "bg", g["color"])
            k.st(d["name"], g["name"])
        y += th + GAP
    for h in _heads[hi:]:
        h["key"] = None
        k.show_hide(h["box"], False)
    for d in _tiles[ti:]:
        d["slug"] = None
        k.show_hide(d["box"], False)
