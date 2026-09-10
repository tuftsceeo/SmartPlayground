"""bbox_ui.py — M5.Widgets screens + M5.Speaker feedback for Broadcast Box.

Third UI attempt for this file. History, in order:
  1. m5ui/lvgl port -- failed on hardware: this board's UIFlow2 build has
     no `m5ui` module at all (`ImportError: no module named 'm5ui'`).
  2. Direct M5.Lcd/M5GFX drawing (fillRect/print) -- worked, but text-only
     and landscape.
  3. This file: `Widgets` (`M5.Widgets`, exposed via `from M5 import *`) --
     the mid-tier retained-mode shape/label library, confirmed present in
     UIFlow2's own blockly-generated code for this exact board. Portrait
     135x240 (`Widgets.setRotation(0)`), per a hand-drawn mockup that used
     this orientation and this API directly.

Portrait is a real change from the landscape 240x135 every prior version
of this file used -- confirm the physical mounting/holding of the Box
tolerates that before relying on it in the field.

## Brand system

Colors, type and copy voice come from
`Live_Page/.design_system/Sept 2026/` (see its readme.md), adapted to
what `Widgets` can actually render:

  - WRITE-mode accents use the brand's own `--write-fg`/`--write-bg`
    (purple) tokens; SERVE-mode and generic success reuse
    `--serve-fg`/`--serve-bg` (teal) -- the design system already assigns
    teal to "connect, success, progress", so this isn't a stretch, it's
    the documented meaning. `--danger`/`--danger-bg` and `--warn`/
    `--warn-bg` are used verbatim. The brand's primary action colour
    (pink) is reserved for the one main tap-target per screen, matching
    its documented role as "the primary action, the brand".
  - Neutrals are the brand's violet-tinted family (`--ink`, `--ink-3`,
    `--muted`, `--border`, `--bg`), not true greys.
  - Fonts: the brand runs on Nunito (UI) and Patrick Hand (accent);
    neither is available on this MCU's built-in font set. Montserrat
    (`Widgets.FONTS.Montserrat12/16/18` -- the only sizes confirmed
    against this board's own UIFlow2-generated code) stands in for
    Nunito. Patrick Hand has no equivalent here and is dropped.
  - Icons: the brand's SVG stroke-icon system cannot render through
    `Widgets`. Its own documented fallback -- plain "->"/"<-" text and
    `</>`-style literal characters -- carries over directly; a `Triangle`
    approximates a chevron the way the source mockup used one.
  - Gradients (every brand button is a two-stop 135deg gradient) have no
    `Widgets` equivalent -- flat fills use the gradient's first stop.
  - Corner radii ("nothing in the product is square") are NOT confirmed
    available on `Widgets.Rectangle` -- the mockup this file is based on
    only ever drew plain rectangles. If a rounded-rect primitive exists,
    this is worth revisiting; until confirmed on hardware, treat every
    box in this file as square-cornered.

Same painter-method API as dial_ui.DialUI, so bbox_server.py stays a
near-copy of bdial_server.py.
"""

import time

import M5
from M5 import *  # noqa: F401,F403 -- brings in `Widgets`, per the confirmed working pattern

# Brand tokens, from Live_Page/.design_system/Sept 2026/tokens/{colors,semantic}.css.
# Flat fills only -- Widgets has no gradient primitive, so each *_GRAD pair
# below collapses to its first (lighter) stop.
PAGE_BG = 0xF7F7FB       # --bg: page ground (violet-tinted, not pure white)
CARD_BG = 0xFFFFFF       # --surface: card/row fill
INK = 0x231F2E           # --ink: primary text
INK_2 = 0x3A3345         # --ink-2
INK_3 = 0x5B5468         # --ink-3: secondary text/hints
MUTED = 0x8B859A         # --muted
BORDER = 0xE8E6F0        # --border: hairline card border

PINK = 0xEF4D92          # --pink: the brand's one primary-action color
PINK_DARK = 0xD13A7C

WRITE_FG = 0x6C4CD1      # --write-fg (== --purple): WRITE-mode accent
WRITE_BG = 0xF2EEFC      # --write-bg
SERVE_FG = 0x1C9A82      # --serve-fg (== --teal-dark): SERVE-mode + success
SERVE_BG = 0xE9FBF6      # --serve-bg
DANGER_FG = 0xC0392B     # --danger
DANGER_BG = 0xFDECEA     # --danger-bg
WARN_FG = 0xA8781E       # --warn
WARN_BG = 0xFFF8E0       # --warn-bg

ROTATION = 0
SCREEN_W = 135
SCREEN_H = 240

# 0-255. StickS3's own docs warn to stay under ~75% (~191) on battery power
# to avoid a brown-out reboot when USB is unplugged.
SPEAKER_VOLUME = 190

FONT12 = None
FONT16 = None
FONT18 = None


def _fonts():
    global FONT12, FONT16, FONT18
    if FONT12 is not None:
        return
    FONT12 = Widgets.FONTS.Montserrat12
    FONT16 = Widgets.FONTS.Montserrat16
    FONT18 = Widgets.FONTS.Montserrat18


# Card interior text budgets are character-count estimates for proportional
# Montserrat on a 119px-wide card, not measured pixel widths -- confirm on
# the device. The tail of a tag name is what distinguishes
# "getcode:my_melody" from "getcode:my_melody_2", so ellipsize the middle.
ROW_CHARS = 16
SELECTED_CHARS = 13
HEADER_CHARS = 20


def _fit(text, budget):
    if len(text) <= budget:
        return text
    keep = budget - 1
    head = (keep + 1) // 2
    tail = keep - head
    return text[:head] + "…" + text[len(text) - tail:]


# Fixed 5-slot carousel: 2 rows above the cursor, the cursor's own row
# (always rendered in the single, visually distinct SELECTED slot), 2
# rows below. Unlike the old MAX_ROWS/_window() scheme this never shifts
# to avoid blank slots near a list's edges -- a slot with nothing at that
# offset is simply blank, which is less surprising than a shifting window
# once the selected row is a fixed screen position rather than "wherever
# the cursor happens to land in a moving strip".
ROWS_ABOVE = 2
ROWS_BELOW = 2


def _slots(entries, cursor):
    """[(text_or_empty, is_selected), ...] for ROWS_ABOVE+1+ROWS_BELOW slots."""
    n = len(entries)
    out = []
    for offset in range(-ROWS_ABOVE, ROWS_BELOW + 1):
        idx = cursor + offset
        text = entries[idx] if 0 <= idx < n else ""
        out.append((text, offset == 0))
    return out


# Row layout (portrait 135x240) -- see module docstring for the derivation.
ROW_H = 32
ROW_GAP = 3
ROW_Y0 = 28
ROW_X = 4
ROW_W = 119
TRACK_X = 125
TRACK_W = 6
BTN_Y = 208
BTN_H = 26


class BboxUI(object):
    def __init__(self):
        # No M5/Widgets calls here -- BboxServer.__init__ constructs this
        # before M5.begin(). begin() is called from run() right after it.
        self._built = False
        self._row_rects = []
        self._row_labels = []
        self._track_dots = []
        self._crumb = None
        self._act_rect = None
        self._act_label = None
        self._next_rect = None
        self._next_tri = None
        self._st_title = None
        self._st_body1 = None
        self._st_body2 = None
        self._st_hint = None
        self._srv_title = None
        self._srv_ssid = None
        self._srv_pickups = None
        self._srv_hint = None
        self._groups = []  # [(name, [widgets...])] for _show()

    def begin(self):
        """Call once, right after M5.begin() -- not before.

        Unguarded, same reasoning as the m5ui attempt this replaces: a UI
        that cannot initialise is a crash, not a silently half-drawn
        screen. If `Widgets` itself is ever missing on a future build,
        this raises loudly here rather than limping along.
        """
        _fonts()
        Widgets.setRotation(ROTATION)
        Widgets.fillScreen(PAGE_BG)
        try:
            M5.Speaker.setVolume(SPEAKER_VOLUME)
        except Exception as e:
            print("# speaker volume err: %s" % str(e))
        if not self._built:
            self._build_all()
            self._built = True

    # ── construction ─────────────────────────────────────────────

    def _card(self, x, y, w, h, border, fill):
        return Widgets.Rectangle(x, y, w, h, border, fill)

    def _label(self, text, x, y, text_c, bg_c, font):
        return Widgets.Label(text, x, y, 1.0, text_c, bg_c, font)

    def _build_all(self):
        self._build_list()
        self._build_status()
        self._build_serve()
        # Groups toggled by _show(); "list" is the default first paint.
        self._groups = [
            ("list", self._list_widgets),
            ("status", self._status_widgets),
            ("serve", self._serve_widgets),
        ]
        self._show("status")

    def _build_list(self):
        self._crumb = self._label("", 4, 6, WARN_FG, PAGE_BG, FONT12)

        for i in range(ROWS_ABOVE + 1 + ROWS_BELOW):
            y = ROW_Y0 + i * (ROW_H + ROW_GAP)
            selected = (i == ROWS_ABOVE)
            if selected:
                rect = self._card(ROW_X, y, ROW_W, ROW_H, WRITE_FG, WRITE_BG)
                lbl = self._label("", ROW_X + 6, y + 8, WRITE_FG, WRITE_BG, FONT16)
            else:
                rect = self._card(ROW_X, y, ROW_W, ROW_H, BORDER, CARD_BG)
                lbl = self._label("", ROW_X + 6, y + 9, INK_3, CARD_BG, FONT12)
            self._row_rects.append(rect)
            self._row_labels.append(lbl)

        # Per-row indicator dots rather than a resized/repositioned fill bar:
        # Rectangle.setColor() is docs-confirmed, but no setSize()/setCursor()
        # equivalent for Rectangle was -- recolouring a fixed dot per row
        # avoids relying on an unconfirmed resize API. _paint_slots() lights
        # a dot WRITE_FG when its row slot holds a real entry and blends it
        # into PAGE_BG when the slot is off the end of the list, e.g. a
        # 3-item list blends the last dot or two away instead of leaving a
        # stray box.
        self._track_dots = []
        for i in range(ROWS_ABOVE + 1 + ROWS_BELOW):
            y = ROW_Y0 + i * (ROW_H + ROW_GAP)
            dot = self._card(TRACK_X, y, TRACK_W, ROW_H, BORDER, BORDER)
            self._track_dots.append(dot)

        self._act_rect = self._card(4, BTN_Y, 88, BTN_H, PINK, PINK)
        self._act_label = self._label("", 14, BTN_Y + 6, 0xFFFFFF, PINK, FONT16)

        self._next_rect = self._card(96, BTN_Y, 35, BTN_H, BORDER, CARD_BG)
        # Downward chevron -- "next" (BtnB). Static; never recoloured.
        # (An earlier revision also added a "B: next" text hint here --
        # reported on hardware as redundant with this icon, and removed.)
        self._next_tri = Widgets.Triangle(
            105, BTN_Y + 8, 122, BTN_Y + 8, 113, BTN_Y + 20, INK_3, INK_3)

        self._list_widgets = (
            [self._crumb] + self._row_rects + self._row_labels
            + self._track_dots
            + [self._act_rect, self._act_label, self._next_rect, self._next_tri])

    def _build_status(self):
        """One reusable screen behind every one-shot painter -- booting,
        idle, receiving, armed, overwrite, scanning, writing/written/
        write_failed/already, done, complete, error, mode_change,
        no_pickup_hint."""
        self._st_title = self._label("", 6, 60, INK, PAGE_BG, FONT18)
        self._st_body1 = self._label("", 6, 100, INK_3, PAGE_BG, FONT12)
        self._st_body2 = self._label("", 6, 124, INK_3, PAGE_BG, FONT12)
        self._st_hint = self._label("", 6, 200, MUTED, PAGE_BG, FONT12)
        self._status_widgets = [self._st_title, self._st_body1, self._st_body2, self._st_hint]

    def _build_serve(self):
        self._srv_title = self._label("Sharing", 6, 40, SERVE_FG, PAGE_BG, FONT18)
        self._srv_ssid = self._label("", 6, 76, INK, PAGE_BG, FONT16)
        self._srv_pickups = self._label("", 6, 104, INK_3, PAGE_BG, FONT12)
        self._srv_hint = self._label("hold button to leave", 6, 200, MUTED, PAGE_BG, FONT12)
        self._serve_widgets = [self._srv_title, self._srv_ssid, self._srv_pickups, self._srv_hint]

    # ── screen switching ─────────────────────────────────────────

    def _show(self, name):
        """The one guarded seam in this file: a paint failure is logged
        with the screen it happened on and re-raised, not swallowed.

        `setVisible` is docs-confirmed on Label/Circle/Image; Rectangle
        and Triangle are assumed to share it via the same base widget
        class ("Widgets — a basic UI library") but this has not been
        exercised on this board specifically -- watch the first real
        screen switch on hardware for a stray AttributeError here.
        """
        try:
            for group_name, widgets in self._groups:
                visible = (group_name == name)
                for w in widgets:
                    w.setVisible(visible)
        except Exception as e:
            print("# _show(%s) FAILED: %s" % (name, str(e)))
            raise

    def _set_text(self, label, text):
        label.setText(text)

    # ── audio (same tones as every prior version of this file) ─────

    def _tone(self, freq, ms):
        try:
            M5.Speaker.tone(freq, ms)
        except Exception as e:
            print("# speaker tone err: %s" % str(e))

    def beep_scan(self):
        self._tone(1000, 30)

    def beep_click(self):
        self._tone(1800, 20)

    def beep_success(self):
        self._tone(523, 100)
        time.sleep_ms(50)
        self._tone(659, 100)
        time.sleep_ms(50)
        self._tone(784, 200)

    def beep_fail(self):
        self._tone(300, 200)
        time.sleep_ms(50)
        self._tone(200, 400)

    # ── status-screen helper ────────────────────────────────────

    def _status(self, title, body1="", body2="", hint="", title_c=INK):
        self._set_text(self._st_title, title)
        self._st_title.setColor(title_c, PAGE_BG)
        self._set_text(self._st_body1, body1)
        self._set_text(self._st_body2, body2)
        self._set_text(self._st_hint, hint)
        self._show("status")

    # ── painters (dial_ui signatures) ───────────────────────────

    def paint_booting(self):
        self._status("Starting", title_c=INK_3)

    def paint_idle(self, linked=True):
        status = "linked to laptop" if linked else "not linked"
        self._status("Broadcast Box", status, "no game loaded yet",
                     title_c=SERVE_FG if linked else INK_3)

    def paint_receiving(self, game_name=""):
        self._status("Getting game...", game_name if game_name else "game")

    def paint_armed(self, label, index=1, total=1):
        self._status(label, "Tag %d/%d" % (index, total),
                     "hold card on reader")

    def paint_overwrite(self, existing, new_label):
        self._status(
            'Overwrite "%s"?' % existing, '-> "%s"' % new_label,
            title_c=WARN_FG,
            hint="A overwrite   B cancel")

    def paint_scanning(self, label):
        self._status(label, "hold card on top", hint="B = back")

    def paint_already(self, label):
        self._status('Already "%s"' % label, "no change needed",
                     title_c=SERVE_FG, hint="press any button")

    def paint_written(self, label, count):
        self._status('"%s" written!' % label, "%d written so far" % count,
                     title_c=SERVE_FG, hint="press any button")

    def paint_write_failed(self, label):
        self._status("Write failed", label, title_c=DANGER_FG,
                     hint="press any button")

    def paint_writing(self, label):
        self._status('Writing "%s"...' % label, "hold card steady")

    def paint_done(self, label, written, total):
        self._status("%s done!" % label, "%d of %d written" % (written, total),
                     title_c=SERVE_FG)

    def paint_complete(self, msg="All tags ready!"):
        self._status(msg, title_c=SERVE_FG)

    def paint_error(self, msg):
        self._status(msg, title_c=DANGER_FG)

    def paint_mode_change(self, to_mode):
        # to_mode is bbox_server's raw mode constant ("SERVE"/"WRITE") --
        # only the DISPLAYED word changes here, to match the SHARE naming.
        tint = SERVE_FG if to_mode == "SERVE" else WRITE_FG
        shown = "SHARE" if to_mode == "SERVE" else to_mode
        self._status("-> %s" % shown, title_c=tint)

    def paint_no_pickup_hint(self):
        self._status("pickup off", "DONE + B1 to share", title_c=WARN_FG)

    def paint_tag_list(self, entries, cursor):
        """Tier 1: games + Utility Tags + DONE.

        The DONE sentinel is bbox_server's, used verbatim in `entries`/
        `cursor` logic -- only its DISPLAYED text changes here, to
        "Enable Share".
        """
        self._set_text(self._crumb, "! pickup off")
        self._crumb.setColor(WARN_FG, PAGE_BG)
        display_entries = ["Enable Share" if e == "DONE" else e for e in entries]
        self._paint_slots(display_entries, cursor)
        cur = entries[cursor] if entries else ""
        self._set_text(self._act_label, "SHARE" if cur == "DONE" else "OPEN")
        self._show("list")

    def paint_tag_group(self, title, rows, cursor, written):
        """Tier 2: one group's tags + "< back"."""
        self._set_text(self._crumb, _fit("< " + title, HEADER_CHARS))
        self._crumb.setColor(INK_3, PAGE_BG)
        display_rows = []
        for r in rows:
            if r == "< back" or not written or not written.get(r):
                display_rows.append(r)
            else:
                display_rows.append("%s ·%d" % (r, written.get(r, 0)))
        self._paint_slots(display_rows, cursor)
        cur = rows[cursor] if rows else ""
        self._set_text(self._act_label, "BACK" if cur == "< back" else "WRITE")
        self._show("list")

    def _paint_slots(self, entries, cursor):
        """Recolour the rectangle and dot FIRST, the label LAST.

        On hardware, a populated row was showing up with real text
        peeking out from behind a blank rectangle covering part of it --
        i.e. the rectangle's own repaint from setColor() was landing on
        top of the label. This library appears to redraw immediately on
        each call rather than maintaining a z-ordered stack, so whichever
        widget is touched most recently wins visually, regardless of the
        order things were constructed in back in _build_list(). Setting
        the label last guarantees it draws on top every time.
        """
        for i, (text, is_selected) in enumerate(_slots(entries, cursor)):
            budget = SELECTED_CHARS if is_selected else ROW_CHARS
            display = _fit(text, budget) if text else ""
            if not text:
                # Off the end of the list -- blend card, label and dot
                # into the page background rather than leaving a blank
                # card sitting in the layout looking like a stray box.
                self._row_rects[i].setColor(PAGE_BG, PAGE_BG)
                self._track_dots[i].setColor(PAGE_BG, PAGE_BG)
                label_c, label_bg = PAGE_BG, PAGE_BG
            elif is_selected:
                self._row_rects[i].setColor(WRITE_FG, WRITE_BG)
                self._track_dots[i].setColor(WRITE_FG, WRITE_FG)
                label_c, label_bg = WRITE_FG, WRITE_BG
            else:
                self._row_rects[i].setColor(BORDER, CARD_BG)
                self._track_dots[i].setColor(WRITE_FG, WRITE_FG)
                label_c, label_bg = INK_3, CARD_BG
            self._row_labels[i].setColor(label_c, label_bg)
            self._set_text(self._row_labels[i], display)

    def paint_serve(self, ssid, pickups=0):
        self._set_text(self._srv_ssid, ssid)
        self._set_text(self._srv_pickups, "pickups: %d total" % pickups)
        self._show("serve")


def demo():
    """Cycle screens — run from REPL: import bbox_ui; bbox_ui.demo()"""
    import time
    M5.begin()
    ui = BboxUI()
    ui.begin()
    screens = [
        lambda: ui.paint_idle(True),
        lambda: ui.paint_receiving("Melody"),
        lambda: ui.paint_tag_list(["Melody", "Utility Tags", "DONE"], 0),
        lambda: ui.paint_tag_list(
            ["Game %d" % i for i in range(1, 9)] + ["Utility Tags", "DONE"], 4),
        lambda: ui.paint_tag_group(
            "Melody", ["getcode:my_melody", "my_melody", "note_c", "< back"],
            2, {"note_c": 3}),
        lambda: ui.paint_no_pickup_hint(),
        lambda: ui.paint_armed("getcode", 1, 1),
        lambda: ui.paint_overwrite("melody", "getcode"),
        lambda: ui.paint_writing("getcode"),
        lambda: ui.paint_already("getcode"),
        lambda: ui.paint_written("getcode", 3),
        lambda: ui.paint_write_failed("getcode"),
        lambda: ui.paint_done("getcode", 1, 1),
        lambda: ui.paint_complete(),
        lambda: ui.paint_mode_change("SERVE"),
        lambda: ui.paint_serve("SP-FILEPUSH", 2),
        lambda: ui.paint_error("no game to serve"),
    ]
    for fn in screens:
        fn()
        time.sleep_ms(2000)
