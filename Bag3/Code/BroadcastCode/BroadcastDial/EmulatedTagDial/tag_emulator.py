"""tag_emulator.py -- keeps the NT3H2111 (nt3h2111.py) holding the tag a
wand should read off the Dial itself.

  GAMES  (game list)     getcode:<slug>@<HOST_ID> of the highlighted game
  TAGS   (a game's tags) getcode:<slug>@<HOST_ID> of the open game
  anything else          stop   (also: Utility group, no game, held result)

A new text is written once it has been wanted for SETTLE_MS, so turning
the knob through the game list does not rewrite the EEPROM per detent; an
unchanged text is never rewritten. A failed write (a wand's field holding
the chip) is retried after RETRY_MS. stop() writes "stop" at once -- the
host calls it before the reader's field comes on.

Imported by etdial_server.run() after the radio prewarm.
"""

import time

STOP = "stop"
SETTLE_MS = 300
RETRY_MS = 1000
CODE_MODES = ("games", "tags")   # station.GAMES, station.TAGS


class TagEmulator:
    def __init__(self, tag, card_text):
        self.tag = tag
        self.card_text = card_text   # etdial_server._card_text: pins HOST_ID
        self.written = None
        self._want = None
        self._since = 0
        self._retry_at = 0

    def wanted(self, st):
        if (st.mode not in CODE_MODES or st._wait_until is not None
                or not st.groups):
            return STOP
        for _, t in st.groups[st.game_sel % len(st.groups)][1]:
            if t.startswith("getcode:"):
                return self.card_text(t)
        return STOP

    def poll(self, st):
        now = time.ticks_ms()
        want = self.wanted(st)
        if want != self._want:
            self._want = want
            self._since = now
        if (want == self.written
                or time.ticks_diff(now, self._since) < SETTLE_MS
                or time.ticks_diff(self._retry_at, now) > 0):
            return
        self._write(want, now)

    def stop(self):
        if self.written != STOP:
            self._write(STOP, time.ticks_ms())

    def _write(self, text, now):
        if self.tag.write_text(text):
            self.written = text
            print("# tag: %s" % text)
        else:
            self._retry_at = time.ticks_add(now, RETRY_MS)
