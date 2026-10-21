"""dial_ui.py -- round-screen painter for the Broadcast Dial (m5ui + LVGL).

Layout from the NFC Station's station_ui.py: choices sit on the rim at
fixed angles, so turning the knob moves the highlight around the ring in
the same direction, and the centre names the selection large.

Pages, built once in begin() and re-textured per paint:

  list    Dot ring: one dot per item around the rim (selected dot large
          and filled); title, item name and n/N in the centre. Over
          DOT_SLOTS items the dots give way to a position arc.
  status  Full rim arc coloured by result, glyph, title, body, hint.
          Boot, idle, scan, read, write and result screens.

A hold ring on LVGL's top layer fills over the 1 s hold (back).

Imported by bdial_server.run() after the radio is up (prewarm), never
before: see BroadcastCode/docs_and_design/2026-09-23-ap-memory-order.md.
"""

import math
import time

import M5
import m5ui
import lvgl as lv

import station_fonts
from dial_board import SPEAKER_VOLUME
from dial_input import HOLD_MAYBE_MS, SERVE_EXIT_MS

# Brand tokens, from Live_Page/.design_system/Sept 2026/tokens/.
PAGE_BG = 0xF7F7FB
INK = 0x231F2E
INK_3 = 0x5B5468
BORDER = 0xE8E6F0
WRITE_FG = 0x6C4CD1
SERVE_FG = 0x1C9A82
DANGER_FG = 0xC0392B
WARN_FG = 0xA8781E

RIM_OUTER = 118
DOT_R = 106
DOT_SMALL = 12
DOT_BIG = 26
DOT_SLOTS = 24
HOLD_SHOW = HOLD_MAYBE_MS / SERVE_EXIT_MS   # ring appears where a release stops being a click
HOLD_STEP = 12
HOLD_W = 10

READ_ENTRY = "Read Card"    # bdial_server.READ_ENTRY


def _rim_xy(deg, r):
    """Offset from centre for a clock angle (0 = 12 o'clock, clockwise)."""
    a = math.radians(deg)
    return int(r * math.sin(a)), int(-r * math.cos(a))


def _display_tag(text):
    """First letter capitalised for display; the card text is unchanged."""
    return text[:1].upper() + text[1:] if text else text


class DialUI:
    def __init__(self, inputs=None):
        self._input = inputs
        self._pages = {}
        self._cur = None
        self.f = {}
        self.ic = {}

    def begin(self):
        """Call once after M5.begin() and the radio prewarm."""
        m5ui.init()
        M5.Speaker.setVolume(SPEAKER_VOLUME)
        self.f = {
            "body": station_fonts.require(station_fonts.BODY),
            "focus": station_fonts.require(station_fonts.FOCUS),
            "glyph": station_fonts.require(station_fonts.GLYPH),
        }
        S = lv.SYMBOL
        self.ic = {
            "read": S.EYE_OPEN, "scan": S.SD_CARD, "ok": S.OK,
            "fail": S.CLOSE, "warn": S.WARNING, "busy": S.REFRESH,
            "usb": S.USB, "code": S.WIFI, "play": S.PLAY,
        }
        self._build_list()
        self._build_status()
        self.hold_arc = self._arc(lv.layer_top(), INK_3, HOLD_W)
        self._visible(self.hold_arc, False)
        self._hold_shown = False
        self._hold_deg = -1

    # -- primitives --------------------------------------------------

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

    def _arc(self, parent, color, width, size=RIM_OUTER * 2):
        """Non-interactive arc, 0 deg at 12 o'clock, angles clockwise."""
        arc = lv.arc(parent)
        arc.set_size(size, size)
        arc.align(lv.ALIGN.CENTER, 0, 0)
        arc.set_rotation(270)
        arc.set_bg_angles(0, 0)
        arc.remove_style(None, lv.PART.KNOB)
        arc.remove_flag(lv.obj.FLAG.CLICKABLE)
        arc.set_style_arc_rounded(False, lv.PART.INDICATOR)
        arc.set_style_arc_width(width, lv.PART.MAIN)
        arc.set_style_arc_width(width, lv.PART.INDICATOR)
        arc.set_style_arc_opa(0, lv.PART.MAIN)
        arc.set_style_arc_color(lv.color_hex(color), lv.PART.INDICATOR)
        return arc

    def _circle(self, parent, d, color):
        c = lv.obj(parent)
        c.set_size(d, d)
        c.set_style_radius(d // 2, 0)
        c.set_style_bg_color(lv.color_hex(color), 0)
        c.set_style_bg_opa(255, 0)
        c.set_style_border_width(0, 0)
        c.set_style_pad_all(0, 0)
        c.remove_flag(lv.obj.FLAG.CLICKABLE)
        c.remove_flag(lv.obj.FLAG.SCROLLABLE)
        return c

    @staticmethod
    def _span(arc, start_deg, end_deg):
        """Show the arc from start_deg to end_deg (clockwise, 0 = 12
        o'clock). A span of 360 or more is a full ring."""
        if end_deg - start_deg >= 360:
            arc.set_angles(0, 360)
            return
        arc.set_angles(int(start_deg) % 360, int(end_deg) % 360)

    @staticmethod
    def _visible(obj, on):
        if on:
            obj.remove_flag(lv.obj.FLAG.HIDDEN)
        else:
            obj.add_flag(lv.obj.FLAG.HIDDEN)

    def flush(self):
        """Render now, for a screen that must be visible before a blocking
        call (card write, result hold)."""
        lv.refr_now(None)

    # -- list: dot ring ----------------------------------------------

    def _build_list(self):
        pg = self._page("list")
        self.l_ptr = self._arc(pg, WRITE_FG, 6)
        self.l_dots = [self._circle(pg, DOT_SMALL, BORDER) for _ in range(DOT_SLOTS)]
        self.l_title = self._label(pg, self.f["body"], WRITE_FG, w=130, y=-52)
        self.l_cur = self._label(pg, self.f["focus"], INK, w=170, y=0)
        self.l_count = self._label(pg, self.f["body"], INK_3, y=50)

    def _dot_ring(self, n, sel):
        dots = n <= DOT_SLOTS
        step = 360 / n
        for i, d in enumerate(self.l_dots):
            if not dots or i >= n:
                self._visible(d, False)
                continue
            self._visible(d, True)
            big = i == sel
            size = DOT_BIG if big else DOT_SMALL
            d.set_size(size, size)
            d.set_style_radius(size // 2, 0)
            d.set_style_bg_color(lv.color_hex(WRITE_FG if big else BORDER), 0)
            dx, dy = _rim_xy(i * step, DOT_R)
            d.align(lv.ALIGN.CENTER, dx, dy)
        self._visible(self.l_ptr, not dots)
        if not dots:
            half = max(step / 2, 4)
            self._span(self.l_ptr, sel * step - half, sel * step + half)

    def _show_list(self, title, items, sel):
        self._dot_ring(len(items), sel)
        self.l_title.set_text(title)
        self.l_cur.set_text(items[sel])
        self.l_count.set_text("%d/%d" % (sel + 1, len(items)))
        self._show("list")

    def _row(self, r, code_tag, play_tag):
        if r == code_tag:
            return self.ic["code"] + " Code"
        if r == play_tag:
            return self.ic["play"] + " Play"
        if r == READ_ENTRY:
            return self.ic["read"] + " Read"
        return _display_tag(r)

    def paint_tag_list(self, entries, cursor):
        """Top level: one row per game, then Utility Tags."""
        self._show_list("Games", entries, cursor)

    def paint_tag_group(self, title, rows, cursor, written):
        """One group's tags. A game group's first two rows are
        getcode:<slug> and <slug>; a tag written since boot gets a tick."""
        code_tag = play_tag = None
        if rows and rows[0].startswith("getcode:"):
            code_tag = rows[0]
            slug = code_tag[len("getcode:"):]
            if len(rows) > 1 and rows[1] == slug:
                play_tag = slug
        shown = []
        for r in rows:
            label = self._row(r, code_tag, play_tag)
            if written and written.get(r):
                label += " " + self.ic["ok"]
            shown.append(label)
        self._show_list(title, shown, cursor)

    # -- status: result ring -----------------------------------------

    def _build_status(self):
        pg = self._page("status")
        self.s_ring = self._arc(pg, WRITE_FG, 10)
        self.s_glyph = self._label(pg, self.f["glyph"], WRITE_FG, y=-50)
        self.s_title = self._label(pg, self.f["focus"], INK, w=180, y=2)
        self.s_body = self._label(pg, self.f["body"], INK_3, w=160, y=44)
        self.s_hint = self._label(pg, self.f["body"], WRITE_FG, w=110, y=80)

    def _status(self, glyph, color, title, body="", hint="", fill=100):
        self.s_ring.set_style_arc_color(lv.color_hex(color), lv.PART.INDICATOR)
        self._span(self.s_ring, 0, 360 * fill // 100)
        self.s_glyph.set_text(self.ic[glyph])
        self.s_glyph.set_style_text_color(lv.color_hex(color), 0)
        self.s_title.set_text(title)
        self.s_body.set_text(body)
        self.s_hint.set_text(hint)
        self._show("status")

    def paint_booting(self):
        self._status("busy", INK_3, "Starting", "", "", 30)

    def paint_idle(self, linked=True):
        self._status("usb", SERVE_FG if linked else INK_3, "No Game",
                     "Linked" if linked else "Not Linked", "", 0)

    def paint_scanning(self, label):
        self._status("scan", WRITE_FG, _display_tag(label), "Hold Card", "", 0)

    def paint_reader(self, existing=None, scanned=False):
        """Read Card: waiting (scanned=False), then each card's text in
        place (existing None or "" for a blank card)."""
        if not scanned:
            self._status("read", WRITE_FG, "Read", "Hold Card", "", 0)
        elif existing:
            self._status("ok", SERVE_FG, existing, "", "")
        else:
            self._status("warn", WARN_FG, "Blank Card", "", "")

    def paint_writing(self, label):
        self._status("busy", WRITE_FG, "Writing", _display_tag(label), "", 30)

    def paint_already(self, label):
        self._status("ok", SERVE_FG, "Already Set", _display_tag(label))

    def paint_written(self, label, count):
        self._status("ok", SERVE_FG, "Done", _display_tag(label), "x%d" % count)

    def paint_write_failed(self, label):
        self._status("fail", DANGER_FG, "Write Failed", _display_tag(label))

    # -- hold progress -----------------------------------------------

    def show_hold(self, fraction):
        """Fill a rim ring clockwise from 12 o'clock while the button is
        held toward the 1 s back. Hidden below HOLD_SHOW and once the
        hold fires or the button is released."""
        if fraction is None or fraction < HOLD_SHOW:
            if self._hold_shown:
                self._visible(self.hold_arc, False)
                self._hold_shown = False
                self._hold_deg = -1
            return
        f = (fraction - HOLD_SHOW) / (1.0 - HOLD_SHOW)
        deg = int(360 * f) // HOLD_STEP * HOLD_STEP
        if deg == self._hold_deg:
            return
        self._hold_deg = deg
        self._span(self.hold_arc, 0, max(deg, HOLD_STEP))
        if not self._hold_shown:
            self._visible(self.hold_arc, True)
            self._hold_shown = True

    # -- sound -------------------------------------------------------

    def _tone(self, freq, ms):
        try:
            M5.Speaker.tone(freq, ms)
        except Exception as e:
            print("# speaker tone err: %s" % str(e))

    # The piezo crackles below about 3 kHz. Clicks, turns and scans are
    # silent; a finished card read or write sounds.
    def beep_scan(self):
        pass

    def beep_click(self):
        pass

    def _beeps(self, freq, ms, gap, n):
        for i in range(n):
            if i:
                time.sleep_ms(gap)
            self._tone(freq, ms)
            time.sleep_ms(ms)

    def beep_success(self):
        self._beeps(4800, 100, 80, 2)

    def beep_fail(self):
        self._beeps(3600, 70, 60, 3)
