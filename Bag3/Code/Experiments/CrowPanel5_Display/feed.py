"""Chat feed for home (1) and the group chat (1B): a fixed pool of slots, newest at the bottom.

Each slot holds every bubble kind (a note, a sent command, a device's reply, a roll call's
answer); fill shows the one in use. Sent commands: a game (pink), Send code (purple, with how many
wands have it) and Roll call (white). A roll call's answer reads like "someone is typing" while it
runs (1C: wand count and three dots) and becomes the playground's reply when it ends (1D: N Wands,
M Stations, expand icon). No error rows or busy bubble.
"""

import time


import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12, F14, F16, R, GREY

POOL = 6


def _slot(area):
    s = {}
    note = k.pill(k.line(area, lv.FLEX_ALIGN.CENTER), "", t.INK_3, GREY, radius=t.R_PILL, px=12, py=6)
    note.set_style_pad_column(6, 0)
    k.icon(note, "sparkle_14", t.PURPLE).move_to_index(0)
    s["note_b"] = k.text(note, "", t.INK, F12)
    s["note"] = note.get_parent()
    s["note_t"] = k.lbl(note)

    rep, s["rep_t"], _ = k.bubble(area, False)
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
    s["mine_code"] = k.icon(bub, "code_20", t.SURFACE)
    s["mine_rc"] = k.icon(bub, "roll_call_18", t.TEAL_DARK)
    s["mine_bub"] = bub
    s["mine_t"] = k.text(bub, "", t.SURFACE, F16)
    sub = k.row(mine, 4)
    s["mine_w"] = k.icon(sub, "wand_18", t.TEAL_DARK)
    s["mine_n"] = k.text(sub, "", t.TEAL_DARK, F12)
    s["mine_s"] = k.text(sub, "", t.TEAL_DARK, F12)
    s["mine"] = mine.get_parent()

    rc = k.row(k.line(area, lv.FLEX_ALIGN.START), 10)
    rc.set_style_bg_opa(lv.OPA.COVER, 0)
    rc.set_style_bg_color(k.c(t.SURFACE), 0)
    rc.set_style_border_width(2, 0)
    rc.set_style_border_color(k.c(t.BORDER), 0)
    rc.set_style_radius(R, 0)
    rc.set_style_pad_hor(14, 0)
    rc.set_style_pad_ver(10, 0)
    s["rc_w"] = k.icon(rc, "wand_18", t.TEAL_DARK)
    s["rc_n"] = k.text(rc, "", t.TEAL_DARK, F16)
    dots = k.row(rc, 4)
    s["rc_dots"] = dots
    s["rc_d"] = [k.box(dots, 0, 0, 8, 8, t.TEAL_DARK, 4) for _ in range(3)]
    col = k.plain(lv.obj(rc))
    col.set_size(lv.SIZE_CONTENT, lv.SIZE_CONTENT)
    col.set_style_bg_opa(lv.OPA.TRANSP, 0)
    col.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    col.set_style_pad_row(2, 0)
    s["rc_col"] = col
    s["rc_wands"] = k.text(col, "", t.TEAL_DARK, F16)
    s["rc_stns"] = k.text(col, "", t.INK, F16)
    s["rc_exp"] = k.box(rc, 0, 0, 36, 36, GREY, 10)
    k.icon(s["rc_exp"], "expand_18", t.PURPLE, align=lv.ALIGN.CENTER)
    s["rc"] = rc.get_parent()

    return s


def build(scr, x, y, w, h):
    area = k.plain(lv.obj(scr))
    area.set_pos(x, y)
    area.set_size(w, h)
    area.set_style_bg_opa(lv.OPA.TRANSP, 0)
    area.set_style_radius(0, 0)
    area.set_style_pad_hor(16, 0)
    area.set_style_pad_ver(12, 0)
    area.set_style_pad_row(10, 0)
    area.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    area.set_flex_align(lv.FLEX_ALIGN.END, lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START)
    return [_slot(area) for _ in range(POOL)]


def _fill(s, e):
    ty = None if e is None else ("rep" if e["t"] == "reply" else e["t"])
    for name in ("note", "rep", "mine", "rc"):
        k.show_hide(s[name], ty == name)
    if ty == "note":
        k.st(s["note_t"], e["text"])
        k.st(s["note_b"], e.get("b", ""))
    elif ty == "rep":
        k.st(s["rep_t"], e["text"])
        k.sty(s["rep_t"], "text", t.WARN[0] if e.get("warn") else t.INK)
    elif ty == "mine":
        _mine(s, e)
    elif ty == "rc":
        _rc(s, e)


def _mine(s, e):
    k.st(s["mine_t"], e["text"])
    k.sty(s["mine_ic"], "bg", e.get("color", 0xBF75C9))
    stop = e["text"] == "Stop"
    ic = e.get("icon")
    k.show_hide(s["mine_ic"], ic not in ("code", "roll"))
    k.show_hide(s["mine_note"], not stop and ic is None)
    k.show_hide(s["mine_stop"], stop)
    k.show_hide(s["mine_find"], ic == "find")
    k.show_hide(s["mine_code"], ic == "code")
    k.show_hide(s["mine_rc"], ic == "roll")
    look = "stop" if stop else (ic if ic in ("code", "roll") else "game")
    if s.get("look") != look:      # styles set directly, so only when the look changes
        s["look"] = look
        b = s["mine_bub"]
        if look in ("stop", "roll"):
            b.set_style_bg_grad_dir(lv.GRAD_DIR.NONE, 0)
            b.set_style_bg_color(k.c(GREY if stop else t.SURFACE), 0)
        elif look == "code":
            k.grad(b, t.PURPLE, 0x5A3DB8)
        else:
            k.grad(b)
        b.set_style_border_width(2 if look == "roll" else 0, 0)
        b.set_style_border_color(k.c(t.BORDER), 0)
    k.sty(s["mine_t"], "text", t.INK if stop or ic == "roll" else t.SURFACE)
    d = e.get("dist") if ic == "code" else None
    n = None if d is None else sum(1 for v in d["state"].values() if v == "has")
    k.show_hide(s["mine_w"], bool(n))
    k.st(s["mine_n"], str(n) if n else "")
    k.st(s["mine_s"], panel.P.mine_sub(e))
    k.sty(s["mine_s"], "text", t.INK_3 if ic in ("code", "roll") else t.TEAL_DARK)


def _rc(s, e):
    run = e["run"]
    for o in (s["rc_w"], s["rc_n"], s["rc_dots"]):
        k.show_hide(o, run)
    for o in (s["rc_col"], s["rc_exp"]):
        k.show_hide(o, not run)
    if run:
        k.st(s["rc_n"], str(panel.P.heard_counts(e["macs"])[0]))
        on = (time.ticks_ms() // 400) % 3
        for i, d in enumerate(s["rc_d"]):
            k.sty(d, "bg", t.TEAL_DARK if i == on else 0xA4DDD2)
    else:
        k.st(s["rc_wands"], f"{e['w']} Wands")
        k.st(s["rc_stns"], f"{e['s']} Stations")


def fill(slots, log):
    """Show the newest entries of log (the current chat's) in the slots, oldest at the top."""
    log = [e for e in log if e["t"] in ("note", "mine", "reply", "rc")][-len(slots):]
    off = len(slots) - len(log)
    for i, s in enumerate(slots):
        _fill(s, log[i - off] if i >= off else None)
