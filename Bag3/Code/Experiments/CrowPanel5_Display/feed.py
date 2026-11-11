"""Chat feed for home (1) and the group chat (1B): a fixed pool of slots, newest at the bottom.

Each slot holds every bubble kind (a note, a sent command, a device's reply); fill shows the one
in use. Sent commands only: no roll-call summary, error rows or busy bubble.
"""

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
    s["mine_roll"] = k.icon(s["mine_ic"], "roll_call_18", t.SURFACE, align=lv.ALIGN.CENTER)
    s["mine_bub"] = bub
    s["mine_t"] = k.text(bub, "", t.SURFACE, F16)
    s["mine_s"] = k.text(mine, "", t.TEAL_DARK, F12)
    s["mine"] = mine.get_parent()
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
    for name in ("note", "rep", "mine"):
        k.show_hide(s[name], ty == name)
    if ty == "note":
        k.st(s["note_t"], e["text"])
        k.st(s["note_b"], e.get("b", ""))
    elif ty == "rep":
        k.st(s["rep_t"], e["text"])
        k.sty(s["rep_t"], "text", t.WARN[0] if e.get("warn") else t.INK)
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


def fill(slots, log):
    """Show the newest entries of log (the current chat's) in the slots, oldest at the top."""
    log = [e for e in log if e["t"] in ("note", "mine", "reply")][-len(slots):]
    off = len(slots) - len(log)
    for i, s in enumerate(slots):
        _fill(s, log[i - off] if i >= off else None)
