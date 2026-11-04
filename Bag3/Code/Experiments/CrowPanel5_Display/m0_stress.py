"""M0 coexistence stress test: ESP-NOW + RGB display/GT911 touch + PN532 on the touch bus.

Imported by m0_main.py after the radio is up. Stages are logged with m0_diag.line; then a soak
(status poll every 2 s, NFC detect, moving bar, touch counter), then 50 radio off/on cycles, then
the soak continues.
"""

import time

import i2c

import board
import display_lvgl
import home
import m0_diag
from pn532_bus import PN532Bus
from ws1850s import WS1850S

SOAK_S = 10          # first soak, seconds
CYCLES = 2
POLL_MS = 2000
LOG_MS = 10000
NFC_MS = 250
_CAUSES = {1: "power_on", 2: "hard_reset(EN)", 3: "wdt", 4: "deepsleep", 5: "soft_reset"}

_buses = []
_orig_init = i2c.I2C.Bus.__init__


def _grab(self, *a, **k):
    _orig_init(self, *a, **k)
    _buses.append(self)


class WSReader:
    """WS1850S with the PN532Bus detect/field interface."""

    def __init__(self, bus):
        self.r = WS1850S(bus)

    def field(self, on):
        if on:
            self.r.antenna_on()
        else:
            self.r.antenna_off()

    def detect(self):
        return self.r.read_uid_full()


class State:
    def __init__(self):
        self.polls = 0
        self.replies = 0
        self.nfc_ok = 0
        self.nfc_miss = 0
        self.nfc_err = 0
        self.touches = 0
        self.cycle_min = None

    def text(self):
        return f"polls={self.polls} replies={self.replies} nfc_ok={self.nfc_ok} nfc_miss={self.nfc_miss} nfc_err={self.nfc_err} touches={self.touches}"


def _overlay(st):
    import lvgl as lv
    top = lv.layer_top()
    track = lv.obj(top)
    track.set_size(board.LCD_W, 6)
    track.set_pos(0, 0)
    track.set_style_bg_color(lv.color_hex(0x202020), 0)
    track.set_style_border_width(0, 0)
    track.set_style_radius(0, 0)
    track.remove_flag(lv.obj.FLAG.CLICKABLE)
    track.remove_flag(lv.obj.FLAG.SCROLLABLE)
    bar = lv.obj(top)
    bar.set_size(80, 6)
    bar.set_pos(0, 0)
    bar.set_style_bg_color(lv.color_hex(0xFF2D8A), 0)
    bar.set_style_border_width(0, 0)
    bar.set_style_radius(0, 0)
    bar.remove_flag(lv.obj.FLAG.CLICKABLE)
    bar.remove_flag(lv.obj.FLAG.SCROLLABLE)
    lab = lv.label(top)
    lab.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    lab.set_style_bg_color(lv.color_hex(0x000000), 0)
    lab.set_style_bg_opa(lv.OPA.COVER, 0)
    lab.set_pos(240, 8)
    lab.set_text("M0 touches 0")
    lab.remove_flag(lv.obj.FLAG.CLICKABLE)

    def on_press(e):
        st.touches += 1

    lv.screen_active().add_event_cb(on_press, lv.EVENT.PRESSED, None)
    return bar, lab


def _nfc_step(nfc, st):
    try:
        if nfc.detect():
            st.nfc_ok += 1
        else:
            st.nfc_miss += 1
    except Exception as e:
        st.nfc_err += 1
        if st.nfc_err <= 3:
            print(f"M0 nfc error: {e}")


def _poll_radio(mgr, st):
    for _ in range(4):
        kind, data, mac = mgr.poll()
        if kind is None:
            break
        if isinstance(data, dict) and data.get("type") == "status_report":
            st.replies += 1


def _soak(mgr, nfc, st, bar, lab, seconds):
    end = None if seconds is None else time.ticks_add(time.ticks_ms(), seconds * 1000)
    now = time.ticks_ms()
    next_poll = next_log = next_nfc = now
    x = 0
    while end is None or time.ticks_diff(end, time.ticks_ms()) > 0:
        now = time.ticks_ms()
        if time.ticks_diff(now, next_poll) >= 0:
            next_poll = time.ticks_add(now, POLL_MS)
            mgr.broadcast({"type": "status_poll"})
            st.polls += 1
        _poll_radio(mgr, st)
        if nfc is not None and time.ticks_diff(now, next_nfc) >= 0:
            _nfc_step(nfc, st)
            next_nfc = time.ticks_add(time.ticks_ms(), NFC_MS)
        x = (x + 6) % (board.LCD_W - 80)
        bar.set_x(x)
        lab.set_text(f"M0 touches {st.touches}")
        if time.ticks_diff(now, next_log) >= 0:
            next_log = time.ticks_add(now, LOG_MS)
            m0_diag.line("soak", st.text())
        time.sleep_ms(1)


def _cycles(mgr, nfc, st, bar, lab):
    m0_diag.line("cycles0", "start")
    worst = None
    fails = 0
    for i in range(CYCLES):
        mgr.shutdown()
        nfc_note = ""
        if nfc is not None:
            try:
                nfc.field(True)
                nfc_note = " uid=" + str(nfc.detect()) 
                nfc.field(False)
            except Exception as e:
                nfc_note = f" nfc_err={e}"
        for _ in range(10):
            bar.set_x((bar.get_x() + 6) % (board.LCD_W - 80))
            time.sleep_ms(10)
        try:
            mgr.init()
            ok = "up"
        except Exception as e:
            ok = f"INIT FAILED: {e}"
            fails += 1
        big = m0_diag.line(f"cycle{i + 1:02d}", ok + nfc_note)
        worst = big if worst is None else min(worst, big)
        if fails:
            break
    st.cycle_min = worst
    print(f"M0 cycles done: radio_fail={fails} smallest_int_largest={worst}")


def run(mgr, cause):
    time.sleep_ms(1)
    m0_diag.line("radio_up", f"reset_cause={cause}({_CAUSES.get(cause, '?')})")
    i2c.I2C.Bus.__init__ = _grab
    st = State()
    display, touch, th = display_lvgl.init()
    i2c.I2C.Bus.__init__ = _orig_init
    m0_diag.line("display")
    home.show()
    m0_diag.line("home")
    bar, lab = _overlay(st)
    nfc = None
    try:
        bus = _buses[0]
        print(f"M0 i2c scan: {[hex(a) for a in bus.scan()]}")
        found = bus.scan()
        if 0x28 in found:
            nfc = WSReader(bus)
            m0_diag.line("ws1850s", f"version={hex(nfc.r.version())}")
            found = ()
        for _ in range(0 if nfc else 4):
            for a in (0x24, 0x22):
                try:
                    bus.writeto(a, b"\x00")
                except OSError:
                    pass
            time.sleep_ms(100)
            found = bus.scan()
            print(f"M0 rescan: {[hex(a) for a in found]}")
        fw = None
        for addr in (() if nfc else (0x24, 0x22)):
            nfc = PN532Bus(bus, addr)
            try:
                fw = nfc.start()
                print(f"M0 pn532 answered at {hex(addr)}")
                break
            except Exception as e:
                print(f"M0 pn532 at {hex(addr)} failed: {e}")
        if fw is None and nfc is None:
            raise OSError("no PN532")
        nfc.field(True)
        if fw is not None:
            m0_diag.line("pn532", f"fw={fw}")
    except Exception as e:
        print(f"M0 pn532 init failed: {e}")
        m0_diag.line("pn532", "FAILED")
        nfc = None
    _soak(mgr, nfc, st, bar, lab, SOAK_S)
    m0_diag.line("soak_done", st.text())
    _cycles(mgr, nfc, st, bar, lab)
    _soak(mgr, nfc, st, bar, lab, None)
