"""tag_emulator.py -- keeps the NT3H2111 (nt3h2111.py, MIKROE NFC Tag 2
Click on Port A) holding the card a wand should read off the Dial.

  GAMES   getcode:<slug>@<HOST_ID> of the highlighted game
  TAGS    the highlighted tag (no press needed)
  held    text from the keyboard or a Read copy (station.py SCAN):
          written at once; the Click keeps it until the knob moves off
          the menu position the Dial returns to
  else    left as it is

A menu text is written once it has been wanted for SETTLE_MS, so turning
the knob through the game list does not rewrite the EEPROM per detent; an
unchanged text is never rewritten. A failed write (a wand's field holding
the chip) is retried after RETRY_MS.

Imported by bdial_server.run() after the radio prewarm.
PEER: Experiments/EmulatedTagDial/tag_emulator.py (diverged: held cards,
no "stop" default).
"""

import time

SETTLE_MS = 300
RETRY_MS = 1000
CODE_MODES = ("games", "tags")   # station.GAMES, station.TAGS


class TagEmulator:
    def __init__(self, tag, card_text):
        self.tag = tag
        self.card_text = card_text   # bdial_server._card_text: pins HOST_ID
        self.written = None
        self.held = None
        self._pinned = False
        self._pin_key = None
        self._want = None
        self._since = 0
        self._retry_at = 0

    def hold(self, text):
        """Emulate `text` until release(); the Click keeps it after."""
        self.held = text
        self._pinned = True
        self._want = None
        self._pin_key = None
        self._retry_at = 0

    def release(self):
        self.held = None

    def ready(self):
        return self.held is not None and self.written == self.held

    def wanted(self, st):
        if self.held is not None:
            return self.held
        if (st.mode not in CODE_MODES or st._wait_until is not None
                or not st.groups):
            return None
        if self._pinned:
            key = (st.mode, st.game_sel, st.tag_sel)
            if self._pin_key is None:
                self._pin_key = key
            if key == self._pin_key:
                return None
            self._pinned = False
        if st.mode == "tags":
            rows = st.tag_options()
            t = rows[st.tag_sel % len(rows)][1]
            return None if t is None else self.card_text(t)
        for _, t in st.groups[st.game_sel % len(st.groups)][1]:
            if t.startswith("getcode:"):
                return self.card_text(t)
        return None

    def poll(self, st):
        now = time.ticks_ms()
        want = self.wanted(st)
        if want != self._want:
            self._want = want
            self._since = now
        if (want is None or want == self.written
                or time.ticks_diff(self._retry_at, now) > 0):
            return
        if want != self.held and time.ticks_diff(now, self._since) < SETTLE_MS:
            return
        self._write(want, now)

    def _write(self, text, now):
        if self.tag.write_text(text):
            self.written = text
            print("# tag: %s" % text)
        else:
            self._retry_at = time.ticks_add(now, RETRY_MS)
