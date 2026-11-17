# Screen 6: Read card (waiting state only; no reader on this board).
import lvgl as lv
import tokens as t
import ui


def build():
    s = ui.screen("read")
    n = ui.box(s, 43, 80, 84, 84, t.PURPLE_50, radius=42)
    ui.label(n, lv.SYMBOL.EYE_OPEN, t.PURPLE, ui.F_BIG).center()
    ui.label(s, "Tap a card", t.INK, ui.F_BIG, x=0, y=178, w=ui.W, center=True)
    ui.button(s, 8, 268, 154, 44, "Exit", "danger", lambda: ui.go("home"))
    return s


ui.register("read", build)
