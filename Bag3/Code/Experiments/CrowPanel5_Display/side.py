"""Left column shared by home (1), the group chat (1B) and the NFC screens (5).

Messages / Tags toggle on top. Messages: the menu (1F: Roll call, Manage groups, History / Undo,
Shutdown), wand and station counts, chat rows, New group.
Tags: the NFC screen's list (scr_cards fills it). Each screen builds its own column with
build(scr, mode) and redraws it with refresh(s) or fill(s, items); the row pool is fixed.
"""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12, R, H, GREY

W = 232
ROWS = 6
ROW_H = 60
_TOP = {"msg": 96, "tags": 74}
# mark -> (avatar bg, glyph color, glyph)
MARK = {"ok": (t.TEAL_50, t.TEAL_DARK, lv.SYMBOL.OK), "now": (None, t.SURFACE, lv.SYMBOL.RIGHT),
        "err": (t.DANGER[1], t.DANGER[0], "!"), "": (GREY, t.INK_3, "")}


def _row(s, side, y):
    row = k.box(side, 8, y, W - 16, ROW_H, t.SURFACE, R)
    row.set_style_bg_color(k.c(t.BG), lv.STATE.PRESSED)
    av = k.box(row, 10, 10, 40, 40, GREY, t.R_PILL)
    ics = {name: k.icon(av, name, t.SURFACE, align=lv.ALIGN.CENTER)
           for name in ("everyone_20", "station_face_20", "wand_20")}
    gl = k.text(av, "", t.PURPLE, k.F16, align=lv.ALIGN.CENTER)
    title = k.slot(row, 60, 20, W - 16 - 60 - 56, t.INK, k.F16)
    note = k.slot(row, W - 16 - 54, 22, 48, t.INK_3, F12)
    r = {"row": row, "av": av, "ics": ics, "gl": gl, "title": title, "note": note, "key": None}
    k.on(row, lambda: r["key"] is not None and s["pick"](r["key"]))
    s["rows"].append(r)


def build(scr, mode, pick=None, toggle=None):
    """mode: "msg" or "tags". pick(key) for a tapped row (Messages rows open chats by default);
    toggle(key) for the Messages / Tags switch."""
    side = k.box(scr, 0, 0, W, H, t.SURFACE)
    k.box(scr, W - 1, 0, 1, H, t.BORDER)
    s = {"mode": mode, "rows": [], "pick": pick or _open_chat, "y": None}
    _, s["seg"], _ = k.seg(side, 10, 12, (("msg", "Messages"), ("tags", "Tags")),
                           toggle or switch, 80, 44)
    s["seg"](mode)
    if mode == "msg":
        mb = k.button(side, W - 10 - 44, 16, 44, "", t.INK, px=0, w=44)     # hamburger
        for dy in (-6, 0, 6):
            k.box(mb, 0, 0, 20, 2, t.INK, 1).align(lv.ALIGN.CENTER, 0, dy)
        k.on(mb, _menu)
        k.icon(side, "wand_18", t.TEAL_DARK, 16, 70)
        s["nw"] = k.text(side, "", t.TEAL_DARK, k.F_BODY, 38, 70)
        k.icon(side, "station_face_20", t.INK_3, 84, 69)
        s["ns"] = k.text(side, "", t.INK_3, k.F_BODY, 108, 70)
    for i in range(ROWS if mode == "tags" else ROWS - 1):
        _row(s, side, _TOP[mode] + i * (ROW_H + 2))
    if mode == "msg":
        new = k.box(side, 8, 0, W - 16, 44, t.SURFACE, R, t.BORDER)
        r = k.row(new)
        r.center()
        k.icon(r, "plus_16", t.PURPLE)
        k.text(r, "New group", t.PURPLE, F12)
        k.on(new, new_group)
        s["new"] = new
    return s


def switch(key):
    """Messages / Tags from a Messages screen."""
    if key == "tags":
        import scr_cards
        scr_cards.start("games")
        k.go("scr_cards")


def _menu():
    import menu
    menu.open()


def roll_everyone():
    """The menu's Roll call is Everyone's: it opens that chat, where 1C shows it running."""
    P = panel.P
    if P.target["kind"] != "all":
        P.set_target("all", "Everyone")
    if k.cur != "home":
        k.home()
    P.act(P.roll_call)


def new_group():
    P = panel.P
    P.pick_mode = "group"
    P.picked = []
    k.go("scr_recipients")


def _open_chat(i):
    P = panel.P
    rows = P.chat_rows()
    if i >= len(rows):
        return
    d = rows[i]
    P.set_target(d["kind"], d["name"], d["macs"])
    if d["kind"] == "one":
        k.go("scr_device")
    elif d["kind"] == "group":
        P.act(P.open_group)
        if k.cur != "scr_group":
            k.home()
            k.go("scr_group")
    elif k.cur != "home":
        k.home()


def fill(s, items):
    """items: [(key, title, note, mark, row_bg)]: mark is a MARK key or (glyph or "@icon", bg, fg);
    row_bg is the row's fill, None for plain."""
    for i, r in enumerate(s["rows"]):
        it = items[i] if i < len(items) else None
        r["key"] = it[0] if it else None
        k.show_hide(r["row"], it is not None)
        if it is None:
            continue
        key, title, note, mark, sel = it
        k.st(r["title"], title)
        k.st(r["note"], note)
        k.sty(r["row"], "bg", sel or t.SURFACE)
        if isinstance(mark, tuple):
            glyph, bg, fg = mark
        else:
            bg, fg, glyph = MARK[mark]
        ic = glyph[1:] if glyph.startswith("@") else None
        for name, im in r["ics"].items():
            k.show_hide(im, name == ic)
            if name == ic and r.get("fg") != fg:
                r["fg"] = fg
                im.set_style_image_recolor(k.c(fg), 0)
        k.st(r["gl"], "" if ic else glyph)
        k.sty(r["gl"], "text", fg)
        if bg is None:
            k.grad(r["av"])
        else:
            r["av"].set_style_bg_grad_dir(lv.GRAD_DIR.NONE, 0)
            k.sty(r["av"], "bg", bg)
    if "new" in s:
        y = _TOP["msg"] + min(len(items), len(s["rows"])) * (ROW_H + 2) + 4
        if s["y"] != y:
            s["y"] = y
            s["new"].set_y(y)


def refresh(s):
    """Messages column: counts from the roster and the chat rows."""
    P = panel.P
    s["seg"](s["mode"])
    if s["mode"] != "msg":
        return
    r = P.roster
    k.st(s["nw"], str(len(r.items("wands"))))
    k.st(s["ns"], str(len(r.items("stations"))))
    items = []
    tg = P.target
    for i, d in enumerate(P.chat_rows()[:len(s["rows"])]):
        active = d["kind"] == tg["kind"] and d["name"] == tg["name"]
        kind = d["kind"]
        if kind == "all":
            mark = ("@everyone_20", None, t.SURFACE)
            sel = t.PINK_50 if active else None
        elif kind == "group":
            mark = (d["glyph"], t.SURFACE if active else t.PURPLE_50, t.PURPLE)
            sel = t.PURPLE_50 if active else None
        elif d["glyph"] == "@station_face_20":
            mark = (d["glyph"], t.TEAL_50, t.TEAL_DARK)
            sel = t.PINK_50 if active else None
        else:
            mark = ("@wand_20", t.WARN[1] if d["warn"] else GREY, t.WARN[0] if d["warn"] else t.INK_3)
            sel = t.PINK_50 if active else None
        items.append((i, d["title"], "", mark, sel))
    fill(s, items)
