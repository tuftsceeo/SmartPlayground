"""Home screen (1 - chat) for the 800x480 CrowPanel: the shared left column, the chat's title,
its feed and the Start / Send code / Stop footer. Content comes from panel.P.
"""

import ds_tokens as t
import feed
import panel
import side
import ui_kit as k
from ui_kit import F16, H

SIDE_W = side.W
HEAD_H = 64
FOOT_H = 78
MAIN_W = k.W - SIDE_W

_w = {}


def _games(mode):
    import scr_games
    scr_games.open(mode)


def footer(scr):
    """Start a game / Send code / Stop, shared with the group chat."""
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


def build():
    scr = k.new_screen()
    _w["side"] = side.build(scr, "msg")
    hd = k.box(scr, SIDE_W, 0, MAIN_W, HEAD_H, t.SURFACE)
    k.box(scr, SIDE_W, HEAD_H - 1, MAIN_W, 1, t.BORDER)
    _w["title"] = k.slot(hd, 16, 22, MAIN_W - 32, t.INK, F16)
    _w["slots"] = feed.build(scr, SIDE_W, HEAD_H, MAIN_W, H - HEAD_H - FOOT_H)
    footer(scr)
    return scr


def refresh():
    P = panel.P
    side.refresh(_w["side"])
    k.st(_w["title"], P.target["name"])
    feed.fill(_w["slots"], P.log())
