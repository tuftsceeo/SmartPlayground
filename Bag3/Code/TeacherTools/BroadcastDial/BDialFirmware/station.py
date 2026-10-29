"""station.py -- Broadcast Dial screens: the NFC Station's mode machine.

Modes (intents from dial_input; EXIT = 1 s hold):

  HOME   ring: Read / Tags / Text          ACT opens
  READ   field on, reports each new card   ACT on a read card copies it
                                           EXIT -> HOME
         back to Hold Card READ_CLEAR_MS after the card is lifted
  GAMES  dot ring: loaded games, Utility   ACT -> TAGS, EXIT -> HOME
  TAGS   dot ring: All, Code, Play, the game's tags (Utility: stop,
         battery)                          ACT -> SCAN (All -> write-all),
                                           EXIT -> GAMES
  ALLNEXT write-all: next tag shown; scans it once the written card is
          removed (ABSENT_POLLS misses), EXIT -> TAGS
  TEXT   ring keyboard (text_entry)        done -> SCAN, cancel -> HOME
  SCAN   field on, writes the target       EXIT -> where it came from

SCAN writes whatever card is presented. A card that already carries the
target is reported, not rewritten. After a write the result is held on
screen briefly; success returns to the mode SCAN came from, failure
re-arms the same scan.

`host` (bdial_server.BdialServer) supplies the reader and the Dial side:
  host.nfc                  reader, or None
  host.init_nfc()           re-create the reader
  host.tag_groups()         [(name, [(label, tag), ...], all_ok), ...]
  host.has_games()          True when a game is loaded
  host.words()              keyboard word bank
  host.card_text(tag)       bytes-to-write for a tag (getcode pins the host)
  host.radio_off()          called before the field comes on
  host.on_card(tag, text)   a card was read
  host.on_written(tag, uid) a card was written (or already carried it)

serving() is True on the screens where the radio may serve.
"""

import time

import text_entry
from dial_input import NEXT, PREV, ACT, EXIT, TURN_SETTLE_MS

# NDEF text overhead: TLV (2) + record header (3) + "T" (1) + lang "en"
# with its length byte (3) + terminator (1) = 10 bytes. existing_text()
# reads NTAG pages 4-19 only (64 bytes), so longer text reads back
# truncated and fails verify.
NDEF_OVERHEAD = 10
READ_WINDOW = 64
TEXT_MAX = READ_WINDOW - NDEF_OVERHEAD

RESULT_HOLD_OK_MS = 1000
CANCEL_PROMPT_MS = 2000   # discard prompt returns to the keyboard after this
RESULT_HOLD_FAIL_MS = 700
NFC_REINIT_AFTER = 15
DETECT_MS = 80
ABSENT_POLLS = 3          # consecutive misses before a card counts as lifted
READ_CLEAR_MS = 5000      # Read: back to Hold Card this long after the card is lifted
SETTLE_OVER = 10          # lists longer than this move once the knob settles

HOME = "home"
READ = "read"
GAMES = "games"
TAGS = "tags"
TEXT = "text"
SCAN = "scan"
ALLNEXT = "allnext"
ALL_ITEM = "All"

HOME_ITEMS = (("Read", READ), ("Tags", GAMES), ("Text", TEXT))
SERVE_MODES = (HOME, GAMES, TAGS)


def _log(msg):
    print("# [dial] %s" % msg)


class Station:
    def __init__(self, ui, inputs, host, card):
        self.ui = ui
        self.inputs = inputs
        self.host = host
        self.card = card
        self._field = False
        self._fails = 0

        self.mode = HOME
        self.home_sel = 0
        self.groups = []
        self.game_sel = 0
        self.tag_sel = 0
        self.entry = None
        self.scan_tag = None
        self.scan_label = None
        self.scan_return = HOME
        self.read_text = None
        self.all_tags = []
        self.all_i = 0
        self._last_uid = None
        self._misses = 0
        self._lifted_at = None
        self._wait_until = None     # see _wait
        self._wait_then = None
        self._wait_back = None
        self._cancel_at = None

    def serving(self):
        """True on a menu screen with no result being held."""
        return self.mode in SERVE_MODES and self._wait_until is None

    def reload(self):
        """Games changed: rebuild the groups. Anywhere inside a group
        (its list, a scan from it, write-all, a held result) goes back to
        the game list, since the group may be gone."""
        self.groups = self.host.tag_groups()
        self.game_sel = 0
        self.tag_sel = 0
        inside = self.mode in (GAMES, TAGS, ALLNEXT) or (
            self.mode == SCAN and self.scan_return in (TAGS, ALLNEXT))
        if inside:
            self._wait_until = None
            self.go_games()

    # -- reader ------------------------------------------------------

    def _set_field(self, on):
        nfc = self.host.nfc
        if nfc is None or on == self._field:
            return
        if on:
            self.host.radio_off()
            # A MIFARE auth latches MFCrypto1On, which blocks REQA; clear it
            # before every scan.
            nfc.stop_crypto1()
            nfc.antenna_on()
        else:
            nfc.antenna_off()
            nfc.stop_crypto1()
        self._field = on

    def field_off(self):
        self._set_field(False)

    def _detect(self):
        """One poll. Returns a tag dict or None; recovers a wedged reader."""
        nfc = self.host.nfc
        if nfc is None:
            return None
        try:
            tag = nfc.detect_tag(timeout=DETECT_MS)
        except OSError as e:
            self._fails += 1
            if self._fails <= 3 or self._fails % 5 == 0:
                _log("detect_tag err (%d in a row): %s" % (self._fails, e))
            if self._fails >= NFC_REINIT_AFTER:
                _log("reader re-init after %d errors" % self._fails)
                self._fails = 0
                try:
                    self.host.init_nfc()
                    self._field = False
                    self._set_field(True)
                except Exception as e2:
                    _log("reader re-init failed: %s" % e2)
            return None
        self._fails = 0
        return tag

    # -- transitions -------------------------------------------------

    def _settle(self, n):
        self.inputs.settle_ms = TURN_SETTLE_MS if n > SETTLE_OVER else 0

    def _enter(self, mode):
        self.mode = mode
        self.inputs.clear()
        self._last_uid = None
        self._misses = 0
        self._lifted_at = None

    def _show_home(self):
        self._settle(len(HOME_ITEMS))
        self.ui.show_ring([n for n, _ in HOME_ITEMS], self.home_sel)

    def go_home(self):
        self._enter(HOME)
        self._set_field(False)
        self._show_home()

    def go_read(self):
        self._enter(READ)
        self.read_text = None
        self._set_field(True)
        self.ui.show_reader(None, read=False)

    def _show_games(self):
        names = [g[0] for g in self.groups]
        self._settle(len(names))
        self.ui.show_list("Games" if self.host.has_games() else "No Game",
                          names, self.game_sel)

    def go_games(self):
        self._enter(GAMES)
        self._set_field(False)
        self.game_sel %= max(len(self.groups), 1)
        self._show_games()

    def tag_options(self):
        """(label, tag) rows for the open group; All (tag None) first when
        the group allows it."""
        _, rows, all_ok = self.groups[self.game_sel]
        if all_ok and len(rows) > 1:
            return [(ALL_ITEM, None)] + list(rows)
        return list(rows)

    def _show_tags(self):
        rows = self.tag_options()
        self._settle(len(rows))
        self.ui.show_list(self.groups[self.game_sel][0],
                          [r[0] for r in rows], self.tag_sel)

    def go_tags(self):
        self._enter(TAGS)
        self._set_field(False)
        self.tag_sel %= len(self.tag_options())
        self._show_tags()

    def go_all(self):
        """Write every tag of the open group, one card each."""
        self.all_tags = [r for r in self.groups[self.game_sel][1]]
        self.all_i = 0
        label, tag = self.all_tags[0]
        self.go_scan(tag, label, ALLNEXT)

    def go_allnext(self):
        """Write-all between cards: show the next tag and wait until the
        card just written leaves the field, then scan for the next one."""
        self._enter(ALLNEXT)
        self._set_field(True)
        self.ui.show_next(self.all_tags[self.all_i][0], self.all_i + 1,
                          len(self.all_tags))

    def go_text(self, keep=False):
        self._enter(TEXT)
        self._set_field(False)
        self.host.radio_off()
        self.inputs.settle_ms = TURN_SETTLE_MS
        if not keep or self.entry is None:
            self.entry = text_entry.TextEntry(TEXT_MAX, self.host.words())
        self.ui.show_keyboard(self.entry.view())

    def go_scan(self, tag, label, ret):
        self._enter(SCAN)
        self.scan_tag = tag
        self.scan_label = label
        self.scan_return = ret
        self._set_field(True)
        if ret == ALLNEXT:
            self.ui.show_scan(label, "%d/%d" % (self.all_i + 1, len(self.all_tags)))
        else:
            self.ui.show_scan(label)

    def _after_write(self):
        """Where a scan goes after the card is written (or already set)."""
        if self.scan_return != ALLNEXT:
            self._go(self.scan_return)
            return
        self.all_i += 1
        if self.all_i < len(self.all_tags):
            self.go_allnext()
            return
        self.ui.show_result("ok", "All Done", self.groups[self.game_sel][0])
        self.ui.beep_success()
        self._wait(RESULT_HOLD_OK_MS, self.go_tags, self.go_tags)

    def _go(self, mode):
        if mode == HOME:
            self.go_home()
        elif mode == READ:
            self.go_read()
        elif mode == GAMES:
            self.go_games()
        elif mode == TAGS:
            self.go_tags()
        elif mode == TEXT:
            self.go_text(keep=True)
        elif mode == ALLNEXT:
            self.go_tags()      # leaving write-all ends it
        else:
            raise ValueError("no transition to %r" % mode)

    # -- per-mode input ----------------------------------------------

    def _step(self, sel, n, intent):
        if intent not in (NEXT, PREV):
            return sel
        self.ui.beep_turn()
        for i in [intent] + self._more_turns():
            sel = (sel + (1 if i == NEXT else -1)) % n
        return sel

    def _more_turns(self):
        """Pop rotation intents already queued behind the current one, so a
        settled spin repaints once."""
        out = []
        while self.inputs.peek() in (NEXT, PREV):
            out.append(self.inputs.pop())
        return out

    def _home(self, intent):
        if intent in (NEXT, PREV):
            self.home_sel = self._step(self.home_sel, len(HOME_ITEMS), intent)
            self._show_home()
        elif intent == ACT:
            self.ui.beep_click()
            self._go(HOME_ITEMS[self.home_sel][1])

    def _games(self, intent):
        if intent in (NEXT, PREV):
            self.game_sel = self._step(self.game_sel, len(self.groups), intent)
            self._show_games()
        elif intent == ACT:
            self.ui.beep_click()
            self.tag_sel = 0
            self.go_tags()
        elif intent == EXIT:
            self.go_home()

    def _tags(self, intent):
        rows = self.tag_options()
        if intent in (NEXT, PREV):
            self.tag_sel = self._step(self.tag_sel, len(rows), intent)
            self._show_tags()
        elif intent == ACT:
            self.ui.beep_click()
            label, tag = rows[self.tag_sel]
            if tag is None:
                self.go_all()
            else:
                self.go_scan(tag, label, TAGS)
        elif intent == EXIT:
            self.go_games()

    def _allnext(self, intent):
        if intent == EXIT:
            self.go_tags()
            return
        if self._detect() is not None:
            self._misses = 0
            return
        self._misses += 1
        if self._misses >= ABSENT_POLLS:
            label, tag = self.all_tags[self.all_i]
            self.go_scan(tag, label, ALLNEXT)

    def _text(self, intent):
        if intent is None:
            # Discard prompt left alone: back to the keyboard, text kept.
            if self.entry.mode == text_entry.M_CANCEL:
                if self._cancel_at is None:
                    self._cancel_at = time.ticks_ms()
                elif time.ticks_diff(time.ticks_ms(), self._cancel_at) >= CANCEL_PROMPT_MS:
                    self._cancel_at = None
                    self.entry.resume()
                    self.ui.show_keyboard(self.entry.view())
            else:
                self._cancel_at = None
            return
        self._cancel_at = None
        ev = self.entry.handle(intent)
        if ev is None:
            if intent in (NEXT, PREV):
                self.ui.beep_turn()
                for i in self._more_turns():
                    self.entry.handle(i)     # rotation never returns an event
            self.ui.show_keyboard(self.entry.view())
            return
        kind = ev[0]
        if kind == "done":
            self.ui.beep_click()
            self.go_scan(ev[1], ev[1], TEXT)
        elif kind == "cancel":
            self.entry = None
            self.go_home()
        else:                               # "full" / "empty"
            self.ui.beep_fail()
            self.ui.show_keyboard(self.entry.view())

    def _read(self, intent):
        if intent == EXIT:
            self.go_home()
            return
        if intent == ACT and self.read_text:
            self.ui.beep_click()
            self.go_scan(self.read_text, self.read_text, READ)
            return
        tag = self._detect()
        if tag is None:
            # One missed poll is not a lift: a Classic card that failed auth
            # often misses the next REQA.
            self._misses += 1
            if self._misses >= ABSENT_POLLS and self._last_uid is not None:
                self._last_uid = None
                self._lifted_at = time.ticks_ms()
            self._read_clear()
            return
        self._misses = 0
        self._lifted_at = None
        if tag["uid_hex"] == self._last_uid:
            return
        self._last_uid = tag["uid_hex"]
        self.ui.beep_scan()
        text = self.card.existing_text(self.host.nfc, tag)
        self.host.nfc.stop_crypto1()    # leave plain mode for the next REQA
        self.read_text = text
        self.host.on_card(tag, text)
        self.ui.show_reader(text)
        if text:
            self.ui.beep_success()
        else:
            self.ui.beep_fail()

    def _read_clear(self):
        """Back to Hold Card READ_CLEAR_MS after the card was lifted, unless
        a hold has started."""
        if self._lifted_at is None:
            return
        if self.inputs.hold_fraction() is not None:
            self._lifted_at = time.ticks_ms()   # button down: restart the wait
            return
        if time.ticks_diff(time.ticks_ms(), self._lifted_at) >= READ_CLEAR_MS:
            self._lifted_at = None
            self.read_text = None
            self.ui.show_reader(None, read=False)

    def _scan(self, intent):
        if intent == EXIT:
            self._go(self.scan_return)
            return
        tag = self._detect()
        if tag is None:
            return
        self.ui.beep_scan()
        nfc = self.host.nfc
        label = self.scan_label
        want = self.host.card_text(self.scan_tag)
        existing = self.card.existing_text(nfc, tag)
        self.host.on_card(tag, existing)
        ret = self.scan_return
        back = lambda: self._go(ret)
        if existing == want:
            self._mark_written(want)
            self.host.on_written(self.scan_tag, tag["uid_hex"], False)
            self.ui.show_result("ok", "Already Set", label)
            self.ui.beep_success()
            self._wait(RESULT_HOLD_OK_MS, self._after_write, back)
            return
        self.ui.show_result("busy", "Writing", label)
        self.ui.flush()             # visible before the blocking write
        ok = self.card.write_text(nfc, tag, want)
        if ok:
            _log("written %r uid=%s" % (want, tag["uid_hex"]))
            self._mark_written(want)
            self.host.on_written(self.scan_tag, tag["uid_hex"], True)
            self.ui.show_result("ok", "Done", label)
            self.ui.beep_success()
            self._wait(RESULT_HOLD_OK_MS, self._after_write, back)
        else:
            _log("write FAILED %r uid=%s" % (want, tag["uid_hex"]))
            self.ui.show_result("fail", "Write Failed", label)
            self.ui.beep_fail()
            tag_, label_ = self.scan_tag, label
            self._wait(RESULT_HOLD_FAIL_MS,
                       lambda: self.go_scan(tag_, label_, ret), back)

    def _mark_written(self, text):
        if self.scan_return == TEXT and self.entry is not None:
            self.entry.mark_written(text)

    def _wait(self, ms, then, back):
        """Keep the current screen for ms without blocking the loop, then run
        `then`. A hold (EXIT) during the wait runs `back` instead; other
        input is dropped."""
        if ms <= 0:
            then()
            return
        self._wait_until = time.ticks_add(time.ticks_ms(), ms)
        self._wait_then = then
        self._wait_back = back

    def _waiting(self, intent):
        """True while a _wait is pending (and handles it)."""
        if self._wait_until is None:
            return False
        if intent == EXIT:
            fn = self._wait_back
        elif time.ticks_diff(time.ticks_ms(), self._wait_until) >= 0:
            fn = self._wait_then
        else:
            return True
        self._wait_until = None
        fn()
        return True

    # -- loop --------------------------------------------------------

    def step(self):
        """One loop iteration minus serial and radio: input, then the
        current mode."""
        self.inputs.update()        # M5.update(): includes LVGL redraw
        # Home has no back, so a hold there shows no progress ring.
        self.ui.show_hold(None if self.mode == HOME else self.inputs.hold_fraction())
        intent = self.inputs.pop()
        if self._waiting(intent):
            return
        if self.mode == HOME:
            if intent:
                self._home(intent)
        elif self.mode == GAMES:
            if intent:
                self._games(intent)
        elif self.mode == TAGS:
            if intent:
                self._tags(intent)
        elif self.mode == ALLNEXT:
            self._allnext(intent)
        elif self.mode == TEXT:
            self._text(intent)
        elif self.mode == READ:
            self._read(intent)
        elif self.mode == SCAN:
            self._scan(intent)
