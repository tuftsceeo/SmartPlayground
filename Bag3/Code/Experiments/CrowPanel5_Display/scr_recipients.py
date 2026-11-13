"""Screens 2 (New group) and 2B (Edit group, from the pencil in 1B).

Devices in Wands, Stations and Unknown / Other sections, each under a header that opens and closes
it. Each tile has two tap zones and no long press: the avatar circle adds or removes the device
(pink check), the rest of the tile sends Find (purple outline and "Blinking" for 5 s). Tiles show
signal (3 bars, a red X when not heard) and battery. The rail pages the list; no free scrolling.
New group: "N picked" and Save group (asks for a name). Edit group: the group's name as the
title, Delete group and Save.
"""

import time

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12, R, GREY

COLS = 4
TH = 60
GAP = 8             # between sections and their tiles
TGAP = 6            # between tiles
AREA_X = 16
AREA_Y = 72
FOOT_Y = 405
AREA_W = k.W - AREA_X - 12 - 52 - 12
AREA_H = FOOT_Y - 8 - AREA_Y
TW = (AREA_W - (COLS - 1) * TGAP) // COLS
POOL = 20           # up to 5 rows of 4 fit the area
MISS = 0x9A93A8
RING = 0xD9D5E4
FIND_MS = 5000      # the wand's Find runs 5 s (Wand Module/finddevice.py DURATION_MS)
_SECTIONS = (("wands", "Wands"), ("stations", "Stations"), ("other", "Unknown / Other"))
# battery level -> (color, fill width)
_BAT = {"high": (t.TEAL_DARK, 13), "medium": (t.INK_3, 9), "low": (t.WARN[0], 5),
        "critical": (t.DANGER[0], 2)}
_tiles = []
_heads = []
_w = {"page": 0, "open": {"wands": True, "stations": True, "other": False}}
_finding = {}       # mac -> ticks when its Blinking state ends


def _zone(parent, x, y, w, h, fn):
    z = k.box(parent, x, y, w, h, t.SURFACE)
    z.set_style_bg_opa(lv.OPA.TRANSP, 0)
    z.add_flag(lv.obj.FLAG.CLICKABLE)
    k.on(z, fn)
    return z


def _tile(scr):
    b = k.box(scr, 0, 0, TW, TH, t.SURFACE, R, t.SURFACE, 2)
    d = {"box": b, "mac": None}
    pick = _zone(b, 2, 6, 44, 44, lambda: _toggle(d))
    av = k.box(pick, 4, 4, 36, 36, GREY, t.R_PILL, RING, 2)
    im = k.icon(av, "wand_18", t.INK_3, align=lv.ALIGN.CENTER)
    gl = k.text(av, "", t.SURFACE, k.F16, align=lv.ALIGN.CENTER)
    z = _zone(b, 50, 0, TW - 54, TH - 4, lambda: _find(d))
    name = k.slot(z, 0, 9, TW - 58, t.INK, k.F_BODY)
    bars = [k.box(z, x, 33 + y, 4, h, t.BORDER, 1) for x, y, h in ((1, 9, 5), (7, 5, 9), (13, 1, 13))]
    miss = k.text(z, lv.SYMBOL.CLOSE, t.DANGER[0], F12, 2, 32)
    blink = k.row(z, 4)
    blink.set_pos(0, 32)
    k.icon(blink, "blink_14", t.PURPLE)
    k.text(blink, "Blinking", t.PURPLE, F12)
    bat = k.box(z, 24, 34, 60, 14, t.SURFACE)
    bat.set_style_bg_opa(lv.OPA.TRANSP, 0)
    shell = k.box(bat, 0, 1, 19, 12, t.SURFACE, 3, t.TEAL_DARK, 2)
    shell.set_style_bg_opa(lv.OPA.TRANSP, 0)
    fill = k.box(shell, 3, 3, 13, 6, t.TEAL_DARK, 1)
    nub = k.box(bat, 19, 4, 2, 6, t.TEAL_DARK, 1)
    pct = k.text(bat, "", t.TEAL_DARK, F12, 24, 0)
    d.update({"av": av, "im": im, "gl": gl, "name": name, "bars": bars, "miss": miss, "bat": bat,
              "shell": shell, "fill": fill, "nub": nub, "pct": pct, "blink": blink})
    _tiles.append(d)


def _head(scr):
    b = k.box(scr, AREA_X, 0, AREA_W, 56, t.SURFACE, 12)
    chev = k.box(b, 4, 4, 48, 48, t.SURFACE, 12, t.BORDER, 2)
    mark = k.text(chev, lv.SYMBOL.DOWN, t.INK_3, k.F16, align=lv.ALIGN.CENTER)
    r = k.row(b, 10)
    r.align(lv.ALIGN.LEFT_MID, 62, 0)
    title = k.text(r, "", t.INK, k.F16)
    n = k.pill(r, "0", t.INK_3, GREY, py=2)
    h = {"box": b, "mark": mark, "title": title, "n": k.lbl(n), "key": None, "geo": None}
    b.add_flag(lv.obj.FLAG.CLICKABLE)
    k.on(b, lambda: h["key"] and _fold(h["key"]))
    _heads.append(h)


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
    P = panel.P
    if d["mac"]:
        until = time.ticks_add(time.ticks_ms(), FIND_MS)
        _finding[d["mac"]] = until
        if P.wake is None or time.ticks_diff(until, P.wake) < 0:
            P.wake = until          # redraw when Blinking ends
        P.act(P.find, d["mac"])
        refresh()


def _fold(key):
    _w["open"][key] = not _w["open"][key]
    refresh()


def _page(n):
    _w["page"] = max(0, _w["page"] + n)
    refresh()


def _save():
    P = panel.P
    if not P.picked:
        return          # Save is disabled with nothing picked
    if P.pick_mode == "edit":
        P.act(P.update_group)
        return
    import kbd
    kbd.open("", "", 20, lambda s: P.act(P.save_group, s))


def _delete():
    P = panel.P
    P.act(P.delete_group, P.edit_name)


def build():
    scr = k.new_screen()
    hd, _w["title"], _ = k.header(scr, "New group", k.back,
                                  f"Tap the circle to add{k.DOT}tap the name to find", 560)
    rc = k.button(hd, k.W - 16 - 44, 10, 44, "", t.TEAL_DARK, "roll_call_18", px=12, w=44)
    k.on(rc, lambda: panel.P.act(panel.P.roll_call))
    _w["rc"] = rc
    for _ in _SECTIONS:
        _head(scr)
    for _ in range(POOL):
        _tile(scr)
    _w["rail"] = k.rail(scr, k.W - 12 - 52, AREA_Y + 4, AREA_H - 8, lambda: _page(-1), lambda: _page(1))
    _w["empty"] = k.text(scr, "No devices yet. Tap Roll call.", t.MUTED, k.F_BODY, 16, 96)

    ft = k.box(scr, 0, FOOT_Y, k.W, k.H - FOOT_Y, t.SURFACE)
    k.box(scr, 0, FOOT_Y, k.W, 1, t.BORDER)
    _w["picked"] = k.slot(ft, 16, 27, 200, t.INK, k.F_HEAD)
    sv = k.button(ft, k.W - 16 - 170, 10, 52, "Save group", t.SURFACE, primary=True, w=170, font=k.F_HEAD)
    k.on(sv, _save)
    _w["save"] = sv
    es = k.button(ft, k.W - 16 - 120, 10, 52, "Save", t.SURFACE, primary=True, w=120, font=k.F_HEAD)
    k.on(es, _save)
    _w["esave"] = es
    dl = k.button(ft, k.W - 16 - 120 - 10 - 170, 10, 52, "Delete group", t.DANGER[0], "trash_18",
                  font=k.F_BODY, w=170)
    dl.set_style_border_color(k.c(0xF3C5C0), 0)
    k.on(dl, _delete)
    _w["del"] = dl
    return scr


def _lines(P):
    """The list as lines: ("h", key, title, count) headers and ("r", [entries]) tile rows.
    Empty sections are left out."""
    groups = {"wands": [], "stations": [], "other": []}
    for e in P.roster.items():
        groups[P.roster.section(e)].append(e)
    out = []
    for key, title in _SECTIONS:
        es = groups[key]
        if not es:
            continue
        out.append(("h", key, title, len(es)))
        if _w["open"][key]:
            for i in range(0, len(es), COLS):
                out.append(("r", es[i:i + COLS]))
    return out


def _gap(prev, ln):
    return TGAP if prev == "r" and ln[0] == "r" else GAP


def _pages(lines):
    """Start index of each page: as many lines as fit in the area."""
    starts = [0]
    y = 0
    prev = None
    for i, ln in enumerate(lines):
        h = 56 if ln[0] == "h" else TH
        g = _gap(prev, ln) if y else 0
        if y and y + g + h > AREA_H:
            starts.append(i)
            y = 0
            g = 0
        y += g + h
        prev = ln[0]
    return starts


def _place(o, cache, x, y):
    if cache.get("geo") != (x, y):
        cache["geo"] = (x, y)
        o.set_pos(x, AREA_Y + y)


def _bat_level(b):
    if b < 10:
        return "critical"
    if b < 20:
        return "low"
    return "medium" if b < 60 else "high"


def _sig(rssi):
    if rssi is None:
        return 0
    return 3 if rssi > -60 else (2 if rssi > -75 else 1)


def _fill(P, d, e):
    mac = e["mac"]
    sec = P.roster.section(e)
    heard = e["seen"] is not None and (e["heard"] or P.last_call is None)
    picked = mac in P.picked
    b = e["battery"]
    lvl = _bat_level(b) if b is not None and heard else None
    k.st(d["name"], P.roster.name(mac))
    k.sty(d["name"], "text", MISS if not heard else (t.DANGER[0] if lvl == "critical" else
                                                    (t.WARN[0] if lvl == "low" else t.INK)))
    finding = mac in _finding
    bg = t.PINK_50 if picked else t.SURFACE
    k.sty(d["box"], "bg", bg)
    k.sty(d["box"], "border", t.PURPLE if finding else bg)
    k.sty(d["av"], "border", t.PINK if picked else RING)
    k.show_hide(d["blink"], finding)
    # avatar: pink check when picked, else the kind's icon ("?" for unknown)
    look = "pick" if picked else sec
    if d.get("look") != look:
        d["look"] = look
        img = look in ("wands", "stations")
        k.show_hide(d["im"], img)
        k.show_hide(d["gl"], not img)
        if img:
            d["im"].set_src(k._icon_src("wand_18" if look == "wands" else "station_face_20"))
            d["im"].set_style_image_recolor(k.c(t.TEAL_DARK if look == "stations" else t.INK_3), 0)
        k.st(d["gl"], lv.SYMBOL.OK if picked else "?")
    stn = look == "stations"
    k.sty(d["av"], "bg", t.PINK if picked else (t.TEAL_50 if stn else GREY))
    k.sty(d["gl"], "text", t.SURFACE if picked else t.INK_3)
    op = lv.OPA.COVER if heard else 115
    if d.get("op") != op:
        d["op"] = op
        d["av"].set_style_opa(op, 0)
    n = _sig(e["rssi"]) if heard else 0
    for i, bar in enumerate(d["bars"]):
        k.sty(bar, "bg", t.TEAL_DARK if i < n else t.BORDER)
    for bar in d["bars"]:
        k.show_hide(bar, not finding)
    k.show_hide(d["miss"], not heard and not finding)
    k.show_hide(d["bat"], lvl is not None and not finding)
    if lvl is not None:
        col, fw = _BAT[lvl]
        k.sty(d["shell"], "border", col)
        k.sty(d["fill"], "bg", col)
        k.sty(d["nub"], "bg", col)
        k.sty(d["pct"], "text", col)
        k.st(d["pct"], f"{b}%")
        if d.get("fw") != fw:
            d["fw"] = fw
            d["fill"].set_width(fw)


def refresh():
    P = panel.P
    now = time.ticks_ms()
    for mac in [m for m, u in _finding.items() if time.ticks_diff(now, u) >= 0]:
        del _finding[mac]
    lines = _lines(P)
    starts = _pages(lines)
    _w["page"] = min(_w["page"], len(starts) - 1)
    first = starts[_w["page"]]
    last = starts[_w["page"] + 1] if _w["page"] + 1 < len(starts) else len(lines)
    _w["rail"](_w["page"], len(starts))
    y = 0
    hi = ti = 0
    prev = None
    for ln in lines[first:last]:
        if y:
            y += _gap(prev, ln)
        prev = ln[0]
        if ln[0] == "h":
            h = _heads[hi]
            hi += 1
            h["key"] = ln[1]
            k.show_hide(h["box"], True)
            _place(h["box"], h, AREA_X, y)
            k.st(h["title"], ln[2])
            k.st(h["n"], str(ln[3]))
            k.st(h["mark"], lv.SYMBOL.DOWN if _w["open"][ln[1]] else lv.SYMBOL.RIGHT)
            y += 56
            continue
        for c, e in enumerate(ln[1]):
            if ti >= POOL:
                break
            d = _tiles[ti]
            ti += 1
            d["mac"] = e["mac"]
            k.show_hide(d["box"], True)
            _place(d["box"], d, AREA_X + c * (TW + TGAP), y)
            _fill(P, d, e)
        y += TH
    for h in _heads[hi:]:
        h["key"] = None
        k.show_hide(h["box"], False)
    for d in _tiles[ti:]:
        d["mac"] = None
        k.show_hide(d["box"], False)
    k.show_hide(_w["empty"], not P.roster.d)
    k.busy(_w["rc"], P.rolling())
    n = len(P.picked)
    k.st(_w["picked"], f"{n} picked")
    edit = P.pick_mode == "edit"
    k.st(_w["title"], P.edit_name if edit else "New group")
    k.show_hide(_w["save"], not edit)
    k.show_hide(_w["esave"], edit)
    k.show_hide(_w["del"], edit)
    k.set_enabled(_w["save"], n > 0)
    k.set_enabled(_w["esave"], n > 0)
