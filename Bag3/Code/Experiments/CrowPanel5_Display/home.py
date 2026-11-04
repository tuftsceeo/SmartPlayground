"""Home screen (1 - Playground chat) for the 800x480 CrowPanel.

Layout follows the Main design board. Content comes from panel.P.
"""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12, F14, F16, R, H, GREY

SIDE_W = 232
HEAD_H = 64
FOOT_H = 78
MAIN_W = k.W - SIDE_W
POOL = 6

_rows = []
_w = {}


def _chat_row(side, y):
    row = k.box(side, 8, y, SIDE_W - 16, 60, t.SURFACE, R)
    row.set_style_bg_color(k.c(t.BG), lv.STATE.PRESSED)
    av = k.box(row, 10, 10, 40, 40, t.PURPLE_50, t.R_PILL)
    ic = k.icon(av, "everyone_20", t.SURFACE, align=lv.ALIGN.CENTER)
    stn = k.icon(av, "station_face_20", t.TEAL_DARK, align=lv.ALIGN.CENTER)
    gl = k.text(av, "", t.PURPLE, F14, align=lv.ALIGN.CENTER)
    title = k.slot(row, 60, 11, SIDE_W - 92, t.INK, k.F_BODY)
    sub = k.slot(row, 60, 32, SIDE_W - 92, t.INK_3, F12)
    r = {"row": row, "av": av, "ic": ic, "stn": stn, "gl": gl, "title": title, "sub": sub, "data": None}
    k.on(row, lambda: _pick(r))
    _rows.append(r)


def _pick(r):
    d = r["data"]
    if d is None:
        return
    P = panel.P
    P.set_target(d["kind"], d["name"], d["macs"])
    if d["kind"] == "one":
        k.go("scr_device")


def _sidebar(scr):
    side = k.box(scr, 0, 0, SIDE_W, H, t.SURFACE)
    k.box(scr, SIDE_W - 1, 0, 1, H, t.BORDER)
    k.text(side, "Playground", t.INK, k.F_HEAD, 16, 22)
    radar = k.button(side, SIDE_W - 60, 10, 44, "", t.PURPLE, "radar_20", px=12, w=44)
    k.on(radar, lambda: panel.P.act(panel.P.roll_call))
    for i in range(4):
        _chat_row(side, 66 + 62 * i)
    new = k.box(side, 8, 318, SIDE_W - 16, 44, t.SURFACE, R, t.BORDER)
    r = k.row(new)
    r.center()
    k.icon(r, "plus_16", t.PURPLE)
    k.text(r, "New group", t.PURPLE, F12)
    k.on(new, lambda: _open_list("group"))

    k.box(side, 0, H - 70, SIDE_W - 1, 1, GREY)
    link = k.pill(side, "ChatBroadcast linked", t.SERVE[0], t.SERVE[1], radius=t.R_PILL, px=10, py=6)
    link.set_style_pad_column(6, 0)
    k.icon(link, "plug_14", t.SERVE[0]).move_to_index(0)
    link.set_pos(12, H - 60)
    k.on(link, lambda: k.go("scr_linked"))
    _w["link"] = link
    _w["radio_ic"] = k.radio_icon(side, 12, H - 26)
    _w["radio"] = k.slot(side, 38, H - 24, 150, t.INK_3, F12, "Radio on")


def _header(scr):
    hd = k.box(scr, SIDE_W, 0, MAIN_W, HEAD_H, t.SURFACE)
    k.box(scr, SIDE_W, HEAD_H - 1, MAIN_W, 1, t.BORDER)
    _w["title"] = k.slot(hd, 16, 12, 260, t.INK, F16)
    _w["sub"] = k.slot(hd, 16, 36, 260, t.INK_3, F12)
    x = MAIN_W - 16
    for label, fg, ic, fn in (("NFC Tags", t.PURPLE, "cards_18", lambda: k.go("scr_tags_home")),
                              ("Find", t.INK_3, "find_18", lambda: panel.P.act(panel.P.find_all)),
                              ("Roll call", t.TEAL_DARK, "roll_call_18", lambda: panel.P.act(panel.P.roll_call))):
        b = k.button(hd, 0, 10, 44, label, fg, ic)
        b.update_layout()
        x -= b.get_width()
        b.set_x(x)
        x -= 12
        k.on(b, fn)


def _open_list(mode):
    panel.P.pick_mode = mode
    panel.P.picked = [] if mode == "group" else list(panel.P.target["macs"] or [])
    k.go("scr_recipients")


def _slot(area):
    """One chat-log slot holding every bubble kind; refresh shows the one in use."""
    s = {}
    note = k.pill(k.line(area, lv.FLEX_ALIGN.CENTER), "", t.INK_3, GREY, radius=t.R_PILL, px=12, py=6)
    note.set_style_pad_column(6, 0)
    k.icon(note, "sparkle_14", t.PURPLE).move_to_index(0)
    s["note_b"] = k.text(note, "", t.INK, F12)
    s["note"] = note.get_parent()
    s["note_t"] = k.lbl(note)

    rep = k.plain(lv.obj(area))
    rep.set_size(lv.SIZE_CONTENT, lv.SIZE_CONTENT)
    rep.set_style_bg_color(k.c(t.SURFACE), 0)
    rep.set_style_border_width(2, 0)
    rep.set_style_border_color(k.c(t.BORDER), 0)
    rep.set_style_radius(R, 0)
    rep.set_style_pad_hor(12, 0)
    rep.set_style_pad_ver(10, 0)
    rep.set_style_pad_row(8, 0)
    rep.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    top = k.row(rep, 8)
    spin = lv.spinner(top)
    spin.set_size(18, 18)
    spin.set_anim_params(1000, 200)
    spin.set_style_arc_width(3, 0)
    spin.set_style_arc_width(3, lv.PART.INDICATOR)
    spin.set_style_arc_color(k.c(t.BORDER), 0)
    spin.set_style_arc_color(k.c(t.TEAL), lv.PART.INDICATOR)
    s["spin"] = spin
    s["rep_t"] = k.text(top, "", t.INK, F14)
    chips = k.row(rep, 6)
    s["c_ready"] = k.lbl(k.pill(chips, "", t.SERVE[0], t.SERVE[1]))
    s["c_low"] = k.lbl(k.pill(chips, "", t.WARN[0], t.WARN[1]))
    s["c_stn"] = k.lbl(k.pill(chips, "", t.INK_3, GREY))
    see = k.text(rep, f"See list{k.ARROW}", t.PURPLE, F12)
    see.set_style_pad_ver(8, 0)
    see.set_style_pad_right(24, 0)
    see.set_ext_click_area(8)
    k.on(see, lambda: _open_list("chat"))
    s["see"] = see
    s["chips"] = chips
    s["rep"] = rep

    mine = k.plain(lv.obj(k.line(area, lv.FLEX_ALIGN.END)))
    mine.set_size(lv.SIZE_CONTENT, lv.SIZE_CONTENT)
    mine.set_style_bg_opa(lv.OPA.TRANSP, 0)
    mine.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    mine.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.END, lv.FLEX_ALIGN.END)
    mine.set_style_pad_row(4, 0)
    bub = k.row(mine, 10)
    k.grad(bub)
    bub.set_style_bg_opa(lv.OPA.COVER, 0)
    bub.set_style_radius(R, 0)
    bub.set_style_pad_hor(14, 0)
    bub.set_style_pad_ver(10, 0)
    s["mine_ic"] = k.box(bub, 0, 0, 28, 28, 0xBF75C9, 8)
    s["mine_note"] = k.icon(s["mine_ic"], "music_note_16", t.SURFACE, align=lv.ALIGN.CENTER)
    s["mine_stop"] = k.icon(s["mine_ic"], "stop_20", t.SURFACE, align=lv.ALIGN.CENTER)
    s["mine_find"] = k.icon(s["mine_ic"], "find_18", t.SURFACE, align=lv.ALIGN.CENTER)
    s["mine_roll"] = k.icon(s["mine_ic"], "roll_call_18", t.SURFACE, align=lv.ALIGN.CENTER)
    s["mine_bub"] = bub
    s["mine_t"] = k.text(bub, "", t.SURFACE, F16)
    s["mine_s"] = k.text(mine, "", t.TEAL_DARK, F12)
    s["mine"] = mine.get_parent()

    err = k.row(area, 10)
    err.set_style_bg_color(k.c(t.DANGER[1]), 0)
    err.set_style_bg_opa(lv.OPA.COVER, 0)
    err.set_style_radius(R, 0)
    err.set_style_pad_hor(12, 0)
    err.set_style_pad_ver(8, 0)
    s["err_t"] = k.text(err, "", t.INK, F14)
    b = k.button(err, 0, 0, 36, "Try again", t.DANGER[0], font=F14, px=12)
    b.set_style_radius(12, 0)
    s["err"] = err
    s["entry"] = None

    def again():
        e = s["entry"]
        if e and e.get("retry"):
            fn = e["retry"][0]
            panel.P.act(fn, *e["retry"][1:])
    k.on(b, again)
    return s


def _chat(scr):
    area = k.plain(lv.obj(scr))
    area.set_pos(SIDE_W, HEAD_H)
    area.set_size(MAIN_W, H - HEAD_H - FOOT_H)
    area.set_style_bg_opa(lv.OPA.TRANSP, 0)
    area.set_style_radius(0, 0)
    area.set_style_pad_hor(16, 0)
    area.set_style_pad_ver(12, 0)
    area.set_style_pad_row(10, 0)
    area.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    area.set_flex_align(lv.FLEX_ALIGN.END, lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START)
    _w["slots"] = [_slot(area) for _ in range(POOL)]
    _w["empty"] = k.text(scr, "Nothing sent yet. Try Roll call.", t.MUTED, F14, SIDE_W + 16, HEAD_H + 16)


def _footer(scr):
    ft = k.box(scr, SIDE_W, H - FOOT_H, MAIN_W, FOOT_H, t.SURFACE)
    k.box(scr, SIDE_W, H - FOOT_H, MAIN_W, 1, t.BORDER)
    start = k.button(ft, 16, 11, 56, "Start a game", t.SURFACE, "play_20", font=F16, px=20, primary=True)
    start.update_layout()
    code = k.button(ft, 16 + start.get_width() + 10, 11, 56, "Send code", t.PURPLE, "code_20", font=F16, px=16)
    stop = k.button(ft, 0, 11, 56, "Stop", t.INK, "stop_20", t.DANGER[0], F16, px=20)
    stop.update_layout()
    stop.set_x(MAIN_W - 16 - stop.get_width())
    k.on(start, lambda: _games("start"))
    k.on(code, lambda: _games("code"))
    k.on(stop, lambda: panel.P.act(panel.P.stop))


def _games(mode):
    import scr_games
    scr_games.open(mode)


def build():
    scr = k.new_screen()
    _sidebar(scr)
    _header(scr)
    _chat(scr)
    _footer(scr)
    return scr


def _fill(s, e):
    # mine: what the teacher sent (right); rep and reply: what devices said (left)
    ty = None if e is None else ("rep" if e["t"] == "reply" else e["t"])
    for name in ("note", "rep", "mine", "err"):
        k.show_hide(s[name], ty == name)
    s["entry"] = e
    if e is None:
        return
    if ty == "note":
        k.st(s["note_t"], e["text"])
        k.st(s["note_b"], e.get("b", ""))
    elif e["t"] == "reply":
        k.st(s["rep_t"], e["text"])
        k.sty(s["rep_t"], "text", t.WARN[0] if e.get("warn") else (t.INK_3 if e.get("busy") else t.INK))
        k.show_hide(s["spin"], bool(e.get("busy")))
        k.show_hide(s["chips"], False)
        k.show_hide(s["see"], False)
    elif ty == "rep":
        n = e["n"]
        k.sty(s["rep_t"], "text", t.INK)
        k.show_hide(s["spin"], False)
        k.show_hide(s["see"], True)
        k.st(s["rep_t"], "No one answered - is the radio on and are wands awake?" if n == 0
             else ("1 device answered" if n == 1 else f"{n} devices answered"))
        k.show_hide(s["chips"], n > 0)
        k.st(s["c_ready"], f"{e['ready']} ready")
        k.st(s["c_low"], f"{e['low']} low battery")
        k.st(s["c_stn"], f"{e['stn']} stations")
    elif ty == "mine":
        k.st(s["mine_t"], e["text"])
        k.sty(s["mine_ic"], "bg", e.get("color", 0xBF75C9))
        stop = e["text"] == "Stop"
        ic = e.get("icon")
        k.show_hide(s["mine_note"], not stop and ic is None)
        k.show_hide(s["mine_stop"], stop)
        k.show_hide(s["mine_find"], ic == "find")
        k.show_hide(s["mine_roll"], ic == "roll")
        if stop:
            s["mine_bub"].set_style_bg_grad_dir(lv.GRAD_DIR.NONE, 0)
            k.sty(s["mine_bub"], "bg", GREY)
        else:
            k.grad(s["mine_bub"])
        k.sty(s["mine_t"], "text", t.INK if stop else t.SURFACE)
        k.st(s["mine_s"], panel.P.mine_sub(e))
    else:
        k.st(s["err_t"], e["text"])


def refresh():
    P = panel.P
    rows = P.chat_rows()
    for i, r in enumerate(_rows):
        d = rows[i] if i < len(rows) else None
        r["data"] = d
        k.show_hide(r["row"], d is not None)
        if d is None:
            continue
        active = d["kind"] == P.target["kind"] and d["name"] == P.target["name"]
        k.sty(r["row"], "bg", t.PINK_50 if active else t.SURFACE)
        k.st(r["title"], d["title"])
        k.st(r["sub"], d["sub"])
        k.sty(r["sub"], "text", t.WARN[0] if d["warn"] else t.INK_3)
        station = d["glyph"] == "@station_face_20"
        k.show_hide(r["ic"], d["kind"] == "all")
        k.show_hide(r["stn"], station)
        k.st(r["gl"], "" if d["glyph"].startswith("@") else d["glyph"])
        if d["kind"] == "all":
            k.grad(r["av"])
        else:
            r["av"].set_style_bg_grad_dir(lv.GRAD_DIR.NONE, 0)
            group = d["kind"] == "group"
            k.sty(r["av"], "bg", t.PURPLE_50 if group else (t.TEAL_50 if station else GREY))
            k.sty(r["gl"], "text", t.PURPLE if group else t.INK_3)
    k.st(_w["title"], P.target["name"])
    if P.fleet is not None and P.fleet.scanning:
        k.st(_w["sub"], "Roll call - listening...")
    elif P.last_call:
        k.st(_w["sub"], P.answered())
    else:
        k.st(_w["sub"], P.count_text())
    log = P.log()
    if P.fleet is not None and P.fleet.scanning:
        # roll call still listening: a busy bubble until the answers are in
        log = log + [{"t": "reply", "text": "", "busy": True}]
    log = log[-POOL:]
    off = POOL - len(log)
    for i, s in enumerate(_w["slots"]):
        _fill(s, log[i - off] if i >= off else None)
    k.show_hide(_w["empty"], not log)
    k.show_hide(_w["link"], P.host is not None and P.host.linked)
    k.st(_w["radio"], "Radio on" if P.radio else "Radio paused")
    _w["radio_ic"](P.radio)
