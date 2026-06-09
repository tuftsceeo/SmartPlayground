"""E-ink touch UI for the M5Paper wand remote."""

import time

import M5
from M5 import *

from config import (
    BLACK,
    COMMANDS,
    CONTROLS,
    DEBOUNCE_MS,
    GAME_BTN_H,
    GAP,
    GHOST_REFRESH_EVERY,
    MARGIN,
    SCREEN_H,
    SCREEN_W,
    STATUS_H,
    STOP_BTN_H,
    TITLE_H,
    WHITE,
    CONTROL_BTN_H,
)


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
        self._feedback_y = self._status_y + STATUS_H
        self._tap_count = 0
        self._last_tap_ms = 0
        self._ghost_due = False
        self._build_layout()

    def _build_layout(self):
        col_w = (SCREEN_W - (2 * MARGIN) - GAP) // 2
        y = TITLE_H + STATUS_H + GAP

        for i, cmd in enumerate(COMMANDS):
            row = i // 2
            col = i % 2
            x = MARGIN + col * (col_w + GAP)
            by = y + row * (GAME_BTN_H + GAP)
            self.buttons.append(
                _Button(cmd["id"], cmd["label"], "game", x, by, col_w, GAME_BTN_H)
            )

        games_bottom = y + 3 * (GAME_BTN_H + GAP) - GAP
        battery_y = games_bottom + GAP
        stop_y = battery_y + CONTROL_BTN_H + GAP

        for ctrl in CONTROLS:
            if ctrl["id"] == "battery":
                self.buttons.append(
                    _Button(
                        ctrl["id"],
                        ctrl["label"],
                        "control",
                        MARGIN,
                        battery_y,
                        SCREEN_W - (2 * MARGIN),
                        CONTROL_BTN_H,
                    )
                )
            elif ctrl["id"] == "stop":
                self.buttons.append(
                    _Button(
                        ctrl["id"],
                        ctrl["label"],
                        "control",
                        MARGIN,
                        stop_y,
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

    def _draw_text_centered(self, text, cx, cy, fg, bg, size=2):
        try:
            M5.Lcd.setTextSize(size)
        except Exception:
            pass
        try:
            M5.Lcd.setTextColor(fg, bg)
        except Exception:
            pass
        char_w = 8 * size
        tw = len(text) * char_w
        x = cx - (tw // 2)
        y = cy - (8 * size // 2)
        try:
            M5.Lcd.setCursor(x, y)
            M5.Lcd.print(text)
        except Exception:
            pass

    def _draw_button(self, btn, highlight=False):
        if btn.inverted and not highlight:
            fill, border, text = BLACK, BLACK, WHITE
        elif highlight:
            fill, border, text = BLACK, BLACK, WHITE
        else:
            fill, border, text = WHITE, BLACK, BLACK

        M5.Lcd.fillRect(btn.x, btn.y, btn.w, btn.h, fill)
        M5.Lcd.drawRect(btn.x, btn.y, btn.w, btn.h, border)
        self._draw_text_centered(
            btn.label,
            btn.x + btn.w // 2,
            btn.y + btn.h // 2,
            text,
            fill,
            size=2,
        )

    def _draw_title(self):
        mac_tail = self.mac_str.replace(":", "")[-4:]
        title = "Wand Remote  %s" % mac_tail
        M5.Lcd.fillRect(0, 0, SCREEN_W, TITLE_H, WHITE)
        self._draw_text_centered(title, SCREEN_W // 2, TITLE_H // 2, BLACK, WHITE, size=2)

    def _draw_status(self, extra=""):
        M5.Lcd.fillRect(0, self._status_y, SCREEN_W, STATUS_H, WHITE)
        if self.espnow_ready:
            status = "NOW Ready  %s" % self.mac_str
        else:
            status = "NOW Init..."
        if extra:
            status = extra
        try:
            M5.Lcd.setTextSize(1)
            M5.Lcd.setTextColor(BLACK, WHITE)
            M5.Lcd.setCursor(MARGIN, self._status_y + 8)
            M5.Lcd.print(status)
        except Exception:
            pass

    def paint_full(self):
        self._epd_mode(quality=True)
        M5.Lcd.clear(WHITE)
        self._draw_title()
        self._draw_status()
        for btn in self.buttons:
            self._draw_button(btn)
        self._tap_count = 0

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
        self._epd_mode(quality=False)
        self._draw_button(btn, highlight=True)
        self._draw_status("Sent: %s" % label)
        time.sleep_ms(200)
        self._draw_button(btn)
        self._draw_status()
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
