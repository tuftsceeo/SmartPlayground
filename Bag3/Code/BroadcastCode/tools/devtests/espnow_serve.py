"""
espnow_serve.py -- Phase 1 bench: can an S3 Box or Dial serve games over ESP-NOW?

Run on the Dial (StampS3A) or Box (StickS3) with `mpremote resume run`, beside
a MockWandEUM wand (wand B) held close. It does what xfer_host.py does on a C6
wand, but through NativeManager below, a minimal manager written straight
against `espnow` with no C6 antenna pins (espnow_manager.py drives GPIO3/14).

Needs on the board's flash: /flash/games/<SLUG>.py (make_speed_games.py) and
EspnowModem/host/code_sender.py. Nothing else is imported from the firmware
unless PRELOAD_UI or NFC_FIELD ask for it.

Bench conditions, one run each (edit the knobs, rerun):
  1. IMPORT_ONLY = True        import espnow, ESPNow().active(True), print, exit
  2. NFC_FIELD = "off"         transfer with the reader RF field off
  3. NFC_FIELD = "on"          transfer with the field on, then reset_log.last()
  4. PRELOAD_UI = True         bring the UI up first, then start ESP-NOW; the
                               BRINGUP line shows idf_largest before and after

NativeManager is plain Python over `espnow`/`network`, imported lazily, so
tests/test_espnow_serve.py drives it with a fake `espnow` module.
"""

import sys
import time
import json

IMPORT_ONLY = False
SLUG = "speed36"
RUNS = 1
NFC_FIELD = None             # None / "off" / "on": reader RF field, set first
PRELOAD_UI = False           # build the board's UI before ESP-NOW starts
RADIO_FIRST = False          # with PRELOAD_UI: start ESP-NOW, then build the UI
UI_TICK = True               # with PRELOAD_UI: call M5.update() every loop
SLOW_CALL_MS = 20            # trace any manager send/add_peer slower than this
RUN_TIMEOUT_MS = 60000
STARTUP_MS = 2000

BROADCAST_MAC = b"\xff\xff\xff\xff\xff\xff"
SEND_RETRY_MS = 30
ESPNOW_RXBUF = 4096          # driver default 526 B holds ~2 frames (EspnowModem uses 8192)


def mac_str_to_bytes(mac_str):
    return bytes([int(p, 16) for p in mac_str.split(":")])


def mac_bytes_to_str(mac_bytes):
    return ":".join("%02X" % b for b in mac_bytes)


class NativeManager:
    """The slice of ESPNowManager that CodeSender and a getcode trigger use."""

    def __init__(self):
        self.enow = None
        self._active = False
        self._peers = {}

    @property
    def is_active(self):
        return self._active

    def init(self):
        if self._active:
            return
        import network
        import espnow
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        sta.disconnect()
        self.enow = espnow.ESPNow()
        try:
            self.enow.config(rxbuf=ESPNOW_RXBUF)
        except Exception:
            pass
        self.enow.active(True)
        try:
            self.enow.add_peer(BROADCAST_MAC)
        except Exception:
            pass
        self._active = True

    def shutdown(self):
        if not self._active:
            return
        try:
            self.enow.active(False)
        except Exception:
            pass
        self.enow = None
        self._active = False
        self._peers.clear()

    def add_peer(self, mac_str):
        if not self._active:
            self.init()
        if mac_str not in self._peers:
            mac = mac_str_to_bytes(mac_str)
            try:
                self.enow.add_peer(mac)
            except Exception:
                pass
            self._peers[mac_str] = mac

    def remove_peer(self, mac_str):
        mac = self._peers.pop(mac_str, None)
        if mac is not None:
            try:
                self.enow.del_peer(mac)
            except Exception:
                pass

    def broadcast(self, data):
        if not self._active:
            return False
        msg = data if isinstance(data, (str, bytes)) else json.dumps(data)
        # Broadcasts are never ACKed: async send, one retry on a full TX queue.
        for attempt in range(2):
            try:
                self.enow.send(BROADCAST_MAC, msg, False)
                return True
            except OSError:
                time.sleep_ms(SEND_RETRY_MS)
            except Exception:
                return False
        return False

    def broadcast_stop(self):
        return self.broadcast(["stop"])

    def send_to(self, mac_str, data):
        if not self._active:
            return False
        mac = self._peers.get(mac_str)
        if mac is None:
            mac = mac_str_to_bytes(mac_str)
        msg = data if isinstance(data, (str, bytes)) else json.dumps(data)
        return self._send("send_to", mac, msg)

    def send_raw(self, mac_bytes, raw_bytes):
        if not self._active:
            return False
        return self._send("send_raw", mac_bytes, raw_bytes)

    def _send(self, name, mac, msg):
        t0 = time.ticks_ms()
        err = None
        try:
            ok = bool(self.enow.send(mac, msg))
        except Exception as e:
            ok, err = False, e
        ms = time.ticks_diff(time.ticks_ms(), t0)
        if ms > SLOW_CALL_MS or err is not None:
            _trace("slow_" + name, ms=ms, ok=ok, err=repr(err), n=len(msg))
        return ok

    def poll(self, timeout_ms=0):
        """(msg_type, data, mac_str) or (None, None, None). Every message is
        "raw": JSON decoded to a dict/list, anything else as bytes."""
        if not self._active:
            return None, None, None
        try:
            mac, msg = self.enow.irecv(timeout_ms)
        except Exception:
            return None, None, None
        if msg is None:
            return None, None, None
        mac_str = mac_bytes_to_str(mac) if mac else None
        try:
            return "raw", json.loads(msg), mac_str
        except (ValueError, UnicodeError):
            return "raw", bytes(msg), mac_str


def install_manager_shim():
    """code_sender does `from espnow_manager import mac_str_to_bytes`. On an
    S3 there is no espnow_manager.py to import, so provide the one function."""
    if "espnow_manager" not in sys.modules:
        class _Shim:
            pass
        _Shim.mac_str_to_bytes = staticmethod(mac_str_to_bytes)
        sys.modules["espnow_manager"] = _Shim


# ─── BENCH (device only) ─────────────────────

def _idf_largest():
    try:
        import esp32
        # PSRAM is one multi-MB region; the radio needs internal DRAM.
        return max(r[2] for r in esp32.idf_heap_info(esp32.HEAP_DATA)
                   if r[0] < 1024 * 1024)
    except Exception:
        return None


def _idf_free():
    try:
        import esp32
        return sum(r[1] for r in esp32.idf_heap_info(esp32.HEAP_DATA)
                   if r[0] < 1024 * 1024)
    except Exception:
        return None


def _enow_stats(mgr):
    """(tx_pkts, tx_responses, tx_failures, rx_packets, rx_dropped)."""
    try:
        return mgr.enow.stats()
    except Exception:
        return None


TRACE_PATH = "/flash/bench_trace.txt"
TRACE_KEEP = 4000            # bytes of the previous run kept for the next one
TRACE_EVERY_MS = 500


def _supply():
    """(vbus_mV, battery_mV) from M5.Power when this build has them, else None."""
    out = []
    for name in ("getVBUSVoltage", "getBatteryVoltage"):
        try:
            import M5
            out.append(int(getattr(M5.Power, name)()))
        except Exception:
            out.append(None)
    return tuple(out)


def _trace(stage, **kw):
    """Append one line and close, so it is on flash if the board drops after.
    Never raises."""
    try:
        extra = " ".join("%s=%s" % (k, v) for k, v in kw.items())
        with open(TRACE_PATH, "a") as f:
            f.write("%d %s idf=%s supply=%s %s\n"
                    % (time.ticks_ms(), stage, _idf_largest(), _supply(), extra))
    except Exception as e:
        print("BENCH trace failed: %r" % (e,))


def _report_previous_run():
    """Print what the last run left behind, then start a fresh trace file."""
    import machine
    print("BENCH reset_cause=%s (1=PWRON 2=HARD 3=WDT 4=DEEPSLEEP 5=SOFT)"
          % machine.reset_cause())
    try:
        with open(TRACE_PATH) as f:
            tail = f.read()[-TRACE_KEEP:]
        print("BENCH previous trace tail:\n" + tail)
    except OSError:
        print("BENCH no previous trace")
    try:
        import os
        os.remove(TRACE_PATH)
    except OSError:
        pass


def _set_nfc_field(state):
    try:
        import dial_board
        nfc = dial_board.make_reader()
    except ImportError:
        import machine
        from card_writer import NfcWriter
        i2c = machine.SoftI2C(sda=machine.Pin(9), scl=machine.Pin(10), freq=100000)
        nfc = NfcWriter(i2c, 0x28)
        nfc.init()
    nfc.antenna_on() if state == "on" else nfc.antenna_off()
    return nfc


_ui_tick = None


def _build_ui():
    """Late bring-up: M5 and the board's UI exist before ESP-NOW starts.
    The Dial draws with LVGL (DialUI); the Stick only has M5.Widgets (BboxUI,
    constructed before M5.begin(), begin() after it)."""
    global _ui_tick
    import M5
    try:
        from dial_input import DialInput
        from dial_ui import DialUI
        inp = DialInput()
        M5.begin()
        inp.begin()
        ui = DialUI(inp)
        ui.begin()
        ui.paint_serve(None)
        if UI_TICK:
            _ui_tick = inp.update  # M5.update(): LVGL redraw + encoder
        return ui
    except ImportError:
        from bbox_ui import BboxUI
        ui = BboxUI()
        M5.begin()
        ui.begin()
        return ui


def _serve_once(mgr, sender, slug):
    sender.last_result = None
    mgr.broadcast({"type": "getcode", "slug": slug})
    t0 = time.ticks_ms()
    last = t0
    ui_max = 0
    while time.ticks_diff(time.ticks_ms(), t0) < RUN_TIMEOUT_MS:
        if _ui_tick is not None:
            u0 = time.ticks_ms()
            _ui_tick()
            ui_max = max(ui_max, time.ticks_diff(time.ticks_ms(), u0))
        mt, data, mac = mgr.poll()
        if mt is not None:
            sender.handle(mt, data, mac)
        now = time.ticks_ms()
        if time.ticks_diff(now, last) >= TRACE_EVERY_MS:
            last = now
            sess = list(sender.sessions.values())
            _trace("serve", t=time.ticks_diff(now, t0),
                   gets=sess[0].gets if sess else None,
                   frames=sess[0].frames if sess else None,
                   fail=sess[0].send_fail if sess else None,
                   ui_max=ui_max, enow=_enow_stats(mgr),
                   idf_free=_idf_free())
            ui_max = 0
        r = sender.last_result
        if r is not None:
            return r["ok"], "%d B %d ms frames=%d send_fail=%d %s" % (
                r["bytes"], r["ms"], r["frames"], r["send_fail"], r["why"])
        time.sleep_ms(1)
    return False, "host timeout"


def main():
    _report_previous_run()
    _trace("start", nfc_field=NFC_FIELD, preload_ui=PRELOAD_UI,
           ui_tick=UI_TICK, idf_free=_idf_free())
    try:
        _main()
        _trace("done")
    except BaseException as e:
        _trace("EXCEPTION", err=repr(e))
        try:
            sys.print_exception(e)
        except Exception:
            pass
        raise


def _main():
    import gc
    print("BENCH start slug=%s nfc_field=%s preload_ui=%s"
          % (SLUG, NFC_FIELD, PRELOAD_UI))
    keep = []
    if NFC_FIELD:
        keep.append(_set_nfc_field(NFC_FIELD))
        print("BENCH nfc field", NFC_FIELD)
        _trace("nfc_field_set", state=NFC_FIELD)
    before = _idf_largest()
    mgr = NativeManager()
    if PRELOAD_UI and not RADIO_FIRST:
        keep.append(_build_ui())
        gc.collect()
    mid = _idf_largest()
    _trace("ui_done")
    try:
        mgr.init()
    except Exception as e:
        print("BENCH espnow init FAILED: %r  idf_largest=%s" % (e, mid))
        raise
    if PRELOAD_UI and RADIO_FIRST:
        keep.append(_build_ui())
        gc.collect()
    print("BENCH BRINGUP idf_largest before_ui=%s before_radio=%s after_radio=%s"
          " idf_free=%s" % (before, mid, _idf_largest(), _idf_free()))
    if IMPORT_ONLY:
        print("BENCH import_only ok")
        return
    _trace("radio_up", idf_free=_idf_free())
    install_manager_shim()
    from code_sender import CodeSender
    sender = CodeSender(mgr)
    time.sleep_ms(STARTUP_MS)
    for run in range(1, RUNS + 1):
        mgr.broadcast_stop()
        time.sleep_ms(1500)
        ok, detail = _serve_once(mgr, sender, SLUG)
        print("BENCH result slug=%s run=%d ok=%s %s" % (SLUG, run, ok, detail))
        _trace("result", ok=ok, detail=detail)
    try:
        import reset_log
        print("BENCH reset_log", reset_log.last(3))
    except Exception as e:
        print("BENCH reset_log unavailable: %r" % (e,))
    print("BENCH done gc_free=%d" % gc.mem_free())


if __name__ == "__main__":
    main()
