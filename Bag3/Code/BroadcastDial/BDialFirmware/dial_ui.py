"""dial_ui.py — LVGL / m5ui screens behind bbox_ui.py's painter API.

Same method names and signatures as BboxUI so bdial_server.py stays a
near-copy of bbox_server.py. Four pages are built once in begin() and
re-textured per paint (down from a prior one-page-per-state design) --
dial_board.py's Phase 0 log records a real hardware failure, "H5 FAIL --
SoftAP OOM with 8 LVGL pages resident (~40 kB free)", with 17 pages
resident at the time. Fewer resident pages is not just tidier code, it is
the fix for that failure -- re-run the Stage 11 probe in tools/probe_dial.py
after any change here and update the H5 line with the new numbers.

Style reference: Bag2/Code/DialSpeaker/Dial_Music.py (M5 Dial v1) --
light page, dark-grey text, Material-blue accents, LVGL SYMBOL glyphs as
icons, rounded m5ui.M5Button. Palette matches bbox_ui.py so Box and Dial
still read as one product.

Design notes (round-display / small-screen navigation):
  - The tag list is a real m5ui.M5Roller (centre-selected wheel), the
    canonical crown/encoder list widget, rather than three bare labels.
  - A breadcrumb chip at the top always names the current tier, so a
    two-level hierarchy (games -> tags) never leaves the user unsure
    which list they are looking at.
  - A raw-LVGL position track on the right rim shows list extent/position
    (built from two plain lv.obj rectangles rather than a m5ui widget --
    M5Arc/M5Bar signatures were not available to verify against this repo's
    library version, and this codebase already has a working precedent for
    raw lv.obj primitives in the old scan-ring code).
  - All content sits inside a ~20px inset from the round bezel.

Unverified on hardware -- confirm with tools/probe_dial.py's roller probe and
the demo() sweep below before trusting this on a device:
  - M5Roller.set_options() accepting a python list directly (the wrapper's
    source docstring implies list; falls back to a newline-joined string
    if that raises -- see _roller_set()).
  - Per-part styling (MAIN vs SELECTED) on M5Roller taking a different font
    and colour per part, the way raw lv_roller supports it upstream.
"""

import time

import M5
import m5ui
import lvgl as lv

from dial_board import SCREEN_W, SCREEN_H, SPEAKER_VOLUME
from dial_input import NEXT, PREV, ACT, BACK, EXIT

# Light palette. PEER copy: BroadcastBox/BBoxFirmware/bbox_ui.py -- keep in sync.
PAPER = 0xFFFFFF          # page ground
INK = 0x212121             # primary text
INK_SOFT = 0x757575        # secondary text, counts, hints
RULE = 0xE0E0E0            # dividers, inactive tracks, roller neighbours
PRIMARY = 0x1976D2         # Material blue 700 -- primary action, focus
PRIMARY_SOFT = 0xBBDEFB    # blue 100 -- focus band behind the selected row
OK = 0x2E7D32
DANGER = 0xC62828
CAUTION = 0xEF6C00

FONT14 = None
FONT16 = None
FONT24 = None

# lv.SYMBOL.* glyphs -- ship with the LVGL font, no flash/manifest cost.
IC = {}


# Roller rows are not clipped by the widget, so a long tag name just runs
# past its row -- and an end-truncation would hide exactly the part that
# tells "getcode:my_melody" apart from "getcode:my_melody_2". Ellipsize the
# middle instead, keeping both ends. Carried over from the old bbox_ui.py's
# _fit(); ROW_CHARS is a rough character-count budget, not a measured pixel
# width -- confirm it against the real roller width on hardware.
ROW_CHARS = 26


def _fit(text, budget=ROW_CHARS):
    if len(text) <= budget:
        return text
    keep = budget - 1  # one char spent on the ellipsis
    head = (keep + 1) // 2
    tail = keep - head
    return text[:head] + "\u2026" + text[len(text) - tail:]


def _fonts():
    global FONT14, FONT16, FONT24
    if FONT14 is not None:
        return
    FONT14 = lv.font_montserrat_14
    FONT16 = lv.font_montserrat_16
    FONT24 = lv.font_montserrat_24
    IC.update({
        "open": lv.SYMBOL.RIGHT,
        "back": lv.SYMBOL.LEFT,
        "scan": lv.SYMBOL.SD_CARD,
        "serve": lv.SYMBOL.WIFI,
        "ok": lv.SYMBOL.OK,
        "fail": lv.SYMBOL.CLOSE,
        "warn": lv.SYMBOL.WARNING,
        "usb": lv.SYMBOL.USB,
        "busy": lv.SYMBOL.REFRESH,
        "stop": lv.SYMBOL.STOP,
        "battery": lv.SYMBOL.BATTERY_FULL,
        "read": lv.SYMBOL.EYE_OPEN,
    })


class DialUI(object):
    def __init__(self, inputs=None):
        # No M5 / m5ui calls here -- BdialServer constructs this before
        # M5.begin(). begin() is called from run() right after M5.begin().
        self._input = inputs
        self._pages = {}
        self._cur = None
        self._built = False
        self._lbl = {}
        self._btns = {}
        self._roller = None
        self._track_fill = None

    def set_input(self, inputs):
        self._input = inputs

    def begin(self):
        """Call once, right after M5.begin() -- not before.

        Deliberately unguarded: a UI that cannot initialise is a crash,
        matching dial_board.make_reader()'s and dial_input's stance. The
        old file wrapped every single M5/lvgl call in its own try/except
        and printed through -- that let a half-built screen limp along
        silently, which is the opposite of what a research prototype
        needs from its errors.
        """
        _fonts()
        m5ui.init()
        M5.Speaker.setVolume(SPEAKER_VOLUME)
        if not self._built:
            self._build_all()
            self._built = True

    def _enqueue(self, intent):
        if self._input is not None:
            self._input.enqueue(intent)

    def _cb(self, intent):
        def handler(event_struct):
            if event_struct.code == lv.EVENT.CLICKED:
                self._enqueue(intent)
        return handler

    # ── small construction helpers ──────────────────────────────

    def _page(self, name):
        pg = m5ui.M5Page(bg_c=PAPER)
        self._pages[name] = pg
        return pg

    def _label(self, key, parent, text, x, y, font, color=INK, w=200,
               align=lv.ALIGN.TOP_MID):
        lbl = m5ui.M5Label(
            text, x=x, y=y,
            text_c=color, bg_c=PAPER, bg_opa=0,
            font=font, parent=parent)
        lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        lbl.set_width(w)
        lbl.align(align, 0, y)
        self._lbl[key] = lbl
        return lbl

    def _button(self, key, parent, text, x, y, w, h, bg, intent,
                font=None, text_c=PAPER, outline=False):
        if font is None:
            font = FONT14
        btn = m5ui.M5Button(
            text=text, x=x, y=y, w=w, h=h,
            bg_c=bg if not outline else PAPER, text_c=text_c if not outline else bg,
            font=font, parent=parent)
        btn.set_style_radius(w // 2 if w <= h else h // 2, 0)
        if outline:
            btn.set_style_border_width(2, 0)
            btn.set_style_border_color(lv.color_hex(bg), 0)
        else:
            btn.set_style_border_width(0, 0)
        btn.add_event_cb(self._cb(intent), lv.EVENT.CLICKED, None)
        self._btns[key] = btn
        return btn

    def _show(self, name):
        """The one guarded seam in this file (see module docstring): a
        paint failure is logged with the screen it happened on and then
        re-raised, rather than swallowed, so the caller still sees it."""
        pg = self._pages.get(name)
        if pg is None:
            raise KeyError("dial_ui: no such page %r" % name)
        try:
            pg.screen_load()
            self._cur = name
        except Exception as e:
            print("# screen_load(%s) FAILED: %s" % (name, str(e)))
            raise

    def _set_text(self, key, text):
        self._lbl[key].set_text(text)

    def _set_color(self, key, color):
        self._lbl[key].set_style_text_color(lv.color_hex(color), 0)

    def _roller_set(self, rows):
        """set_options() is documented to take a python list; fall back to
        a newline-joined string if that raises on this firmware build."""
        try:
            self._roller.set_options(rows, lv.roller.MODE.NORMAL)
        except Exception:
            self._roller.set_options("\n".join(rows), lv.roller.MODE.NORMAL)

    def _set_track(self, cursor, total):
        """Right-rim position indicator, drawn from two plain lv.obj
        rectangles rather than a m5ui widget (see module docstring)."""
        if total <= 1:
            frac = 1.0
        else:
            frac = (cursor + 1) / float(total)
        track_h = 120
        fill_h = max(8, int(track_h * frac))
        self._track_fill.set_size(6, fill_h)
        self._track_fill.align(lv.ALIGN.BOTTOM_MID, 0, 0)

    # ── build screens once ──────────────────────────────────────

    def _build_all(self):
        self._build_list()
        self._build_scan()
        self._build_status()
        self._build_serve()

    def _build_list(self):
        pg = self._page("list")

        self._label("lst_crumb", pg, "", 0, 16, FONT14, CAUTION, w=200)

        # Position track -- a light grey channel with a blue fill that
        # grows from the bottom as the cursor advances toward the end.
        track = lv.obj(pg)
        track.set_size(6, 120)
        track.align(lv.ALIGN.RIGHT_MID, -8, 10)
        track.set_style_bg_color(lv.color_hex(RULE), 0)
        track.set_style_bg_opa(255, 0)
        track.set_style_border_width(0, 0)
        track.set_style_radius(3, 0)
        track.remove_flag(lv.obj.FLAG.CLICKABLE)
        fill = lv.obj(track)
        fill.set_size(6, 8)
        fill.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        fill.set_style_bg_color(lv.color_hex(PRIMARY), 0)
        fill.set_style_bg_opa(255, 0)
        fill.set_style_border_width(0, 0)
        fill.set_style_radius(3, 0)
        fill.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._track_fill = fill

        roller = m5ui.M5Roller(
            x=20, y=48, w=190, h=118, options=[""],
            mode=lv.roller.MODE.NORMAL, selected=0, visible_row_count=3,
            font=FONT16, parent=pg)
        roller.align(lv.ALIGN.TOP_MID, -8, 48)
        roller.set_style_radius(12, 0)
        roller.set_style_bg_color(lv.color_hex(PAPER), 0)
        roller.set_style_border_width(1, 0)
        roller.set_style_border_color(lv.color_hex(RULE), 0)
        roller.set_style_text_color(lv.color_hex(INK_SOFT), 0)
        roller.set_style_text_font(FONT14, 0)
        roller.set_style_bg_color(lv.color_hex(PRIMARY_SOFT), lv.PART.SELECTED)
        roller.set_style_text_color(lv.color_hex(INK), lv.PART.SELECTED)
        roller.set_style_text_font(FONT16, lv.PART.SELECTED)
        # Encoder/buttons drive the cursor; a stray touch must not let LVGL's
        # own selection drift out of sync with the server's cursor index.
        roller.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._roller = roller

        self._button("lst_back", pg, IC["back"], 8, 190, 44, 44,
                      INK_SOFT, BACK, FONT16, outline=True)
        self._button("lst_act", pg, IC["open"] + " OPEN", 60, 190, 130, 44,
                      PRIMARY, ACT, FONT14)

    def _build_scan(self):
        pg = self._page("scan")
        ring = lv.obj(pg)
        ring.set_size(200, 200)
        ring.align(lv.ALIGN.CENTER, 0, -6)
        ring.set_style_bg_opa(0, 0)
        ring.set_style_border_width(6, 0)
        ring.set_style_border_color(lv.color_hex(PRIMARY), 0)
        ring.set_style_radius(100, 0)
        ring.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._scan_ring = ring
        self._label("scn_icon", pg, IC["scan"], 0, 55, FONT24, PRIMARY, w=200)
        self._label("scn_label", pg, "", 0, 100, FONT16, INK, w=200)
        self._label("scn_hint", pg, "hold card on screen", 0, 150, FONT14, INK_SOFT, w=200)
        self._button("scn_back", pg, IC["back"] + " BACK", 70, 190, 100, 40,
                      INK_SOFT, BACK, FONT14, outline=True)

    def _build_status(self):
        """One reusable screen behind every one-shot painter -- booting,
        idle, receiving, armed, writing/written/write_failed/already,
        done, complete, error, mode_change, no_pickup_hint, read_result.
        Re-textured and re-tinted per call rather than rebuilt."""
        pg = self._page("status")
        self._label("st_glyph", pg, "", 0, 34, FONT24, PRIMARY, w=200)
        self._label("st_title", pg, "", 0, 90, FONT16, INK, w=200)
        self._label("st_body1", pg, "", 0, 120, FONT14, INK_SOFT, w=200)
        self._label("st_body2", pg, "", 0, 144, FONT14, INK_SOFT, w=200)
        # Whole-page transparent tap target -- dismiss-on-tap for splash
        # screens. Toggled clickable per paint via tap_dismiss.
        tap = m5ui.M5Button(
            text=" ", x=0, y=0, w=SCREEN_W, h=SCREEN_H,
            bg_c=PAPER, text_c=PAPER, font=FONT14, parent=pg)
        tap.set_style_opa(0, 0)
        tap.add_event_cb(self._cb(ACT), lv.EVENT.CLICKED, None)
        tap.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._btns["st_tap"] = tap

    def _build_serve(self):
        pg = self._page("serve")
        self._label("srv_icon", pg, IC["serve"], 0, 28, FONT24, PRIMARY, w=200)
        self._label("srv_ssid", pg, "", 0, 80, FONT16, INK, w=200)
        self._label("srv_pickups", pg, "", 0, 112, FONT14, INK_SOFT, w=200)
        self._label("srv_hint", pg, "hold button to leave", 0, 150, FONT14, INK_SOFT, w=200)
        self._button("srv_close", pg, IC["fail"] + " CLOSE", 70, 185, 100, 40,
                      INK_SOFT, EXIT, FONT14)

    # ── audio (same four beeps as bbox_ui) ──────────────────────

    def _tone(self, freq, ms):
        try:
            M5.Speaker.tone(freq, ms)
        except Exception as e:
            # Kept guarded, unlike the build path above: a piezo hiccup
            # during a scan is not a reason to abort a card write in
            # progress, and this fires on every single click/scan.
            print("# speaker tone err: %s" % str(e))

    # Frequencies tuned for the Dial's piezo buzzer (cfg.buzzer=True on
    # GPIO3), not a real speaker -- it is close to silent below ~2 kHz and
    # peaks (its resonant frequency) around 3000 Hz, confirmed live with a
    # 1-10 kHz sweep (2026-09-09). Clustered close to 3000 rather than
    # spread across a wide range -- anything far from the resonant peak
    # gets quiet fast on this buzzer -- so beeps are told apart mostly by
    # duration/direction, not big pitch jumps.
    def beep_scan(self):
        self._tone(3000, 30)

    def beep_click(self):
        self._tone(3400, 20)

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

    # ── status-screen helper ────────────────────────────────────

    def _status(self, glyph, glyph_color, title, body1="", body2="",
                tap_dismiss=True):
        self._set_text("st_glyph", glyph)
        self._set_color("st_glyph", glyph_color)
        self._set_text("st_title", title)
        self._set_text("st_body1", body1)
        self._set_text("st_body2", body2)
        tap = self._btns["st_tap"]
        if tap_dismiss:
            tap.add_flag(lv.obj.FLAG.CLICKABLE)
        else:
            tap.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._show("status")

    # ── painters (bbox_ui signatures) ───────────────────────────

    def paint_booting(self):
        self._status(IC["busy"], INK_SOFT, "Starting", tap_dismiss=False)

    def paint_idle(self, linked=True):
        status = "linked to laptop" if linked else "not linked"
        self._status(
            IC["usb"], PRIMARY if linked else INK_SOFT,
            "Broadcast Dial", status, "no game loaded yet",
            tap_dismiss=False)

    def paint_receiving(self, game_name=""):
        self._status(
            IC["busy"], PRIMARY, "Getting game...",
            game_name if game_name else "game", tap_dismiss=False)

    def paint_armed(self, label, index=1, total=1):
        self._status(
            IC["scan"], PRIMARY, label,
            "Tag %d/%d" % (index, total), "hold card on reader",
            tap_dismiss=False)

    def paint_read_result(self, existing):
        if existing:
            self._status(IC["read"], PRIMARY, "Card has:",
                          '"%s"' % existing, "tap to continue")
        else:
            self._status(IC["read"], INK_SOFT, "Blank card",
                          "no text found", "tap to continue")

    def paint_scanning(self, label):
        self._set_text("scn_label", label)
        self._show("scan")

    def paint_already(self, label):
        self._status(IC["ok"], OK, 'Already "%s"' % label,
                     "no change needed", "tap to continue")

    def paint_written(self, label, count):
        self._status(IC["ok"], OK, '"%s" written!' % label,
                     "%d written so far" % count, "tap to continue")

    def paint_write_failed(self, label):
        self._status(IC["fail"], DANGER, "Write failed", label,
                     "tap to continue")

    def paint_writing(self, label):
        self._status(IC["busy"], PRIMARY, 'Writing "%s"...' % label,
                     "hold card steady", tap_dismiss=False)

    def paint_done(self, label, written, total):
        self._status(IC["ok"], OK, "%s done!" % label,
                     "%d of %d written" % (written, total),
                     "tap to continue")

    def paint_complete(self, msg="All tags ready!"):
        self._status(IC["ok"], OK, msg, tap_dismiss=True)

    def paint_error(self, msg):
        self._status(IC["fail"], DANGER, msg, tap_dismiss=True)

    def paint_mode_change(self, to_mode):
        self._status(IC["busy"], PRIMARY, "-> %s" % to_mode,
                     tap_dismiss=False)

    def paint_no_pickup_hint(self):
        self._status(IC["warn"], CAUTION, "pickup off", "DONE to serve",
                     tap_dismiss=False)

    def paint_tag_list(self, entries, cursor):
        """Tier 1: games + Utility Tags + DONE. Breadcrumb reads the
        pickup-off warning -- the AP is always down in WRITE mode."""
        self._set_text("lst_crumb", IC["warn"] + " pickup off")
        self._set_color("lst_crumb", CAUTION)
        self._roller_set([_fit(e) for e in entries])
        self._roller.set_selected(cursor, lv.ANIM.OFF)
        self._set_track(cursor, len(entries))
        cur = entries[cursor] if entries else ""
        btn = self._btns["lst_act"]
        if cur == "DONE":
            btn.set_btn_text(IC["serve"] + " SERVE")
        else:
            btn.set_btn_text(IC["open"] + " OPEN")
        self._btns["lst_back"].add_flag(lv.obj.FLAG.HIDDEN)
        self._show("list")

    def paint_tag_group(self, title, rows, cursor, written):
        """Tier 2: one group's tags + "< back". Breadcrumb names the
        group so the user always knows which list they are in."""
        self._set_text("lst_crumb", IC["back"] + " " + title)
        self._set_color("lst_crumb", INK_SOFT)
        display_rows = []
        for r in rows:
            if r == "< back" or not written or not written.get(r):
                display_rows.append(_fit(r))
            else:
                display_rows.append(_fit("%s  \xb7%d" % (r, written.get(r, 0))))
        self._roller_set(display_rows)
        self._roller.set_selected(cursor, lv.ANIM.OFF)
        self._set_track(cursor, len(rows))
        cur = rows[cursor] if rows else ""
        btn = self._btns["lst_act"]
        if cur == "< back":
            btn.set_btn_text(IC["back"] + " BACK")
        else:
            btn.set_btn_text(IC["scan"] + " SCAN")
        self._btns["lst_back"].remove_flag(lv.obj.FLAG.HIDDEN)
        self._show("list")

    def paint_serve(self, ssid, pickups=0):
        self._set_text("srv_ssid", ssid)
        self._set_text("srv_pickups", "pickups: %d total" % pickups)
        self._show("serve")


def demo():
    """Cycle screens — run from REPL: import dial_ui; dial_ui.demo()

    Includes a long tag list / long group and non-zero written counts, to
    exercise roller scrolling, the position track and the middle-of-list
    styling that a 2-3 row demo would never reach.
    """
    import time
    M5.begin()
    ui = DialUI()
    ui.begin()
    long_games = ["Game %d" % i for i in range(1, 13)] + ["Utility Tags", "DONE"]
    long_group_rows = (
        ["getcode:my_super_long_melody_name", "my_super_long_melody_name"]
        + ["note_%s" % c for c in "cdefgab"] + ["< back"])
    long_written = {"note_c": 3, "note_d": 1, "note_e": 12}
    screens = [
        lambda: ui.paint_idle(True),
        lambda: ui.paint_receiving("Melody"),
        lambda: ui.paint_tag_list(["Melody", "Utility Tags", "DONE"], 0),
        lambda: ui.paint_tag_list(long_games, 6),
        lambda: ui.paint_tag_group(
            "Melody", ["getcode:my_melody", "my_melody", "note_c", "< back"],
            2, {"note_c": 3}),
        lambda: ui.paint_tag_group("Melody", long_group_rows, 5, long_written),
        lambda: ui.paint_no_pickup_hint(),
        lambda: ui.paint_armed("getcode", 1, 1),
        lambda: ui.paint_scanning("getcode"),
        lambda: ui.paint_writing("getcode"),
        lambda: ui.paint_already("getcode"),
        lambda: ui.paint_written("getcode", 3),
        lambda: ui.paint_write_failed("getcode"),
        lambda: ui.paint_read_result("getcode:my_melody"),
        lambda: ui.paint_read_result(None),
        lambda: ui.paint_done("getcode", 1, 1),
        lambda: ui.paint_complete(),
        lambda: ui.paint_mode_change("SERVE"),
        lambda: ui.paint_serve("SP-FILEPUSH", 2),
        lambda: ui.paint_error("no game to serve"),
    ]
    for fn in screens:
        fn()
        time.sleep_ms(2000)
