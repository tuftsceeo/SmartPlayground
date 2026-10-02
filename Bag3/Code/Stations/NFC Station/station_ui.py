"""station_ui.py -- round-screen painter for the NFC Station (m5ui + LVGL).

Four pages, built once in begin() and re-textured per paint:

  ring      Home. Glyphs on the rim, highlight arc, selection named in the
            centre at FOCUS size.
  list      Curved carousel. Title on top, selected item at FOCUS size,
            neighbours dimmed above/below, "n/N" below, position arc on
            the right rim.
  status    Glyph, title, body, hint. Used by reader, scan and results.
  keyboard  Ring keyboard for text_entry. Choices on the rim (tappable);
            typed text, expanded selection and byte count in the centre.

Text is BODY (28 px) minimum everywhere; see station_fonts.py. No
rectangular roller. Content stays inside the ~170 px inscribed square; the
rim carries arcs and ring items.

Painter API used by station.py:
  show_ring(names, sel)          show_list(title, items, sel)
  show_reader(text, tag_type)    show_scan(text)
  show_result(kind, title, body) show_keyboard(view)
  beep_click/scan/success/fail
"""

import math
import time

import M5
import m5ui
import lvgl as lv

import station_fonts
import text_entry
from dial_board import SPEAKER_VOLUME

# Brand tokens, from Live_Page/.design_system/Sept 2026/tokens/ (same values
# as BroadcastDial's dial_ui.py).
PAGE_BG = 0xF7F7FB
INK = 0x231F2E
INK_3 = 0x5B5468
BORDER = 0xE8E6F0
PINK = 0xEF4D92
WRITE_FG = 0x6C4CD1
SERVE_FG = 0x1C9A82
DANGER_FG = 0xC0392B
WARN_FG = 0xA8781E

RIM_R = 94          # radius of ring item centres
ARC_SIZE = 236
ARC_W = 8
RING_SLOTS = 12     # preallocated rim labels (keyboard max is 11)
TYPED_TAIL = 8      # characters of typed text shown before the cursor

KIND_STYLE = {      # show_result kind -> (glyph key, colour)
    "ok": ("ok", SERVE_FG),
    "fail": ("fail", DANGER_FG),
    "warn": ("warn", WARN_FG),
    "busy": ("busy", WRITE_FG),
    "info": ("read", WRITE_FG),
}


def _rim_xy(deg, r=RIM_R):
    """Offset from centre for a clock angle (0 = 12 o'clock, clockwise)."""
    a = math.radians(deg)
    return int(r * math.sin(a)), int(-r * math.cos(a))


class StationUI:
    def __init__(self, inputs=None):
        self._input = inputs
        self._pages = {}
        self._cur = None
        self.f = {}
        self.ic = {}

    def begin(self):
        """Call once right after M5.begin(). Missing fonts raise."""
        m5ui.init()
        M5.Speaker.setVolume(SPEAKER_VOLUME)
        self.f = {
            "body": station_fonts.require(station_fonts.BODY),
            "focus": station_fonts.require(station_fonts.FOCUS),
            "glyph": station_fonts.require(station_fonts.GLYPH),
        }
        S = lv.SYMBOL
        self.ic = {
            "Read": S.EYE_OPEN, "Tags": S.LIST, "Text": S.EDIT,
            "read": S.EYE_OPEN, "scan": S.SD_CARD, "ok": S.OK,
            "fail": S.CLOSE, "warn": S.WARNING, "busy": S.REFRESH,
            text_entry.DEL: S.BACKSPACE, text_entry.DONE: S.OK,
            text_entry.WORDS_ITEM: S.LIST, text_entry.BACK_ITEM: S.LEFT,
        }
        self._build_ring()
        self._build_list()
        self._build_status()
        self._build_keyboard()

    # -- helpers -----------------------------------------------------

    def _enqueue(self, intent):
        if self._input is not None:
            self._input.enqueue(intent)

    def _page(self, name):
        pg = m5ui.M5Page(bg_c=PAGE_BG)
        self._pages[name] = pg
        return pg

    def _show(self, name):
        if self._cur != name:
            self._pages[name].screen_load()
            self._cur = name

    def _label(self, parent, font, color=INK, w=None, y=0):
        lbl = lv.label(parent)
        lbl.set_text("")
        lbl.set_style_text_font(font, 0)
        lbl.set_style_text_color(lv.color_hex(color), 0)
        lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        if w is not None:
            lbl.set_width(w)
            lbl.set_long_mode(lv.label.LONG_MODE.SCROLL_CIRCULAR)
        lbl.align(lv.ALIGN.CENTER, 0, y)
        return lbl

    def _arc(self, parent, color):
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

    @staticmethod
    def _segment(arc, centre_deg, span_deg):
        arc.set_angles(int(centre_deg - span_deg / 2) % 360,
                       int(centre_deg + span_deg / 2) % 360)

    @staticmethod
    def _color(lbl, color):
        lbl.set_style_text_color(lv.color_hex(color), 0)

    @staticmethod
    def _visible(obj, on):
        if on:
            obj.remove_flag(lv.obj.FLAG.HIDDEN)
        else:
            obj.add_flag(lv.obj.FLAG.HIDDEN)

    def _ring_labels(self, parent, n, tappable):
        labels = []
        for i in range(n):
            lbl = self._label(parent, self.f["body"], INK_3)
            if tappable:
                lbl.add_flag(lv.obj.FLAG.CLICKABLE)
                lbl.set_ext_click_area(12)
                lbl.add_event_cb(self._tap_cb(i), lv.EVENT.CLICKED, None)
            labels.append(lbl)
        return labels

    def _tap_cb(self, i):
        def handler(event_struct):
            self._enqueue("tap:%d" % i)
        return handler

    def _place_ring(self, labels, texts, sel, arc, color):
        """Lay texts out around the rim; an empty list hides every label
        and leaves the arc to the caller."""
        n = len(texts)
        if n == 0:
            for lbl in labels:
                self._visible(lbl, False)
            return
        step = 360 / n
        for i, lbl in enumerate(labels):
            if i >= n:
                self._visible(lbl, False)
                continue
            self._visible(lbl, True)
            lbl.set_text(texts[i])
            dx, dy = _rim_xy(i * step, RIM_R - 14)
            lbl.align(lv.ALIGN.CENTER, dx, dy)
            self._color(lbl, color if i == sel else INK_3)
        self._segment(arc, sel * step, step - 6)

    # -- pages -------------------------------------------------------

    def _build_ring(self):
        pg = self._page("ring")
        self.r_arc = self._arc(pg, WRITE_FG)
        self.r_items = self._ring_labels(pg, 3, False)
        self.r_name = self._label(pg, self.f["focus"], INK, w=150, y=0)

    def _build_list(self):
        pg = self._page("list")
        self.l_arc = self._arc(pg, WRITE_FG)
        self.l_title = self._label(pg, self.f["body"], WRITE_FG, w=120, y=-82)
        self.l_prev = self._label(pg, self.f["body"], INK_3, w=150, y=-42)
        self.l_prev.set_style_opa(140, 0)
        self.l_cur = self._label(pg, self.f["focus"], INK, w=190, y=0)
        self.l_next = self._label(pg, self.f["body"], INK_3, w=150, y=42)
        self.l_next.set_style_opa(140, 0)
        self.l_count = self._label(pg, self.f["body"], INK_3, y=82)

    def _build_status(self):
        pg = self._page("status")
        self.s_glyph = self._label(pg, self.f["glyph"], WRITE_FG, y=-56)
        self.s_title = self._label(pg, self.f["focus"], INK, w=190, y=-4)
        self.s_body = self._label(pg, self.f["body"], INK_3, w=180, y=40)
        self.s_hint = self._label(pg, self.f["body"], WRITE_FG, w=130, y=80)

    def _build_keyboard(self):
        pg = self._page("keyboard")
        self.k_arc = self._arc(pg, PINK)
        self.k_items = self._ring_labels(pg, RING_SLOTS, True)
        self.k_typed = self._label(pg, self.f["body"], INK, y=-36)
        self.k_hint = self._label(pg, self.f["focus"], PINK, w=130, y=6)
        self.k_count = self._label(pg, self.f["body"], INK_3, y=46)

    # -- painters ----------------------------------------------------

    def show_ring(self, names, sel):
        self._place_ring(self.r_items, [self.ic.get(n, n[:1]) for n in names],
                         sel, self.r_arc, WRITE_FG)
        self.r_name.set_text(names[sel])
        self._show("ring")

    def show_list(self, title, items, sel):
        n = len(items)
        self.l_title.set_text(title)
        self.l_cur.set_text(items[sel])
        many = n > 1
        self._visible(self.l_prev, many)
        self._visible(self.l_next, many)
        if many:
            self.l_prev.set_text(items[(sel - 1) % n])
            self.l_next.set_text(items[(sel + 1) % n])
        self.l_count.set_text("%d/%d" % (sel + 1, n))
        # Position on the right half of the rim, 30..150 deg.
        span = 120 / n
        self._segment(self.l_arc, 30 + sel * span + span / 2, max(span, 8))
        self._show("list")

    def _status(self, glyph, color, title, body="", hint=""):
        self.s_glyph.set_text(self.ic[glyph])
        self._color(self.s_glyph, color)
        self.s_title.set_text(title)
        self.s_body.set_text(body)
        self.s_hint.set_text(hint)
        self._show("status")
        lv.refr_now(None)   # results are painted just before a blocking write

    def show_reader(self, text, tag_type=""):
        if text is None and not tag_type:
            self._status("read", WRITE_FG, "Read", "Hold Card", "Hold: Back")
        elif text:
            self._status("ok", SERVE_FG, text, tag_type, "Click: Copy")
        else:
            self._status("warn", WARN_FG, "No Text", tag_type, "Hold: Back")

    def show_scan(self, text):
        self._status("scan", WRITE_FG, text, "Hold Card", "Hold: Back")

    def show_result(self, kind, title, body=""):
        glyph, color = KIND_STYLE[kind]
        self._status(glyph, color, title, body)

    def show_keyboard(self, view):
        mode = view["mode"]
        choices = view["choices"]
        sel = view["sel"]
        if mode == text_entry.M_WORDS:
            # Words do not fit on the rim: carousel-style centre word.
            self._place_ring(self.k_items, [], 0, self.k_arc, PINK)
            span = 360 / len(choices)
            self._segment(self.k_arc, sel * span, max(span - 4, 6))
            item = choices[sel]
            self.k_hint.set_text("back" if item == text_entry.BACK_ITEM else item)
        elif mode == text_entry.M_CANCEL:
            self._place_ring(self.k_items, [], 0, self.k_arc, PINK)
            self.k_arc.set_angles(0, 0)
            self.k_hint.set_text("Hold: Discard")
        else:
            labels = [self._key_label(c, mode) for c in choices]
            self._place_ring(self.k_items, labels, sel, self.k_arc, PINK)
            self.k_hint.set_text(self._key_hint(choices[sel], mode))
        tail = view["text"][-TYPED_TAIL:]
        if len(view["text"]) > TYPED_TAIL:
            tail = "..." + tail[3:]
        self.k_typed.set_text(tail + "|")
        self.k_count.set_text("%d/%d" % (view["used"], view["max"]))
        self._color(self.k_count, DANGER_FG if view["used"] >= view["max"] else INK_3)
        self._show("keyboard")

    def _key_label(self, c, mode):
        if c in self.ic:
            return self.ic[c]
        if c == " ":
            return "sp"
        if mode == text_entry.M_GROUPS:
            return c[0]         # group shown by its first character
        return c

    def _key_hint(self, c, mode):
        if c == text_entry.DEL:
            return "delete"
        if c == text_entry.DONE:
            return "done"
        if c == text_entry.WORDS_ITEM:
            return "words"
        if c == text_entry.BACK_ITEM:
            return "back"
        if c == " ":
            return "space"
        if mode == text_entry.M_GROUPS:
            return " ".join("sp" if ch == " " else ch for ch in c)
        return c

    # -- sound (piezo peaks ~3 kHz; values from dial_ui.py) ----------

    def _tone(self, freq, ms):
        M5.Speaker.tone(freq, ms)

    def beep_click(self):
        self._tone(3400, 20)

    def beep_scan(self):
        self._tone(3000, 30)

    def beep_success(self):
        self._tone(2800, 100)
        time.sleep_ms(50)
        self._tone(3000, 100)
        time.sleep_ms(50)
        self._tone(3300, 200)

    def beep_fail(self):
        self._tone(3000, 200)
        time.sleep_ms(50)
        self._tone(2200, 400)
