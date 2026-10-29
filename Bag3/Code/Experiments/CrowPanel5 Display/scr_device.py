"""Screen 6 - One device: find, rename, start, stop or send code to this MAC alone."""

import lvgl as lv

import ds_tokens as t
import panel
import roster
import ui_kit as k
from ui_kit import F12, F14, F16, R, GREY

LOG = 5
_w = {}


def _mac():
    m = panel.P.target["macs"]
    return m[0] if m else None


def _rename():
    import kbd
    mac = _mac()
    kbd.open("Rename this device", panel.P.store.names.get(mac, ""), 16,
             lambda s: panel.P.act(panel.P.rename, mac, s))


def _games(mode):
    import scr_games
    scr_games.open(mode)


def build():
    scr = k.new_screen()
    hd, _w["title"] = k.header(scr, "", k.back)
    _w["tag"] = k.pill(hd, "", t.INK_3, GREY)
    _w["tag"].set_pos(520, 20)
    ren = k.button(hd, 660, 10, 44, "Rename", t.PURPLE, w=124)
    k.on(ren, _rename)

    info = k.box(scr, 16, 76, 300, 240, t.SURFACE, R, t.BORDER)
    _w["kind"] = k.slot(info, 16, 14, 268, t.INK, F16)
    _w["heard"] = k.slot(info, 16, 44, 268, t.INK_3, F14)
    _w["batt"] = k.slot(info, 16, 76, 268, t.INK_3, F14)
    _w["sig"] = k.slot(info, 16, 104, 268, t.INK_3, F14)
    _w["game"] = k.slot(info, 16, 132, 268, t.INK_3, F14)
    f = k.button(info, 16, 172, 52, "Find it", t.TEAL_DARK, "find_18", w=268, font=F16)
    k.on(f, lambda: _mac() and panel.P.act(panel.P.find, _mac()))
    _w["find"] = f

    k.text(scr, "Chat", t.INK, F16, 336, 80)
    _w["log"] = [k.slot(scr, 336, 112 + i * 36, 448, t.INK_3, F14) for i in range(LOG)]

    ft = k.box(scr, 0, 402, k.W, 78, t.SURFACE)
    k.box(scr, 0, 402, k.W, 1, t.BORDER)
    s = k.button(ft, 16, 11, 56, "Start game", t.SURFACE, "play_20", font=F16, primary=True, w=200)
    c = k.button(ft, 228, 11, 56, "Send code", t.PURPLE, "code_20", font=F16, w=180)
    st = k.button(ft, 664, 11, 56, "Stop", t.INK, "stop_20", t.DANGER[0], F16, w=120)
    k.on(s, lambda: _games("start"))
    k.on(c, lambda: _games("code"))
    k.on(st, lambda: panel.P.act(panel.P.stop))
    return scr


def _line(e):
    ty = e["t"]
    if ty == "mine":
        return f"{e['text']} - {e['sub']}"
    if ty == "note":
        return f"{e['text']} {e.get('b', '')}"
    if ty == "err":
        return e["text"]
    return f"Roll call - {e['n']} answered"


def refresh():
    P = panel.P
    mac = _mac()
    if mac is None:
        return
    e = P.roster.d.get(mac)
    k.st(_w["title"], P.roster.name(mac))
    k.st(k.lbl(_w["tag"]), roster.tag_of(mac))
    if e is None:
        k.st(_w["kind"], "Device")
        for n in ("heard", "batt", "sig"):
            k.st(_w[n], "")
    else:
        k.st(_w["kind"], "Wand" if P.roster.is_wand(e) else f"Station - {e['kind']}")
        k.st(_w["heard"], f"Heard {P.roster.age(e)}" if e["seen"] else "Not heard")
        b = e["battery"]
        k.st(_w["batt"], "Battery -" if b is None else f"Battery {b}%")
        k.st(_w["sig"], f"Signal {roster.signal_word(e['rssi'])}")
    g = P.playing.get(mac)
    gg = P.lib.get(g) if g else None
    k.st(_w["game"], f"Last game: {gg['name'] if gg else g}" if g else "")
    log = [_line(x) for x in P.log()[-LOG:]]
    for i, lb in enumerate(_w["log"]):
        k.st(lb, log[i] if i < len(log) else "")
