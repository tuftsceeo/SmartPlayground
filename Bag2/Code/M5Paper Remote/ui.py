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
    BORDER_W,
    CONTROLS,
    DEBOUNCE_MS,
    FONT_BATTERY,
    FONT_FOOTER,
    FONT_GAME,
    FONT_SETTINGS,
    FONT_SETTINGS_SMALL,
    FONT_STATUS,
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
    SIGNAL_BAR_GAP,
    SIGNAL_BAR_MIN_H,
    SIGNAL_BAR_STEP,
    SIGNAL_BAR_W,
    SIGNAL_BARS,
    SIGNAL_H,
    SIGNAL_PNGS,
    SIGNAL_W,
    SIGNAL_WORDS,
    STATUS_NAV_W,
    STATUS_ROW_GAP,
    STATUS_ROW_H,
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
        self._batt_last_ms = 0
        self._settings_rows = []
        self._settings_row_h = 0
        self._save_y = 0
        self._settings_enabled = set()
        self._status_rows = []
        self._status_row_layout = []
        self._status_back_y = 0
        self._status_collect_deadline = 0
        self._status_page = 0
        self._status_pages = 1
        self._status_rows_per_page = 1
        self._status_up_rect = None
        self._status_down_rect = None
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
            if ctrl["id"] == "status":
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
        if btn.button_id == "status":
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
        # M5Paper (original) has no charge-detection hardware: isCharging() is
        # hardwired True, getBatteryCurrent()/getVBUSVoltage() are unsupported.
        # Only the voltage-derived level is meaningful, so that's all we read.
        level = None
        try:
            raw = M5.Power.getBatteryLevel()
            if raw is not None:
                level = max(0, min(100, int(raw)))
        except Exception:
            pass
        return level

    def _battery_bucket(self, level):
        if level is None:
            return None
        return (int(level) // 10) * 10

    def _draw_battery_primitive_at(self, x, y):
        body_w = BATT_W - BATT_NUB_W
        for i in range(BATT_FILL_INSET):
            M5.Lcd.drawRect(
                x + i, y + i, body_w - (2 * i), BATT_H - (2 * i), BLACK
            )
        nub_h = BATT_H // 2
        nub_y0 = y + (BATT_H - nub_h) // 2
        M5.Lcd.fillRect(x + body_w, nub_y0, BATT_NUB_W, nub_h, BLACK)

    def _draw_battery_icon(self, x, y, level, clear_region=True):
        """Draw the battery shell (PNG or primitive) plus a proportional fill
        bar at an arbitrary (x, y). Used by both the top bar and status rows."""
        if clear_region:
            M5.Lcd.fillRect(x, y, BATT_W, BATT_H, WHITE)
        self._draw_png(
            BATTERY_PNG,
            x,
            y,
            fallback=lambda: self._draw_battery_primitive_at(x, y),
        )
        inner_x = x + BATT_FILL_INSET
        inner_y = y + BATT_FILL_INSET
        inner_w = BATT_W - BATT_NUB_W - (2 * BATT_FILL_INSET)
        inner_h = BATT_H - (2 * BATT_FILL_INSET)
        if level is not None and inner_w > 0 and inner_h > 0:
            fill_w = (inner_w * max(0, min(100, int(level)))) // 100
            if fill_w > 0:
                M5.Lcd.fillRect(inner_x, inner_y, fill_w, inner_h, BLACK)

    def _draw_battery(self, level, clear_region=True):
        self._draw_battery_icon(
            self._batt_x, self._batt_y, level, clear_region=clear_region
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
        level = self._read_battery()
        bucket = self._battery_bucket(level)
        if bucket == self._batt_shown_bucket:
            return
        self._batt_shown_bucket = bucket
        self._epd_mode(quality=False)
        self._begin_write()
        try:
            self._draw_battery(level, clear_region=True)
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
        if self._last_sent == "Checking status":
            return "Checking status"
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

    def _wand_name(self, mac):
        clean = mac.replace(":", "").upper()
        if len(clean) >= 4:
            return "W-" + clean[-4:]
        return "W-" + clean

    def _signal_level(self, rssi):
        """Map RSSI (dBm) to a 0..3 strength level, or -1 if unknown."""
        if rssi is None:
            return -1
        if rssi >= -55:
            return 3   # Strong
        if rssi >= -68:
            return 2   # Good
        if rssi >= -80:
            return 1   # Fair
        return 0       # Poor

    def _draw_signal_primitive_at(self, x, y, level):
        base_y = y + SIGNAL_H
        for i in range(SIGNAL_BARS):
            bh = SIGNAL_BAR_MIN_H + i * SIGNAL_BAR_STEP
            bx = x + i * (SIGNAL_BAR_W + SIGNAL_BAR_GAP)
            by = base_y - bh
            if i <= level:
                M5.Lcd.fillRect(bx, by, SIGNAL_BAR_W, bh, BLACK)
            else:
                M5.Lcd.drawRect(bx, by, SIGNAL_BAR_W, bh, BLACK)

    def _draw_signal_icon(self, x, y, level):
        if 0 <= level < len(SIGNAL_PNGS):
            self._draw_png(
                SIGNAL_PNGS[level],
                x,
                y,
                fallback=lambda: self._draw_signal_primitive_at(x, y, level),
            )
        else:
            # Unknown signal: all-empty bars.
            self._draw_signal_primitive_at(x, y, -1)

    def _build_status_layout(self):
        """Lay out only the rows on the current page; compute page count."""
        self._status_back_y = SCREEN_H - SETTINGS_SAVE_H - GAP
        y0 = TOP_BAR_H + GAP
        avail = (self._status_back_y - GAP) - y0
        rpp = avail // (STATUS_ROW_H + STATUS_ROW_GAP)
        if rpp < 1:
            rpp = 1
        self._status_rows_per_page = rpp
        total = len(self._status_rows)
        pages = (total + rpp - 1) // rpp
        if pages < 1:
            pages = 1
        self._status_pages = pages
        if self._status_page >= pages:
            self._status_page = pages - 1
        if self._status_page < 0:
            self._status_page = 0
        start = self._status_page * rpp
        end = min(total, start + rpp)
        self._status_row_layout = []
        y = y0
        for idx in range(start, end):
            self._status_row_layout.append({
                "mac": self._status_rows[idx]["mac"],
                "y": y,
                "h": STATUS_ROW_H,
            })
            y += STATUS_ROW_H + STATUS_ROW_GAP

    def _row_data_for(self, mac):
        for row in self._status_rows:
            if row["mac"] == mac:
                return row
        return None

    def _draw_status_row(self, layout, row_data):
        x = MARGIN
        y = layout["y"]
        w = SCREEN_W - (2 * MARGIN)
        h = layout["h"]
        M5.Lcd.fillRect(x, y, w, h, WHITE)
        self._draw_border(x, y, w, h, BLACK)

        text_y = y + (h - FONT_STATUS) // 2

        # Wand name (left).
        name = row_data.get("name", "")
        self._draw_text_left(name, x + 14, text_y, BLACK, WHITE, FONT_STATUS)

        # Battery icon + percent.
        batt = row_data.get("battery")
        batt_x = x + 150
        self._draw_battery_icon(
            batt_x, y + (h - BATT_H) // 2, batt, clear_region=False
        )
        batt_txt = "?" if batt is None else ("%d%%" % int(batt))
        self._draw_text_left(
            batt_txt, batt_x + BATT_W + 12, text_y, BLACK, WHITE, FONT_STATUS
        )

        # Big gap, then signal icon + word.
        rssi = row_data.get("rssi")
        level = self._signal_level(rssi)
        sig_x = x + 330
        self._draw_signal_icon(sig_x, y + (h - SIGNAL_H) // 2, level)
        sig_word = "--" if level < 0 else SIGNAL_WORDS[level]
        self._draw_text_left(
            sig_word, sig_x + SIGNAL_W + 12, text_y, BLACK, WHITE, FONT_STATUS
        )

    def _draw_status_header(self):
        """Title + page indicator + Up/Down nav buttons in the top bar."""
        M5.Lcd.fillRect(0, 0, SCREEN_W, TOP_BAR_H, WHITE)
        self._draw_text_left(
            "Device Status", MARGIN, TOP_BAR_H // 2 - 6, BLACK, WHITE, FONT_SETTINGS
        )
        nav_y = (TOP_BAR_H - STATUS_NAV_W) // 2
        if nav_y < 2:
            nav_y = 2
        nav_h = TOP_BAR_H - 2 * nav_y
        up_x = SCREEN_W - MARGIN - 2 * STATUS_NAV_W - GAP
        down_x = SCREEN_W - MARGIN - STATUS_NAV_W
        self._status_up_rect = (up_x, nav_y, STATUS_NAV_W, nav_h)
        self._status_down_rect = (down_x, nav_y, STATUS_NAV_W, nav_h)
        # Pagination controls only appear when the list spans multiple pages.
        if self._status_pages > 1:
            self._draw_text_centered(
                "%d/%d" % (self._status_page + 1, self._status_pages),
                up_x - GAP - 28,
                TOP_BAR_H // 2,
                BLACK,
                WHITE,
                FONT_SETTINGS,
            )
            self._draw_nav_button(self._status_up_rect, "Up")
            self._draw_nav_button(self._status_down_rect, "Dn")

    def _draw_nav_button(self, rect, label):
        x, y, w, h = rect
        M5.Lcd.fillRect(x, y, w, h, WHITE)
        self._draw_border(x, y, w, h, BLACK)
        self._draw_text_centered(label, x + w // 2, y + h // 2, BLACK, WHITE, FONT_SETTINGS)

    def _draw_status_back(self):
        back_x = MARGIN
        back_w = SCREEN_W - (2 * MARGIN)
        M5.Lcd.fillRect(back_x, self._status_back_y, back_w, SETTINGS_SAVE_H, BLACK)
        self._draw_border(back_x, self._status_back_y, back_w, SETTINGS_SAVE_H, BLACK)
        self._draw_text_centered(
            "Back",
            back_x + back_w // 2,
            self._status_back_y + SETTINGS_SAVE_H // 2,
            WHITE,
            BLACK,
            FONT_SETTINGS,
        )

    def paint_status(self):
        self._epd_mode(quality=True)
        self._build_status_layout()
        self._begin_write()
        try:
            M5.Lcd.clear(WHITE)
            self._draw_status_header()
            if not self._status_rows:
                self._draw_text_centered(
                    "Waiting for wands...",
                    SCREEN_W // 2,
                    SCREEN_H // 2,
                    BLACK,
                    WHITE,
                    FONT_SETTINGS,
                )
            else:
                for layout in self._status_row_layout:
                    row_data = self._row_data_for(layout["mac"])
                    if row_data:
                        self._draw_status_row(layout, row_data)
            self._draw_status_back()
        finally:
            self._end_write()

    def scroll_status(self, direction):
        """Page the device list. direction is 'up' or 'down'."""
        if self.mode != "status":
            return
        page = self._status_page + (1 if direction == "down" else -1)
        if page < 0 or page >= self._status_pages or page == self._status_page:
            return
        self._status_page = page
        self.paint_status()

    def open_status(self):
        self.mode = "status"
        self._status_rows = []
        self._status_page = 0
        self._status_collect_deadline = time.ticks_add(time.ticks_ms(), 6000)
        self._last_sent = "Checking status"
        self.paint_status()

    def close_status(self):
        self.mode = "main"
        self._status_rows = []
        self._status_row_layout = []
        self._status_page = 0
        self.paint_full()

    def upsert_status_report(self, mac, battery, rssi):
        if self.mode != "status":
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self._status_collect_deadline) > 0:
            return
        for row in self._status_rows:
            if row["mac"] == mac:
                row["battery"] = battery
                row["rssi"] = rssi
                self._redraw_status_row(mac)
                return
        was_empty = len(self._status_rows) == 0
        self._status_rows.append({
            "mac": mac,
            "name": self._wand_name(mac),
            "battery": battery,
            "rssi": rssi,
        })
        if was_empty:
            # Clears the "Waiting for wands..." text and draws the first row.
            self.paint_status()
            return
        self._build_status_layout()
        # Partially redraw the new row if it landed on the current page, and
        # refresh the header so the page count stays correct -- no full flash.
        self._redraw_status_row(mac)
        self._epd_mode(quality=False)
        self._begin_write()
        try:
            self._draw_status_header()
        finally:
            self._end_write()

    def _redraw_status_row(self, mac):
        """Partial redraw of one row IF it is on the current page; else no-op."""
        self._build_status_layout()
        layout = None
        for item in self._status_row_layout:
            if item["mac"] == mac:
                layout = item
                break
        if layout is None:
            return
        row_data = self._row_data_for(mac)
        if row_data is None:
            return
        self._epd_mode(quality=False)
        self._begin_write()
        try:
            self._draw_status_row(layout, row_data)
        finally:
            self._end_write()

    def _status_hit(self, x, y):
        if self._status_pages > 1:
            for rect, name in (
                (self._status_up_rect, "__up__"),
                (self._status_down_rect, "__down__"),
            ):
                if rect is None:
                    continue
                rx, ry, rw, rh = rect
                if rx <= x < rx + rw and ry <= y < ry + rh:
                    return name
        back_x = MARGIN
        back_w = SCREEN_W - (2 * MARGIN)
        if (
            back_x <= x < back_x + back_w
            and self._status_back_y <= y < self._status_back_y + SETTINGS_SAVE_H
        ):
            return "__back__"
        return None

    # ── Sleep screen ──────────────────────────────────────────────────────
    def _draw_big_empty_battery(self, x, y, w, h):
        nub_w = 12
        body_w = w - nub_w
        for i in range(4):
            M5.Lcd.drawRect(x + i, y + i, body_w - 2 * i, h - 2 * i, BLACK)
        nub_h = h // 2
        M5.Lcd.fillRect(x + body_w, y + (h - nub_h) // 2, nub_w, nub_h, BLACK)

    def paint_sleep(self, low_batt=False):
        """Full-screen sleep notice. E-ink holds this with zero power."""
        self.mode = "sleep"
        self._epd_mode(quality=True)
        self._begin_write()
        try:
            M5.Lcd.clear(WHITE)
            cx = SCREEN_W // 2
            cy = SCREEN_H // 2
            if low_batt:
                self._draw_big_empty_battery(cx - 80, cy - 170, 160, 80)
                self._draw_text_centered(
                    "Battery Low", cx, cy - 40, BLACK, WHITE, FONT_STOP
                )
                self._draw_text_centered(
                    "Please charge soon", cx, cy + 10, BLACK, WHITE, FONT_SETTINGS
                )
            else:
                self._draw_text_centered(
                    "Device Sleeping", cx, cy - 50, BLACK, WHITE, FONT_STOP
                )
            self._draw_text_centered(
                "Press the side button (up or down)",
                cx, cy + 110, BLACK, WHITE, FONT_SETTINGS,
            )
            self._draw_text_centered(
                "or tap the screen to wake.",
                cx, cy + 150, BLACK, WHITE, FONT_SETTINGS,
            )
        finally:
            self._end_write()

    def read_soc(self):
        return self._read_battery()

    def paint_full(self):
        self._epd_mode(quality=True)
        if self.mode == "settings":
            self.paint_settings()
            return
        if self.mode == "status":
            self.paint_status()
            return
        self._begin_write()
        try:
            M5.Lcd.clear(WHITE)
            self._draw_gear()
            level = self._read_battery()
            self._draw_battery(level)
            self._batt_shown_bucket = self._battery_bucket(level)
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
        if self.mode == "status":
            if not self.try_debounce():
                return None
            hit = self._status_hit(x, y)
            if hit == "__back__":
                return "close_status"
            if hit == "__up__":
                return "status_up"
            if hit == "__down__":
                return "status_down"
            return None

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
        elif btn.button_id == "status":
            self._last_sent = "Checking status"
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
