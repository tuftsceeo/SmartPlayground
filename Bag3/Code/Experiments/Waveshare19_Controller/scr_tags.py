# Screen 3: one game's tags. A row writes that tag; Write all starts at tag 1.
import tokens as t
import fake_data as fake
import ui

_DOT = {"code": t.PURPLE, "play": t.LED_BLUE, "plain": t.MUTED}


def _write(i):
    ui.state()["tag"] = i
    ui.rebuild("write")
    ui.go("write")


def build():
    s = ui.screen("tags")
    ui.header(s, fake.ACTIVE, "games")
    y = 80
    for i, (name, kind, written) in enumerate(fake.TAGS[:3]):
        ui.row(s, y, name + (" •" if written else ""), dot=_DOT[kind],
               fn=(lambda i=i: _write(i)))
        y += 52
    ui.button(s, 8, 268, 154, 44, "Write all", "primary", lambda: _write(0))
    return s


ui.register("tags", build)
