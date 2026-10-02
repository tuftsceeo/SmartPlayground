"""ui_sketches.py -- Phase 0b circular-layout sketches for the NFC Station.

Three candidate layouts for a 240x240 round screen driven by the Dial's
encoder, replacing the BroadcastDial's rectangular M5Roller:

  ring      Rim ring selector. Items sit around the rim; an arc segment
            highlights the selection; the centre repeats it at FOCUS size.
  carousel  Curved list. Selected item large in the centre, neighbours
            smaller and dimmed above/below, pulled inward to follow the
            circle; a rim arc shows list position.
  keyboard  Ring keyboard. Outer ring = letter groups; click opens the
            group's characters on the ring; click commits a character.
            Composed text shows in the centre.

Controls: turn = move, click = select, hold 1 s = next sketch.
Each sketch prints a JSON line with mem_free and the build time when shown.

Run on the Dial with station_fonts.py and dial_input.py on /flash:
    mpremote run tools/ui_sketches.py
"""

import gc
import json
import math
import time

import M5
import m5ui
import lvgl as lv

import station_fonts
from dial_input import DialInput, NEXT, PREV, ACT, EXIT

CX = 120
CY = 120
RIM_R = 92          # radius of rim item centres
ARC_SIZE = 236      # highlight arc diameter
ARC_W = 8

PAGE_BG = 0xF7F7FB
INK = 0x231F2E
INK_3 = 0x5B5468
BORDER = 0xE8E6F0
WRITE_FG = 0x6C4CD1
PINK = 0xEF4D92

HOME_ITEMS = ("Read", "Tags", "Text")
GAME_ITEMS = ("colorquest", "freezedance", "jumpin", "cooking", "melody",
              "shake", "rainbow", "sound")
KEY_GROUPS = ("abcde", "fghij", "klmno", "pqrst", "uvwxy", "z_ ", "01234",
              "56789")
DEL = "<"


def _rim_xy(deg, r=RIM_R):
    """Offset from centre for a clock angle (0 = 12 o'clock, clockwise)."""
    a = math.radians(deg)
    return int(r * math.sin(a)), int(-r * math.cos(a))


def _label(parent, text, font, color=INK, w=None):
    lbl = lv.label(parent)
    lbl.set_text(text)
    lbl.set_style_text_font(font, 0)
    lbl.set_style_text_color(lv.color_hex(color), 0)
    lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    if w is not None:
        lbl.set_width(w)
        lbl.set_long_mode(lv.label.LONG_MODE.SCROLL_CIRCULAR)
    return lbl


def _rim_arc(parent, color):
    """Full-circle track with a movable indicator segment, not clickable."""
    arc = lv.arc(parent)
    arc.set_size(ARC_SIZE, ARC_SIZE)
    arc.align(lv.ALIGN.CENTER, 0, 0)
    arc.set_bg_angles(0, 360)
    arc.set_rotation(270)       # LVGL 0 deg is 3 o'clock; make it 12
    arc.remove_style(None, lv.PART.KNOB)
    arc.remove_flag(lv.obj.FLAG.CLICKABLE)
    arc.set_style_arc_width(ARC_W, lv.PART.MAIN)
    arc.set_style_arc_width(ARC_W, lv.PART.INDICATOR)
    arc.set_style_arc_color(lv.color_hex(BORDER), lv.PART.MAIN)
    arc.set_style_arc_color(lv.color_hex(color), lv.PART.INDICATOR)
    return arc


def _set_segment(arc, centre_deg, span_deg):
    start = int(centre_deg - span_deg / 2) % 360
    end = int(centre_deg + span_deg / 2) % 360
    arc.set_angles(start, end)


class RingSelector:
    """Items on the rim, highlight arc, selection repeated in the centre."""

    def __init__(self, page, items, fonts):
        self.items = items
        self.sel = 0
        self.step = 360 // len(items)
        self.arc = _rim_arc(page, WRITE_FG)
        self.rim = []
        for i, text in enumerate(items):
            # Rim shows only the first letter: full words do not fit 8-up.
            lbl = _label(page, text[0].upper(), fonts["body"], INK_3)
            dx, dy = _rim_xy(i * self.step, RIM_R - 14)
            lbl.align(lv.ALIGN.CENTER, dx, dy)
            self.rim.append(lbl)
        self.centre = _label(page, "", fonts["focus"], INK, w=150)
        self.centre.align(lv.ALIGN.CENTER, 0, 0)
        self._paint()

    def _paint(self):
        _set_segment(self.arc, self.sel * self.step, self.step - 6)
        for i, lbl in enumerate(self.rim):
            lbl.set_style_text_color(
                lv.color_hex(WRITE_FG if i == self.sel else INK_3), 0)
        self.centre.set_text(self.items[self.sel])

    def handle(self, intent):
        if intent == NEXT:
            self.sel = (self.sel + 1) % len(self.items)
        elif intent == PREV:
            self.sel = (self.sel - 1) % len(self.items)
        elif intent == ACT:
            print(json.dumps({"sketch": "ring", "chose": self.items[self.sel]}))
        self._paint()


class Carousel:
    """Curved vertical list: neighbours follow the circle's chord inward."""

    def __init__(self, page, items, fonts):
        self.items = items
        self.sel = 0
        self.arc = _rim_arc(page, WRITE_FG)
        self.prev = _label(page, "", fonts["body"], INK_3, w=130)
        self.prev.set_style_opa(150, 0)
        self.prev.align(lv.ALIGN.CENTER, 0, -62)
        self.cur = _label(page, "", fonts["focus"], INK, w=190)
        self.cur.align(lv.ALIGN.CENTER, 0, 0)
        self.next = _label(page, "", fonts["body"], INK_3, w=130)
        self.next.set_style_opa(150, 0)
        self.next.align(lv.ALIGN.CENTER, 0, 62)
        self._paint()

    def _paint(self):
        n = len(self.items)
        self.prev.set_text(self.items[(self.sel - 1) % n])
        self.cur.set_text(self.items[self.sel])
        self.next.set_text(self.items[(self.sel + 1) % n])
        # Position track on the right half of the rim (30..150 deg).
        span = 120 // n
        _set_segment(self.arc, 30 + self.sel * span + span // 2, max(span, 8))

    def handle(self, intent):
        if intent == NEXT:
            self.sel = (self.sel + 1) % len(self.items)
        elif intent == PREV:
            self.sel = (self.sel - 1) % len(self.items)
        elif intent == ACT:
            print(json.dumps({"sketch": "carousel", "chose": self.items[self.sel]}))
        self._paint()


class RingKeyboard:
    """Two-level ring: groups, then one group's characters plus delete/back."""

    def __init__(self, page, fonts):
        self.page = page
        self.fonts = fonts
        self.text = ""
        self.group = None       # None = choosing a group
        self.sel = 0
        self.arc = _rim_arc(page, PINK)
        self.rim = []
        self.typed = _label(page, "", fonts["body"], INK, w=150)
        self.typed.align(lv.ALIGN.CENTER, 0, -16)
        self.hint = _label(page, "", fonts["body"], WRITE_FG)
        self.hint.align(lv.ALIGN.CENTER, 0, 26)
        self._relayout()

    def _choices(self):
        if self.group is None:
            return list(KEY_GROUPS) + [DEL]
        return list(KEY_GROUPS[self.group]) + [DEL]

    def _relayout(self):
        for lbl in self.rim:
            lbl.delete()
        self.rim = []
        choices = self._choices()
        self.step = 360 // len(choices)
        for i, c in enumerate(choices):
            shown = c
            if self.group is None and len(c) > 2:
                shown = c[0] + c[-1]    # "abcde" -> "ae": range ends
            if c == " ":
                shown = "_"
            lbl = _label(self.page, shown, self.fonts["body"], INK_3)
            dx, dy = _rim_xy(i * self.step, RIM_R - 14)
            lbl.align(lv.ALIGN.CENTER, dx, dy)
            self.rim.append(lbl)
        self.sel = 0
        self._paint()

    def _paint(self):
        _set_segment(self.arc, self.sel * self.step, self.step - 6)
        for i, lbl in enumerate(self.rim):
            lbl.set_style_text_color(
                lv.color_hex(PINK if i == self.sel else INK_3), 0)
        self.typed.set_text(self.text + "|")
        c = self._choices()[self.sel]
        if c == DEL:
            self.hint.set_text("delete" if self.group is None else "back")
        elif c == " ":
            self.hint.set_text("space")
        else:
            self.hint.set_text(c)

    def handle(self, intent):
        n = len(self._choices())
        if intent == NEXT:
            self.sel = (self.sel + 1) % n
        elif intent == PREV:
            self.sel = (self.sel - 1) % n
        elif intent == ACT:
            c = self._choices()[self.sel]
            if self.group is None:
                if c == DEL:
                    self.text = self.text[:-1]
                else:
                    self.group = self.sel
                    self._relayout()
                    return
            else:
                if c != DEL:
                    self.text += c
                self.group = None
                self._relayout()
                return
        self._paint()


SKETCHES = ("ring", "carousel", "keyboard")


def _build(name, fonts):
    t0 = time.ticks_ms()
    page = m5ui.M5Page(bg_c=PAGE_BG)
    if name == "ring":
        view = RingSelector(page, GAME_ITEMS, fonts)
    elif name == "carousel":
        view = Carousel(page, GAME_ITEMS, fonts)
    else:
        view = RingKeyboard(page, fonts)
    page.screen_load()
    lv.refr_now(None)
    gc.collect()
    print(json.dumps({"sketch": name, "build_ms": time.ticks_diff(time.ticks_ms(), t0),
                      "mem_free": gc.mem_free()}))
    return page, view


def run():
    M5.begin()
    m5ui.init()
    fonts = {
        "body": station_fonts.require(station_fonts.BODY),
        "focus": station_fonts.require(station_fonts.FOCUS),
    }
    inputs = DialInput()
    inputs.begin()
    idx = 0
    page, view = _build(SKETCHES[idx], fonts)
    while True:
        inputs.update()
        intent = inputs.pop()
        if intent == EXIT:
            idx = (idx + 1) % len(SKETCHES)
            old = page
            page, view = _build(SKETCHES[idx], fonts)
            old.delete()
            inputs.clear()
        elif intent is not None:
            view.handle(intent)
        time.sleep_ms(1)


run()
