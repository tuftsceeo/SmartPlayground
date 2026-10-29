"""Bench timing probe, imported from the REPL only: kbd_cost(), screen_cost(), loop(seconds)."""

import time

import lvgl as lv
import task_handler

import panel


def _refr():
    t0 = time.ticks_us()
    lv.refr_now(None)
    return time.ticks_diff(time.ticks_us(), t0)


def kbd_cost(n=5):
    import kbd
    kbd.open("Probe", "", 40, lambda s: None)
    _refr()
    out = []
    for _ in range(n):
        kbd._w["ta"].add_char(ord("c"))
        out.append(_refr())
    kbd._w["ta"].delete_char()
    out.append(_refr())
    kbd.close()
    _refr()
    print(f"# kbd key refr us: {out}")


def screen_cost():
    lv.screen_active().invalidate()
    print(f"# full screen refr us: {_refr()}")
    print(f"# idle refr us: {_refr()}")


def loop(seconds=8):
    th = task_handler.TaskHandler._current_instance
    s = {"n": 0, "us": 0, "max": 0, "t0": 0}

    def cb(evt, _):
        if evt == task_handler.TASK_HANDLER_STARTED:
            s["t0"] = time.ticks_us()
        else:
            d = time.ticks_diff(time.ticks_us(), s["t0"])
            s["n"] += 1
            s["us"] += d
            s["max"] = max(s["max"], d)

    th.add_event_cb(cb, task_handler.TASK_HANDLER_STARTED | task_handler.TASK_HANDLER_FINISHED)
    P = panel.P
    n = mx = tot = 0
    end = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        t0 = time.ticks_us()
        P.step()
        d = time.ticks_diff(time.ticks_us(), t0)
        n += 1
        tot += d
        mx = max(mx, d)
        time.sleep_ms(1)
    th.remove_event_cb(cb)
    print(f"# step n={n} avg={tot // max(1, n)} max={mx} us")
    print(f"# lvgl n={s['n']} avg={s['us'] // max(1, s['n'])} max={s['max']} us")
