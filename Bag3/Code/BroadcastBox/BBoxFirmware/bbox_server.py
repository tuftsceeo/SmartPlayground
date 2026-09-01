"""
bbox_server.py — JSON serial dispatcher + NFC card flow + TCP server poll.

See serial_protocol_notes.md for connection/hello/recovery rules.
"""

import gc
import time
import machine

from json_link import JsonLink
from code_server import CodeServer, FS_ROOT, DEFAULT_SRC, SSID
from card_writer import NfcWriter, existing_text, write_text
from bbox_ui import BboxUI

VERSION = "0.1.0"
HEARTBEAT_MS = 5000
GRACE_S = 5

# Grove HY2.0-4P on StickS3, sda=9/scl=10 (same pins as the PN532 it
# replaces). Reader chip is now the WS1850S (addr 0x28, MFRC522-register-
# compatible) instead of the PN532 (addr 0x24) -- the PN532's ~150 mA
# read/write burst coincided with the SoftAP's own power spikes; the
# WS1850S bursts at ~30 mA. See card_writer.py / ws1850s.py.
I2C_SDA = 9
I2C_SCL = 10
NFC_ADDR = 0x28
I2C_FREQ = 100_000

# StickS3's small side button ("Key1"). Momentary, active-low against an
# internal pull-up. Holding it down is what gates NFC polling (see
# _poll_nfc) -- released, the RF field is off and no I2C traffic happens
# at all, on top of the WS1850S swap above. If a given unit's Key1 turns
# out to be wired to G12 instead ("Key2"), change this one constant.
NFC_TRIGGER_PIN = 11

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
        self._last_seen_uid = None  # debounce: one write per physical tap
        self._nfc_fail_count = 0  # consecutive detect_tag errors -- see _poll_nfc
        self._nfc_trigger = None  # NFC_TRIGGER_PIN Pin object, or None if unavailable
        self._nfc_field_on = False  # tracks antenna state -- see _poll_nfc

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
        # WS1850S.__init__ leaves the antenna on; idle until the trigger
        # button says otherwise (see _poll_nfc).
        self.nfc.antenna_off()
        self._nfc_field_on = False

    def _init_nfc_trigger(self):
        try:
            self._nfc_trigger = machine.Pin(
                NFC_TRIGGER_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
        except Exception as e:
            print("# NFC trigger init failed (pin %d): %s" % (NFC_TRIGGER_PIN, str(e)))
            self._nfc_trigger = None

    def _nfc_trigger_pressed(self):
        if self._nfc_trigger is None:
            # No trigger wired -- fail open rather than disable NFC outright.
            return True
        return self._nfc_trigger.value() == 0  # active-low against pull-up

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

    # Consecutive detect_tag() OSErrors before we assume the reader's
    # internal state machine is wedged (not just one bad I2C beat) and
    # try a fresh init() to recover it.
    NFC_REINIT_AFTER = 15

    def _poll_nfc(self):
        if not self._armed_write or self.nfc is None:
            return
        # Gate the RF field itself on NFC_TRIGGER_PIN, not just the polling
        # call below -- the WS1850S otherwise holds the field on continuously
        # once armed, which is most of its idle draw even with no card read
        # in flight. Toggle only on state change to avoid redundant I2C
        # writes every ~1 ms loop iteration while the button sits held.
        pressed = self._nfc_trigger_pressed()
        if pressed != self._nfc_field_on:
            self._nfc_field_on = pressed
            try:
                self.nfc.antenna_on() if pressed else self.nfc.antenna_off()
            except Exception as e:
                print("# NFC antenna %s failed: %s" % ("on" if pressed else "off", str(e)))
            if not pressed:
                self._last_seen_uid = None  # released -- next press is a fresh tap
        if not pressed:
            return
        try:
            tag = self.nfc.detect_tag(timeout=80)
        except OSError as e:
            # The reader over I2C occasionally times out (ETIMEDOUT) on a
            # bad read -- transient, not fatal. Without this catch it took down
            # the whole run() loop (uncaught OSError -> fatal event, server
            # dead until reset).
            self._nfc_fail_count += 1
            # Only print every 5th repeat once we know it's a streak --
            # otherwise a wedged/disconnected reader floods the log with
            # an identical line on every ~80ms poll forever.
            if self._nfc_fail_count <= 3 or self._nfc_fail_count % 5 == 0:
                print("# NFC detect_tag err (%d in a row): %s" % (self._nfc_fail_count, str(e)))
            self._last_seen_uid = None
            if self._nfc_fail_count >= self.NFC_REINIT_AFTER:
                print("# NFC: %d consecutive errors -- attempting re-init" % self._nfc_fail_count)
                self._nfc_fail_count = 0
                try:
                    self._init_nfc()
                    print("# NFC re-init OK")
                except Exception as e2:
                    print("# NFC re-init failed: %s" % str(e2))
                time.sleep_ms(200)  # let the bus settle either way
            return
        self._nfc_fail_count = 0
        if tag is None:
            # Card lifted -- next tap (same or different card) is a new event.
            self._last_seen_uid = None
            return
        if tag['uid_hex'] == self._last_seen_uid:
            # Same card still sitting on the reader from the tap we already
            # handled -- without this, every ~80ms poll would rewrite it and
            # increment self._written again for as long as it stays down.
            return
        self._last_seen_uid = tag['uid_hex']
        self.ui.beep_scan()
        existing = existing_text(self.nfc, tag)
        self.link.send({
            "type": "card_present", "uid": tag['uid_hex'],
            "existing": existing,
        })
        if existing == CARD_LABEL:
            return  # already has this card written -- nothing to do
        if existing:
            self._pending_tag = tag
            self._pending_existing = existing
            self.ui.paint_overwrite(existing, CARD_LABEL)
            return
        self._write_card(tag)

    def _write_card(self, tag):
        self.ui.paint_writing(CARD_LABEL)
        ok = write_text(self.nfc, tag, CARD_LABEL)
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
        self.ui.begin()
        _boot_grace(self.ui)
        try:
            self._init_nfc()
        except Exception as e:
            print("# NFC init failed: %s" % str(e))
        self._init_nfc_trigger()
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
