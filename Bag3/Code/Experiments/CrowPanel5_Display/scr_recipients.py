"""Screen 2 - Who gets it? Pick devices, see battery and signal; hold a tile to find it."""

import lvgl as lv

import ds_tokens as t
import panel
import roster
import ui_kit as k
from ui_kit import F12, R, GREY

COLS = 4
ROWS = 3
TW = 184
TH = 72
TOP = 78
FOOT_Y = 406
_tiles = []
_w = {"filter": "all", "page": 0}


def _tile(scr, i):
    x = 16 + (i % COLS) * (TW + 10)
    y = TOP + (i // COLS) * (TH + 10)
    b = k.box(scr, x, y, TW, TH, t.SURFACE, R, t.BORDER)
    av = k.box(b, 12, 14, 40, 40, GREY, t.R_PILL)
    tag = k.text(av, "", t.INK_3, F12, align=lv.ALIGN.CENTER)
    name = k.slot(b, 62, 14, TW - 74, t.INK, k.F_BODY)
    meta = k.slot(b, 62, 40, TW - 104, t.INK_3, F12)
    bars = k.sig_bars(b, TW - 34, 38)
    d = {"box": b, "av": av, "tag": tag, "name": name, "meta": meta, "bars": bars, "mac": None}
    k.on_tile(b, lambda: _toggle(d), lambda: _find(d))
    _tiles.append(d)


def _toggle(d):
    P = panel.P
    if d["mac"] is None:
        return
    if d["mac"] in P.picked:
        P.picked.remove(d["mac"])
    else:
        P.picked.append(d["mac"])
    refresh()


def _find(d):
    if d["mac"]:
        panel.P.act(panel.P.find, d["mac"])


def _filter(f):
    _w["filter"] = f
    _w["page"] = 0
    refresh()


def _page(n):
    _w["page"] = max(0, _w["page"] + n)
    refresh()


def _save():
    import kbd
    kbd.open("", "", 20, lambda s: panel.P.act(panel.P.save_group, s))


def _chat():
    P = panel.P
    if not P.picked:
        k.toast("Pick some devices first")
        return
    if len(P.picked) == 1:
        P.set_target("one", P.roster.name(P.picked[0]), list(P.picked))
        k.go("scr_device", push=False)
        return
    P.set_target("set", f"{len(P.picked)} picked", list(P.picked))
    k.home()


def build():
    scr = k.new_screen()
    hd, _w["title"], _w["sub"] = k.header(scr, "Who gets it?", k.back, "Hold one to make it blink", 270)
    rc = k.button(hd, 0, 10, 44, "Roll call", t.TEAL_DARK, "roll_call_18")
    rc.update_layout()
    rc.set_x(k.W - 16 - rc.get_width())
    k.on(rc, lambda: panel.P.act(panel.P.roll_call))
    tr, _w["seg"], _w["seg_l"] = k.seg(hd, 0, 8, (("all", "All"), ("wands", "Wands"), ("stations", "Stations")),
                                       _filter, 90)
    tr.set_x(rc.get_x() - 12 - 278)
    for i in range(COLS * ROWS):
        _tile(scr, i)
    _w["empty"] = k.text(scr, "No devices yet. Tap Roll call.", t.MUTED, k.F_BODY, 16, 96)

    ft = k.box(scr, 0, FOOT_Y, k.W, k.H - FOOT_Y, t.SURFACE)
    k.box(scr, 0, FOOT_Y, k.W, 1, t.BORDER)
    _w["picked"] = k.slot(ft, 16, 27, 150, t.INK, k.F_HEAD)
    prev = k.button(ft, 176, 15, 44, "<", t.INK, w=44)
    nxt = k.button(ft, 228, 15, 44, ">", t.INK, w=44)
    k.on(prev, lambda: _page(-1))
    k.on(nxt, lambda: _page(1))
    _w["pager"] = (prev, nxt)
    sv = k.button(ft, 374, 11, 52, "Save group", t.PURPLE, "plus_16", font=k.F_BODY, w=170)
    k.on(sv, _save)
    _w["save"] = sv
    gs = k.button(ft, 556, 11, 52, "Save group", t.SURFACE, primary=True, w=228, font=k.F_HEAD)
    k.on(gs, _save)
    _w["gsave"] = gs
    ch = k.button(ft, 556, 11, 52, "Chat with 0", t.SURFACE, primary=True, w=228, font=k.F_HEAD)
    _w["chat_l"] = k.lbl(ch)
    k.on(ch, _chat)
    _w["chat"] = ch
    return scr


def _meta(P, e, heard):
    if not heard:
        if e["seen"] is None:
            return "Not heard"
        return f"Not heard{k.DOT}{P.roster.age(e).replace(' ago', '')}"
    if not P.roster.is_wand(e):
        return "Station"
    b = e["battery"]
    if P.roster.low(e):
        return "Battery low"
    return "-" if b is None else f"{b}%"


def refresh():
    P = panel.P
    items = P.roster.items(_w["filter"])
    per = COLS * ROWS
    pages = max(1, (len(items) + per - 1) // per)
    if _w["page"] >= pages:
        _w["page"] = pages - 1
    items = items[_w["page"] * per:(_w["page"] + 1) * per]
    _w["seg"](_w["filter"])
    k.st(_w["seg_l"]["all"], f"All {len(P.roster.d)}" if P.roster.d else "All")
    for i, d in enumerate(_tiles):
        e = items[i] if i < len(items) else None
        k.show_hide(d["box"], e is not None)
        d["mac"] = e["mac"] if e else None
        if e is None:
            continue
        mac = e["mac"]
        wand = P.roster.is_wand(e)
        k.st(d["name"], P.roster.name(mac))
        k.st(d["tag"], roster.tag_of(mac) if wand else "STN")
        k.sty(d["av"], "bg", GREY if wand else t.TEAL_50)
        k.sty(d["tag"], "text", t.INK_3 if wand else t.TEAL_DARK)
        heard = e["seen"] is not None and (e["heard"] or P.last_call is None)
        k.st(d["meta"], _meta(P, e, heard))
        k.sty(d["meta"], "text", t.DANGER[0] if not heard else (t.WARN[0] if P.roster.low(e) else t.INK_3))
        d["bars"](k.signal_level(e["rssi"]) if heard else 0, t.TEAL_DARK)
        on_ = mac in P.picked
        k.sty(d["box"], "border", t.PINK if on_ else t.BORDER)
        k.sty(d["box"], "bg", t.PINK_50 if on_ else (t.SURFACE if heard else t.TILE_OFF))
    k.show_hide(_w["empty"], not P.roster.d)
    for b in _w["pager"]:
        k.show_hide(b, pages > 1)
    n = len(P.picked)
    k.st(_w["picked"], f"{n} picked")
    k.st(_w["chat_l"], f"Chat with {n}{k.ARROW}")
    k.set_enabled(_w["chat"], n > 0)
    group = P.pick_mode == "group"
    k.st(_w["title"], "New group" if group else "Who gets it?")
    k.show_hide(_w["chat"], not group)
    k.show_hide(_w["save"], not group)
    k.show_hide(_w["gsave"], group)
    k.set_enabled(_w["gsave"], n > 0)
