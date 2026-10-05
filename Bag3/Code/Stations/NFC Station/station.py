"""station.py -- NFC Station mode machine and main loop.

Modes (intents from dial_input; EXIT = 1 s hold):

  HOME   ring: Read / Tags / Text          ACT opens
  READ   field on, reports each new card   ACT on a read card copies it
                                           EXIT -> HOME (one hold)
         back to Hold Card READ_CLEAR_MS after the card is lifted
  GAMES  dot ring of catalog groups        ACT -> TAGS, EXIT -> HOME
  TAGS   dot ring: All, Start <Game>, the game's card tags
                                           ACT -> SCAN (All -> write-all),
                                           EXIT -> GAMES. A one-tag game
                                           skips TAGS and scans directly.
  ALLNEXT write-all: next tag shown; scans it once the written card is
          removed (ABSENT_POLLS misses), EXIT -> TAGS
  TEXT   ring keyboard (text_entry)        done -> SCAN, cancel -> HOME
  SCAN   field on, writes the target text  EXIT -> where it came from

SCAN writes whatever card is presented. A card that already carries the
target is reported, not rewritten. After a write the result is held on
screen briefly; success returns to the mode SCAN came from, failure
re-arms the same scan.

Hardware is injected (ui, inputs, link, nfc factory, card module) so the
machine runs under CPython with fakes -- see tools/test_station.py.

Serial (newline JSON, json_link.py):
  {"cmd":"identify"}                      -> identity
  {"cmd":"catalog.get"}                   -> catalog {groups, words}
  {"cmd":"catalog.set","index":{...}}     -> ok (index.json shape)
  {"cmd":"words.set","words":[...]}       -> ok
  {"cmd":"write","text":"..."}            -> ok; opens SCAN for that text
  {"cmd":"home"}                          -> ok
  {"cmd":"repl"}                          -> bye; loop exits to the REPL
  {"cmd":"reboot"}
Events: card_read {uid,type,text}, card_written {uid,text},
        write_failed {uid,text}, heartbeat {mode}.
"""

import time

import tag_catalog
from game_tags import GAME_TAGS
import text_entry
from dial_input import NEXT, PREV, ACT, EXIT

VERSION = "0.1.0"
HEARTBEAT_MS = 5000
LOOP_MS = 30              # >0: print loop iterations slower than this (ms), by stage

# NDEF text overhead: TLV (2) + record header (3) + "T" (1) + lang "en"
# with its length byte (3) + terminator (1) = 10 bytes. The readers'
# existing_text()/nfc_reader.py read NTAG pages 4-19 only (64 bytes).
# 54 keeps the whole message, terminator included, in that window; longer
# text writes but reads back truncated, failing verify.
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

HOME = "home"
READ = "read"
GAMES = "games"
TAGS = "tags"
TEXT = "text"
SCAN = "scan"
ALLNEXT = "allnext"     # write-all: waiting for a click before the next tag
ALL_ITEM = "All"

HOME_ITEMS = (("Read", READ), ("Tags", GAMES), ("Text", TEXT))


def _log(msg):
    print("# [station] %s" % msg)


class Station:
    def __init__(self, ui, inputs, link=None, make_nfc=None, card=None,
                 catalog_path=tag_catalog.CATALOG_PATH,
                 words_path=tag_catalog.WORDS_PATH):
        self.ui = ui
        self.inputs = inputs
        self.link = link
        self._make_nfc = make_nfc
        self.card = card
        self.catalog_path = catalog_path
        self.words_path = words_path
        self.nfc = None
        self.nfc_ok = False
        self._field = False
        self._fails = 0

        self.mode = HOME
        self.home_sel = 0
        self.groups = []
        self.words = []
        self.game_sel = 0
        self.tag_sel = 0
        self.entry = None
        self.scan_text = None
        self.scan_return = HOME
        self.read_text = None
        self._last_uid = None
        self._misses = 0
        self._lifted_at = None
        self._beat = 0
        self._cancel_at = None
        self.running = True

        self.handlers = {
            "identify": self.do_identify,
            "catalog.get": self.do_catalog_get,
            "catalog.set": self.do_catalog_set,
            "words.set": self.do_words_set,
            "write": self.do_write,
            "home": self.do_home,
            "repl": self.do_repl,
            "reboot": self.do_reboot,
        }

    # -- setup -------------------------------------------------------

    def load_catalog(self):
        self.groups = tag_catalog.load_groups(self.catalog_path)
        self.words = tag_catalog.load_words(self.groups, self.words_path)

    def init_nfc(self):
        """Bring up the reader. A failure is reported on screen and over
        serial, and re-raised: the station is useless without it."""
        try:
            self.nfc = self._make_nfc()
        except Exception as e:
            self.nfc_ok = False
            self.ui.show_result("fail", "No Reader", str(e)[:40])
            self._send({"type": "error", "code": "nfc_init", "msg": str(e)})
            raise
        self.nfc_ok = True
        self._field = False

    def begin(self):
        self.load_catalog()
        self.init_nfc()
        self._send(self._identity())
        self.go_home()

    # -- serial ------------------------------------------------------

    def _send(self, obj):
        if self.link is not None:
            self.link.send(obj)

    def dispatch(self, cmd):
        name = cmd.get("cmd")
        rid = cmd.get("id")
        h = self.handlers.get(name)
        if h is None:
            self._send({"type": "error", "id": rid, "code": "unknown_cmd", "cmd": name})
            return
        h(cmd, rid)

    def _identity(self, rid=None):
        return {"type": "identity", "id": rid, "device": "nfc_station",
                "version": VERSION, "nfc": self.nfc_ok, "text_max": TEXT_MAX}

    def do_identify(self, cmd, rid):
        self._send(self._identity(rid))

    def do_catalog_get(self, cmd, rid):
        self._send({"type": "catalog", "id": rid,
                    "groups": [[n, t] for n, t in self.groups],
                    "words": self.words})

    def do_catalog_set(self, cmd, rid):
        index = cmd.get("index")
        tag_catalog.groups_from_index(index)        # validate before saving
        tag_catalog.save_json(self.catalog_path, index)
        self.load_catalog()
        self._send({"type": "ok", "id": rid, "cmd": "catalog.set",
                    "groups": len(self.groups)})
        if self.mode in (GAMES, TAGS):
            self.go_games()

    def do_words_set(self, cmd, rid):
        words = cmd.get("words")
        if not isinstance(words, list):
            raise ValueError("words must be a list")
        tag_catalog.save_json(self.words_path, words)
        self.load_catalog()
        self._send({"type": "ok", "id": rid, "cmd": "words.set",
                    "words": len(self.words)})

    def do_write(self, cmd, rid):
        text = str(cmd.get("text", "")).strip().lower()
        if not text or len(text.encode("utf-8")) > TEXT_MAX:
            self._send({"type": "error", "id": rid, "code": "bad_text",
                        "max": TEXT_MAX})
            return
        self._send({"type": "ok", "id": rid, "cmd": "write", "text": text})
        self.go_scan(text, HOME)

    def do_home(self, cmd, rid):
        self._send({"type": "ok", "id": rid, "cmd": "home"})
        self.go_home()

    def do_repl(self, cmd, rid):
        """Stop the main loop and return to the REPL, so mpremote can take
        the board without a Ctrl-C (which m5ui's LVGL callbacks can eat)."""
        self._send({"type": "bye", "id": rid})
        self.running = False

    def do_reboot(self, cmd, rid):
        self._send({"type": "ok", "id": rid, "cmd": "reboot"})
        import machine
        machine.reset()

    # -- reader ------------------------------------------------------

    def _set_field(self, on):
        if self.nfc is None or on == self._field:
            return
        if on:
            # A MIFARE auth latches MFCrypto1On, which blocks REQA; clear it
            # before every scan (see bdial_server._to_scan).
            self.nfc.stop_crypto1()
            self.nfc.antenna_on()
        else:
            self.nfc.antenna_off()
        self._field = on

    def _detect(self):
        """One poll. Returns a tag dict or None; recovers a wedged reader."""
        try:
            tag = self.nfc.detect_tag(timeout=DETECT_MS)
        except OSError as e:
            self._fails += 1
            if self._fails <= 3 or self._fails % 5 == 0:
                _log("detect_tag err (%d in a row): %s" % (self._fails, e))
            if self._fails >= NFC_REINIT_AFTER:
                _log("reader re-init after %d errors" % self._fails)
                self._fails = 0
                self.init_nfc()
                self._set_field(True)
            return None
        self._fails = 0
        return tag

    # -- transitions -------------------------------------------------

    def _enter(self, mode):
        self.mode = mode
        self.inputs.clear()
        self._last_uid = None
        self._misses = 0
        self._lifted_at = None

    def go_home(self):
        self._enter(HOME)
        self._set_field(False)
        self.ui.show_ring([n for n, _ in HOME_ITEMS], self.home_sel)

    def go_read(self):
        self._enter(READ)
        self.read_text = None
        self._set_field(True)
        self.ui.show_reader(None, read=False)

    def go_games(self):
        self._enter(GAMES)
        self._set_field(False)
        self.game_sel %= max(len(self.groups), 1)
        self.ui.show_list("Games", [n for n, _ in self.groups], self.game_sel)

    def tag_options(self):
        """(label, card text) rows for the open group. A game with several
        tags starts with All (write every tag in turn); a game's entry tag
        is labelled "Start <Game>". Utilities has no All."""
        name, tags = self.groups[self.game_sel]
        rows = []
        if len(tags) > 1 and tags[0] in GAME_TAGS:
            rows.append((ALL_ITEM, None))
        for i, t in enumerate(tags):
            label = "Start " + name if i == 0 and t in GAME_TAGS else t
            rows.append((label, t))
        return rows

    def go_tags(self):
        self._enter(TAGS)
        self._set_field(False)
        name, _ = self.groups[self.game_sel]
        rows = self.tag_options()
        self.tag_sel %= len(rows)
        self.ui.show_list(name, [r[0] for r in rows], self.tag_sel)

    def go_all(self):
        """Write every tag of the open group, one card each."""
        self.all_tags = list(self.groups[self.game_sel][1])
        self.all_i = 0
        self.go_scan(self.all_tags[0], ALLNEXT)

    def go_allnext(self):
        """Write-all between cards: show the next tag and wait until the
        card just written leaves the field, then scan for the next one."""
        self._enter(ALLNEXT)
        self._set_field(True)
        self.ui.show_next(self.all_tags[self.all_i], self.all_i + 1, len(self.all_tags))

    def go_text(self, keep=False):
        self._enter(TEXT)
        self._set_field(False)
        if not keep or self.entry is None:
            self.entry = text_entry.TextEntry(TEXT_MAX, self.words)
        self.ui.show_keyboard(self.entry.view())

    def go_scan(self, text, ret):
        self._enter(SCAN)
        self.scan_text = text
        self.scan_return = ret
        self._set_field(True)
        if ret == ALLNEXT:
            self.ui.show_scan(text, "%d/%d" % (self.all_i + 1, len(self.all_tags)))
        else:
            self.ui.show_scan(text)

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
        self._hold(RESULT_HOLD_OK_MS)
        self.go_tags()

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
        fast turn moves several items with one repaint instead of
        repainting once per detent."""
        out = []
        while self.inputs.peek() in (NEXT, PREV):
            out.append(self.inputs.pop())
        return out

    def _home(self, intent):
        if intent in (NEXT, PREV):
            self.home_sel = self._step(self.home_sel, len(HOME_ITEMS), intent)
            self.ui.show_ring([n for n, _ in HOME_ITEMS], self.home_sel)
        elif intent == ACT:
            self.ui.beep_click()
            self._go(HOME_ITEMS[self.home_sel][1])

    def _games(self, intent):
        if intent in (NEXT, PREV):
            self.game_sel = self._step(self.game_sel, len(self.groups), intent)
            self.ui.show_list("Games", [n for n, _ in self.groups], self.game_sel)
        elif intent == ACT:
            self.ui.beep_click()
            self.tag_sel = 0
            tags = self.groups[self.game_sel][1]
            if len(tags) == 1:
                self.go_scan(tags[0], GAMES)    # nothing to choose
            else:
                self.go_tags()
        elif intent == EXIT:
            self.go_home()

    def _tags(self, intent):
        name, _ = self.groups[self.game_sel]
        rows = self.tag_options()
        if intent in (NEXT, PREV):
            self.tag_sel = self._step(self.tag_sel, len(rows), intent)
            self.ui.show_list(name, [r[0] for r in rows], self.tag_sel)
        elif intent == ACT:
            self.ui.beep_click()
            text = rows[self.tag_sel][1]
            if text is None:
                self.go_all()
            else:
                self.go_scan(text, TAGS)
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
            self.go_scan(self.all_tags[self.all_i], ALLNEXT)

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
            self.go_scan(ev[1], TEXT)
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
            self.go_scan(self.read_text, READ)
            return
        tag = self._detect()
        if tag is None:
            # One missed poll is not a lift: a Classic card that failed auth
            # often misses the next REQA, and clearing _last_uid then re-ran
            # the ~2 s read on the same card, over and over.
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
        text = self.card.existing_text(self.nfc, tag)
        self.nfc.stop_crypto1()     # leave plain mode for the next REQA
        self.read_text = text
        self._send({"type": "card_read", "uid": tag["uid_hex"],
                    "tag_type": tag["tag_type"], "text": text})
        self.ui.show_reader(text)
        if text:
            self.ui.beep_success()
        else:
            self.ui.beep_fail()

    def _read_clear(self):
        """Back to Hold Card READ_CLEAR_MS after the card was lifted, unless
        a hold has started (Copy and a new card leave this state first)."""
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
        text = self.scan_text
        existing = self.card.existing_text(self.nfc, tag)
        if existing == text:
            self._mark_written(text)
            self.ui.show_result("ok", "Already Set", text)
            self.ui.beep_success()
            self._hold(RESULT_HOLD_OK_MS)
            self._after_write()
            return
        self.ui.show_result("busy", "Writing", text)
        ok = self.card.write_text(self.nfc, tag, text)
        if ok:
            _log("written %r uid=%s" % (text, tag["uid_hex"]))
            self._send({"type": "card_written", "uid": tag["uid_hex"], "text": text})
            self._mark_written(text)
            self.ui.show_result("ok", "Done", text)
            self.ui.beep_success()
            self._hold(RESULT_HOLD_OK_MS)
            self._after_write()
        else:
            _log("write FAILED %r uid=%s" % (text, tag["uid_hex"]))
            self._send({"type": "write_failed", "uid": tag["uid_hex"], "text": text})
            self.ui.show_result("fail", "Oops", "Hold Still")
            self.ui.beep_fail()
            self._hold(RESULT_HOLD_FAIL_MS)
            self.go_scan(text, self.scan_return)

    def _mark_written(self, text):
        if self.scan_return == TEXT and self.entry is not None:
            self.entry.mark_written(text)

    def _hold(self, ms):
        time.sleep_ms(ms)

    # -- loop --------------------------------------------------------

    def step(self):
        """One loop iteration minus serial: input, then the current mode."""
        t0 = time.ticks_ms()
        self.inputs.update()        # M5.update(): includes LVGL redraw
        t1 = time.ticks_ms()
        # Home has no back, so a hold there shows no progress ring.
        self.ui.show_hold(None if self.mode == HOME else self.inputs.hold_fraction())
        t2 = time.ticks_ms()
        intent = self.inputs.pop()
        self._t = (t0, t1, t2, intent)
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

    def run(self):
        self.begin()
        while self.running:
            if self.link is not None:
                self.link.pump(idle_ms=0)
            t0 = time.ticks_ms()
            self.step()
            self.ui.tick()
            now = time.ticks_ms()
            if LOOP_MS and time.ticks_diff(now, t0) >= LOOP_MS:
                s0, s1, s2, intent = self._t
                print("# loop %d ms: m5.update %d, hold %d, mode %d (%s, %s)"
                      % (time.ticks_diff(now, t0), time.ticks_diff(s1, s0),
                         time.ticks_diff(s2, s1), time.ticks_diff(now, s2),
                         self.mode, intent))
            if time.ticks_diff(now, self._beat) >= HEARTBEAT_MS:
                self._beat = now
                self._send({"type": "heartbeat", "mode": self.mode})
            time.sleep_ms(1)
