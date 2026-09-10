"""bbox_ui.py — LVGL / m5ui screens for Broadcast Box (landscape 240x135).

Ported from the original M5.Lcd / M5GFX text renderer onto the same
m5ui/LVGL stack the Dial uses, so Box and Dial share one widget vocabulary
and one light palette instead of two separately-hand-drawn dark screens.
Same method names and signatures as DialUI so bbox_server.py stays a
near-copy of bdial_server.py -- see that file's module docstring for the
shared design notes (roller-as-list, breadcrumb, position track).

Hardware gate -- READ BEFORE TRUSTING THIS FILE ON A DEVICE: nothing in
this repo has previously imported m5ui/lvgl on a StickS3. The Dial's own
dial_board.py records a hardware failure (SoftAP OOM with LVGL pages
resident), and the Stick has less headroom than the Dial. probe_stick.py
now has an `m5ui` availability + heap check -- run it and read the result
before deploying this file. If m5ui.init() or the post-arm() heap check
fails on the Stick, fall back to the previous M5.Lcd/M5GFX renderer
(git history has it) rather than shipping a UI that cannot coexist with
SoftAP.

Two differences from the Dial, both because the Stick has no touch
screen, only BtnA/BtnB (see buttons.py):
  - The roller is present for its visual list (centre-selected wheel,
    position track) but is not the input source -- buttons.py's
    NEXT/PREV/ACT edges drive the same set_selected() calls the Dial's
    encoder drives, and nothing here registers a click callback.
  - Where the Dial has a tap-dismiss overlay or touch buttons, the Box
    shows two small persistent chips naming what BtnA and BtnB currently
    do, replacing the button-name strings baked into the old screen text
    ("BtnA=open BtnB=next").
"""

import time

import M5
import m5ui
import lvgl as lv

WHITE = 0xFFFFFF
BLACK = 0x000000

# Light palette. PEER copy: BroadcastDial/BDialFirmware/dial_ui.py -- keep in sync.
PAPER = 0xFFFFFF
INK = 0x212121
INK_SOFT = 0x757575
RULE = 0xE0E0E0
PRIMARY = 0x1976D2
PRIMARY_SOFT = 0xBBDEFB
OK = 0x2E7D32
DANGER = 0xC62828
CAUTION = 0xEF6C00

ROTATION = 1
SCREEN_W = 240
SCREEN_H = 135

# 0-255. StickS3's own docs warn to stay under ~75% (~191) on battery power
# to avoid a brown-out reboot when USB is unplugged.
SPEAKER_VOLUME = 190

FONT14 = None
FONT16 = None
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
    global FONT14, FONT16
    if FONT14 is not None:
        return
    FONT14 = lv.font_montserrat_14
    FONT16 = lv.font_montserrat_16
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
        "next": lv.SYMBOL.DOWN,
    })


class BboxUI(object):
    def __init__(self):
        # No M5 hardware calls here -- BboxServer.__init__ constructs this
        # before M5.begin(). begin() is called from run() right after it.
        self._pages = {}
        self._cur = None
        self._built = False
        self._lbl = {}
        self._roller = None
        self._track_fill = None

    def begin(self):
        """Call once, right after M5.begin() -- not before.

        Deliberately unguarded, same reasoning as DialUI.begin(): a UI
        that cannot initialise must be a crash, not a silently half-drawn
        screen. This is also where a StickS3 that cannot run m5ui will
        fail loudly, which is the point of the Stage 0 gate above.
        """
        M5.Lcd.setRotation(ROTATION)
        _fonts()
        m5ui.init()
        M5.Speaker.setVolume(SPEAKER_VOLUME)
        if not self._built:
            self._build_all()
            self._built = True

    def _page(self, name):
        pg = m5ui.M5Page(bg_c=PAPER)
        self._pages[name] = pg
        return pg

    def _label(self, key, parent, text, y, font, color=INK, w=220,
               align=lv.ALIGN.TOP_MID):
        lbl = m5ui.M5Label(
            text, x=0, y=y,
            text_c=color, bg_c=PAPER, bg_opa=0,
            font=font, parent=parent)
        lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        lbl.set_width(w)
        lbl.align(align, 0, y)
        self._lbl[key] = lbl
        return lbl

    def _show(self, name):
        """The one guarded seam in this file: a paint failure is logged
        with the screen it happened on and re-raised, not swallowed."""
        pg = self._pages.get(name)
        if pg is None:
            raise KeyError("bbox_ui: no such page %r" % name)
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
        try:
            self._roller.set_options(rows, lv.roller.MODE.NORMAL)
        except Exception:
            self._roller.set_options("\n".join(rows), lv.roller.MODE.NORMAL)

    def _set_track(self, cursor, total):
        frac = 1.0 if total <= 1 else (cursor + 1) / float(total)
        track_h = 78
        fill_h = max(6, int(track_h * frac))
        self._track_fill.set_size(5, fill_h)
        self._track_fill.align(lv.ALIGN.BOTTOM_MID, 0, 0)

    # ── build screens once ──────────────────────────────────────

    def _build_all(self):
        self._build_list()
        self._build_scan()
        self._build_status()
        self._build_serve()

    def _build_list(self):
        pg = self._page("list")
        self._label("lst_crumb", pg, "", 2, FONT14, CAUTION)

        track = lv.obj(pg)
        track.set_size(5, 78)
        track.align(lv.ALIGN.RIGHT_MID, -6, 6)
        track.set_style_bg_color(lv.color_hex(RULE), 0)
        track.set_style_bg_opa(255, 0)
        track.set_style_border_width(0, 0)
        track.set_style_radius(2, 0)
        track.remove_flag(lv.obj.FLAG.CLICKABLE)
        fill = lv.obj(track)
        fill.set_size(5, 6)
        fill.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        fill.set_style_bg_color(lv.color_hex(PRIMARY), 0)
        fill.set_style_bg_opa(255, 0)
        fill.set_style_border_width(0, 0)
        fill.set_style_radius(2, 0)
        fill.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._track_fill = fill

        roller = m5ui.M5Roller(
            x=6, y=18, w=200, h=78, options=[""],
            mode=lv.roller.MODE.NORMAL, selected=0, visible_row_count=2,
            font=FONT14, parent=pg)
        roller.align(lv.ALIGN.TOP_LEFT, 6, 18)
        roller.set_style_radius(8, 0)
        roller.set_style_bg_color(lv.color_hex(PAPER), 0)
        roller.set_style_border_width(1, 0)
        roller.set_style_border_color(lv.color_hex(RULE), 0)
        roller.set_style_text_color(lv.color_hex(INK_SOFT), 0)
        roller.set_style_bg_color(lv.color_hex(PRIMARY_SOFT), lv.PART.SELECTED)
        roller.set_style_text_color(lv.color_hex(INK), lv.PART.SELECTED)
        roller.set_style_text_font(FONT16, lv.PART.SELECTED)
        # No touch on this board -- BtnA/BtnB drive the cursor via
        # buttons.py; the roller is display-only.
        roller.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._roller = roller

        # Persistent chips naming what each physical button currently does.
        self._label("lst_a_chip", pg, "", 118, FONT14, PRIMARY, w=140,
                     align=lv.ALIGN.BOTTOM_LEFT)
        self._label("lst_b_chip", pg, IC["next"] + " next", 118, FONT14,
                     INK_SOFT, w=90, align=lv.ALIGN.BOTTOM_RIGHT)

    def _build_scan(self):
        pg = self._page("scan")
        self._label("scn_label", pg, "", 8, FONT16, INK)
        self._label("scn_hint", pg, "hold card on top", 40, FONT14, INK_SOFT)
        self._label("scn_b_chip", pg, IC["back"] + " back", 108, FONT14,
                     INK_SOFT, w=90, align=lv.ALIGN.BOTTOM_RIGHT)

    def _build_status(self):
        """One reusable screen behind every one-shot painter -- booting,
        idle, receiving, armed, overwrite, writing/written/write_failed/
        already, done, complete, error, mode_change, no_pickup_hint."""
        pg = self._page("status")
        self._label("st_title", pg, "", 6, FONT16, INK)
        self._label("st_body1", pg, "", 40, FONT14, INK_SOFT)
        self._label("st_body2", pg, "", 62, FONT14, INK_SOFT)
        self._label("st_hint", pg, "", 108, FONT14, INK_SOFT,
                     align=lv.ALIGN.BOTTOM_MID)

    def _build_serve(self):
        pg = self._page("serve")
        self._label("srv_icon", pg, IC["serve"], 4, FONT16, PRIMARY)
        self._label("srv_ssid", pg, "", 34, FONT16, INK)
        self._label("srv_pickups", pg, "", 62, FONT14, INK_SOFT)
        self._label("srv_hint", pg, "hold BtnA to write tags", 108, FONT14,
                     INK_SOFT, align=lv.ALIGN.BOTTOM_MID)

    # ── audio (same tones as the original M5GFX renderer) ───────

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
        self._set_text("st_title", title)
        self._set_color("st_title", title_c)
        self._set_text("st_body1", body1)
        self._set_text("st_body2", body2)
        self._set_text("st_hint", hint)
        self._show("status")

    # ── painters (dial_ui signatures) ───────────────────────────

    def paint_booting(self):
        self._status("Starting", title_c=INK_SOFT)

    def paint_idle(self, linked=True):
        status = "linked to laptop" if linked else "not linked"
        self._status("Broadcast Box", status, "no game loaded yet")

    def paint_receiving(self, game_name=""):
        self._status("Getting game...", game_name if game_name else "game")

    def paint_armed(self, label, index=1, total=1):
        self._status(label, "Tag %d/%d" % (index, total),
                     "hold card on reader")

    def paint_overwrite(self, existing, new_label):
        self._status(
            'Overwrite "%s"?' % existing, '-> "%s"' % new_label,
            title_c=CAUTION,
            hint=IC["ok"] + " A overwrite   " + IC["fail"] + " B cancel")

    def paint_scanning(self, label):
        self._set_text("scn_label", label)
        self._show("scan")

    def paint_already(self, label):
        self._status('Already "%s"' % label, "no change needed",
                     title_c=OK, hint="press any button")

    def paint_written(self, label, count):
        self._status('"%s" written!' % label, "%d written so far" % count,
                     title_c=OK, hint="press any button")

    def paint_write_failed(self, label):
        self._status("Write failed", label, title_c=DANGER,
                     hint="press any button")

    def paint_writing(self, label):
        self._status('Writing "%s"...' % label, "hold card steady")

    def paint_done(self, label, written, total):
        self._status("%s done!" % label, "%d of %d written" % (written, total),
                     title_c=OK)

    def paint_complete(self, msg="All tags ready!"):
        self._status(msg, title_c=OK)

    def paint_error(self, msg):
        self._status(msg, title_c=DANGER)

    def paint_mode_change(self, to_mode):
        self._status("-> %s" % to_mode, title_c=PRIMARY)

    def paint_no_pickup_hint(self):
        self._status("pickup off", "DONE + B1 to serve", title_c=CAUTION)

    def paint_tag_list(self, entries, cursor):
        """Tier 1: games + Utility Tags + DONE."""
        self._set_text("lst_crumb", IC["warn"] + " pickup off")
        self._roller_set([_fit(e) for e in entries])
        self._roller.set_selected(cursor, lv.ANIM.OFF)
        self._set_track(cursor, len(entries))
        cur = entries[cursor] if entries else ""
        if cur == "DONE":
            self._set_text("lst_a_chip", IC["serve"] + " A serve")
        else:
            self._set_text("lst_a_chip", IC["open"] + " A open")
        self._show("list")

    def paint_tag_group(self, title, rows, cursor, written):
        """Tier 2: one group's tags + "< back"."""
        self._set_text("lst_crumb", IC["back"] + " " + title)
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
        if cur == "< back":
            self._set_text("lst_a_chip", IC["back"] + " A back")
        else:
            self._set_text("lst_a_chip", IC["scan"] + " A scan")
        self._show("list")

    def paint_serve(self, ssid, pickups=0):
        self._set_text("srv_ssid", ssid)
        self._set_text("srv_pickups", "pickups: %d total" % pickups)
        self._show("serve")


def demo():
    """Cycle screens — run from REPL: import bbox_ui; bbox_ui.demo()"""
    import time
    M5.begin()
    ui = BboxUI()
    ui.begin()
    long_games = ["Game %d" % i for i in range(1, 9)] + ["Utility Tags", "DONE"]
    screens = [
        lambda: ui.paint_idle(True),
        lambda: ui.paint_receiving("Melody"),
        lambda: ui.paint_tag_list(["Melody", "Utility Tags", "DONE"], 0),
        lambda: ui.paint_tag_list(long_games, 4),
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
