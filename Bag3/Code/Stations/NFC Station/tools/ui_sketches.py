"""ui_sketches.py -- drive station_ui's real pages on the Dial, no NFC.

Layout check for the round-screen painter: every page station.py uses,
with sample data, interactive where it makes sense.

  home       icon ring (Read / Tags / Text)
  games      dot ring, 16 items
  long       dot ring past DOT_SLOTS (position arc only), 30 items
  keyboard   live ring keyboard (text_entry); turn, click, tap rim keys
  status     cycles result screens on each click

Controls: turn = move, click = select, hold 1 s = next sketch.
Prints one JSON line per sketch with mem_free and paint time.

Run with the station files on /flash:
    mpremote run tools/ui_sketches.py
"""

import gc
import json
import time

import M5

import text_entry
from dial_input import DialInput, NEXT, PREV, ACT, EXIT
from station_ui import StationUI

GAMES = ["Colorquest", "Cooking", "Freezedance", "Gestures", "Goalrace",
         "Jump", "Jumpin", "Melody", "Multiicecream", "Nfcsound", "Rainbow",
         "Shake", "Shakerainbow", "Simpleicecream", "Sound", "Controls"]
LONG = ["item %d" % i for i in range(30)]
WORDS = ["melody", "stop", "goal", "teamblue", "rainbow"]
STATUS = (("reader", None), ("read", "melody"), ("scan", "teamgreen"),
          ("busy", "Writing"), ("ok", "Done"), ("fail", "Oops"),
          ("warn", "No Text"))
SKETCHES = ("home", "games", "long", "keyboard", "status")


class Sketch:
    def __init__(self, ui, name):
        self.ui = ui
        self.name = name
        self.sel = 0
        self.entry = text_entry.TextEntry(54, WORDS)

    def paint(self):
        t0 = time.ticks_ms()
        ui = self.ui
        if self.name == "home":
            ui.show_ring(["Read", "Tags", "Text"], self.sel % 3)
        elif self.name == "games":
            ui.show_list("Games", GAMES, self.sel % len(GAMES))
        elif self.name == "long":
            ui.show_list("Long", LONG, self.sel % len(LONG))
        elif self.name == "keyboard":
            ui.show_keyboard(self.entry.view())
        else:
            kind, text = STATUS[self.sel % len(STATUS)]
            if kind == "reader":
                ui.show_reader(None)
            elif kind == "read":
                ui.show_reader(text, "NTAG")
            elif kind == "scan":
                ui.show_scan(text)
            else:
                ui.show_result(kind, text, "teamgreen")
        return time.ticks_diff(time.ticks_ms(), t0)

    def handle(self, intent):
        if self.name == "keyboard":
            ev = self.entry.handle(intent)
            if ev is not None:
                print(json.dumps({"sketch": "keyboard", "event": list(ev)}))
                if ev[0] in ("done", "cancel"):
                    self.entry = text_entry.TextEntry(54, WORDS)
        elif intent == NEXT or (intent == ACT and self.name == "status"):
            self.sel += 1
        elif intent == PREV:
            self.sel -= 1
        return self.paint()


def run():
    M5.begin()
    inputs = DialInput()
    inputs.begin()
    ui = StationUI(inputs)
    ui.begin()
    idx = 0
    sk = Sketch(ui, SKETCHES[idx])
    ms = sk.paint()
    gc.collect()
    print(json.dumps({"sketch": sk.name, "paint_ms": ms, "mem_free": gc.mem_free()}))
    while True:
        inputs.update()
        intent = inputs.pop()
        if intent == EXIT and sk.name != "keyboard":
            idx = (idx + 1) % len(SKETCHES)
            sk = Sketch(ui, SKETCHES[idx])
            ms = sk.paint()
            gc.collect()
            print(json.dumps({"sketch": sk.name, "paint_ms": ms, "mem_free": gc.mem_free()}))
            inputs.clear()
        elif intent == EXIT and sk.entry.mode == text_entry.M_LETTERS and not sk.entry.text:
            idx = (idx + 1) % len(SKETCHES)
            sk = Sketch(ui, SKETCHES[idx])
            sk.paint()
            inputs.clear()
        elif intent is not None:
            sk.handle(intent)
        time.sleep_ms(1)


run()
