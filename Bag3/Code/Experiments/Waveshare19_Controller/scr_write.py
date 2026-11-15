# Screens 4 and 5: hold card (fake 1.5 s write), then the result.
# The fourth write fails, the rest succeed, so both bands can be seen.
import lvgl as lv
import tokens as t
import fake_data as fake
import ui

_timer = None


def _finish(tm):
    ui.rebuild("result")
    ui.go("result")


def build_write():
    global _timer
    i = ui.state()["tag"]
    name = fake.TAGS[i][0]
    s = ui.screen("write")
    n = ui.box(s, 43, 62, 84, 84, t.PURPLE_50, radius=42)
    ui.label(n, lv.SYMBOL.EYE_OPEN, t.PURPLE, ui.F_BIG).center()
    ui.label(s, name, t.INK, ui.F_BIG, x=0, y=158, w=ui.W, center=True)
    ui.label(s, "Tag %d of %d" % (i + 1, len(fake.TAGS)), t.INK_3, ui.F14, x=0, y=192, w=ui.W, center=True)
    track = ui.box(s, 8, 222, 154, 10, t.BORDER, radius=5)
    ui.box(track, 0, 0, 62, 10, t.PURPLE, radius=5)
    ui.button(s, 8, 268, 154, 44, "Cancel", "danger", lambda: _cancel())
    _timer = lv.timer_create(_finish, 1500, None)
    _timer.set_repeat_count(1)
    return s


def _cancel():
    if _timer is not None:
        _timer.delete()
    ui.go("tags")


def build_result():
    i = ui.state()["tag"]
    name = fake.TAGS[i][0]
    ok = i != 3
    last = i >= len(fake.TAGS) - 1
    s = ui.screen("result")
    band = ui.box(s, 8, 90, 154, 80, t.TEAL_50 if ok else 0xFDECEA, radius=12)
    fg = t.TEAL if ok else t.DANGER
    ui.label(band, "Written" if ok else "Write failed", fg, ui.F_BIG, x=0, y=10, w=154, center=True)
    ui.label(band, name, fg, ui.F14, x=0, y=46, w=154, center=True)
    ui.label(s, "Tag %d of %d" % (i + 1, len(fake.TAGS)), t.INK_3, ui.F14, x=0, y=182, w=ui.W, center=True)
    if last:
        ui.button(s, 8, 268, 154, 44, "Done", "primary", lambda: ui.go("tags"))
    else:
        ui.button(s, 8, 268, 154, 44, "Next", "primary", _next)
    return s


def _next():
    ui.state()["tag"] += 1
    ui.rebuild("write")
    ui.go("write")


ui.register("write", build_write)
ui.register("result", build_result)
