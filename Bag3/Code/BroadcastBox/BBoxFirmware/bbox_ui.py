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

_DEJAVU_NAMES = {
    9: "DejaVu9", 12: "DejaVu12", 18: "DejaVu18", 24: "DejaVu24",
    40: "DejaVu40",
}


def _set_font(size):
    name = _DEJAVU_NAMES.get(size)
    font = getattr(M5.Lcd.FONTS, name, None) if name else None
    if font is not None:
        try:
            M5.Lcd.setFont(font)
            return
        except Exception:
            pass
    try:
        M5.Lcd.setTextSize(2)
    except Exception:
        pass


def _draw_centered(text, bg, fg, font_size=18):
    try:
        M5.Lcd.startWrite()
    except Exception:
        pass
    try:
        M5.Lcd.fillScreen(bg)
        _set_font(font_size)
        try:
            M5.Lcd.setTextColor(fg, bg)
        except Exception:
            pass
        y = SCREEN_H // 2 - font_size // 2
        try:
            M5.Lcd.setCursor(8, y)
            M5.Lcd.print(text)
        except Exception:
            pass
    finally:
        try:
            M5.Lcd.endWrite()
        except Exception:
            pass


def _draw_lines(lines, bg=BG, fg=WHITE):
    """lines: list of (text, font_size, color_or_none)"""
    try:
        M5.Lcd.startWrite()
    except Exception:
        pass
    try:
        M5.Lcd.fillScreen(bg)
        y = 8
        for text, size, color in lines:
            _set_font(size)
            c = color if color is not None else fg
            try:
                M5.Lcd.setTextColor(c, bg)
            except Exception:
                pass
            try:
                M5.Lcd.setCursor(8, y)
                M5.Lcd.print(text)
            except Exception:
                pass
            y += size + 6
    finally:
        try:
            M5.Lcd.endWrite()
        except Exception:
            pass


class BboxUI(object):
    def __init__(self):
        try:
            M5.Lcd.setRotation(ROTATION)
        except Exception as e:
            print("# setRotation err: %s" % str(e))
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
            ("short=cancel long=ok", 9, MUTED),
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
        _draw_centered(msg, BG, WARN, 14)


def demo():
    """Cycle screens — run from REPL: import bbox_ui; bbox_ui.demo()"""
    import time
    import M5
    M5.begin()
    ui = BboxUI()
    screens = [
        lambda: ui.paint_idle(True),
        lambda: ui.paint_receiving("Melody"),
        lambda: ui.paint_armed("getcode", 1, 1),
        lambda: ui.paint_overwrite("melody", "getcode"),
        lambda: ui.paint_writing("getcode"),
        lambda: ui.paint_done("getcode", 1, 1),
        lambda: ui.paint_complete(),
    ]
    for fn in screens:
        fn()
        time.sleep_ms(2000)
