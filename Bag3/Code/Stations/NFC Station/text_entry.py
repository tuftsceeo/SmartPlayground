"""text_entry.py -- dial-driven text entry state machine (no display code).

Ring keyboard, two levels:

  GROUPS  ring of letter groups, plus "words", delete and done.
          ACT on a group opens it; on delete removes the last character;
          on done finishes.
  CHARS   ring of one group's characters plus "back".
          ACT on a character appends it and returns to GROUPS.
  WORDS   list of whole words (tag names, /flash/words.json).
          ACT appends the word (with a separating space when needed) and
          returns to GROUPS; ACT on "back" returns without appending.
  CANCEL  shown after a hold when text is not empty. A second hold
          discards; any other intent returns to GROUPS.

Intents come from dial_input (NEXT/PREV/ACT/EXIT), "tap:<i>" from a touch
on rim item i (select + act), and DEL / DONE defined here. handle() returns None or an event tuple:

  ("done", text)   finished, text stripped and non-empty
  ("cancel",)      discarded
  ("full",)        a character or word would exceed max_bytes
  ("empty",)       done with nothing entered

Alphabet is lowercase only: every NDEF-text reader in Bag3 lowercases card
text on read, so capitals would not survive.
"""

from dial_input import NEXT, PREV, ACT, EXIT

DEL = "del"
DONE = "done"

GROUPS = ("abcde", "fghij", "klmno", "pqrst", "uvwxy", "z_ ", "01234",
          "56789")
WORDS_ITEM = "words"
BACK_ITEM = "back"

M_GROUPS = "groups"
M_CHARS = "chars"
M_WORDS = "words"
M_CANCEL = "cancel"


class TextEntry:
    def __init__(self, max_bytes, words=(), text=""):
        self.max_bytes = max_bytes
        self.words = list(words)
        self.text = text
        self.mode = M_GROUPS
        self.group = None
        self.sel = 0

    # -- choices -----------------------------------------------------

    def choices(self):
        """Ring/list items for the current mode, as internal values."""
        if self.mode == M_GROUPS:
            items = list(GROUPS)
            if self.words:
                items.append(WORDS_ITEM)
            items.append(DEL)
            items.append(DONE)
            return items
        if self.mode == M_CHARS:
            return list(GROUPS[self.group]) + [BACK_ITEM]
        if self.mode == M_WORDS:
            return [BACK_ITEM] + self.words
        return [DONE]

    def selected(self):
        return self.choices()[self.sel]

    # -- editing -----------------------------------------------------

    def _fits(self, s):
        return len((self.text + s).encode("utf-8")) <= self.max_bytes

    def _append(self, s):
        if not self._fits(s):
            return ("full",)
        self.text += s
        return None

    def _finish(self):
        out = self.text.strip()
        if not out:
            return ("empty",)
        return ("done", out)

    def _to(self, mode, group=None):
        self.mode = mode
        self.group = group
        self.sel = 0

    # -- input -------------------------------------------------------

    def handle(self, intent):
        if intent and intent.startswith("tap:"):
            # Touch on rim item i: select it, then act on it.
            i = int(intent[4:])
            if self.mode == M_CANCEL or i >= len(self.choices()):
                return None
            self.sel = i
            intent = ACT
        if self.mode == M_CANCEL:
            if intent == EXIT:
                return ("cancel",)
            self._to(M_GROUPS)
            return None

        if intent == NEXT:
            self.sel = (self.sel + 1) % len(self.choices())
            return None
        if intent == PREV:
            self.sel = (self.sel - 1) % len(self.choices())
            return None
        if intent == DEL:
            self.text = self.text[:-1]
            return None
        if intent == DONE:
            return self._finish()
        if intent == EXIT:
            if self.mode != M_GROUPS:
                self._to(M_GROUPS)
                return None
            if self.text:
                self._to(M_CANCEL)
                return None
            return ("cancel",)
        if intent != ACT:
            return None

        item = self.selected()
        if self.mode == M_GROUPS:
            if item == DEL:
                self.text = self.text[:-1]
                return None
            if item == DONE:
                return self._finish()
            if item == WORDS_ITEM:
                self._to(M_WORDS)
                return None
            self._to(M_CHARS, GROUPS.index(item))
            return None

        if self.mode == M_CHARS:
            ev = None
            if item != BACK_ITEM:
                ev = self._append(item)
            self._to(M_GROUPS)
            return ev

        # M_WORDS
        ev = None
        if item != BACK_ITEM:
            sep = " " if self.text and not self.text.endswith(" ") else ""
            ev = self._append(sep + item)
        self._to(M_GROUPS)
        return ev

    # -- view --------------------------------------------------------

    def view(self):
        """Plain-data snapshot for the painter."""
        return {
            "mode": self.mode,
            "choices": self.choices(),
            "sel": self.sel,
            "text": self.text,
            "used": len(self.text.encode("utf-8")),
            "max": self.max_bytes,
        }
