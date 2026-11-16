# Screen 1: Home.
import lvgl as lv
import tokens as t
import fake_data as fake
import ui


def build():
    s = ui.screen("home")
    card = ui.box(s, 8, 40, 154, 70, t.SURFACE, t.BORDER)
    ui.label(card, "Game", t.INK_3, ui.F14, x=10, y=6)
    ui.label(card, fake.ACTIVE, t.INK, ui.F_BIG, x=10, y=26)
    ui.button(s, 8, 118, 154, 56, lv.SYMBOL.LIST + "  Games", "primary", lambda: ui.go("games"))
    ui.button(s, 8, 182, 154, 56, lv.SYMBOL.EYE_OPEN + "  Read card", "plain", lambda: ui.go("read"))
    ui.button(s, 8, 246, 154, 56, lv.SYMBOL.WIFI + "  Serving  %d" % fake.PULLS, "plain",
              lambda: ui.go("serve"))
    return s


ui.register("home", build)
