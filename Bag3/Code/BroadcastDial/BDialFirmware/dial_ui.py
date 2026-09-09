"""dial_ui.py — LVGL / m5ui screens behind bbox_ui.py's painter API.

Same method names and signatures as BboxUI so bdial_server.py stays a
near-copy of bbox_server.py. Screens are built once in begin() and swapped
with screen_load(); paints only update label text.

Style reference: Bag2/Code/DialSpeaker/Dial_Music.py (M5 Dial v1).
Palette matches bbox_ui.py so Box and Dial read as one product.
"""

import time

import M5
import m5ui
import lvgl as lv

from dial_board import SCREEN_W, SCREEN_H, SPEAKER_VOLUME
from dial_input import NEXT, PREV, ACT, BACK, EXIT

WHITE = 0xFFFFFF
BLACK = 0x000000
BG = 0x111111
ACCENT = 0x3FE0C2
WARN = 0xFF7A4A
MUTED = 0x888888
AMBER = 0xFFA000

FONT14 = None
FONT16 = None
FONT24 = None


def _fonts():
    global FONT14, FONT16, FONT24
    if FONT14 is None:
        FONT14 = lv.font_montserrat_14
        FONT16 = lv.font_montserrat_16
        FONT24 = lv.font_montserrat_24


def _safe(fn, label):
    try:
        fn()
    except Exception as e:
        print("# %s err: %s" % (label, str(e)))


class DialUI(object):
    def __init__(self, inputs=None):
        # No M5 / m5ui calls here — BdialServer constructs this before
        # M5.begin(). begin() is called from run() right after M5.begin().
        self._input = inputs
        self._pages = {}
        self._cur = None
        self._built = False
        # Widgets filled in _build_*
        self._lbl = {}
        self._btns = {}

    def set_input(self, inputs):
        self._input = inputs

    def begin(self):
        """Call once, right after M5.begin() — not before."""
        _fonts()
        try:
            m5ui.init()
        except Exception as e:
            print("# m5ui.init err: %s" % str(e))
        try:
            M5.Speaker.setVolume(SPEAKER_VOLUME)
        except Exception as e:
            print("# speaker volume err: %s" % str(e))
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

    def _page(self, name, bg=BG):
        pg = m5ui.M5Page(bg_c=bg)
        self._pages[name] = pg
        return pg

    def _label(self, key, parent, text, y, font, color=WHITE, w=200):
        lbl = m5ui.M5Label(
            text, x=20, y=y,
            text_c=color, bg_c=BG, bg_opa=0,
            font=font, parent=parent)
        lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        lbl.set_width(w)
        lbl.align(lv.ALIGN.TOP_MID, 0, y)
        self._lbl[key] = lbl
        return lbl

    def _round_btn(self, key, parent, text, x, y, w, h, bg, intent, font=None):
        if font is None:
            font = FONT14
        btn = m5ui.M5Button(
            text=text, x=x, y=y, w=w, h=h,
            bg_c=bg, text_c=WHITE, font=font, parent=parent)
        btn.set_style_radius(w // 2 if w <= h else h // 2, 0)
        btn.set_style_border_width(0, 0)
        btn.add_event_cb(self._cb(intent), lv.EVENT.CLICKED, None)
        self._btns[key] = btn
        return btn

    def _show(self, name):
        pg = self._pages.get(name)
        if pg is None:
            return
        try:
            pg.screen_load()
            self._cur = name
        except Exception as e:
            print("# screen_load(%s) err: %s" % (name, str(e)))

    def _set_text(self, key, text):
        lbl = self._lbl.get(key)
        if lbl is None:
            return
        try:
            lbl.set_text(text)
        except Exception as e:
            print("# set_text(%s) err: %s" % (key, str(e)))

    def _set_color(self, key, color):
        lbl = self._lbl.get(key)
        if lbl is None:
            return
        try:
            lbl.set_style_text_color(lv.color_hex(color), 0)
        except Exception as e:
            print("# set_color(%s) err: %s" % (key, str(e)))

    # ── build screens once ──────────────────────────────────────

    def _build_all(self):
        self._build_simple("booting", "Starting", AMBER, BLACK)
        self._build_idle()
        self._build_receiving()
        self._build_armed()
        self._build_scanning()
        self._build_splash("already", ACCENT)
        self._build_splash("written", ACCENT)
        self._build_splash("write_failed", WARN)
        self._build_splash("read_result", ACCENT)
        self._build_writing()
        self._build_done()
        self._build_complete()
        self._build_error()
        self._build_tag_list()
        self._build_tag_group()
        self._build_serve()
        self._build_mode_change()
        self._build_no_pickup()

    def _build_simple(self, name, title, bg, fg):
        pg = self._page(name, bg)
        self._label("%s_title" % name, pg, title, 100, FONT24, fg)

    def _build_idle(self):
        pg = self._page("idle")
        self._label("idle_title", pg, "Broadcast Dial", 70, FONT16, WHITE)
        self._label("idle_status", pg, "linked to laptop", 110, FONT14, ACCENT)
        self._label("idle_sub", pg, "no game loaded yet", 140, FONT14, MUTED)

    def _build_receiving(self):
        pg = self._page("receiving")
        self._label("recv_title", pg, "Getting game...", 90, FONT16, WHITE)
        self._label("recv_sub", pg, "game", 130, FONT14, MUTED)

    def _build_armed(self):
        pg = self._page("armed")
        self._label("armed_idx", pg, "Tag 1/1", 50, FONT14, MUTED)
        self._label("armed_label", pg, "", 90, FONT24, WHITE)
        self._label("armed_hint", pg, "hold card on reader", 150, FONT14, ACCENT)

    def _build_scanning(self):
        pg = self._page("scanning")
        # Rim ring as a "tap here" affordance — antenna is under the screen.
        try:
            ring = lv.obj(pg)
            ring.set_size(220, 220)
            ring.align(lv.ALIGN.CENTER, 0, 0)
            ring.set_style_bg_opa(0, 0)
            ring.set_style_border_width(6, 0)
            ring.set_style_border_color(lv.color_hex(ACCENT), 0)
            ring.set_style_radius(110, 0)
            ring.remove_flag(lv.obj.FLAG.CLICKABLE)
            self._scan_ring = ring
        except Exception as e:
            print("# scan ring err: %s" % str(e))
            self._scan_ring = None
        self._label("scan_title", pg, "Scanning", 80, FONT16, WHITE)
        self._label("scan_label", pg, "", 110, FONT24, ACCENT)
        self._label("scan_hint", pg, "hold card on screen", 160, FONT14, MUTED)
        self._round_btn("scan_back", pg, "BACK", 70, 190, 100, 36, MUTED, BACK, FONT14)

    def _build_splash(self, name, accent):
        pg = self._page(name, accent if name != "write_failed" else BG)
        fg = BLACK if name != "write_failed" else WARN
        bg = accent if name != "write_failed" else BG
        # Re-tint page for write_failed stays BG; already/written are full-bleed.
        if name == "write_failed":
            pg = self._pages[name]
        self._label("%s_title" % name, pg, "", 80, FONT16, fg if name != "write_failed" else WARN)
        self._label("%s_sub" % name, pg, "", 120, FONT14, MUTED if name == "write_failed" else (BLACK if name != "write_failed" else MUTED))
        # Dim the sub on full-bleed fills
        if name != "write_failed":
            self._set_color("%s_sub" % name, 0x222222)
        self._label("%s_hint" % name, pg, "press to continue", 170, FONT14, MUTED if name == "write_failed" else 0x333333)
        # Whole-screen tap dismisses via a transparent full-bleed button
        try:
            tap = m5ui.M5Button(
                text=" ", x=0, y=0, w=SCREEN_W, h=SCREEN_H,
                bg_c=bg, text_c=bg, font=FONT14, parent=pg)
            tap.set_style_opa(0, 0)
            tap.add_event_cb(self._cb(ACT), lv.EVENT.CLICKED, None)
        except Exception as e:
            print("# splash tap err: %s" % str(e))

    def _build_writing(self):
        pg = self._page("writing")
        self._label("writing_title", pg, 'Writing...', 90, FONT16, WHITE)
        self._label("writing_hint", pg, "hold card steady", 130, FONT14, MUTED)

    def _build_done(self):
        pg = self._page("done")
        self._label("done_title", pg, "", 90, FONT16, ACCENT)
        self._label("done_sub", pg, "", 130, FONT14, MUTED)

    def _build_complete(self):
        pg = self._page("complete")
        self._label("complete_title", pg, "All tags ready!", 100, FONT16, ACCENT)

    def _build_error(self):
        pg = self._page("error")
        self._label("error_title", pg, "", 100, FONT16, WARN)

    def _build_tag_list(self):
        pg = self._page("tag_list")
        self._label("tl_hdr", pg, "pickup off", 18, FONT14, WARN)
        self._label("tl_prev", pg, "", 60, FONT14, MUTED)
        self._label("tl_cur", pg, "", 100, FONT24, WHITE)
        self._label("tl_next", pg, "", 150, FONT14, MUTED)
        self._round_btn("tl_act", pg, "OPEN", 70, 185, 100, 40, ACCENT, ACT, FONT14)

    def _build_tag_group(self):
        pg = self._page("tag_group")
        self._label("tg_hdr", pg, "", 18, FONT14, WARN)
        self._label("tg_prev", pg, "", 60, FONT14, MUTED)
        self._label("tg_cur", pg, "", 100, FONT24, WHITE)
        self._label("tg_count", pg, "", 135, FONT14, MUTED)
        self._label("tg_next", pg, "", 160, FONT14, MUTED)
        self._round_btn("tg_act", pg, "SCAN", 70, 185, 100, 40, ACCENT, ACT, FONT14)

    def _build_serve(self):
        pg = self._page("serve")
        self._label("serve_title", pg, "Serving", 40, FONT16, ACCENT)
        self._label("serve_ssid", pg, "", 80, FONT16, WHITE)
        self._label("serve_pickups", pg, "pickups: 0", 120, FONT14, MUTED)
        self._label("serve_hint", pg, "hold button to leave", 150, FONT14, MUTED)
        # CLOSE emits EXIT (same as the hold) — stray taps are the same risk
        # as a stray bump, so the hold stays as well.
        self._round_btn("serve_close", pg, "CLOSE", 70, 180, 100, 40, MUTED, EXIT, FONT14)

    def _build_mode_change(self):
        pg = self._page("mode_change", AMBER)
        self._label("mc_title", pg, "", 100, FONT24, BLACK)

    def _build_no_pickup(self):
        pg = self._page("no_pickup")
        self._label("np_title", pg, "pickup off", 90, FONT16, WARN)
        self._label("np_hint", pg, "DONE to serve", 130, FONT14, MUTED)

    # ── audio (same four beeps as bbox_ui) ──────────────────────

    def _tone(self, freq, ms):
        try:
            M5.Speaker.tone(freq, ms)
        except Exception as e:
            print("# speaker tone err: %s" % str(e))

    # Frequencies tuned for the Dial's piezo buzzer (cfg.buzzer=True on
    # GPIO3), not a real speaker -- it is close to silent below ~2 kHz and
    # peaks (its resonant frequency) around 3000 Hz, confirmed live with a
    # 1-10 kHz sweep (2026-09-09). The original tones here (523-1800 Hz,
    # picked as if this were a musical speaker like the Box's) were real
    # but essentially inaudible. Clustered close to 3000 now rather than
    # spread across a wide range like the Box's tones -- anything far from
    # the resonant peak gets quiet fast on this buzzer -- so beeps are told
    # apart mostly by duration/direction, not big pitch jumps.
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

    # ── painters (bbox_ui signatures) ───────────────────────────

    def paint_booting(self):
        _safe(lambda: self._show("booting"), "paint_booting")

    def paint_idle(self, linked=True):
        def go():
            self._set_text("idle_status",
                           "linked to laptop" if linked else "not linked")
            self._set_color("idle_status", ACCENT if linked else MUTED)
            self._show("idle")
        _safe(go, "paint_idle")

    def paint_receiving(self, game_name=""):
        def go():
            self._set_text("recv_sub", game_name if game_name else "game")
            self._show("receiving")
        _safe(go, "paint_receiving")

    def paint_armed(self, label, index=1, total=1):
        def go():
            self._set_text("armed_idx", "Tag %d/%d" % (index, total))
            self._set_text("armed_label", label)
            self._show("armed")
        _safe(go, "paint_armed")

    def paint_read_result(self, existing):
        def go():
            if existing:
                self._set_text("read_result_title", "Card has:")
                self._set_text("read_result_sub", '"%s"' % existing)
            else:
                self._set_text("read_result_title", "Blank card")
                self._set_text("read_result_sub", "no text found")
            self._show("read_result")
        _safe(go, "paint_read_result")

    def paint_scanning(self, label):
        def go():
            self._set_text("scan_label", label)
            self._show("scanning")
        _safe(go, "paint_scanning")

    def paint_already(self, label):
        def go():
            self._set_text("already_title", 'Already "%s"' % label)
            self._set_text("already_sub", "no change needed")
            self._show("already")
        _safe(go, "paint_already")

    def paint_written(self, label, count):
        def go():
            self._set_text("written_title", '"%s" written!' % label)
            self._set_text("written_sub", "%d written so far" % count)
            self._show("written")
        _safe(go, "paint_written")

    def paint_write_failed(self, label):
        def go():
            self._set_text("write_failed_title", "Write failed")
            self._set_text("write_failed_sub", label)
            self._show("write_failed")
        _safe(go, "paint_write_failed")

    def paint_writing(self, label):
        def go():
            self._set_text("writing_title", 'Writing "%s"...' % label)
            self._show("writing")
        _safe(go, "paint_writing")

    def paint_done(self, label, written, total):
        def go():
            self._set_text("done_title", "%s done!" % label)
            self._set_text("done_sub", "%d of %d written" % (written, total))
            self._show("done")
        _safe(go, "paint_done")

    def paint_complete(self, msg="All tags ready!"):
        def go():
            self._set_text("complete_title", msg)
            self._show("complete")
        _safe(go, "paint_complete")

    def paint_error(self, msg):
        def go():
            self._set_text("error_title", msg)
            self._show("error")
        _safe(go, "paint_error")

    def paint_tag_list(self, entries, cursor):
        """Focused entry large and centred; neighbours dimmed; pickup-off header."""
        def go():
            n = len(entries)
            cur = entries[cursor] if n else ""
            prev = entries[cursor - 1] if n and cursor > 0 else (
                entries[n - 1] if n > 1 else "")
            nxt = entries[cursor + 1] if n and cursor + 1 < n else (
                entries[0] if n > 1 else "")
            if prev == cur:
                prev = ""
            if nxt == cur:
                nxt = ""
            self._set_text("tl_hdr", "pickup off")
            self._set_text("tl_prev", prev)
            self._set_text("tl_cur", cur)
            self._set_text("tl_next", nxt)
            # DONE gets the accent treatment via button label.
            btn = self._btns.get("tl_act")
            if btn is not None:
                try:
                    if cur == "DONE":
                        btn.set_btn_text("SERVE")
                    else:
                        btn.set_btn_text("OPEN")
                except Exception:
                    pass
            self._show("tag_list")
        _safe(go, "paint_tag_list")

    def paint_tag_group(self, title, rows, cursor, written):
        """Focused tag + cumulative write count; neighbours dimmed."""
        def go():
            n = len(rows)
            cur = rows[cursor] if n else ""
            prev = rows[cursor - 1] if n and cursor > 0 else ""
            nxt = rows[cursor + 1] if n and cursor + 1 < n else ""
            count = 0
            if written and cur and cur != "< back":
                count = written.get(cur, 0)
            self._set_text("tg_hdr", title)
            self._set_text("tg_prev", prev)
            self._set_text("tg_cur", cur)
            if cur == "< back":
                self._set_text("tg_count", "")
            else:
                self._set_text("tg_count", "%d written" % count)
            self._set_text("tg_next", nxt)
            btn = self._btns.get("tg_act")
            if btn is not None:
                try:
                    btn.set_btn_text("BACK" if cur == "< back" else "SCAN")
                except Exception:
                    pass
            self._show("tag_group")
        _safe(go, "paint_tag_group")

    def paint_serve(self, ssid, pickups=0):
        def go():
            self._set_text("serve_ssid", ssid)
            self._set_text("serve_pickups", "pickups: %d total" % pickups)
            self._show("serve")
        _safe(go, "paint_serve")

    def paint_mode_change(self, to_mode):
        def go():
            self._set_text("mc_title", "-> %s" % to_mode)
            self._show("mode_change")
        _safe(go, "paint_mode_change")

    def paint_no_pickup_hint(self):
        _safe(lambda: self._show("no_pickup"), "paint_no_pickup_hint")


def demo():
    """Cycle screens — run from REPL: import dial_ui; dial_ui.demo()"""
    import time
    M5.begin()
    ui = DialUI()
    ui.begin()
    screens = [
        lambda: ui.paint_idle(True),
        lambda: ui.paint_receiving("Melody"),
        lambda: ui.paint_tag_list(["Melody", "Utility Tags", "DONE"], 0),
        lambda: ui.paint_tag_group(
            "Melody", ["getcode:my_melody", "my_melody", "note_c", "< back"],
            2, {"note_c": 3}),
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
