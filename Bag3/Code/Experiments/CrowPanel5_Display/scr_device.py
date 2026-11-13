"""Screen 6 - One device: chat with this MAC alone, plus an aside with its nickname and Find.

Battery and signal show only as replies to Find (bubbles), not as tiles that don't update."""

import lvgl as lv

import ds_tokens as t
import panel
import roster
import ui_kit as k
from ui_kit import F12, GREY

LOG = 5
ASIDE_X = 552
ASIDE_W = 248
FOOT_Y = 402
_w = {}


def _mac():
    m = panel.P.target["macs"]
    return m[0] if m else None


def _rename():
    import kbd
    mac = _mac()
    kbd.open("", panel.P.store.names.get(mac, ""), 16,
             lambda s: panel.P.act(panel.P.rename, mac, s))


def _games(mode):
    import scr_games
    scr_games.open(mode)


def _tile(parent, x, y, w, h, label):
    b = k.box(parent, x, y, w, h, t.SURFACE, 12, t.BORDER)
    k.text(b, label, t.INK_3, F12, 12, 8)
    return b, k.slot(b, 12, 28, w - 24, t.INK, k.F_HEAD)


def build():
    scr = k.new_screen()
    hd, _w["title"], _w["sub"] = k.header(scr, "", k.back, "", 300)
    _w["title"].set_x(120)
    _w["sub"].set_x(120)
    av = k.box(hd, 68, 12, 40, 40, GREY, t.R_PILL)
    _w["av"] = av
    _w["tag"] = k.text(av, "", t.INK_3, F12, align=lv.ALIGN.CENTER)

    area = k.plain(lv.obj(scr))
    area.set_pos(0, 64)
    area.set_size(ASIDE_X, FOOT_Y - 64)
    area.set_style_bg_opa(lv.OPA.TRANSP, 0)
    area.set_style_pad_hor(16, 0)
    area.set_style_pad_ver(12, 0)
    area.set_style_pad_row(10, 0)
    area.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    area.set_flex_align(lv.FLEX_ALIGN.END, lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START)
    _w["mine"] = []
    _w["theirs"] = []
    for _ in range(LOG):        # pairs, so the shown bubble of each keeps log order
        _w["mine"].append(k.bubble(area, True))
        _w["theirs"].append(k.bubble(area, False))

    side = k.box(scr, ASIDE_X, 64, ASIDE_W, FOOT_Y - 64, t.BG)
    k.box(scr, ASIDE_X, 64, 1, FOOT_Y - 64, t.BORDER)
    _w["about"] = k.slot(side, 16, 12, ASIDE_W - 32, t.INK, k.F_HEAD)
    nb, _w["nick"] = _tile(side, 16, 40, ASIDE_W - 32, 56, "Nickname")
    k.on(nb, _rename)
    f = k.button(side, 16, 112, 52, "Find it again", t.SURFACE, "find_18", font=k.F_HEAD,
                 primary="teal", w=ASIDE_W - 32)
    k.on(f, lambda: _mac() and panel.P.act(panel.P.find, _mac()))

    ft = k.box(scr, 0, FOOT_Y, k.W, k.H - FOOT_Y, t.SURFACE)
    k.box(scr, 0, FOOT_Y, k.W, 1, t.BORDER)
    s = k.button(ft, 16, 11, 56, "Start game", t.SURFACE, "play_20", font=k.F_HEAD, primary=True, w=200)
    st = k.button(ft, 228, 11, 56, "Stop", t.INK, "stop_20", t.DANGER[0], k.F_HEAD, w=120)
    c = k.button(ft, 360, 11, 56, "Send code", t.PURPLE, "code_20", font=k.F_HEAD, w=180)
    k.on(s, lambda: _games("start"))
    k.on(st, lambda: panel.P.act(panel.P.stop))
    k.on(c, lambda: _games("code"))
    return scr


def _theirs(e):
    """(text, color) for a left bubble."""
    ty = e["t"]
    if ty == "err":
        return e["text"], t.DANGER[0]
    return e.get("b") and f"{e['text']} {e['b']}" or e["text"], t.WARN[0] if e.get("warn") else t.INK


def refresh():
    P = panel.P
    mac = _mac()
    if mac is None:
        return
    e = P.roster.d.get(mac)
    wand = e is None or P.roster.is_wand(e)
    k.st(_w["title"], P.roster.name(mac))
    k.st(_w["tag"], roster.tag_of(mac) if wand else "STN")
    k.sty(_w["av"], "bg", GREY if wand else t.TEAL_50)
    kind = "Wand" if wand else "Station"
    k.st(_w["about"], f"About this {kind.lower()}")
    if e is None or e["seen"] is None:
        k.st(_w["sub"], kind)
    else:
        k.st(_w["sub"], f"{kind}{k.DOT}heard {P.roster.age(e)}")
    k.st(_w["nick"], P.store.names.get(mac) or "")
    # roll-call answers show in the header ("heard 1 min ago"); notes are Home's
    log = [x for x in P.log() if x["t"] not in ("rep", "note")][-LOG:]
    # bubbles in log order: a mine/theirs pair per slot, only one shown
    for i in range(LOG):
        x = log[i] if i < len(log) else None
        mine = x is not None and x["t"] == "mine"
        ln, lb, sub = _w["mine"][i]
        k.show_hide(ln, mine)
        if mine:
            k.st(lb, x["text"])
            k.st(sub, P.mine_sub(x))
        ln, lb, sub = _w["theirs"][i]
        k.show_hide(ln, x is not None and not mine)
        if x is not None and not mine:
            s, col = _theirs(x)
            k.st(lb, s)
            k.sty(lb, "text", col)
            k.st(sub, "")
