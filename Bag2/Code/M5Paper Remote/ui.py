"""E-ink touch UI for the M5Paper wand remote."""

import time

import M5
from M5 import *

from config import (
    BATTERY_BTN_H,
    BLACK,
    BORDER_W,
    COMMANDS,
    CONTROLS,
    DEBOUNCE_MS,
    FONT_BATTERY,
    FONT_FOOTER,
    FONT_GAME,
    FONT_STATUS,
    FONT_STOP,
    FONT_TITLE,
    FOOTER_H,
    GAP,
    GHOST_REFRESH_EVERY,
    MARGIN,
    PRESS_FLASH_MS,
    SCREEN_H,
    SCREEN_W,
    STATUS_H,
    STOP_BTN_H,
    TITLE_H,
    WHITE,
)

# DejaVu font sizes present on this firmware. Map a point size to its
# M5.Lcd.FONTS attribute name. ONLY these objects are passed to setFont() --
# never None, which hard-faults the chip.
_DEJAVU_NAMES = {
    9: "DejaVu9",
    12: "DejaVu12",
    18: "DejaVu18",
    24: "DejaVu24",
    40: "DejaVu40",
    56: "DejaVu56",
    72: "DejaVu72",
}


def _set_font(size):
    """Select the DejaVu font for `size` points. Safe: only sets a real font."""
    name = _DEJAVU_NAMES.get(size)
    if name is not None:
        font = getattr(M5.Lcd.FONTS, name, None)
        if font is not None:
            M5.Lcd.setFont(font)
            return
    try:
        M5.Lcd.setTextSize(1)
    except Exception:
        pass


class _Button(object):
    __slots__ = ("button_id", "label", "kind", "x", "y", "w", "h", "inverted")

    def __init__(self, button_id, label, kind, x, y, w, h, inverted=False):
        self.button_id = button_id
        self.label = label
        self.kind = kind
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.inverted = inverted

    def contains(self, px, py):
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h


class RemoteUI(object):
    def __init__(self, mac_str, espnow_ready=True):
        self.mac_str = mac_str
        self.espnow_ready = espnow_ready
        self.buttons = []
        self._status_y = TITLE_H
        self._footer_y = 0
        self._battery_y = 0
        self._stop_y = 0
        self._game_btn_h = 0
        self._tap_count = 0
        self._last_tap_ms = 0
        self._ghost_due = False
        self._last_sent = "Ready"
        self._active_game_id = None
        self._build_layout()

    def _build_layout(self):
        self.buttons = []
        rows = (len(COMMANDS) + 1) // 2

        self._stop_y = SCREEN_H - STOP_BTN_H
        self._footer_y = self._stop_y - GAP - FOOTER_H
        self._battery_y = self._footer_y - GAP - BATTERY_BTN_H
        game_top = TITLE_H + STATUS_H + GAP
        game_bottom = self._battery_y - GAP
        game_area = game_bottom - game_top
        self._game_btn_h = (game_area - (rows - 1) * GAP) // rows
        if self._game_btn_h < 44:
            self._game_btn_h = 44

        col_w = (SCREEN_W - (2 * MARGIN) - GAP) // 2
        for i, cmd in enumerate(COMMANDS):
            row = i // 2
            col = i % 2
            x = MARGIN + col * (col_w + GAP)
            by = game_top + row * (self._game_btn_h + GAP)
            self.buttons.append(
                _Button(
                    cmd["id"], cmd["label"], "game", x, by, col_w, self._game_btn_h
                )
            )

        for ctrl in CONTROLS:
            if ctrl["id"] == "battery":
                self.buttons.append(
                    _Button(
                        ctrl["id"],
                        ctrl["label"],
                        "control",
                        MARGIN,
                        self._battery_y,
                        SCREEN_W - (2 * MARGIN),
                        BATTERY_BTN_H,
                    )
                )
            elif ctrl["id"] == "stop":
                self.buttons.append(
                    _Button(
                        ctrl["id"],
                        ctrl["label"],
                        "control",
                        MARGIN,
                        self._stop_y,
                        SCREEN_W - (2 * MARGIN),
                        STOP_BTN_H,
                        inverted=True,
                    )
                )

    def _epd_mode(self, quality=False):
        try:
            if quality:
                M5.Lcd.setEpdMode(M5.Lcd.EPDMode.EPD_QUALITY)
            else:
                M5.Lcd.setEpdMode(M5.Lcd.EPDMode.EPD_FAST)
        except Exception:
            try:
                M5.Lcd.setEpdMode(0 if quality else 2)
            except Exception:
                pass

    def _set_text_datum_center(self):
        try:
            M5.Lcd.setTextDatum(M5.Lcd.Datum.middle_center)
            return True
        except Exception:
            pass
        try:
            M5.Lcd.setTextDatum(4)
            return True
        except Exception:
            pass
        return False

    def _draw_text_centered(self, text, cx, cy, fg, bg, font_size):
        _set_font(font_size)
        try:
            M5.Lcd.setTextColor(fg, bg)
        except Exception:
            pass
        if self._set_text_datum_center():
            try:
                M5.Lcd.drawString(text, cx, cy)
                return
            except Exception:
                pass
        char_w = 6 * max(1, font_size // 9)
        tw = len(text) * char_w
        x = cx - (tw // 2)
        y = cy - (font_size // 2)
        try:
            M5.Lcd.setCursor(x, y)
            M5.Lcd.print(text)
        except Exception:
            pass

    def _draw_text_left(self, text, x, y, fg, bg, font_size):
        _set_font(font_size)
        try:
            M5.Lcd.setTextColor(fg, bg)
            M5.Lcd.setCursor(x, y)
            M5.Lcd.print(text)
        except Exception:
            pass

    def _draw_border(self, x, y, w, h, color):
        for i in range(BORDER_W):
            M5.Lcd.drawRect(x + i, y + i, w - (2 * i), h - (2 * i), color)

    def _button_style(self, btn, highlight=False):
        active = (
            btn.kind == "game"
            and btn.button_id == self._active_game_id
            and not highlight
        )
        if btn.inverted or highlight or active:
            return BLACK, BLACK, WHITE
        return WHITE, BLACK, BLACK

    def _font_for_button(self, btn):
        if btn.button_id == "stop":
            return FONT_STOP
        if btn.button_id == "battery":
            return FONT_BATTERY
        return FONT_GAME

    def _draw_button(self, btn, highlight=False):
        fill, border, text = self._button_style(btn, highlight=highlight)
        M5.Lcd.fillRect(btn.x, btn.y, btn.w, btn.h, fill)
        self._draw_border(btn.x, btn.y, btn.w, btn.h, border)
        self._draw_text_centered(
            btn.label,
            btn.x + btn.w // 2,
            btn.y + btn.h // 2,
            text,
            fill,
            self._font_for_button(btn),
        )

    def _draw_title(self):
        mac_tail = self.mac_str.replace(":", "")[-4:]
        title = "Wand Remote  %s" % mac_tail
        M5.Lcd.fillRect(0, 0, SCREEN_W, TITLE_H, WHITE)
        self._draw_text_centered(
            title, SCREEN_W // 2, TITLE_H // 2, BLACK, WHITE, FONT_TITLE
        )

    def _draw_status(self):
        M5.Lcd.fillRect(0, self._status_y, SCREEN_W, STATUS_H, WHITE)
        if self.espnow_ready:
            status = "NOW Ready  %s" % self.mac_str
        else:
            status = "NOW Init..."
        self._draw_text_left(
            status, MARGIN, self._status_y + 10, BLACK, WHITE, FONT_STATUS
        )

    def _draw_footer(self):
        M5.Lcd.fillRect(0, self._footer_y, SCREEN_W, FOOTER_H, WHITE)
        self._draw_border(0, self._footer_y, SCREEN_W, FOOTER_H, BLACK)
        self._draw_text_centered(
            self._last_sent,
            SCREEN_W // 2,
            self._footer_y + FOOTER_H // 2,
            BLACK,
            WHITE,
            FONT_FOOTER,
        )

    def _find_button(self, button_id):
        for btn in self.buttons:
            if btn.button_id == button_id:
                return btn
        return None

    def paint_full(self):
        self._epd_mode(quality=True)
        M5.Lcd.clear(WHITE)
        self._draw_title()
        self._draw_status()
        for btn in self.buttons:
            self._draw_button(btn)
        self._draw_footer()

    def maybe_ghost_refresh(self):
        if self._ghost_due:
            self._ghost_due = False
            self.paint_full()

    def hit_test(self, x, y):
        for btn in self.buttons:
            if btn.contains(x, y):
                return btn
        return None

    def try_debounce(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_tap_ms) < DEBOUNCE_MS:
            return False
        self._last_tap_ms = now
        return True

    def show_feedback(self, btn, label):
        prev_active = self._active_game_id

        if btn.button_id == "stop":
            self._last_sent = "Stopped"
            self._active_game_id = None
        elif btn.button_id == "battery":
            self._last_sent = "Battery poll"
        else:
            self._last_sent = label
            if btn.kind == "game":
                self._active_game_id = btn.button_id

        self._epd_mode(quality=False)
        self._draw_button(btn, highlight=True)
        time.sleep_ms(PRESS_FLASH_MS)

        self._epd_mode(quality=True)
        if prev_active and prev_active != self._active_game_id:
            old_btn = self._find_button(prev_active)
            if old_btn:
                self._draw_button(old_btn)
        self._draw_button(btn)
        self._draw_footer()

        self._tap_count += 1
        if self._tap_count % GHOST_REFRESH_EVERY == 0:
            self._ghost_due = True

    def poll_touch(self):
        M5.update()
        pt = self._read_touch_m5()
        if pt is not None:
            return pt
        return self._read_touch_tp()

    def _read_touch_m5(self):
        try:
            if M5.Touch.getCount() <= 0:
                return None
            try:
                detail = M5.Touch.getDetail(0)
                if detail and not detail[6]:
                    return None
            except Exception:
                pass
            return M5.Touch.getX(), M5.Touch.getY()
        except Exception:
            return None

    def _read_touch_tp(self):
        try:
            if not hasattr(M5, "TP"):
                return None
            if hasattr(M5.TP, "touched"):
                if not M5.TP.touched():
                    return None
                pt = M5.TP.getPoint(0)
                return pt.x, pt.y
        except Exception:
            return None
        return None
