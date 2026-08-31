"""
bbox_server.py — JSON serial dispatcher + NFC card flow + TCP server poll.

See serial_protocol_notes.md for connection/hello/recovery rules.
"""

import gc
import time
import machine

from json_link import JsonLink
from code_server import CodeServer, FS_ROOT, DEFAULT_SRC, SSID
from card_writer import NfcWriter, existing_opcode_name, write_opcode
from bbox_ui import BboxUI

VERSION = "0.1.0"
HEARTBEAT_MS = 5000
GRACE_S = 5

# Grove HY2.0-4P on StickS3 — confirmed via mpremote i2c.scan(): PN532
# answers at 0x24 on sda=9/scl=10 (fw 1.6), not the 4/5 previously assumed
# here. sda=4/scl=5 scan empty and _init_nfc() below raises ETIMEDOUT,
# leaving self.nfc None so _poll_nfc() silently no-ops forever.
I2C_SDA = 9
I2C_SCL = 10
NFC_ADDR = 0x24
I2C_FREQ = 100_000

PAYLOAD_PATH = DEFAULT_SRC
CARD_LABEL = "getcode"
HOLD_MS = 800


def _boot_grace(ui):
    ui.paint_booting()
    print("# booting -- Ctrl-C within %ds to stay at the REPL" % GRACE_S)
    for remaining in range(GRACE_S, 0, -1):
        print("# %d..." % remaining)
        time.sleep_ms(1000)


class BboxServer:
    def __init__(self, debug=False):
        self.ui = BboxUI()
        self.link = JsonLink(self.dispatch, debug=debug)
        self.code = CodeServer()
        self.nfc = None
        self.running = True
        self.linked = True
        self._armed_write = False
        self._card_index = 1
        self._card_total = 1
        self._pending_tag = None
        self._pending_existing = None
        self._pending_label = CARD_LABEL
        self._written = 0
        self._btn_ok = False
        self._btn = None
        self._hold_start = 0

        self.handlers = {
            "hello": self.do_hello,
            "info": self.do_info,
            "arm": self.do_arm,
            "disarm": self.do_disarm,
            "repl": self.do_repl,
            "reboot": self.do_reboot,
        }

    def _init_nfc(self):
        i2c = machine.SoftI2C(
            sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=I2C_FREQ)
        self.nfc = NfcWriter(i2c, NFC_ADDR)
        self.nfc.init()

    def _init_button(self):
        try:
            import M5
            M5.BtnA.isPressed()
            self._btn = True
        except Exception:
            self._btn = False

    def _poll_button(self):
        if not self._btn:
            return None
        try:
            import M5
            M5.update()
            if M5.BtnA.wasPressed():
                return "short"
            if M5.BtnA.isPressed():
                if self._hold_start == 0:
                    self._hold_start = time.ticks_ms()
                elif time.ticks_diff(time.ticks_ms(), self._hold_start) >= HOLD_MS:
                    self._hold_start = 0
                    return "long"
            else:
                self._hold_start = 0
        except Exception:
            self._btn = False
        return None

    def dispatch(self, cmd):
        name = cmd.get("cmd")
        rid = cmd.get("id")
        handler = self.handlers.get(name)
        if handler is None:
            self.link.send({"type": "error", "id": rid, "code": "unknown_cmd", "cmd": name})
            return
        handler(cmd, rid)

    def _hello_payload(self, rid=None):
        return {
            "type": "hello", "id": rid,
            "device": "broadcast_box", "version": VERSION,
            "w": 240, "h": 135, "nfc": True,
        }

    def _send_hello(self, rid=None):
        self.link.send(self._hello_payload(rid))

    def do_hello(self, cmd, rid):
        self._send_hello(rid)

    def do_info(self, cmd, rid):
        self.link.send({
            "type": "info", "id": rid,
            "version": VERSION, "mem": gc.mem_free(),
            "armed": self.code.armed, "linked": self.linked,
            "payload_ready": self._payload_ready(),
            "written": self._written, "up": time.ticks_ms(),
        })

    def _try_arm(self):
        """Arm (AP + card-write-ready) if payload.py exists. Idempotent.

        This is the box's own boot-time decision, not something the laptop
        has to request -- a payload on flash is a standing fact, not a
        session state, so the box should act on it with or without a live
        serial link (unplugged-in-the-field is the normal case, not an
        edge case). Returns True if armed (or already armed).
        """
        if self._armed_write:
            return True
        if not self._payload_ready():
            return False
        if not self.code.arm():
            return False
        self._armed_write = True
        self._written = 0
        self.ui.paint_armed(CARD_LABEL, self._card_index, self._card_total)
        self.link.send({"type": "armed", "id": None, "ssid": SSID})
        return True

    def do_arm(self, cmd, rid):
        # Manual/legacy entry point -- normal flow arms itself in run(),
        # but this stays around for REPL testing and forcing a re-arm.
        if not self._payload_ready():
            self.link.send({"type": "error", "id": rid, "code": "no_payload",
                             "msg": "payload.py not on device"})
            return
        if self._try_arm():
            self.link.send({"type": "armed", "id": rid, "ssid": SSID})
        else:
            self.link.send({"type": "error", "id": rid, "code": "arm_failed"})

    def do_disarm(self, cmd, rid):
        self.code.disarm()
        self._armed_write = False
        self._pending_tag = None
        self.ui.paint_idle(self.linked)
        self.link.send({"type": "ok", "id": rid, "cmd": "disarm"})

    def _repaint_ready(self):
        """Screen after a wand-pull transfer ok/fail -- stay on the card
        screen if still armed for writing, otherwise idle."""
        if self._armed_write:
            self.ui.paint_armed(CARD_LABEL, self._card_index, self._card_total)
        else:
            self.ui.paint_idle(self.linked)

    def do_repl(self, cmd, rid):
        self.link.send({"type": "bye", "id": rid, "reboot": "soft"})
        self.running = False

    def do_reboot(self, cmd, rid):
        hard = bool(cmd.get("hard"))
        self.link.send({"type": "bye", "id": rid, "reboot": "hard" if hard else "soft"})
        self.running = False
        if hard:
            machine.reset()

    def _payload_ready(self):
        try:
            import os
            return os.stat(PAYLOAD_PATH)[6] > 0
        except OSError:
            return False

    def _poll_nfc(self):
        if not self._armed_write or self.nfc is None:
            return
        tag = self.nfc.detect_tag(timeout=80)
        if tag is None:
            return
        self.ui.beep_scan()
        existing = existing_opcode_name(self.nfc, tag)
        self.link.send({
            "type": "card_present", "uid": tag['uid_hex'],
            "existing": existing,
        })
        if existing and existing != CARD_LABEL:
            self._pending_tag = tag
            self._pending_existing = existing
            self.ui.paint_overwrite(existing, CARD_LABEL)
            return
        self._write_card(tag)

    def _write_card(self, tag):
        self.ui.paint_writing(CARD_LABEL)
        ok = write_opcode(self.nfc, tag, CARD_LABEL)
        if ok:
            self._written += 1
            self.ui.paint_done(CARD_LABEL, self._written, self._card_total)
            self.ui.beep_success()
            self.link.send({
                "type": "card_written", "label": CARD_LABEL, "uid": tag['uid_hex'],
            })
            time.sleep_ms(2000)
            if self._written >= self._card_total:
                self.ui.paint_complete()
                time.sleep_ms(1500)
            else:
                self.ui.paint_armed(CARD_LABEL, self._card_index, self._card_total)
        else:
            self.ui.paint_error("try again")
            self.ui.beep_fail()
            time.sleep_ms(1500)
            self.ui.paint_armed(CARD_LABEL, self._card_index, self._card_total)

    def _handle_button(self, action):
        if action is None:
            return
        if self._pending_tag is not None and self._pending_existing:
            if action == "short":
                self._pending_tag = None
                self._pending_existing = None
                self.ui.paint_armed(CARD_LABEL, self._card_index, self._card_total)
            elif action == "long":
                tag = self._pending_tag
                self._pending_tag = None
                self._pending_existing = None
                self._write_card(tag)

    def run(self):
        import M5
        M5.begin()
        _boot_grace(self.ui)
        try:
            self._init_nfc()
        except Exception as e:
            print("# NFC init failed: %s" % str(e))
        self._init_button()
        self._send_hello()
        if not self._try_arm():
            self.ui.paint_idle(self.linked)
        last_hb = time.ticks_ms()
        while self.running:
            self.link.pump(idle_ms=20, drain_ms=40)
            xfer = self.code.poll()
            if xfer == 'serving':
                self.ui.paint_receiving()
            elif xfer == 'ok':
                self._repaint_ready()
            elif xfer == 'fail':
                self.ui.paint_error("transfer failed")
                time.sleep_ms(1000)
                self._repaint_ready()
            self._poll_nfc()
            self._handle_button(self._poll_button())
            now = time.ticks_ms()
            if time.ticks_diff(now, last_hb) > HEARTBEAT_MS:
                self.link.send({"type": "heartbeat", "up": now, "mem": gc.mem_free()})
                last_hb = now
            time.sleep_ms(1)
