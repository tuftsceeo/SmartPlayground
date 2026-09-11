"""dial_ui.py — LVGL / m5ui screens behind bbox_ui.py's painter API.

Same method names and signatures as BboxUI so bdial_server.py stays a
near-copy of bbox_server.py. Four pages are built once in begin() and
re-textured per paint (down from a prior one-page-per-state design) --
dial_board.py's Phase 0 log records a real hardware failure, "H5 FAIL --
SoftAP OOM with 8 LVGL pages resident (~40 kB free)", with 17 pages
resident at the time. Fewer resident pages is not just tidier code, it is
the fix for that failure -- re-run the Stage 11 probe in tools/probe_dial.py
after any change here and update the H5 line with the new numbers.

## Stack: m5ui/LVGL, and why the Box is on a different one

M5's docs say "do not mix M5GFX, M5Widgets and M5UI simultaneously", and
recommend M5UI/LVGL for new interactive UI. This file follows that: it is
cleanly `m5ui` + raw `lvgl`, never `M5.Lcd` or `M5.Widgets`. (Raw `lv.obj`
primitives -- the scan ring and the position track -- are NOT mixing;
m5ui is built on LVGL, so they are one stack.)

The peer file bbox_ui.py CANNOT follow that recommendation. The Box's
StickS3 UIFlow2 build has no `m5ui` module at all (`ImportError`,
confirmed on the device 2026-09-10), so it runs on `M5.Widgets`. That is
a hardware fact, not a style choice, and it is why the two files
hand-duplicate the palette block below instead of sharing a theme
module: they must stay on separate rendering stacks.

None of bbox_ui.py's redraw workarounds belong here. That file clears and
fully redraws every screen, blanks a label before setting it, and
sandwiches a rect recolour around every label on a saturated background
-- all because `Widgets` draws immediately with no scene graph. LVGL is a
real retained-mode compositor: re-texture the resident page and call
screen_load(). Do not port those patterns. Likewise the Box's "only
bullet and degree render" glyph finding is about the MCU's baked
Montserrat subset under `Widgets`; LVGL ships the lv.SYMBOL set, so the
icons below are safe.

## Brand system

Colours come from Live_Page/.design_system/Sept 2026/tokens/ -- the same
tokens bbox_ui.py carries, so the "PEER copy" comment is literally true.
Role assignment matches the Box: pink is the one primary action per
screen, purple (write-fg/bg) is the selection and anything write-mode,
teal (serve-fg) is success and share-mode, amber/red are warn and danger.

Form comes from Bag2/Code/DialSpeaker/Dial_Music.py, the Music Dial that
already runs LVGL on this display: light page, borderless buttons,
generous radius, a large montserrat_24 symbol, and soft drop shadows.
One upgrade over that reference -- the design system says shadows are
coloured, never neutral ("pink actions glow pink"), so the primary
button's shadow is PINK_DARK rather than Dial_Music's grey.

Two brand rules this file can honour that bbox_ui.py physically cannot:
"nothing in the product is square" (LVGL has set_style_radius; the Box's
Widgets.Rectangle had no confirmed rounded-rect) and coloured shadows
(no Widgets equivalent at all).

**Casing deliberately diverges from the design system.** The brand readme
says "Sentence case everywhere". Firmware here uses Title Case, by
explicit direction, because these screens are read at arm's length in a
classroom rather than in a browser. This is intentional -- do not "fix"
it back to sentence case. ALL-CAPS is reserved for button labels
(OPEN/SHARE/WRITE/BACK), which is its own convention, not raw data.

Design notes (round-display / small-screen navigation):
  - The tag list is a real m5ui.M5Roller (centre-selected wheel), the
    canonical crown/encoder list widget, rather than three bare labels.
  - A breadcrumb chip at the top always names the current tier, so a
    two-level hierarchy (games -> tags) never leaves the user unsure
    which list they are looking at.
  - A raw-LVGL position track on the right rim shows list extent and
    position, built from two plain lv.obj rectangles. NOTE: an earlier
    version of this docstring claimed M5Arc/M5Bar signatures "were not
    available to verify" -- that was wrong. M5UI does ship M5Arc and
    M5Bar. The raw rectangles are kept because they work and swapping
    widgets is unrelated risk; M5Arc is the obvious follow-up for a rim
    indicator that actually follows the round bezel.
  - Every widget is placed against the round bezel's chord width at its
    OWN top and bottom edge, not just a flat inset -- see _SAFE_NOTE.

Unverified on hardware -- confirm with tools/probe_dial.py's roller probe
and the demo() sweep below before trusting this on a device:
  - Per-part styling (MAIN vs SELECTED) on M5Roller taking a different
    font and colour per part, the way raw lv_roller supports it upstream.
    M5's own roller example styles nothing per-part, so this is the one
    genuinely open question -- and it is what draws the purple selection
    band. If it silently no-ops, fall back to Dial_Music.py's proven
    pattern (a centred current-item label plus prev/next affordances),
    not to a third invented approach.
  - M5Roller.set_options() accepting a python list at runtime. The
    constructor's `options=` list form is vendor-documented; set_options
    is not, so _roller_set() keeps a newline-joined fallback.
"""

import time

import M5
import m5ui
import lvgl as lv

from dial_board import SCREEN_W, SCREEN_H, SPEAKER_VOLUME
from dial_input import NEXT, PREV, ACT, BACK, EXIT

# Brand tokens, from Live_Page/.design_system/Sept 2026/tokens/.
# PEER copy: BroadcastBox/BBoxFirmware/bbox_ui.py -- keep in sync.
PAGE_BG = 0xF7F7FB       # --bg: page ground (violet-tinted, not pure white)
CARD_BG = 0xFFFFFF       # --surface: card/roller fill
INK = 0x231F2E           # --ink: primary text
INK_2 = 0x3A3345         # --ink-2
INK_3 = 0x5B5468         # --ink-3: secondary text/hints
MUTED = 0x8B859A         # --muted
BORDER = 0xE8E6F0        # --border: hairline border, inactive track

PINK = 0xEF4D92          # --pink: the brand's one primary-action colour
PINK_DARK = 0xD13A7C     # used for the primary button's coloured glow

WRITE_FG = 0x6C4CD1      # --write-fg (== --purple): WRITE-mode accent
WRITE_BG = 0xF2EEFC      # --write-bg: the roller's selected band
SERVE_FG = 0x1C9A82      # --serve-fg (== --teal-dark): SERVE-mode + success
SERVE_BG = 0xE9FBF6      # --serve-bg
DANGER_FG = 0xC0392B     # --danger
DANGER_BG = 0xFDECEA     # --danger-bg
WARN_FG = 0xA8781E       # --warn
WARN_BG = 0xFFF8E0       # --warn-bg

WHITE = 0xFFFFFF         # button/chip text on a saturated fill

FONT14 = None
FONT16 = None
FONT24 = None

# lv.SYMBOL.* glyphs -- ship with the LVGL font, no flash/manifest cost.
IC = {}

# _SAFE_NOTE: this is a 240x240 ROUND panel, so the usable width at any
# row y is the circle's chord there, not 240. Half-chord at row y is
# sqrt(120^2 - (y-120)^2): ~120px at the middle, but only ~56px at y=226.
# A widget must fit the chord at its own TOP and BOTTOM edge, whichever is
# tighter -- a full-width bar like the Box's SERVE banner has its corners
# cut off, which is why the banner became an inset pill here. The bottom
# button row sits at y=158..200 for exactly this reason; it used to run to
# y=234, where only ~75px of width actually exists.

# Roller rows are not clipped by the widget, so a long tag name just runs
# past its row. ROW_CHARS is a rough character-count budget, not a
# measured pixel width -- confirm it against the real roller width on
# hardware.
ROW_CHARS = 26

ELLIPSIS = "..."


def _fit(text, budget=ROW_CHARS):
    """Truncate to budget, keeping the START and appending ELLIPSIS.

    An earlier version split the budget between head and tail (keeping
    both ends, ellipsizing the middle) specifically so a numbered variant
    like "getcode:my_melody_2" stayed distinguishable from
    "getcode:my_melody". Reported on the Box's hardware as a net loss: it
    cut the meaningful prefix ("getcode:...") down to a few characters to
    make room for a tail fragment nobody was reading. Same tag names on
    the same list here, so the same trade applies -- keep this if it
    comes up again.
    """
    if len(text) <= budget:
        return text
    return text[:budget - len(ELLIPSIS)] + ELLIPSIS


def _display_tag(text):
    """Capitalize a raw tag/game identifier for display only.

    bdial_server.py's entries, groups and written-count keys are raw
    lowercase identifiers ("note_c", "getcode:my_melody", "stop") that
    also have to match exactly what is written to a physical NFC card --
    that underlying value is never touched. This only capitalizes the
    first letter for the on-screen copy, so a plain lowercase identifier
    never reads as a typo or an afterthought. Internal colons and
    underscores are left alone.
    """
    return text[:1].upper() + text[1:] if text else text


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


# Bottom action row. Both x positions are used: ACT_X_SOLO centres the
# action button when the back button is hidden (tier 1), ACT_X_PAIR shifts
# it right to make room when both are shown (tier 2).
BTN_Y = 158
BTN_H = 42
# Rim track height. Shortened from the old 120 so the track's own top and
# bottom ends stay inside the bezel's chord at x~=228 (see _SAFE_NOTE):
# at +-60px from centre the circle has only ~104px of half-width left,
# which the old length overran.
TRACK_H = 80
ACT_W = 104
ACT_X_SOLO = (SCREEN_W - ACT_W) // 2
ACT_X_PAIR = 88
BACK_X = 34
BACK_W = 42


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
        self._scan_ring = None

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
        pg = m5ui.M5Page(bg_c=PAGE_BG)
        self._pages[name] = pg
        return pg

    def _label(self, key, parent, text, x, y, font, color=INK, w=200,
               align=lv.ALIGN.TOP_MID):
        lbl = m5ui.M5Label(
            text, x=x, y=y,
            text_c=color, bg_c=PAGE_BG, bg_opa=0,
            font=font, parent=parent)
        lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        lbl.set_width(w)
        lbl.align(align, 0, y)
        self._lbl[key] = lbl
        return lbl

    def _chip(self, key, parent, text, y, font, text_c, bg_c, w=170, pad=6):
        """A filled, rounded, centred label -- the brand's chip/pill.

        Same construction Dial_Music.py uses for its volume overlay (a
        M5Label with a real background, a radius and vertical padding),
        which is the proven way to get a filled pill on this stack
        without a second widget. Used for the breadcrumb and for the
        SERVE screen's purple identifier: the Box paints that as a
        full-width banner at y=0, which would have its corners cut off by
        this round bezel, so it becomes an inset pill instead.
        """
        lbl = m5ui.M5Label(
            text, x=0, y=y,
            text_c=text_c, bg_c=bg_c, bg_opa=255,
            font=font, parent=parent)
        lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        lbl.set_width(w)
        lbl.set_style_radius(14, 0)
        lbl.set_style_pad_top(pad, 0)
        lbl.set_style_pad_bottom(pad, 0)
        lbl.align(lv.ALIGN.TOP_MID, 0, y)
        self._lbl[key] = lbl
        return lbl

    def _button(self, key, parent, text, x, y, w, h, bg, intent,
                font=None, text_c=WHITE, outline=False, glow=None):
        if font is None:
            font = FONT14
        btn = m5ui.M5Button(
            text=text, x=x, y=y, w=w, h=h,
            bg_c=bg if not outline else PAGE_BG,
            text_c=text_c if not outline else bg,
            font=font, parent=parent)
        btn.set_style_radius(w // 2 if w <= h else h // 2, 0)
        if outline:
            btn.set_style_border_width(2, 0)
            btn.set_style_border_color(lv.color_hex(bg), 0)
        else:
            btn.set_style_border_width(0, 0)
        if glow is not None:
            # Coloured shadow, per the design system's "shadows are
            # coloured, never neutral". Dial_Music.py uses the same three
            # calls with a grey; the brand asks for the action's own hue.
            btn.set_style_shadow_width(12, 0)
            btn.set_style_shadow_color(lv.color_hex(glow), 0)
            btn.set_style_shadow_opa(70, 0)
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
        """The constructor's `options=` list form is vendor-documented;
        set_options() at runtime is not, so fall back to a newline-joined
        string if the list form raises on this firmware build."""
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
        fill_h = max(8, int(TRACK_H * frac))
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

        # Breadcrumb as a real purple chip rather than bare text: it is
        # the mode indicator as much as the tier indicator, and purple is
        # WRITE mode throughout both devices.
        self._chip("lst_crumb", pg, "", 12, FONT14, WRITE_FG, WRITE_BG, w=170)

        # Position track -- a hairline channel with a purple fill that
        # grows from the bottom as the cursor advances toward the end.
        # Shortened from 120 to TRACK_H so its own ends stay inside the
        # round bezel's chord at that height (see _SAFE_NOTE).
        track = lv.obj(pg)
        track.set_size(6, TRACK_H)
        track.align(lv.ALIGN.RIGHT_MID, -6, 4)
        track.set_style_bg_color(lv.color_hex(BORDER), 0)
        track.set_style_bg_opa(255, 0)
        track.set_style_border_width(0, 0)
        track.set_style_radius(3, 0)
        track.remove_flag(lv.obj.FLAG.CLICKABLE)
        fill = lv.obj(track)
        fill.set_size(6, 8)
        fill.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        fill.set_style_bg_color(lv.color_hex(WRITE_FG), 0)
        fill.set_style_bg_opa(255, 0)
        fill.set_style_border_width(0, 0)
        fill.set_style_radius(3, 0)
        fill.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._track_fill = fill

        roller = m5ui.M5Roller(
            x=36, y=46, w=168, h=96, options=[""],
            mode=lv.roller.MODE.NORMAL, selected=0, visible_row_count=3,
            font=FONT16, parent=pg)
        # Offset left of centre to clear the rim track. Span works out to
        # x=32..200; the bezel's chord at y=46 allows 25.5..214.5, so this
        # keeps a real margin on both sides rather than a half-pixel one.
        roller.align(lv.ALIGN.TOP_MID, -4, 46)
        roller.set_style_radius(16, 0)          # brand card radius
        roller.set_style_bg_color(lv.color_hex(CARD_BG), 0)
        roller.set_style_border_width(1, 0)
        roller.set_style_border_color(lv.color_hex(BORDER), 0)
        roller.set_style_text_color(lv.color_hex(INK_3), 0)
        roller.set_style_text_font(FONT14, 0)
        # The purple selection band -- the single most important piece of
        # this restyle, and the one thing in this file that no vendor
        # example confirms. See the module docstring's fallback.
        roller.set_style_bg_color(lv.color_hex(WRITE_BG), lv.PART.SELECTED)
        roller.set_style_text_color(lv.color_hex(WRITE_FG), lv.PART.SELECTED)
        roller.set_style_text_font(FONT16, lv.PART.SELECTED)
        # Encoder/buttons drive the cursor; a stray touch must not let LVGL's
        # own selection drift out of sync with the server's cursor index.
        roller.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._roller = roller

        self._button("lst_back", pg, IC["back"], BACK_X, BTN_Y, BACK_W, BTN_H,
                     INK_3, BACK, FONT16, outline=True)
        self._button("lst_act", pg, IC["open"] + " OPEN",
                     ACT_X_SOLO, BTN_Y, ACT_W, BTN_H,
                     PINK, ACT, FONT14, glow=PINK_DARK)

    def _build_scan(self):
        pg = self._page("scan")
        ring = lv.obj(pg)
        ring.set_size(200, 200)
        ring.align(lv.ALIGN.CENTER, 0, -6)
        ring.set_style_bg_opa(0, 0)
        ring.set_style_border_width(6, 0)
        ring.set_style_border_color(lv.color_hex(WRITE_FG), 0)
        ring.set_style_radius(100, 0)
        ring.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._scan_ring = ring
        self._label("scn_icon", pg, IC["scan"], 0, 55, FONT24, WRITE_FG, w=170)
        self._label("scn_label", pg, "", 0, 100, FONT16, INK, w=180)
        self._label("scn_hint", pg, "Hold Card on Screen", 0, 140, FONT14,
                    INK_3, w=180)
        self._button("scn_back", pg, IC["back"] + " BACK", 70, 178, 100, 40,
                     INK_3, BACK, FONT14, outline=True)

    def _build_status(self):
        """One reusable screen behind every one-shot painter -- booting,
        idle, receiving, armed, writing/written/write_failed/already,
        done, complete, error, mode_change, no_pickup_hint, read_result.
        Re-textured and re-tinted per call rather than rebuilt."""
        pg = self._page("status")
        self._label("st_glyph", pg, "", 0, 34, FONT24, WRITE_FG, w=170)
        self._label("st_title", pg, "", 0, 90, FONT16, INK, w=200)
        self._label("st_body1", pg, "", 0, 120, FONT14, INK_3, w=200)
        self._label("st_body2", pg, "", 0, 144, FONT14, INK_3, w=200)
        # Whole-page transparent tap target -- dismiss-on-tap for splash
        # screens. Toggled clickable per paint via tap_dismiss.
        tap = m5ui.M5Button(
            text=" ", x=0, y=0, w=SCREEN_W, h=SCREEN_H,
            bg_c=PAGE_BG, text_c=PAGE_BG, font=FONT14, parent=pg)
        tap.set_style_opa(0, 0)
        tap.add_event_cb(self._cb(ACT), lv.EVENT.CLICKED, None)
        tap.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._btns["st_tap"] = tap

    def _build_serve(self):
        pg = self._page("serve")
        # The Box's full-width purple SERVE banner, reshaped for a round
        # panel: an inset pill carrying the icon and the word together.
        # Static text -- LVGL retains it, so paint_serve() never re-sets
        # it (contrast bbox_ui.py, which must redraw everything).
        self._chip("srv_title", pg, IC["serve"] + " Sharing", 44, FONT16,
                   WHITE, WRITE_FG, w=160, pad=8)
        # The SoftAP SSID is deliberately NOT shown -- see paint_serve().
        self._label("srv_pickups", pg, "", 0, 106, FONT16, INK, w=190)
        self._label("srv_hint", pg, "Hold Button to Exit", 0, 142, FONT14,
                    INK_3, w=190)
        self._button("srv_close", pg, IC["fail"] + " CLOSE", 70, 180, 100, 42,
                     PINK, EXIT, FONT14, glow=PINK_DARK)

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
        self._status(IC["busy"], INK_3, "Starting", tap_dismiss=False)

    def paint_idle(self, linked=True):
        # No "Broadcast Dial" title: decorative branding was dropped from
        # both devices, functional state text kept. The link status IS
        # the state, so it is the title.
        status = "Linked to Laptop" if linked else "Not Linked"
        self._status(
            IC["usb"], SERVE_FG if linked else INK_3,
            status, "No Game Loaded Yet",
            tap_dismiss=False)

    def paint_receiving(self, game_name=""):
        self._status(
            IC["busy"], WRITE_FG,
            _display_tag(game_name) if game_name else "Game",
            tap_dismiss=False)

    def paint_armed(self, label, index=1, total=1):
        self._status(
            IC["scan"], WRITE_FG, '"%s"' % _display_tag(label),
            "Tag %d/%d" % (index, total), "Hold Near Reader",
            tap_dismiss=False)

    def paint_read_result(self, existing):
        if existing:
            self._status(IC["read"], WRITE_FG, "Card Has:",
                         '"%s"' % _display_tag(existing), "Tap to Continue")
        else:
            self._status(IC["read"], INK_3, "Blank Card",
                         "No Text Found", "Tap to Continue")

    def paint_scanning(self, label):
        self._set_text("scn_label", '"%s"' % _display_tag(label))
        self._show("scan")

    def paint_already(self, label):
        self._status(IC["ok"], SERVE_FG, 'Already "%s"' % _display_tag(label),
                     "No Change Needed", "Tap to Continue")

    def paint_written(self, label, count):
        self._status(IC["ok"], SERVE_FG, '"%s" Written!' % _display_tag(label),
                     "%d Written So Far" % count, "Tap to Continue")

    def paint_write_failed(self, label):
        self._status(IC["fail"], DANGER_FG, "Write Failed",
                     '"%s"' % _display_tag(label), "Tap to Continue")

    def paint_writing(self, label):
        self._status(IC["busy"], WRITE_FG,
                     'Writing "%s"...' % _display_tag(label),
                     "Hold Card Steady", tap_dismiss=False)

    def paint_done(self, label, written, total):
        self._status(IC["ok"], SERVE_FG, "%s Done!" % _display_tag(label),
                     "%d of %d Written" % (written, total),
                     "Tap to Continue")

    def paint_complete(self, msg="All Tags Ready!"):
        self._status(IC["ok"], SERVE_FG, msg, tap_dismiss=True)

    def paint_error(self, msg):
        self._status(IC["fail"], DANGER_FG, msg, tap_dismiss=True)

    def paint_mode_change(self, to_mode):
        # to_mode is bdial_server's raw mode constant ("SERVE"/"WRITE") --
        # only the DISPLAYED word changes here, to match the SHARE naming.
        # Kept ALL-CAPS deliberately: this mirrors the action-button
        # convention, not the Title Case applied to the rest of the copy.
        tint = SERVE_FG if to_mode == "SERVE" else WRITE_FG
        shown = "SHARE" if to_mode == "SERVE" else to_mode
        self._status(IC["busy"], tint, "-> %s" % shown, tap_dismiss=False)

    def paint_no_pickup_hint(self):
        self._status(IC["warn"], WARN_FG, "Pickup Off", "DONE to Share",
                     tap_dismiss=False)

    def paint_tag_list(self, entries, cursor):
        """Tier 1: games + Utility Tags + DONE.

        The DONE sentinel is bdial_server's, used verbatim in `entries`/
        `cursor` logic -- only its DISPLAYED text changes here, to
        "Enable Share".
        """
        # Positive mode label rather than a warning about what's disabled:
        # WRITE mode always has the AP down, so the old "pickup off"
        # breadcrumb read as an alarm about a normal, permanent state.
        self._set_text("lst_crumb", "Tag Writer")
        display_entries = ["Enable Share" if e == "DONE" else e
                           for e in entries]
        self._roller_set([_fit(e) for e in display_entries])
        self._roller.set_selected(cursor, lv.ANIM.OFF)
        self._set_track(cursor, len(entries))
        cur = entries[cursor] if entries else ""
        btn = self._btns["lst_act"]
        if cur == "DONE":
            btn.set_btn_text(IC["serve"] + " SHARE")
        else:
            btn.set_btn_text(IC["open"] + " OPEN")
        # Back is hidden here, so re-centre the action button rather than
        # leaving it parked in its two-button position. align() rather than
        # set_pos(): align() is already exercised on m5ui wrappers elsewhere
        # in this file, set_pos() is not.
        btn.align(lv.ALIGN.TOP_LEFT, ACT_X_SOLO, BTN_Y)
        self._btns["lst_back"].add_flag(lv.obj.FLAG.HIDDEN)
        self._show("list")

    def paint_tag_group(self, title, rows, cursor, written):
        """Tier 2: one group's tags + "< back". Breadcrumb names the
        group so the user always knows which list they are in."""
        self._set_text("lst_crumb", _fit(IC["back"] + " " + title, 20))
        display_rows = []
        for r in rows:
            if r == "< back":
                # "< back" -> "< Back": not run through _display_tag(),
                # whose first-letter capitalization would land on the
                # leading "<" instead of the word "back".
                display_rows.append("< Back")
            elif not written or not written.get(r):
                display_rows.append(_display_tag(r))
            else:
                display_rows.append("%s (%d)" % (_display_tag(r),
                                                 written.get(r, 0)))
        self._roller_set([_fit(r) for r in display_rows])
        self._roller.set_selected(cursor, lv.ANIM.OFF)
        self._set_track(cursor, len(rows))
        cur = rows[cursor] if rows else ""
        btn = self._btns["lst_act"]
        if cur == "< back":
            btn.set_btn_text(IC["back"] + " BACK")
        else:
            btn.set_btn_text(IC["scan"] + " WRITE")
        btn.align(lv.ALIGN.TOP_LEFT, ACT_X_PAIR, BTN_Y)
        self._btns["lst_back"].remove_flag(lv.obj.FLAG.HIDDEN)
        self._show("list")

    def paint_serve(self, ssid, pickups=0):
        # `ssid` is accepted for call-site parity with bdial_server.py but
        # deliberately never shown -- the SoftAP name is not information a
        # teacher needs; that the box is sharing, and the pickup count,
        # are. Kept as a parameter rather than dropped so bdial_server.py
        # needs no change.
        self._set_text("srv_pickups", "Pickups: %d Total" % pickups)
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
        lambda: ui.paint_error("No Game to Serve"),
    ]
    # get_options() is a documented M5Roller getter -- assert the rows
    # actually landed rather than eyeballing the wheel, since set_options()
    # at runtime is the one roller call no vendor example covers.
    ui.paint_tag_list(long_games, 6)
    print("### roller options after set: %r" % (ui._roller.get_options(),))
    for fn in screens:
        fn()
        time.sleep_ms(2000)
