"""enc_probe.py -- does the Dial's encoder lose detents when the loop stalls?

No station code. Instructions are shown on the Dial's screen. For each
trial the screen names a motion ("Turn 5 forward"); make it, then press
the button. The count since the trial started is recorded and printed.

Trials (detents forward, counted at a human pace): 1, 5, 20. All run twice:
  fast   loop polls every 1 ms
  stall  loop sleeps 300 ms per iteration, like a slow redraw

If stall counts come out lower than fast counts, Rotary is decoded in
software during M5.update() and loop stalls drop steps. Counts that are a
multiple of the detents (10 for 5) mean several counts per detent.

    mpremote connect <port> resume run tools/enc_probe.py
"""

import time

import M5
import m5ui
import lvgl as lv
from hardware import Rotary

TRIALS = ((1, "1 forward"), (5, "5 forward"), (20, "20 forward"))
PHASES = (("fast", 1), ("stall", 300))

M5.begin()
m5ui.init()
page = m5ui.M5Page(bg_c=0xFFFFFF)
page.screen_load()


def _label(y, font):
    lbl = lv.label(page)
    lbl.set_style_text_font(font, 0)
    lbl.set_style_text_color(lv.color_hex(0x231F2E), 0)
    lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    lbl.set_width(200)
    lbl.align(lv.ALIGN.CENTER, 0, y)
    return lbl


head = _label(-70, lv.font_montserrat_16)
task = _label(-20, lv.font_montserrat_24)
hint = _label(30, lv.font_montserrat_16)
count = _label(70, lv.font_montserrat_24)

rot = Rotary()
print("Rotary:", Rotary, [n for n in dir(rot) if not n.startswith("_")])


def show(h, t, n, c=""):
    head.set_text(h)
    task.set_text(t)
    hint.set_text(n)
    count.set_text(c)
    lv.refr_now(None)


def wait_release():
    while M5.BtnA.isPressed():
        M5.update()
        time.sleep_ms(5)


def trial(phase, stall_ms, i, want, words):
    rot.reset_rotary_value()
    start = rot.get_rotary_value()
    shown = None
    while True:
        M5.update()
        v = rot.get_rotary_value() - start
        if v != shown:
            show("%s  %d/%d" % (phase, i, len(TRIALS)), "Turn " + words,
                 "then press the button", "count %d" % v)
            shown = v
        if M5.BtnA.wasPressed() or M5.BtnA.isPressed():
            wait_release()
            break
        time.sleep_ms(stall_ms)
    v = rot.get_rotary_value() - start
    print("%-5s turn %-20s detents %2d  counted %3d" % (phase, words, want, v))
    return v


results = []
for phase, stall_ms in PHASES:
    show(phase, "Get ready", "press the button to start", "")
    while not (M5.BtnA.wasPressed() or M5.BtnA.isPressed()):
        M5.update()
        time.sleep_ms(5)
    wait_release()
    for i, (want, words) in enumerate(TRIALS, 1):
        results.append((phase, want, words, trial(phase, stall_ms, i, want, words)))

show("done", "Finished", "results on serial", "")
print("== summary (phase, detents, counted)")
for phase, want, words, v in results:
    print("%-5s %-20s %2d -> %3d" % (phase, words, want, v))
