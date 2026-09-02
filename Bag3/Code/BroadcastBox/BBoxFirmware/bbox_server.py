"""
bbox_server.py — JSON serial dispatcher + NFC card flow + TCP server poll.

Phase A mode machine. The invariant this file exists to hold:

    at most one of {WiFi AP, NFC RF field} is energized at any instant.

Before Phase A, a game on flash meant both at once, indefinitely -- the AP
came up at boot and the reader was polled continuously, which is the load
the box browns out under on a current-limited USB port (see known_issue.md).
Now the two live in separate modes and the teacher moves between them:

    WRITE  AP down.  Reader polled only while B1 is held.
    SERVE  Reader antenna off, no I2C at all.  AP up, serving wand pulls.
    IDLE   Neither.  No game on flash, so there is nothing to do.

There is deliberately no RECEIVING mode: the app pushes code over the raw
REPL, which interrupts this program and soft-resets the board
(ChatBroadcast's boxFirmwareInstaller.pushPayload), so an upload is not a
state this firmware is ever in. It comes back from that reset, finds a game
on flash, and starts in WRITE.

See serial_protocol_notes.md for connection/hello/recovery rules, and
design/phase-a-box-power-modes.plan.md for the state diagram.
"""

import gc
import time
import machine

import reset_log
from buttons import Buttons
from json_link import JsonLink
from code_server import CodeServer, FS_ROOT, DEFAULT_SRC, SSID
from card_writer import NfcWriter, existing_text, write_text
from bbox_ui import BboxUI

VERSION = "0.1.0"
HEARTBEAT_MS = 5000
GRACE_S = 5

# Grove HY2.0-4P on StickS3, sda=9/scl=10 (same pins as the PN532 it
# replaces). Reader chip is the WS1850S (addr 0x28, MFRC522-register-
# compatible) instead of the PN532 (addr 0x24) -- the PN532's ~150 mA
# read/write burst coincided with the SoftAP's own power spikes; the
# WS1850S bursts at ~30 mA. See card_writer.py / ws1850s.py.
I2C_SDA = 9
I2C_SCL = 10
NFC_ADDR = 0x28
I2C_FREQ = 100_000

PAYLOAD_PATH = DEFAULT_SRC

# The tags a teacher writes for one game. Phase A text only: the wand
# matches tag text by exact set membership, so these must stay strings it
# already knows -- "getcode" is in its BROADCAST set and "jumpin" in its
# GAME_TAGS. The getcode:<name> format from the design doc needs the wand to
# prefix-parse and lands with the wand change in Phase B.
TAG_LIST = ("getcode", "jumpin")
DONE_ENTRY = "DONE"

# BtnA hold that leaves SERVE and returns to WRITE. This is the only hold
# gesture left in the firmware, kept deliberately: leaving SERVE is rare and
# should not happen from a stray bump. Everything in WRITE is a plain press.
SERVE_EXIT_MS = 1000

MODE_IDLE = "IDLE"
MODE_WRITE = "WRITE"
MODE_SERVE = "SERVE"

# WRITE-mode sub-states. BtnA acts, BtnB scrolls or backs out; no holds.
#   MENU      list of tags     A = scan (or serve on DONE)  B = next
#   SCAN      RF field on      A = -                        B = menu
#   OVERWRITE prompt up        A = write it                 B = menu
#   SPLASH    result shown     A = menu                     B = menu
W_MENU = "menu"
W_SCAN = "scan"
W_OVERWRITE = "overwrite"
W_SPLASH = "splash"


def _log(msg):
    print("# [box] %s" % msg)


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

        self._mode = MODE_IDLE
        self._nfc_ok = False  # real _init_nfc() result -- reported in hello
        self._nfc_field_on = False
        self._nfc_fail_count = 0  # consecutive detect_tag errors -- see _scan_step
        self._write_state = W_MENU  # WRITE sub-state; see W_* above

        self._entries = list(TAG_LIST) + [DONE_ENTRY]
        self._cursor = 0
        self._written = {}  # entry name -> count written this session

        self._buttons = Buttons()
        self._b1_was_down = False  # for deriving a press edge

        self._pending_tag = None
        self._pending_existing = None

        self.handlers = {
            "hello": self.do_hello,
            "info": self.do_info,
            "arm": self.do_arm,
            "disarm": self.do_disarm,
            "repl": self.do_repl,
            "reboot": self.do_reboot,
        }

    # ─────────────────────────────────────────────
    # HARDWARE INIT
    # ─────────────────────────────────────────────

    def _init_nfc(self):
        i2c = machine.SoftI2C(
            sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=I2C_FREQ)
        self.nfc = NfcWriter(i2c, NFC_ADDR)
        self.nfc.init()
        # WS1850S.__init__ leaves the antenna on; idle until B1 says otherwise.
        self.nfc.antenna_off()
        self._nfc_field_on = False

    # ─────────────────────────────────────────────
    # BUTTONS
    # ─────────────────────────────────────────────
    # B1 = BtnA (front button), B2 = BtnB (side button) -- see buttons.py.
    # No fallback path: if the buttons are broken, that must be visible as
    # a crash or a print, not as a silently-degraded input mode.

    def _b1_held_ms(self):
        return self._buttons.b1_held_ms()

    def _b1_press_edge(self):
        """Rising edge on B1, derived here so buttons.py stays as reviewed."""
        down = self._buttons.b1_down()
        edge = down and not self._b1_was_down
        self._b1_was_down = down
        return edge

    # ─────────────────────────────────────────────
    # MODES
    # ─────────────────────────────────────────────

    def _set_mode(self, new_mode, announce=True):
        """Single point of truth for the radio/reader invariant.

        Every transition leaves the mode it is leaving fully de-energized
        before energizing anything for the mode it is entering. Keeping this
        in one method is also what makes the reboot-into-mode variant a
        contained change if T1's AP-cycle probe shows in-place AP down/up is
        not reliable on this hardware: only this method would swap to writing
        a mode flag and calling machine.reset().
        """
        if new_mode == self._mode:
            return
        old = self._mode
        if announce:
            self.ui.paint_mode_change(new_mode)

        # --- leave ---
        if old == MODE_SERVE:
            self.code.disarm()  # ap.active(False) + AP_SETTLE_MS
        if old == MODE_WRITE:
            self._nfc_field(False)
            self._clear_pending()

        # --- enter ---
        if new_mode == MODE_SERVE:
            if not self.code.arm():
                # No game on flash, or the socket would not bind. Say so and
                # stay where we were rather than sitting on a dead AP.
                print("# SERVE refused: CodeServer.arm() failed")
                self.ui.paint_error("no game to serve")
                time.sleep_ms(1500)
                self._mode = old
                self._repaint()
                return
            self.link.send({"type": "armed", "id": None, "ssid": SSID})

        self._mode = new_mode
        # A gesture that caused the switch must not carry into the new mode:
        # the B1 hold that left SERVE would otherwise immediately read as a
        # hold in WRITE, and a B2 press made while B2 was unused would fire
        # as a stale scroll.
        self._buttons.clear()
        self._b1_was_down = self._buttons.b1_down()
        self._write_state = W_MENU
        self._nfc_fail_count = 0
        print("# mode %s -> %s" % (old, new_mode))
        self._repaint()

    def _repaint(self):
        if self._mode == MODE_WRITE:
            self.ui.paint_tag_list(self._entries, self._cursor, self._written)
        elif self._mode == MODE_SERVE:
            self.ui.paint_serve(SSID, self.code.pickups)
        else:
            self.ui.paint_idle(self.linked)

    def _current_entry(self):
        return self._entries[self._cursor]

    # ─────────────────────────────────────────────
    # JSON API
    # ─────────────────────────────────────────────

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
            # Report what _init_nfc() actually did. This used to be a hard
            # True even when init raised ETIMEDOUT, so the app was told a
            # reader was present when it was not (known_issue.md).
            "w": 240, "h": 135, "nfc": self._nfc_ok,
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
            "written": sum(self._written.values()), "up": time.ticks_ms(),
        })

    def do_arm(self, cmd, rid):
        """Legacy/REPL entry point -- now means "go to SERVE".

        Arming used to mean AP up *and* card writing at once; that pairing is
        exactly what Phase A separates. The box no longer does this at boot:
        it starts in WRITE and a teacher chooses DONE + B1 to serve.
        """
        if not self._payload_ready():
            self.link.send({"type": "error", "id": rid, "code": "no_payload",
                             "msg": "payload.py not on device"})
            return
        self._set_mode(MODE_SERVE)
        if self._mode == MODE_SERVE:
            self.link.send({"type": "ok", "id": rid, "cmd": "arm", "ssid": SSID})
        else:
            self.link.send({"type": "error", "id": rid, "code": "arm_failed"})

    def do_disarm(self, cmd, rid):
        self._set_mode(MODE_WRITE if self._payload_ready() else MODE_IDLE)
        self.link.send({"type": "ok", "id": rid, "cmd": "disarm"})

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

    # ─────────────────────────────────────────────
    # WRITE MODE
    # ─────────────────────────────────────────────

    def _nfc_field(self, on):
        """Energize/de-energize the reader, tracking state to avoid redundant
        I2C writes on every loop iteration."""
        if self.nfc is None or on == self._nfc_field_on:
            return
        self._nfc_field_on = on
        try:
            self.nfc.antenna_on() if on else self.nfc.antenna_off()
            _log("field -> %s (chip reports ant=%s crypto=%s)"
                 % ("ON" if on else "off", self.nfc.antenna_is_on(),
                    self.nfc.crypto_on()))
        except Exception as e:
            print("# NFC antenna %s FAILED: %s" % ("on" if on else "off", str(e)))

    def _clear_pending(self):
        self._pending_tag = None
        self._pending_existing = None

    # ─────────────────────────────────────────────
    # WRITE MODE — sub-state machine
    # ─────────────────────────────────────────────

    def _to_menu(self):
        _log("state %s -> menu" % self._write_state)
        self._write_state = W_MENU
        self._nfc_field(False)
        self._clear_pending()
        self._repaint()

    def _to_scan(self):
        _log("state %s -> scan (target=%s)"
             % (self._write_state, self._current_entry()))
        self._write_state = W_SCAN
        self._clear_pending()
        # Never begin a scan in encrypted mode: a MIFARE auth from an
        # earlier scan latches MFCrypto1On, and while it is set the reader
        # cannot answer a plain REQA, so nothing is ever detected. Toggling
        # the antenna does not clear it -- only this does (or a reboot,
        # which is why the first scan after boot used to be the only one
        # that worked).
        if self.nfc is not None:
            self.nfc.stop_crypto1()
        self._nfc_field(True)
        self.ui.paint_scanning(self._current_entry())

    def _to_splash(self):
        """Result is on screen; it stays there until a button dismisses it.

        The RF field goes down here rather than at the next menu paint --
        nothing is being scanned while a result is being read, so there is
        no reason to keep the antenna energized for it.
        """
        _log("state %s -> splash" % self._write_state)
        self._write_state = W_SPLASH
        self._nfc_field(False)
        self._clear_pending()

    def _poll_write(self):
        """WRITE mode. BtnA acts, BtnB scrolls/backs out. No holds."""
        b1 = self._b1_press_edge()
        b2 = self._buttons.b2_pressed()
        if b1 or b2:
            _log("BTN %s in state=%s cursor=%d(%s)"
                 % ("A" if b1 else "B", self._write_state,
                    self._cursor, self._current_entry()))

        if self._write_state == W_MENU:
            if b2:
                self.ui.beep_click()
                self._cursor = (self._cursor + 1) % len(self._entries)
                self._repaint()
            elif b1:
                self.ui.beep_click()
                if self._current_entry() == DONE_ENTRY:
                    self._set_mode(MODE_SERVE)
                else:
                    self._to_scan()
            return

        if self._write_state == W_SCAN:
            if b2:
                self.ui.beep_click()
                self._to_menu()
                return
            self._scan_step()
            return

        if self._write_state == W_OVERWRITE:
            if b1:
                self.ui.beep_click()
                tag = self._pending_tag
                entry = self._current_entry()
                self._clear_pending()
                self._write_card(tag, entry)
            elif b2:
                self.ui.beep_click()
                self._to_menu()
            return

        if self._write_state == W_SPLASH:
            if b1 or b2:
                self.ui.beep_click()
                self._to_menu()
            return

    # Consecutive detect_tag() OSErrors before we assume the reader's
    # internal state machine is wedged (not just one bad I2C beat) and
    # try a fresh init() to recover it.
    NFC_REINIT_AFTER = 15

    def _scan_step(self):
        """One polling pass while in W_SCAN. The field is already on.

        Detection ends the scan either way -- into OVERWRITE, or straight
        through a write into SPLASH -- so there is no same-card debounce to
        keep here: nothing polls the reader again until the teacher starts
        a new scan from the menu.
        """
        if self.nfc is None:
            return
        entry = self._current_entry()
        try:
            tag = self.nfc.detect_tag(timeout=80)
        except OSError as e:
            # The reader over I2C occasionally times out (ETIMEDOUT) on a
            # bad read -- transient, not fatal. Without this catch it took
            # down the whole run() loop (uncaught OSError -> fatal event,
            # server dead until reset).
            self._nfc_fail_count += 1
            # Only print every 5th repeat once we know it's a streak --
            # otherwise a wedged/disconnected reader floods the log with an
            # identical line on every poll forever.
            if self._nfc_fail_count <= 3 or self._nfc_fail_count % 5 == 0:
                print("# NFC detect_tag err (%d in a row): %s" % (self._nfc_fail_count, str(e)))
            if self._nfc_fail_count >= self.NFC_REINIT_AFTER:
                print("# NFC: %d consecutive errors -- attempting re-init" % self._nfc_fail_count)
                self._nfc_fail_count = 0
                try:
                    self._init_nfc()
                    print("# NFC re-init OK")
                    # _init_nfc() leaves the antenna off; we are still in
                    # W_SCAN, so put the field back up or the scan would
                    # sit there polling a de-energized reader forever.
                    self._nfc_field(True)
                except Exception as e2:
                    print("# NFC re-init failed: %s" % str(e2))
                time.sleep_ms(200)  # let the bus settle either way
            return
        self._nfc_fail_count = 0
        if tag is None:
            return  # nothing on the reader yet -- keep scanning
        self.ui.beep_scan()
        _log("DETECTED uid=%s sak=0x%02X type=%s"
             % (tag['uid_hex'], tag['sak'], tag['tag_type']))
        existing = existing_text(self.nfc, tag)
        _log("read result: existing=%s target=%s" % (repr(existing), repr(entry)))
        self.link.send({
            "type": "card_present", "uid": tag['uid_hex'], "existing": existing,
        })
        if existing == entry:
            # Already carries the text we would write -- report, don't rewrite.
            _log("card already carries %s -- no write" % repr(entry))
            self.ui.paint_already(entry)
            self.ui.beep_success()
            self._to_splash()
            return
        if existing:
            # Keep the field UP: the write that BtnA may be about to confirm
            # needs the card still energized and selectable.
            self._pending_tag = tag
            self._pending_existing = existing
            _log("card has %s, want %s -> OVERWRITE prompt"
                 % (repr(existing), repr(entry)))
            self.ui.paint_overwrite(existing, entry)
            self._write_state = W_OVERWRITE
            return
        self._write_card(tag, entry)

    def _write_card(self, tag, entry):
        """Write, then leave the result on screen until a button dismisses it."""
        _log("WRITE attempt: target=%s uid=%s" % (repr(entry), tag['uid_hex']))
        self.ui.paint_writing(entry)
        ok = write_text(self.nfc, tag, entry)
        _log("WRITE result: %s" % ("OK" if ok else "FAILED"))
        if ok:
            self._written[entry] = self._written.get(entry, 0) + 1
            self.ui.paint_written(entry, self._written[entry])
            self.ui.beep_success()
            self.link.send({
                "type": "card_written", "label": entry, "uid": tag['uid_hex'],
            })
        else:
            self.ui.paint_write_failed(entry)
            self.ui.beep_fail()
        self._to_splash()

    # ─────────────────────────────────────────────
    # SERVE MODE
    # ─────────────────────────────────────────────

    def _serve_abort_requested(self):
        """should_abort hook for CodeServer.poll().

        Samples the buttons itself: poll() blocks for the whole transfer, so
        the main loop's update() is not running and a cached reading would
        never change. Without this the hold-to-exit gesture is unreachable
        for the duration of a transfer.
        """
        self._buttons.update()
        return self._buttons.b1_held_ms() >= SERVE_EXIT_MS

    def _on_serve_event(self, event):
        if event == 'serving':
            self.ui.paint_receiving()

    def _poll_serve(self):
        xfer = self.code.poll(on_event=self._on_serve_event,
                              should_abort=self._serve_abort_requested)
        if xfer == 'ok':
            self._repaint()
        elif xfer == 'fail':
            self.ui.paint_error("transfer failed")
            time.sleep_ms(1000)
            self._repaint()
        elif xfer == 'abort':
            # The teacher held B1 through a transfer; that is the exit
            # gesture. The wand sees a short read, drops its .part file and
            # retries within its own attempt budget.
            print("# serve aborted by B1 hold")
            self._set_mode(MODE_WRITE if self._payload_ready() else MODE_IDLE)
            return
        if self._b1_held_ms() >= SERVE_EXIT_MS:
            self._set_mode(MODE_WRITE if self._payload_ready() else MODE_IDLE)

    # ─────────────────────────────────────────────
    # RUN
    # ─────────────────────────────────────────────

    def run(self):
        # First, before the grace window or anything that can raise: this
        # boot's reset_cause(). The board's USB is native CDC, so a reset
        # drops the port and the cause has to be read on the *next* boot
        # (known_issue.md discriminating test 1).
        reset_log.record(self._mode)

        import M5
        M5.begin()
        self.ui.begin()
        _boot_grace(self.ui)
        try:
            self._init_nfc()
            self._nfc_ok = True
        except Exception as e:
            print("# NFC init failed: %s" % str(e))
            self._nfc_ok = False
        self._send_hello()

        # Boot into WRITE when there is a game on flash. This replaces the
        # old auto-arm, which raised the AP here: a game on flash means the
        # box is ready to write tags, not that it is broadcasting. Off-USB
        # operation is unaffected -- it just starts in WRITE, and a teacher
        # selects DONE + B1 when the wands should pick code up.
        self._mode = MODE_IDLE
        self._set_mode(MODE_WRITE if self._payload_ready() else MODE_IDLE,
                       announce=False)
        self._repaint()

        last_hb = time.ticks_ms()
        while self.running:
            self.link.pump(idle_ms=20, drain_ms=40)
            self._buttons.update()
            if self._mode == MODE_SERVE:
                self._poll_serve()
            elif self._mode == MODE_WRITE:
                # IDLE deliberately polls nothing: no game on flash means
                # there is neither a tag to write nor code to serve.
                self._poll_write()
            now = time.ticks_ms()
            if time.ticks_diff(now, last_hb) > HEARTBEAT_MS:
                self.link.send({"type": "heartbeat", "up": now, "mem": gc.mem_free()})
                last_hb = now
            time.sleep_ms(1)
