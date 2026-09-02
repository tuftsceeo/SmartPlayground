"""
bbox_ui.py — M5.Lcd screens + M5.Speaker feedback for Broadcast Box
(landscape 240x135).

Modeled on Bag2/Code/StickS3 Narrator/narrator_ui.py: try/except on every
M5 call, DejaVu fonts, _LAYOUT_TABLE for centering. Speaker volume follows
the same StickS3 board caution as narrator/main.py's SPEAKER_VOLUME.
"""

import time

import M5

WHITE = 0xFFFFFF
BLACK = 0x000000
BG = 0x111111
ACCENT = 0x3FE0C2
WARN = 0xFF7A4A
MUTED = 0x888888
AMBER = 0xFFA000

ROTATION = 1
SCREEN_W = 240
SCREEN_H = 135

# 0-255. StickS3's own docs warn to stay under ~75% (~191) on battery power
# to avoid a brown-out reboot when USB is unplugged -- same caution as
# Bag2/Code/StickS3 Narrator/main.py's SPEAKER_VOLUME.
SPEAKER_VOLUME = 190

# Per-font-selection tracing. Off by default: this fires ~4 times per
# screen repaint, which drowns everything else on the serial log. Font
# *failures* below are not gated -- those always print.
VERBOSE = False

_DEJAVU_NAMES = {
    9: "DejaVu9", 12: "DejaVu12", 18: "DejaVu18", 24: "DejaVu24",
    40: "DejaVu40",
}


# Last resort if M5.Lcd.fontHeight() itself throws -- normal DejaVu9 line
# height is ~15px (9px glyph + leading); this is only for total failure.
_FALLBACK_LINE_HEIGHT = 30


def _measured_height(context):
    """Real pixel height of the CURRENT font, per M5.Lcd.fontHeight() --
    used instead of trusting the "9"/"12"/etc in a font's name. Called
    both after a successful setFont() and on every error path in
    _set_font() below, so line spacing always reflects whatever font is
    actually active."""
    try:
        h = M5.Lcd.fontHeight()
        if VERBOSE:
            print("# %s, fontHeight()=%s" % (context, str(h)))
        return int(h) if h else _FALLBACK_LINE_HEIGHT
    except Exception as e:
        print("# %s, fontHeight() unavailable: %s" % (context, str(e)))
        return _FALLBACK_LINE_HEIGHT


def _set_font(size):
    """Select a DejaVu font and return its measured pixel height for
    caller-side line spacing.

    setTextSize() is set to 1 once, in BboxUI.begin(), and never touched
    again anywhere in this file -- it's a scale multiplier on top of
    whatever font is active, independent of setFont(). If a font
    name/lookup fails, log it and leave whatever font was already active
    in place rather than falling back to setTextSize().
    """
    name = _DEJAVU_NAMES.get(size)
    if name is None:
        print("# font err: no DejaVu mapping for size %s -- leaving current font as-is" % str(size))
        return _measured_height("no mapping for %s" % str(size))

    font = getattr(M5.Lcd.FONTS, name, None)
    if font is None:
        print("# font err: M5.Lcd.FONTS has no '%s' -- leaving current font as-is" % name)
        return _measured_height("FONTS has no %s" % name)

    try:
        M5.Lcd.setFont(font)
    except Exception as e:
        print("# setFont(%s) err: %s -- leaving current font as-is" % (name, str(e)))
        return _measured_height("setFont(%s) failed" % name)

    return _measured_height("font %s set OK" % name)


def _draw_centered(text, bg, fg, font_size=18):
    try:
        M5.Lcd.startWrite()
    except Exception as e:
        print("# startWrite err: %s" % str(e))
    try:
        try:
            M5.Lcd.fillScreen(bg)
        except Exception as e:
            print("# fillScreen err: %s" % str(e))
        text_h = _set_font(font_size)
        try:
            M5.Lcd.setTextColor(fg, bg)
        except Exception as e:
            print("# setTextColor err: %s" % str(e))
        y = SCREEN_H // 2 - text_h // 2
        try:
            M5.Lcd.setCursor(8, y)
            M5.Lcd.print(text)
        except Exception as e:
            print("# draw_centered print('%s') err: %s" % (text, str(e)))
    finally:
        try:
            M5.Lcd.endWrite()
        except Exception as e:
            print("# endWrite err: %s" % str(e))


LINE_PADDING = 4  # extra gap below each line, on top of its measured height


def _draw_lines(lines, bg=BG, fg=WHITE):
    """lines: list of (text, font_size, color_or_none)"""
    try:
        M5.Lcd.startWrite()
    except Exception as e:
        print("# startWrite err: %s" % str(e))
    try:
        try:
            M5.Lcd.fillScreen(bg)
        except Exception as e:
            print("# fillScreen err: %s" % str(e))
        y = 8
        for text, size, color in lines:
            text_h = _set_font(size)
            c = color if color is not None else fg
            try:
                M5.Lcd.setTextColor(c, bg)
            except Exception as e:
                print("# setTextColor err: %s" % str(e))
            try:
                M5.Lcd.setCursor(8, y)
                M5.Lcd.print(text)
            except Exception as e:
                print("# draw_lines print('%s') err: %s" % (text, str(e)))
            y += text_h + LINE_PADDING
    finally:
        try:
            M5.Lcd.endWrite()
        except Exception as e:
            print("# endWrite err: %s" % str(e))


class BboxUI(object):
    def __init__(self):
        # No M5 hardware calls here -- BboxServer.__init__ constructs this
        # object (self.ui = BboxUI()) before BboxServer.run() ever calls
        # M5.begin(). Lcd/Speaker calls made before begin() silently fail
        # (or worse, leave the driver in a state that corrupts font loading
        # once begin() does run) -- see begin() below, which is called
        # from run() right after M5.begin().
        pass

    def begin(self):
        """Call once, right after M5.begin() -- not before."""
        try:
            M5.Lcd.setRotation(ROTATION)
        except Exception as e:
            print("# setRotation err: %s" % str(e))
        # Set once, here, and never touched again anywhere in this file --
        # setTextSize() scales on top of setFont(), so leaving it at
        # anything but 1 would silently scale every DejaVu font drawn.
        try:
            M5.Lcd.setTextSize(1)
        except Exception as e:
            print("# setTextSize(1) err: %s" % str(e))
        try:
            M5.Speaker.setVolume(SPEAKER_VOLUME)
        except Exception as e:
            print("# speaker volume err: %s" % str(e))

    def _tone(self, freq, ms):
        try:
            M5.Speaker.tone(freq, ms)
        except Exception as e:
            print("# speaker tone err: %s" % str(e))

    # Mirrors Bag2/Utilities/writetoNFCcards.py's Beeper -- same feel as
    # the wand's own NFC feedback, just via M5.Speaker instead of a piezo.
    def beep_scan(self):
        """Short click the instant a tag is detected on the reader."""
        self._tone(1000, 30)

    def beep_click(self):
        """Immediate feedback that a button press was registered -- fires
        before anything else happens, so a press is never silent even if
        the gesture it started (e.g. a scan) finds nothing."""
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

    # Back to the original stylized per-screen sizing -- titles bigger than
    # captions -- now that _set_font()/_draw_lines() derive real spacing
    # from M5.Lcd.fontHeight() instead of guessing from these numbers.
    # Only valid DejaVu sizes here: 9, 12, 18, 24, 40 (see _DEJAVU_NAMES).
    def paint_booting(self):
        _draw_centered("Starting", AMBER, BLACK, 24)

    # Screen 10 — idle / linked
    def paint_idle(self, linked=True):
        status = "linked to laptop" if linked else "not linked"
        _draw_lines([
            ("Broadcast Box", 18, WHITE),
            (status, 12, ACCENT if linked else MUTED),
            ("no game loaded yet", 12, MUTED),
        ])

    # Screen 11 — receiving (TCP transfer)
    def paint_receiving(self, game_name=""):
        sub = game_name if game_name else "game"
        _draw_lines([
            ("Getting game...", 18, WHITE),
            (sub, 12, MUTED),
        ])

    # Screen 13 — armed for card
    def paint_armed(self, label, index=1, total=1):
        _draw_lines([
            ("Tag %d/%d" % (index, total), 12, MUTED),
            (label, 24, WHITE),
            ("hold card on reader", 12, ACCENT),
        ])

    # Screen 14 — overwrite check
    def paint_overwrite(self, existing, new_label):
        _draw_lines([
            ("Card already has:", 12, MUTED),
            ('"%s"' % existing, 18, WHITE),
            ('Overwrite with "%s"?' % new_label, 12, WARN),
            ("BtnA = overwrite   BtnB = cancel", 9, MUTED),
        ])

    # Screen 15b — actively scanning (field on, waiting for a card)
    def paint_scanning(self, label):
        _draw_lines([
            ('Scanning: %s' % label, 18, WHITE),
            ("hold card on top", 12, ACCENT),
            ("BtnB = back", 9, MUTED),
        ])

    # Screen 15c — card already carries the text we would write
    def paint_already(self, label):
        _draw_lines([
            ('Already "%s"' % label, 18, ACCENT),
            ("no change needed", 12, MUTED),
            ("press any button", 9, MUTED),
        ])

    # Screen 15d — write succeeded; stays up until a button dismisses it
    def paint_written(self, label, count):
        _draw_lines([
            ('"%s" written!' % label, 18, ACCENT),
            ("%d this session" % count, 12, MUTED),
            ("press any button", 9, MUTED),
        ])

    # Screen 15e — write failed
    def paint_write_failed(self, label):
        _draw_lines([
            ("Write failed", 18, WARN),
            (label, 12, MUTED),
            ("press any button", 9, MUTED),
        ])

    # Screen 15 — writing
    def paint_writing(self, label):
        _draw_lines([
            ('Writing "%s"...' % label, 18, WHITE),
            ("hold card steady", 12, MUTED),
        ])

    # Screen 16 — done
    def paint_done(self, label, written, total):
        _draw_lines([
            ("%s done!" % label, 18, ACCENT),
            ("%d of %d written" % (written, total), 12, MUTED),
        ])

    # Screen 17 — role set complete
    def paint_complete(self, msg="All tags ready!"):
        _draw_centered(msg, BG, ACCENT, 18)

    def paint_error(self, msg):
        # 14 isn't a real DejaVu size (see _DEJAVU_NAMES) -- 12 is the
        # closest available.
        _draw_centered(msg, BG, WARN, 12)

    # Screen 20 — WRITE mode tag list (Phase A)
    def paint_tag_list(self, entries, cursor, written):
        """entries: list of tag names plus a trailing "DONE" sentinel.
        cursor: index into entries of the currently selected row.
        written: dict name -> count already written this session.

        Carries its own "pickup off" header rather than leaving that to a
        separate screen: in WRITE mode the AP is always down (the whole
        point of the mode split), and a teacher looking at this list needs
        to see that wands cannot fetch code right now. A separate full-screen
        hint would have to blank the list to say so.

        240x135 fits a size-9 header plus ~4 size-12 rows -- longer lists
        show a window around cursor rather than overflowing.
        """
        max_rows = 4
        n = len(entries)
        if n <= max_rows:
            start = 0
        else:
            start = cursor - max_rows // 2
            if start < 0:
                start = 0
            if start > n - max_rows:
                start = n - max_rows
        lines = [("BtnA=scan BtnB=next  pickup off", 9, WARN)]
        for i in range(start, min(start + max_rows, n)):
            name = entries[i]
            marker = ">" if i == cursor else " "
            if name == "DONE":
                lines.append(("%s DONE" % marker, 12, ACCENT))
            else:
                count = written.get(name, 0) if written else 0
                lines.append(("%s %s (%d)" % (marker, name, count), 12,
                               WHITE if i == cursor else MUTED))
        _draw_lines(lines)

    # Screen 21 — SERVE mode (AP up)
    def paint_serve(self, ssid, pickups=0):
        _draw_lines([
            ("Serving", 18, ACCENT),
            (ssid, 12, WHITE),
            ("pickups: %d" % pickups, 12, MUTED),
            ("hold BtnA to write tags", 9, MUTED),
        ])

    # Screen 22 — transient mode-change screen
    def paint_mode_change(self, to_mode):
        _draw_centered("-> %s" % to_mode, AMBER, BLACK, 18)

    # Screen 23 — standalone "no pickup" notice, for IDLE with no game loaded
    # (paint_tag_list carries its own header in WRITE mode).
    def paint_no_pickup_hint(self):
        _draw_lines([
            ("pickup off", 12, WARN),
            ("DONE + B1 to serve", 9, MUTED),
        ])


def demo():
    """Cycle screens — run from REPL: import bbox_ui; bbox_ui.demo()"""
    import time
    import M5
    M5.begin()
    ui = BboxUI()
    ui.begin()
    screens = [
        lambda: ui.paint_idle(True),
        lambda: ui.paint_receiving("Melody"),
        lambda: ui.paint_tag_list(["getcode", "jumpin", "DONE"], 0, {"getcode": 1}),
        lambda: ui.paint_no_pickup_hint(),
        lambda: ui.paint_armed("getcode", 1, 1),
        lambda: ui.paint_overwrite("melody", "getcode"),
        lambda: ui.paint_writing("getcode"),
        lambda: ui.paint_done("getcode", 1, 1),
        lambda: ui.paint_complete(),
        lambda: ui.paint_mode_change("SERVE"),
        lambda: ui.paint_serve("SP-FILEPUSH", 2),
    ]
    for fn in screens:
        fn()
        time.sleep_ms(2000)
