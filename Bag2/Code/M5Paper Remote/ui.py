"""E-ink touch UI for the M5Paper wand remote."""

import time

import M5
from M5 import *

from config import (
    ALL_GAMES,
    BATT_FILL_INSET,
    BATT_H,
    BATT_NUB_W,
    BATT_POLL_MS,
    BATT_W,
    BATTERY_BTN_H,
    BATTERY_PNG,
    BLACK,
    BOLT_H,
    BOLT_PNG,
    BOLT_W,
    BORDER_W,
    CONTROLS,
    DEBOUNCE_MS,
    FONT_BATTERY,
    FONT_FOOTER,
    FONT_GAME,
    FONT_SETTINGS,
    FONT_SETTINGS_SMALL,
    FONT_STOP,
    FOOTER_H,
    GAP,
    GEAR_H,
    GEAR_HIT,
    GEAR_PNG,
    GEAR_W,
    LCD_SHOW_AFTER_END_WRITE,
    MARGIN,
    PRESS_FLASH_MS,
    SCREEN_H,
    SCREEN_W,
    SETTINGS_MAC_H,
    SETTINGS_SAVE_H,
    STOP_BTN_H,
    TOP_BAR_H,
    WHITE,
    build_commands,
    save_enabled_ids,
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
    def __init__(self, mac_str, commands, espnow_ready=True):
        self.mac_str = mac_str
        self.commands = list(commands)
        self.espnow_ready = espnow_ready
        self.mode = "main"
        self.buttons = []
        self._footer_y = 0
        self._battery_y = 0
        self._stop_y = 0
        self._game_btn_h = 0
        self._gear_x = SCREEN_W - MARGIN - GEAR_HIT
        self._gear_y = 0
        self._gear_w = GEAR_HIT
        self._gear_h = TOP_BAR_H
        self._gear_draw_x = 0
        self._gear_draw_y = 0
        self._batt_x = 0
        self._batt_y = 0
        self._batt_shown_bucket = None
        self._batt_shown_charging = None
        self._batt_last_ms = 0
        self._settings_rows = []
        self._settings_row_h = 0
        self._save_y = 0
        self._settings_enabled = set()
        self._last_tap_ms = 0
        self._last_sent = "Ready"
        self._active_game_id = None
        self._build_layout()

    def _build_layout(self):
        self.buttons = []
        rows = (len(self.commands) + 1) // 2
        if rows < 1:
            rows = 1

        self._stop_y = SCREEN_H - STOP_BTN_H
        self._footer_y = self._stop_y - GAP - FOOTER_H
        self._battery_y = self._footer_y - GAP - BATTERY_BTN_H
        self._batt_x = MARGIN
        self._batt_y = (TOP_BAR_H - BATT_H) // 2
        self._gear_draw_x = self._gear_x + (GEAR_HIT - GEAR_W) // 2
        self._gear_draw_y = (TOP_BAR_H - GEAR_H) // 2
        game_top = TOP_BAR_H
        game_bottom = self._battery_y - GAP
        game_area = game_bottom - game_top
        self._game_btn_h = (game_area - (rows - 1) * GAP) // rows
        if self._game_btn_h < 44:
            self._game_btn_h = 44

        col_w = (SCREEN_W - (2 * MARGIN) - GAP) // 2
        for i, cmd in enumerate(self.commands):
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

    def _build_settings_layout(self):
        self._settings_rows = []
        rows = (len(ALL_GAMES) + 1) // 2
        self._save_y = SCREEN_H - SETTINGS_MAC_H - GAP - SETTINGS_SAVE_H
        rows_top = TOP_BAR_H + GAP
        rows_bottom = self._save_y - GAP
        rows_area = rows_bottom - rows_top
        self._settings_row_h = (rows_area - (rows - 1) * GAP) // rows
        if self._settings_row_h < 48:
            self._settings_row_h = 48

        col_w = (SCREEN_W - (2 * MARGIN) - GAP) // 2
        for i, game in enumerate(ALL_GAMES):
            row = i // 2
            col = i % 2
            x = MARGIN + col * (col_w + GAP)
            y = rows_top + row * (self._settings_row_h + GAP)
            self._settings_rows.append(
                {
                    "id": game["id"],
                    "label": game["label"],
                    "x": x,
                    "y": y,
                    "w": col_w,
                    "h": self._settings_row_h,
                }
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

    def _begin_write(self):
        try:
            M5.Lcd.startWrite()
        except Exception:
            pass

    def _end_write(self):
        try:
            M5.Lcd.endWrite()
            if LCD_SHOW_AFTER_END_WRITE:
                M5.Lcd.show()
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

    def _draw_png(self, path, x, y, fallback=None):
        try:
            M5.Lcd.drawPng(path, x, y)
            return True
        except Exception:
            pass
        try:
            from Widgets import Image

            Image(path, x, y)
            return True
        except Exception:
            pass
        try:
            M5.Lcd.drawBmp(path, x, y)
            return True
        except Exception:
            pass
        if fallback is not None:
            fallback()
        return False

    def _draw_gear_primitive(self):
        cx = self._gear_x + self._gear_w // 2
        cy = self._gear_y + self._gear_h // 2
        r = 14
        M5.Lcd.fillCircle(cx, cy, r, WHITE)
        M5.Lcd.drawCircle(cx, cy, r, BLACK)
        M5.Lcd.fillCircle(cx, cy, 5, BLACK)
        for dx, dy in (
            (0, -18),
            (13, -13),
            (18, 0),
            (13, 13),
            (0, 18),
            (-13, 13),
            (-18, 0),
            (-13, -13),
        ):
            M5.Lcd.fillRect(cx + dx - 2, cy + dy - 2, 4, 4, BLACK)

    def _draw_gear(self):
        self._draw_png(
            GEAR_PNG,
            self._gear_draw_x,
            self._gear_draw_y,
            fallback=self._draw_gear_primitive,
        )

    def _read_battery(self):
        level = None
        charging = False
        try:
            raw = M5.Power.getBatteryLevel()
            if raw is not None:
                level = max(0, min(100, int(raw)))
        except Exception:
            pass
        try:
            charging = bool(M5.Power.isCharging())
        except Exception:
            pass
        return level, charging

    def _battery_bucket(self, level):
        if level is None:
            return None
        return (int(level) // 10) * 10

    def _draw_battery_primitive(self):
        x = self._batt_x
        y = self._batt_y
        body_w = BATT_W - BATT_NUB_W
        for i in range(BATT_FILL_INSET):
            M5.Lcd.drawRect(
                x + i, y + i, body_w - (2 * i), BATT_H - (2 * i), BLACK
            )
        nub_h = BATT_H // 2
        nub_y0 = y + (BATT_H - nub_h) // 2
        M5.Lcd.fillRect(x + body_w, nub_y0, BATT_NUB_W, nub_h, BLACK)

    def _bolt_draw_xy(self):
        body_w = BATT_W - BATT_NUB_W
        bolt_x = self._batt_x + (body_w - BOLT_W) // 2
        bolt_y = self._batt_y + (BATT_H - BOLT_H) // 2
        return bolt_x, bolt_y

    def _draw_bolt_primitive(self):
        bx, by = self._bolt_draw_xy()
        M5.Lcd.fillTriangle(
            bx + int(BOLT_W * 0.58),
            by,
            bx + int(BOLT_W * 0.05),
            by + int(BOLT_H * 0.58),
            bx + int(BOLT_W * 0.42),
            by + int(BOLT_H * 0.58),
            BLACK,
        )
        M5.Lcd.fillTriangle(
            bx + int(BOLT_W * 0.42),
            by + int(BOLT_H * 0.58),
            bx + int(BOLT_W * 0.30),
            by + BOLT_H - 1,
            bx + int(BOLT_W * 0.95),
            by + int(BOLT_H * 0.38),
            BLACK,
        )
        M5.Lcd.fillTriangle(
            bx + int(BOLT_W * 0.55),
            by + int(BOLT_H * 0.38),
            bx + int(BOLT_W * 0.95),
            by + int(BOLT_H * 0.38),
            bx + int(BOLT_W * 0.42),
            by + int(BOLT_H * 0.58),
            BLACK,
        )

    def _draw_battery(self, level, charging, clear_region=True):
        if clear_region:
            M5.Lcd.fillRect(self._batt_x, self._batt_y, BATT_W, BATT_H, WHITE)
        self._draw_png(
            BATTERY_PNG,
            self._batt_x,
            self._batt_y,
            fallback=self._draw_battery_primitive,
        )
        inner_x = self._batt_x + BATT_FILL_INSET
        inner_y = self._batt_y + BATT_FILL_INSET
        inner_w = BATT_W - BATT_NUB_W - (2 * BATT_FILL_INSET)
        inner_h = BATT_H - (2 * BATT_FILL_INSET)
        if level is not None and inner_w > 0 and inner_h > 0:
            fill_w = (inner_w * max(0, min(100, int(level)))) // 100
            if fill_w > 0:
                M5.Lcd.fillRect(inner_x, inner_y, fill_w, inner_h, BLACK)
        if charging:
            bolt_x, bolt_y = self._bolt_draw_xy()
            self._draw_png(
                BOLT_PNG,
                bolt_x,
                bolt_y,
                fallback=self._draw_bolt_primitive,
            )

    def update_battery(self):
        if self.mode != "main":
            return
        now = time.ticks_ms()
        if (
            self._batt_last_ms
            and time.ticks_diff(now, self._batt_last_ms) < BATT_POLL_MS
        ):
            return
        self._batt_last_ms = now
        level, charging = self._read_battery()
        bucket = self._battery_bucket(level)
        if (
            bucket == self._batt_shown_bucket
            and charging == self._batt_shown_charging
        ):
            return
        self._batt_shown_bucket = bucket
        self._batt_shown_charging = charging
        self._epd_mode(quality=False)
        self._begin_write()
        try:
            self._draw_battery(level, charging, clear_region=True)
        finally:
            self._end_write()

    def _gear_hit(self, x, y):
        return (
            self._gear_x <= x < self._gear_x + self._gear_w
            and self._gear_y <= y < self._gear_y + self._gear_h
        )

    def _footer_banner_text(self):
        if self._active_game_id:
            return "Now Playing: %s" % self._last_sent
        if self._last_sent == "Stopped":
            return "Stopped"
        if self._last_sent == "Checking batteries":
            return "Checking batteries"
        return "Ready"

    def _draw_footer(self):
        M5.Lcd.fillRect(0, self._footer_y, SCREEN_W, FOOTER_H, WHITE)
        self._draw_text_centered(
            self._footer_banner_text(),
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

    def _draw_settings_row(self, row, enabled):
        if enabled:
            fill, border, text = BLACK, BLACK, WHITE
            mark = "[x]"
        else:
            fill, border, text = WHITE, BLACK, BLACK
            mark = "[ ]"
        M5.Lcd.fillRect(row["x"], row["y"], row["w"], row["h"], fill)
        self._draw_border(row["x"], row["y"], row["w"], row["h"], border)
        line = "%s %s" % (mark, row["label"])
        self._draw_text_left(
            line,
            row["x"] + 8,
            row["y"] + row["h"] // 2 - 8,
            text,
            fill,
            FONT_SETTINGS,
        )

    def _paint_settings_content(self):
        M5.Lcd.fillRect(0, 0, SCREEN_W, TOP_BAR_H, WHITE)
        self._draw_text_left(
            "Choose Games",
            MARGIN,
            TOP_BAR_H // 2 - 6,
            BLACK,
            WHITE,
            FONT_SETTINGS,
        )
        for row in self._settings_rows:
            self._draw_settings_row(row, row["id"] in self._settings_enabled)
        save_x = MARGIN
        save_w = SCREEN_W - (2 * MARGIN)
        M5.Lcd.fillRect(save_x, self._save_y, save_w, SETTINGS_SAVE_H, BLACK)
        self._draw_border(save_x, self._save_y, save_w, SETTINGS_SAVE_H, BLACK)
        self._draw_text_centered(
            "Save & Back",
            save_x + save_w // 2,
            self._save_y + SETTINGS_SAVE_H // 2,
            WHITE,
            BLACK,
            FONT_SETTINGS,
        )
        mac_y = SCREEN_H - SETTINGS_MAC_H
        M5.Lcd.fillRect(0, mac_y, SCREEN_W, SETTINGS_MAC_H, WHITE)
        self._draw_text_centered(
            "Device: %s" % self.mac_str,
            SCREEN_W // 2,
            mac_y + SETTINGS_MAC_H // 2,
            BLACK,
            WHITE,
            FONT_SETTINGS_SMALL,
        )

    def paint_full(self):
        self._epd_mode(quality=True)
        if self.mode == "settings":
            self.paint_settings()
            return
        self._begin_write()
        try:
            M5.Lcd.clear(WHITE)
            self._draw_gear()
            level, charging = self._read_battery()
            self._draw_battery(level, charging)
            self._batt_shown_bucket = self._battery_bucket(level)
            self._batt_shown_charging = charging
            self._batt_last_ms = time.ticks_ms()
            for btn in self.buttons:
                self._draw_button(btn)
            self._draw_footer()
        finally:
            self._end_write()

    def paint_settings(self):
        self._epd_mode(quality=True)
        self._build_settings_layout()
        self._begin_write()
        try:
            M5.Lcd.clear(WHITE)
            self._paint_settings_content()
        finally:
            self._end_write()

    def _redraw_settings_row(self, game_id):
        for row in self._settings_rows:
            if row["id"] == game_id:
                self._epd_mode(quality=False)
                self._begin_write()
                try:
                    self._draw_settings_row(row, game_id in self._settings_enabled)
                finally:
                    self._end_write()
                return

    def open_settings(self):
        self.mode = "settings"
        self._settings_enabled = set(cmd["id"] for cmd in self.commands)
        self.paint_settings()

    def _settings_hit(self, x, y):
        for row in self._settings_rows:
            if (
                row["x"] <= x < row["x"] + row["w"]
                and row["y"] <= y < row["y"] + row["h"]
            ):
                return row["id"]
        save_x = MARGIN
        save_w = SCREEN_W - (2 * MARGIN)
        if (
            save_x <= x < save_x + save_w
            and self._save_y <= y < self._save_y + SETTINGS_SAVE_H
        ):
            return "__save__"
        return None

    def _toggle_settings_row(self, game_id):
        if game_id in self._settings_enabled:
            if len(self._settings_enabled) <= 1:
                return
            self._settings_enabled.discard(game_id)
        else:
            self._settings_enabled.add(game_id)

    def _save_settings(self):
        if len(self._settings_enabled) < 1:
            return False
        save_enabled_ids(list(self._settings_enabled))
        self.commands = build_commands(self._settings_enabled)
        self._build_layout()
        self.mode = "main"
        self.paint_full()
        return True

    def on_touch(self, x, y):
        if self.mode == "settings":
            if not self.try_debounce():
                return None
            hit = self._settings_hit(x, y)
            if hit == "__save__":
                self._save_settings()
                return None
            if hit is not None:
                self._toggle_settings_row(hit)
                self._redraw_settings_row(hit)
            return None

        if self._gear_hit(x, y):
            return "open_settings"

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
            self._last_sent = "Checking batteries"
        else:
            self._last_sent = label
            if btn.kind == "game":
                self._active_game_id = btn.button_id

        self._epd_mode(quality=False)
        self._begin_write()
        try:
            self._draw_button(btn, highlight=True)
        finally:
            self._end_write()
        time.sleep_ms(PRESS_FLASH_MS)

        self._epd_mode(quality=True)
        self._begin_write()
        try:
            if prev_active and prev_active != self._active_game_id:
                old_btn = self._find_button(prev_active)
                if old_btn:
                    self._draw_button(old_btn)
            self._draw_button(btn)
            self._draw_footer()
        finally:
            self._end_write()

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
