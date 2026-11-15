# Screen 7: Serving status with fake pull counts.
import tokens as t
import fake_data as fake
import ui


def build():
    s = ui.screen("serve")
    a = ui.box(s, 8, 40, 154, 84, t.SURFACE, t.BORDER)
    ui.label(a, "Sharing", t.INK_3, ui.F14, x=10, y=6)
    ui.label(a, fake.HOST_ID, t.INK, ui.F_BIG, x=10, y=24)
    ui.label(a, fake.ACTIVE, t.INK_3, ui.F14, x=10, y=58)
    b = ui.box(s, 8, 132, 154, 56, t.SURFACE, t.BORDER)
    ui.label(b, str(fake.PULLS), t.INK, ui.F_BIG, x=10, y=12)
    ui.label(b, "pulls", t.INK_3, ui.F14, x=64, y=18)
    ui.row(s, 196, fake.RECENT[0][0], fake.RECENT[0][1])
    ui.button(s, 8, 268, 154, 44, "Stop", "danger", lambda: ui.go("home"))
    return s


ui.register("serve", build)
