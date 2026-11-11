"""Screen 7 - Plugged into a computer: 7.1/7.2 Connecting until ChatBroadcast links, and 7.3
Update needed when ChatBroadcast speaks a different link protocol (host.mismatch)."""

import lvgl as lv

import ds_tokens as t
import panel
import ui_kit as k
from ui_kit import F12

_w = {}


def build():
    scr = k.new_screen()
    x = 316
    ok = k.box(scr, 56, 130, 220, 220, t.TEAL_50, 24)
    k.icon(ok, "computer_link_120", t.TEAL_DARK, align=lv.ALIGN.CENTER)
    bad = k.box(scr, 56, 130, 220, 220, t.DANGER[1], 24)
    k.icon(bad, "update_88", t.DANGER[0], align=lv.ALIGN.CENTER)
    _w["tiles"] = (ok, bad)
    _w["title"] = k.text(scr, "Connecting", t.INK, k.F_TITLE, x, 174)
    _w["dot"] = k.box(scr, x, 214, 10, 10, t.TEAL, t.R_PILL)
    _w["state"] = k.text(scr, "Waiting...", t.INK_3, F12, x + 20, 212)
    # quiet way back to the panel's own screens when the computer keeps talking
    ch = k.button(scr, x, 256, 52, "Just charge", t.INK_3, font=k.F_BODY, w=150)
    k.on(ch, lambda: panel.P.act(panel.P.host.release))
    again = k.button(scr, x + 162, 256, 52, "Try again", t.SURFACE, font=k.F_BODY, primary="purple", w=170)
    k.on(again, lambda: panel.P.act(panel.P.host.retry))
    _w["again"] = again
    return scr


def refresh():
    h = panel.P.host
    bad = h is not None and h.mismatch
    ok_t, bad_t = _w["tiles"]
    k.show_hide(ok_t, not bad)
    k.show_hide(bad_t, bad)
    k.show_hide(_w["again"], bad)
    k.st(_w["title"], "Update needed" if bad else "Connecting")
    k.st(_w["state"], "Not connected" if bad else "Waiting...")
    k.sty(_w["state"], "text", t.DANGER[0] if bad else t.INK_3)
    k.sty(_w["dot"], "bg", t.DANGER[0] if bad else t.TEAL)
