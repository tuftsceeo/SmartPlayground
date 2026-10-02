"""text_entry.py -- dial-driven text entry state machine (no display code).

Rotary ring keyboard: every choice sits on the rim at a fixed angle, so one
encoder detent moves the highlight one item around the ring and the knob's
rotation matches the highlight's. ACT types the highlighted item and the
highlight stays put, so repeated or nearby letters cost no extra turns.

Rings (mode):
  LETTERS  a..z, space, "#", delete, done                   (30 items)
  MORE     0..9, "-", ".", words (if any), "abc", delete, done
  WORDS    back, then whole words (tag names, /flash/words.json); ACT
           appends the word with a separating space and returns to LETTERS
  CANCEL   after a hold with text entered: a second hold leaves (and
           discards unwritten text), any other intent returns to LETTERS.
           view()["written"] tells the painter whether the text was
           already written to a card (back arrow) or would be lost (trash).

LETTERS is laid out in segments of three (abc, def, ... yz_, then the
three commands), matching the ring's drawn segments.

Intents: dial_input NEXT/PREV/ACT/EXIT, "tap:<i>" (touch on rim item i:
select + act), and DEL / DONE. handle() returns None or an event tuple:
  ("done", text) | ("cancel",) | ("full",) | ("empty",)

Lowercase only: every NDEF-text reader in Bag3 lowercases card text.
"""

from dial_input import NEXT, PREV, ACT, EXIT

DEL = "del"
DONE = "done"
MORE_ITEM = "#"
LETTERS_ITEM = "abc"
WORDS_ITEM = "words"
BACK_ITEM = "back"
SPACE = " "

LETTERS = tuple("abcdefghijklmnopqrstuvwxyz") + (SPACE, MORE_ITEM, DEL, DONE)
MORE = tuple("0123456789-.")
SEGMENT = 3

M_LETTERS = "letters"
M_MORE = "more"
M_WORDS = "words"
M_CANCEL = "cancel"


class TextEntry:
    def __init__(self, max_bytes, words=(), text=""):
        self.max_bytes = max_bytes
        self.words = list(words)
        self.text = text
        self.mode = M_LETTERS
        self.sel = 0
        self._letters_sel = 0
        self.written = None     # text last written to a card, if any

    # -- choices -----------------------------------------------------

    def choices(self):
        """Ring items for the current mode, as internal values."""
        if self.mode == M_LETTERS:
            return list(LETTERS)
        if self.mode == M_MORE:
            items = list(MORE)
            if self.words:
                items.append(WORDS_ITEM)
            return items + [LETTERS_ITEM, DEL, DONE]
        if self.mode == M_WORDS:
            return [BACK_ITEM] + self.words
        return [DONE]

    def selected(self):
        return self.choices()[self.sel]

    # -- editing -----------------------------------------------------

    def _append(self, s):
        if len((self.text + s).encode("utf-8")) > self.max_bytes:
            return ("full",)
        self.text += s
        return None

    def _finish(self):
        out = self.text.strip()
        if not out:
            return ("empty",)
        return ("done", out)

    def _to(self, mode):
        if self.mode == M_LETTERS:
            self._letters_sel = self.sel
        self.mode = mode
        # Returning to LETTERS restores the highlight where it was left.
        self.sel = self._letters_sel if mode == M_LETTERS else 0

    # -- input -------------------------------------------------------

    def handle(self, intent):
        if intent and intent.startswith("tap:"):
            i = int(intent[4:])
            if self.mode == M_CANCEL or i >= len(self.choices()):
                return None
            self.sel = i
            intent = ACT
        if self.mode == M_CANCEL:
            if intent == EXIT:
                return ("cancel",)
            self._to(M_LETTERS)
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
            if self.mode != M_LETTERS:
                self._to(M_LETTERS)
                return None
            if self.text:
                self._to(M_CANCEL)
                return None
            return ("cancel",)
        if intent != ACT:
            return None

        item = self.selected()
        if item == DEL:
            self.text = self.text[:-1]
            return None
        if item == DONE:
            return self._finish()
        if item == MORE_ITEM:
            self._to(M_MORE)
            return None
        if item == LETTERS_ITEM or item == BACK_ITEM:
            self._to(M_LETTERS)
            return None
        if item == WORDS_ITEM:
            self._to(M_WORDS)
            return None
        if self.mode == M_WORDS:
            sep = " " if self.text and not self.text.endswith(" ") else ""
            ev = self._append(sep + item)
            self._to(M_LETTERS)
            return ev
        return self._append(item)

    def mark_written(self, text):
        """Record that text was written to a card."""
        self.written = text

    def is_written(self):
        """True when the current text is what was last written to a card,
        so leaving loses nothing."""
        return self.written is not None and self.text.strip() == self.written

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
            "written": self.is_written(),
        }
