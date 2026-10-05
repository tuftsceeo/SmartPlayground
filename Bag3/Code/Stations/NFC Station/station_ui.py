"""station_ui.py -- round-screen painter for the NFC Station (m5ui + LVGL).

Every selector puts its choices on the rim at fixed angles, so turning the
dial moves the highlight around the ring in the same direction as the
knob, and the centre names the selection large. No rectangular roller.

Pages, built once in begin() and re-textured per paint:

  home      Icon ring: coloured circles with glyphs at 12, 4 and 8
            o'clock; the selected one is enlarged and outlined; its name
            sits in the centre.
  list      Dot ring: one dot per item around the rim (selected dot large
            and filled, with an arc pointer); title, item name (FOCUS) and
            n/N in the centre. Over DOT_SLOTS items the dots give way to a
            position arc.
  status    Full rim arc coloured by result (ok / fail / busy ...), glyph,
            title, body, hint. Reader, scan and write results.
  keyboard  Segmented ring keyboard: all ring items as labels in a rim
            band, rotated tangent to the ring with bottoms toward the centre
            (rim_rotation), each in an
            arc slot sized to its glyph width (slot_angles), grouped into SEGMENT-item sections with
            alternating tint;
            the highlighted item gets a filled arc cell. Centre: typed
            text, the highlighted item at GLYPH size, byte count. Rim
            labels are tappable. WORDS mode uses the dot ring in the band
            with the word in the centre. CANCEL (unwritten text only)
            uses the status page: red trash, "Clear?", "Hold".

Text is BODY (28 px) minimum; see station_fonts.py.

A hold ring on LVGL's top layer fills over the 1 s hold on any page.

Painter API used by station.py:
  show_ring(names, sel)          show_list(title, items, sel)
  show_reader(text, tag_type)    show_scan(text)
  show_result(kind, title, body) show_keyboard(view)
  show_hold(fraction)            beep_click/scan/success/fail
"""

import json
import math
import time

import M5
import m5ui
import lvgl as lv

import station_fonts
import text_entry
from dial_board import SPEAKER_VOLUME, SCREEN_W, SCREEN_H

# Brand tokens, from Live_Page/.design_system/Sept 2026/tokens/ (same values
# as BroadcastDial's dial_ui.py).
PAGE_BG = 0xF7F7FB
CARD_BG = 0xFFFFFF
INK = 0x231F2E
INK_3 = 0x5B5468
BORDER = 0xE8E6F0
PINK = 0xEF4D92
WRITE_FG = 0x6C4CD1
WRITE_BG = 0xF2EEFC
SERVE_FG = 0x1C9A82
DANGER_FG = 0xC0392B
WARN_FG = 0xA8781E
WHITE = 0xFFFFFF

# Rim geometry (screen 240 x 240, centre 120,120).
RIM_OUTER = 118         # outer edge of the keyboard band
BAND_W = 44             # keyboard band width: radii 74..118
KEY_R = 97              # keyboard label centre radius
DOT_R = 106             # list dot centre radius
DOT_SMALL = 12
DOT_BIG = 26
DOT_SLOTS = 24          # most items shown as dots; more -> position arc
KEY_SLOTS = 30          # preallocated keyboard labels (len(LETTERS))
HOME_R = 86             # home icon centre radius
HOME_D = 52             # home icon diameter (selected: HOME_D + 10)
TYPED_MAX_W = 100       # px: inner-circle chord at the typed line (y=-36)
CARET_W = 3             # px: caret bar width; CARET_GAP px after the text
CARET_GAP = 3
CARET_H = 26
CARET_BLINK_MS = 530
PAINT_MS = False        # True: print keyboard paint time (incl. LVGL refresh)
ROTATE_RIM = True       # False: upright rim letters (A/B test of rotation cost)
TURN_BEEP = True        # False: no beep per detent (A/B test of speaker cost)
SEG_TINTS = True        # False: no tinted section arcs behind the rim letters
CELL_DOT = False        # True: selection is a filled circle behind the letter,
                        # not a 44 px-wide arc segment (cheaper to redraw)
CELL_DOT_D = 36         # selection circle diameter
IMAGE_RING = True       # draw IMAGE_RINGS from pre-rendered images
IMAGE_RINGS = ("letters",)  # rings with an image; others use live labels
                        # (each image is 115 KB of the ~786 KB /flash)
                        # (tools/gen_ring.py): only the highlight is live
RING_DIR = "/flash"     # kb_<ring>.bin and kb_rings.json location
HOLD_SHOW = 0.35        # hold fraction before the hold ring appears (350 ms)
HOLD_STEP = 12          # degrees per hold-ring update (30 redraws per hold)
HOLD_W = 10             # hold ring width, same as the result ring

HOME_STYLE = {          # home item -> (glyph key, circle colour)
    "Read": ("read", SERVE_FG),
    "Tags": ("tags", WRITE_FG),
    "Text": ("text", PINK),
}
KIND_STYLE = {          # show_result kind -> (glyph key, colour, arc fill %)
    "ok": ("ok", SERVE_FG, 100),
    "fail": ("fail", DANGER_FG, 100),
    "warn": ("warn", WARN_FG, 100),
    "busy": ("busy", WRITE_FG, 30),
    "info": ("read", WRITE_FG, 100),
}


def _rim_xy(deg, r):
    """Offset from centre for a clock angle (0 = 12 o'clock, clockwise)."""
    a = math.radians(deg)
    return int(r * math.sin(a)), int(-r * math.cos(a))


def rim_rotation(deg):
    """Label rotation (degrees, -180..180) for a rim item at clock angle deg.

    Tangent to the ring with every label's baseline toward the centre, so
    the ring reads continuously all the way round (lower-half letters are
    upside down, as on a printed dial). Upright labels do not fit 30-up at
    28 px: at 3 and 9 o'clock neighbours stack vertically and the line
    height, not the glyph width, sets the spacing.
    """
    d = deg % 360
    if d > 180:
        return d - 360
    return d


def slot_at(slots, dx, dy):
    """Index of the ring slot under a touch at (dx, dy) from the centre,
    or None if the touch is off the keyboard band."""
    r = math.sqrt(dx * dx + dy * dy)
    if not slots or r < RIM_OUTER - BAND_W - 6 or r > RIM_OUTER + 6:
        return None
    a = math.degrees(math.atan2(dx, -dy)) % 360
    for i, (c, half) in enumerate(slots):
        d = (a - c + 540) % 360 - 180
        if abs(d) <= half:
            return i
    return None


def slot_angles(widths, radius, min_gap=2):
    """Centre angle and half-span (degrees) per ring item, item 0 at 12.

    Each item's slot is proportional to its rendered width plus an equal
    share of the leftover circumference, so wide glyphs (m, w) get more
    arc than narrow ones (i, l) and adjacent labels do not overlap.
    Raises ValueError if the items cannot fit with min_gap px between
    neighbours at this radius.
    """
    circ = 2 * math.pi * radius
    total = sum(widths)
    spare = circ - total
    n = len(widths)
    if spare < min_gap * n:
        raise ValueError("ring items need %d px, %d available at r=%d"
                         % (total + min_gap * n, circ, radius))
    gap = spare / n
    out = []
    pos = -(widths[0] + gap) / 2        # centre item 0 at 0 deg
    for w in widths:
        slot = w + gap
        centre = pos + slot / 2
        out.append((centre * 360 / circ, slot * 180 / circ))
        pos += slot
    return out


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
            "read": S.EYE_OPEN, "tags": S.LIST, "text": S.EDIT,
            "scan": S.SD_CARD, "ok": S.OK, "fail": S.CLOSE,
            "warn": S.WARNING, "busy": S.REFRESH, "trash": S.TRASH,
            "back": S.LEFT,
            text_entry.DEL: S.BACKSPACE, text_entry.DONE: S.OK,
            text_entry.WORDS_ITEM: S.LIST, text_entry.BACK_ITEM: S.LEFT,
        }
        self._build_home()
        self._build_list()
        self._build_status()
        self._build_keyboard()
        # Hold-to-back progress ring, on LVGL's top layer above every page.
        self.hold_arc = self._arc(lv.layer_top(), INK_3, HOLD_W)
        self._visible(self.hold_arc, False)
        self._hold_shown = False
        self._hold_deg = -1

    # -- primitives --------------------------------------------------

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
        o'clock). A span of 360 or more is a full ring; reducing both ends
        mod 360 would give start == end, which LVGL draws as nothing."""
        if end_deg - start_deg >= 360:
            arc.set_angles(0, 360)
            return
        arc.set_angles(int(start_deg) % 360, int(end_deg) % 360)

    @staticmethod
    def _color(lbl, color):
        lbl.set_style_text_color(lv.color_hex(color), 0)

    @staticmethod
    def _visible(obj, on):
        if on:
            obj.remove_flag(lv.obj.FLAG.HIDDEN)
        else:
            obj.add_flag(lv.obj.FLAG.HIDDEN)

    def _tap_cb(self, i):
        def handler(event_struct):
            self._enqueue("tap:%d" % i)
        return handler

    # -- home: icon ring ---------------------------------------------

    def _build_home(self):
        pg = self._page("home")
        self.h_icons = []
        for name in ("Read", "Tags", "Text"):
            glyph, color = HOME_STYLE[name]
            c = self._circle(pg, HOME_D, color)
            g = self._label(c, self.f["body"], WHITE)
            g.set_text(self.ic[glyph])
            self.h_icons.append(c)
        self.h_name = self._label(pg, self.f["focus"], INK, w=100)

    def show_ring(self, names, sel):
        step = 360 / len(names)
        for i, c in enumerate(self.h_icons):
            if i >= len(names):
                self._visible(c, False)
                continue
            self._visible(c, True)
            big = i == sel
            d = HOME_D + 10 if big else HOME_D
            c.set_size(d, d)
            c.set_style_radius(d // 2, 0)
            c.set_style_border_width(4 if big else 0, 0)
            c.set_style_border_color(lv.color_hex(INK), 0)
            c.set_style_opa(255 if big else 170, 0)
            dx, dy = _rim_xy(i * step, HOME_R)
            c.align(lv.ALIGN.CENTER, dx, dy)
        self.h_name.set_text(names[sel])
        self._show("home")

    # -- list: dot ring ----------------------------------------------

    def _build_list(self):
        pg = self._page("list")
        self.l_ptr = self._arc(pg, WRITE_FG, 6)
        self.l_dots = [self._circle(pg, DOT_SMALL, BORDER) for _ in range(DOT_SLOTS)]
        self.l_title = self._label(pg, self.f["body"], WRITE_FG, w=130, y=-52)
        self.l_cur = self._label(pg, self.f["focus"], INK, w=170, y=0)
        self.l_count = self._label(pg, self.f["body"], INK_3, y=50)

    def _dot_ring(self, n, sel):
        """Dots for n items (selected large), or a position arc if n is
        more than DOT_SLOTS."""
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
        half = max(step / 2, 4)
        self._span(self.l_ptr, sel * step - half, sel * step + half)

    def show_list(self, title, items, sel):
        self._dot_ring(len(items), sel)
        self.l_title.set_text(title)
        self.l_cur.set_text(items[sel])
        self.l_count.set_text("%d/%d" % (sel + 1, len(items)))
        self._show("list")

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
        self._color(self.s_glyph, color)
        self.s_title.set_text(title)
        self.s_body.set_text(body)
        self.s_hint.set_text(hint)
        self._show("status")
        lv.refr_now(None)   # results are painted just before a blocking write

    def show_reader(self, text, tag_type=""):
        if text is None and not tag_type:
            self._status("read", WRITE_FG, "Read", "Hold Card", "", 0)
        elif text:
            self._status("ok", SERVE_FG, text, tag_type, "Copy")
        else:
            self._status("warn", WARN_FG, "No Text", tag_type, "")

    def show_scan(self, text):
        self._status("scan", WRITE_FG, text, "Hold Card", "", 0)

    def show_result(self, kind, title, body=""):
        glyph, color, fill = KIND_STYLE[kind]
        self._status(glyph, color, title, body, "", fill)

    # -- keyboard: segmented ring ------------------------------------

    def _build_keyboard(self):
        pg = self._page("keyboard")
        self.k_img = None
        self._rings = None
        if IMAGE_RING:
            # Rings pre-rendered by tools/gen_ring.py. A missing file is a
            # deploy error: fail loudly rather than fall back silently.
            with open(RING_DIR + "/kb_rings.json") as f:
                self._rings = json.load(f)
            self.k_img = lv.image(pg)
            self.k_img.align(lv.ALIGN.CENTER, 0, 0)
            self.k_img.add_flag(lv.obj.FLAG.CLICKABLE)
            self.k_img.add_event_cb(self._ring_tap, lv.EVENT.CLICKED, None)
            self._k_img_src = None
        self._img_active = False
        nseg = KEY_SLOTS // text_entry.SEGMENT
        live = True                 # live labels serve rings without an image
        self.k_segs = [self._arc(pg, WRITE_BG if i % 2 else CARD_BG, BAND_W)
                       for i in range(nseg if SEG_TINTS and live else 0)]
        if CELL_DOT:
            self.k_cell = self._circle(pg, CELL_DOT_D, PINK)
        else:
            self.k_cell = self._arc(pg, PINK, BAND_W)
        # Image mode: one live label draws the highlighted item in white.
        self.k_hi = self._label(pg, self.f["body"], WHITE) if IMAGE_RING else None
        self.k_keys = []
        for i in range(KEY_SLOTS if live else 0):
            lbl = self._label(pg, self.f["body"], INK)
            lbl.add_flag(lv.obj.FLAG.CLICKABLE)
            lbl.set_ext_click_area(6)
            lbl.add_event_cb(self._tap_cb(i), lv.EVENT.CLICKED, None)
            self.k_keys.append(lbl)
        self.k_dots = [self._circle(pg, DOT_SMALL, BORDER) for _ in range(DOT_SLOTS)]
        self._k_ring = None
        self._k_slots = None
        self._k_rot = None
        self._kb_mode = None        # last painted state, for show_keyboard
        self._kb_ring_shown = None
        self._kb_sel = None
        self._kb_text = None
        self.k_typed = self._label(pg, self.f["body"], INK, y=-36)
        # Caret: a separate pink bar, not a "|" glyph, which reads as "l".
        self.k_caret = lv.obj(pg)
        self.k_caret.set_size(CARET_W, CARET_H)
        self.k_caret.set_style_radius(1, 0)
        self.k_caret.set_style_border_width(0, 0)
        self.k_caret.set_style_bg_color(lv.color_hex(PINK), 0)
        self.k_caret.set_style_bg_opa(255, 0)
        self.k_caret.remove_flag(lv.obj.FLAG.CLICKABLE)
        self.k_caret.remove_flag(lv.obj.FLAG.SCROLLABLE)
        self._caret_on = True
        self._caret_at = 0
        self.k_sel = self._label(pg, self.f["glyph"], PINK, w=120, y=6)
        self.k_count = self._label(pg, self.f["body"], INK_3, y=44)

    def _fit_tail(self, lbl, text, max_w):
        """Show the end of text, dropping leading characters (marked "..")
        until text plus caret is at most max_w px wide, then place the
        caret after it. Returns the label width."""
        room = max_w - CARET_GAP - CARET_W
        shown = text
        cut = 0
        while True:
            lbl.set_text(shown)
            lbl.update_layout()
            w = lbl.get_width()
            if w <= room or cut >= len(text):
                break
            cut += 1
            shown = ".." + text[cut:]
        # Text + caret centred as one unit.
        total = w + CARET_GAP + CARET_W
        lbl.align(lv.ALIGN.CENTER, (w - total) // 2, -36)
        self.k_caret.align(lv.ALIGN.CENTER, total // 2 - CARET_W // 2, -36)
        self._caret_on = True       # solid right after a keystroke
        self._caret_at = time.ticks_ms()
        self._visible(self.k_caret, True)
        return w

    def tick(self):
        """Call once per main-loop iteration: blinks the caret.

        Driven from the main loop rather than an LVGL timer: a Ctrl-C that
        lands inside an LVGL timer callback is caught by m5ui's port and
        never reaches the REPL, which blocks mpremote.
        """
        if self._cur != "keyboard":
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self._caret_at) < CARET_BLINK_MS:
            return
        self._caret_at = now
        self._caret_on = not self._caret_on
        self._visible(self.k_caret, self._caret_on)

    def _key_text(self, c):
        if c in self.ic:
            return self.ic[c]
        if c == text_entry.SPACE:
            return "_"
        return c

    def _sel_text(self, c):
        if c == text_entry.SPACE:
            return "_"
        if c == text_entry.MORE_ITEM:
            return "123"
        if c in self.ic:
            return self.ic[c]
        return c

    def show_keyboard(self, view):
        """Paint the keyboard, touching only what changed since the last
        call: a detent recolours two labels, moves the cell and sets the
        centre item; the text line repaints only when the text changes;
        the full ring layout only when the ring's contents change.

        Every widget change marks its area for redraw, and rim labels are
        rotated (drawn through an LVGL layer), so a full repaint per
        detent redraws most of the band and lags behind the encoder.
        """
        t0 = time.ticks_ms() if PAINT_MS else 0
        mode = view["mode"]
        if mode == text_entry.M_CANCEL:
            self._kb_cancel(view)
        else:
            self._kb_paint(view)
        if PAINT_MS:
            lv.refr_now(None)
            print("# paint keyboard %d ms" % time.ticks_diff(time.ticks_ms(), t0))

    def _kb_cancel(self, view):
        """Discard prompt on the status page, so the keyboard is not on
        screen while it cannot be used. The keyboard page is left as it
        was; returning to it only swaps the page back."""
        self._status("trash", DANGER_FG, "Clear?", "Hold", "", 0)

    def _kb_paint(self, view):
        mode = view["mode"]
        ring = tuple(view["choices"])
        if mode != self._kb_mode or ring != self._kb_ring_shown:
            self._kb_layout(view)
        elif view["sel"] != self._kb_sel:
            self._kb_move(view, self._kb_sel)
        text_key = (view["text"], view["used"], view["written"], mode)
        if text_key != self._kb_text:
            self._kb_text_line(view)
            self._kb_text = text_key
        self._kb_mode = mode
        self._kb_ring_shown = ring
        self._kb_sel = view["sel"]
        self._show("keyboard")

    def _kb_layout(self, view):
        """Full keyboard layout for a new ring (or a new mode)."""
        mode = view["mode"]
        choices = view["choices"]
        sel = view["sel"]
        n = len(choices)
        keys = mode in (text_entry.M_LETTERS, text_entry.M_MORE)
        words = mode == text_entry.M_WORDS

        slots = None
        ring = tuple(choices) if keys else None
        name = "letters" if mode == text_entry.M_LETTERS else "more"
        use_img = (keys and self.k_img is not None and name in IMAGE_RINGS)
        self._img_active = use_img
        if self.k_img is not None:
            self._visible(self.k_img, use_img)
            self._visible(self.k_hi, use_img)
        if use_img:
            spec = self._rings[name]
            if list(spec["items"]) != list(choices):
                raise ValueError("kb_rings.json %s ring %r does not match %r; "
                                 "rerun tools/gen_ring.py" % (name, spec["items"], choices))
            src = "S:%s/kb_%s.bin" % (RING_DIR, name)
            if src != self._k_img_src:
                self.k_img.set_src(src)
                self._k_img_src = src
            self._k_slots = [tuple(x) for x in spec["slots"]]
            self._k_ring = ring
            slots = self._k_slots
        elif keys:
            if ring != self._k_ring or self._k_rot != ring:
                for i in range(n):
                    self.k_keys[i].set_text(self._key_text(choices[i]))
                self.k_keys[0].get_parent().update_layout()
                self._k_slots = slot_angles(
                    [self.k_keys[i].get_width() for i in range(n)], KEY_R)
                self._k_ring = ring
            slots = self._k_slots
        for i, lbl in enumerate(self.k_keys):
            if not keys or use_img or i >= n:
                self._visible(lbl, False)
                continue
            self._visible(lbl, True)
            if ring != self._k_rot:
                dx, dy = _rim_xy(slots[i][0], KEY_R)
                lbl.align(lv.ALIGN.CENTER, dx, dy)
                lbl.set_style_transform_pivot_x(lbl.get_width() // 2, 0)
                lbl.set_style_transform_pivot_y(lbl.get_height() // 2, 0)
                if ROTATE_RIM:
                    lbl.set_style_transform_rotation(int(rim_rotation(slots[i][0]) * 10), 0)
            self._color(lbl, WHITE if i == sel else INK)
        if keys and not use_img:
            self._k_rot = ring

        seg_items = text_entry.SEGMENT
        nseg = (n + seg_items - 1) // seg_items if keys and not use_img else 0
        for i, arc in enumerate(self.k_segs):
            if i >= nseg:
                self._visible(arc, False)
                continue
            self._visible(arc, True)
            first = slots[i * seg_items]
            last = slots[min((i + 1) * seg_items, n) - 1]
            self._span(arc, first[0] - first[1], last[0] + last[1])

        step = 360 / n
        dots_on = words and n <= DOT_SLOTS
        for i, d in enumerate(self.k_dots):
            show = dots_on and i < n
            self._visible(d, show)
            if show:
                dx, dy = _rim_xy(i * step, DOT_R)
                d.align(lv.ALIGN.CENTER, dx, dy)
                self._dot_style(d, i == sel)

        if mode == text_entry.M_CANCEL:
            self._visible(self.k_cell, False)
            self.k_sel.set_style_text_font(self.f["glyph"], 0)
            self.k_sel.set_text(self.ic["trash"])
            return
        self._visible(self.k_cell, keys)
        if keys:
            self._cell_to(slots[sel])
            if use_img:
                self._hi_to(choices[sel], slots[sel])
        self.k_sel.set_style_text_font(self.f["focus" if words else "glyph"], 0)
        self._set_sel_text(view)

    def _kb_move(self, view, old):
        """Selection moved within the same ring: two labels (or dots), the
        cell, the centre item."""
        mode = view["mode"]
        sel = view["sel"]
        if mode in (text_entry.M_LETTERS, text_entry.M_MORE):
            if self._img_active:
                self._hi_to(view["choices"][sel], self._k_slots[sel])
            else:
                self._color(self.k_keys[old], INK)
                self._color(self.k_keys[sel], WHITE)
            self._cell_to(self._k_slots[sel])
        elif mode == text_entry.M_WORDS and len(view["choices"]) <= DOT_SLOTS:
            self._dot_style(self.k_dots[old], False)
            self._dot_style(self.k_dots[sel], True)
        self._set_sel_text(view)

    def _ring_tap(self, event_struct):
        """Image mode: map a touch on the ring band to the slot under it."""
        p = lv.point_t()
        lv.indev_active().get_point(p)
        i = slot_at(self._k_slots, p.x - SCREEN_W // 2, p.y - SCREEN_H // 2)
        if i is not None:
            self._enqueue("tap:%d" % i)

    def _hi_to(self, item, slot):
        """Image mode: draw the highlighted item as one white rotated label
        over the cell; the ring image underneath stays untouched."""
        lbl = self.k_hi
        lbl.set_text(self._key_text(item))
        lbl.update_layout()
        dx, dy = _rim_xy(slot[0], KEY_R)
        lbl.align(lv.ALIGN.CENTER, dx, dy)
        lbl.set_style_transform_pivot_x(lbl.get_width() // 2, 0)
        lbl.set_style_transform_pivot_y(lbl.get_height() // 2, 0)
        lbl.set_style_transform_rotation(int(rim_rotation(slot[0]) * 10), 0)

    def _cell_to(self, slot):
        """Move the selection highlight to a rim slot (centre, half-span)."""
        c, half = slot
        if CELL_DOT:
            dx, dy = _rim_xy(c, KEY_R)
            self.k_cell.align(lv.ALIGN.CENTER, dx, dy)
        else:
            self._span(self.k_cell, c - half, c + half)

    def _dot_style(self, d, big):
        size = DOT_BIG if big else DOT_SMALL
        d.set_size(size, size)
        d.set_style_radius(size // 2, 0)
        d.set_style_bg_color(lv.color_hex(PINK if big else BORDER), 0)

    def _set_sel_text(self, view):
        item = view["choices"][view["sel"]]
        if view["mode"] == text_entry.M_WORDS:
            self.k_sel.set_text("back" if item == text_entry.BACK_ITEM else item)
        else:
            self.k_sel.set_text(self._sel_text(item))

    def _kb_text_line(self, view):
        self._fit_tail(self.k_typed, view["text"], TYPED_MAX_W)
        if view["mode"] == text_entry.M_CANCEL:
            self.k_count.set_text("Hold")
            self._color(self.k_count, DANGER_FG)
        else:
            self.k_count.set_text("%d/%d" % (view["used"], view["max"]))
            self._color(self.k_count, DANGER_FG if view["used"] >= view["max"] else INK_3)

    # -- hold progress -----------------------------------------------

    def show_hold(self, fraction):
        """Fill a rim ring clockwise from 12 o'clock while the button is
        held toward the 1 s back/exit. Hidden for short clicks (under
        HOLD_SHOW) and once the hold fires or the button is released."""
        if fraction is None or fraction < HOLD_SHOW:
            if self._hold_shown:
                self._visible(self.hold_arc, False)
                self._hold_shown = False
                self._hold_deg = -1
            return
        # The ring fills over the time left after it appears, in HOLD_STEP
        # steps: it sits on the top layer, so every change redraws the
        # (rotated) labels beneath it.
        f = (fraction - HOLD_SHOW) / (1.0 - HOLD_SHOW)
        deg = int(360 * f) // HOLD_STEP * HOLD_STEP
        if deg == self._hold_deg:
            return
        self._hold_deg = deg
        self._span(self.hold_arc, 0, max(deg, HOLD_STEP))
        if not self._hold_shown:
            self._visible(self.hold_arc, True)
            self._hold_shown = True

    # -- sound (piezo peaks ~3 kHz; values from dial_ui.py) ----------

    def _tone(self, freq, ms):
        M5.Speaker.tone(freq, ms)

    def beep_click(self):
        self._tone(3400, 20)

    def beep_turn(self):
        """Per-detent tick; off when TURN_BEEP is False."""
        if TURN_BEEP:
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
