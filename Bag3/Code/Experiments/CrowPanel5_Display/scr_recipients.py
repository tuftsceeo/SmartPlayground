"""Screen 2 - Who gets it? Pick devices, see battery and signal; hold a tile to find it."""

import lvgl as lv

import ds_tokens as t
import panel
import roster
import ui_kit as k
from ui_kit import F12, F14, F16, R, GREY

COLS = 4
ROWS = 3
TW = 182
TH = 88
_tiles = []
_w = {"filter": "all", "page": 0}


def _tile(scr, i):
    x = 16 + (i % COLS) * (TW + 12)
    y = 120 + (i // COLS) * (TH + 10)
    b = k.box(scr, x, y, TW, TH, t.SURFACE, R, t.BORDER)
    name = k.slot(b, 12, 10, TW - 70, t.INK, F16)
    tag = k.pill(b, "", t.INK_3, GREY)
    tag.align(lv.ALIGN.TOP_RIGHT, -8, 8)
    batt = k.slot(b, 12, 42, TW - 24, t.INK_3, F14)
    sig = k.slot(b, 12, 66, TW - 24, t.INK_3, F12)
    d = {"box": b, "name": name, "tag": tag, "batt": batt, "sig": sig, "mac": None}
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
    kbd.open("Name this group", "", 20, lambda s: panel.P.act(panel.P.save_group, s))


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
    _, _w["title"] = k.header(scr, "Who gets it?", k.back)
    x = 16
    _w["tabs"] = {}
    for f, label in (("all", "All"), ("wands", "Wands"), ("stations", "Stations")):
        b = k.button(scr, x, 72, 40, label, t.INK_3, w=110)
        k.on(b, lambda f=f: _filter(f))
        _w["tabs"][f] = b
        x += 120
    _w["picked"] = k.slot(scr, 400, 82, 160, t.INK, F16)
    prev = k.button(scr, 640, 72, 40, "<", t.INK, w=60)
    nxt = k.button(scr, 712, 72, 40, ">", t.INK, w=60)
    k.on(prev, lambda: _page(-1))
    k.on(nxt, lambda: _page(1))
    for i in range(COLS * ROWS):
        _tile(scr, i)
    _w["empty"] = k.text(scr, "No devices yet. Tap Roll call.", t.MUTED, F16, 16, 140)
    ft = k.box(scr, 0, 456 - 40, k.W, 64, t.SURFACE)
    rc = k.button(ft, 16, 8, 48, "Roll call", t.TEAL_DARK, "roll_call_18")
    k.on(rc, lambda: panel.P.act(panel.P.roll_call))
    sv = k.button(ft, 200, 8, 48, "Save group", t.PURPLE, "plus_16")
    k.on(sv, _save)
    _w["save"] = sv
    gs = k.button(ft, 560, 8, 48, "Save group", t.SURFACE, primary=True, w=224, font=F16)
    k.on(gs, _save)
    _w["gsave"] = gs
    ch = k.button(ft, 560, 8, 48, "Chat with 0", t.SURFACE, primary=True, w=224, font=F16)
    _w["chat_l"] = k.lbl(ch)
    k.on(ch, _chat)
    _w["chat"] = ch
    return scr


def refresh():
    P = panel.P
    items = P.roster.items(_w["filter"])
    per = COLS * ROWS
    pages = max(1, (len(items) + per - 1) // per)
    if _w["page"] >= pages:
        _w["page"] = pages - 1
    items = items[_w["page"] * per:(_w["page"] + 1) * per]
    for f, b in _w["tabs"].items():
        k.sty(b, "border", t.PINK if f == _w["filter"] else t.BORDER)
    for i, d in enumerate(_tiles):
        e = items[i] if i < len(items) else None
        k.show_hide(d["box"], e is not None)
        d["mac"] = e["mac"] if e else None
        if e is None:
            continue
        mac = e["mac"]
        k.st(d["name"], P.roster.name(mac))
        k.st(k.lbl(d["tag"]), roster.tag_of(mac) if P.roster.is_wand(e) else "STN")
        b = e["battery"]
        k.st(d["batt"], "Battery -" if b is None else f"Battery {b}%")
        k.sty(d["batt"], "text", t.WARN[0] if P.roster.low(e) else t.INK_3)
        heard = e["heard"] or P.last_call is None
        k.st(d["sig"], f"{roster.signal_word(e['rssi'])} - {P.roster.age(e)}" if heard else "Not heard")
        k.sty(d["sig"], "text", t.INK_3 if heard else t.DANGER[0])
        d["box"].set_style_opa(lv.OPA.COVER if heard else 150, 0)
        on_ = mac in P.picked
        k.sty(d["box"], "border", t.PINK if on_ else t.BORDER)
        k.sty(d["box"], "bg", t.PINK_50 if on_ else t.SURFACE)
    k.show_hide(_w["empty"], not P.roster.d)
    n = len(P.picked)
    k.st(_w["picked"], f"{n} picked - page {_w['page'] + 1}/{pages}")
    k.st(_w["chat_l"], f"Chat with {n}")
    k.set_enabled(_w["chat"], n > 0)
    group = P.pick_mode == "group"
    k.st(_w["title"], "New group" if group else "Who gets it?")
    k.show_hide(_w["chat"], not group)
    k.show_hide(_w["save"], not group)
    k.show_hide(_w["gsave"], group)
    k.set_enabled(_w["gsave"], n > 0)
