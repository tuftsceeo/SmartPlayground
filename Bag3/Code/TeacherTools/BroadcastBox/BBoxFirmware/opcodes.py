"""
Opcode table — compact card encoding + single source of truth for tag names
============================================================================
Every wand card stores a fixed 4-byte "opcode" at page/block 5:

    byte 0 : 0x5A   MAGIC — "this is a SmartPlayground opcode card"
    byte 1 : op     the TYPE     (GAME / NOTE / COLOR / CONTROL / ...)
    byte 2 : arg    the VALUE    (which game, which note, which color, ...)
    byte 3 : chk    MAGIC ^ op ^ arg  (catches misreads / blank pages)

The app still speaks in the string command names it always has
("colorquest", "note_c", "turnred", "stop", ...). This module is the ONLY
place that maps those names to/from the on-card bytes:

    encode("note_c")            -> b'\\x5a\\x03\\x01\\x58'   (write to page 5)
    decode(page5_bytes)         -> "note_c"                  (read from page 5)

Because the whole meaning lives in one page, retrieval is a single page
read (NTAG) or one auth + one block read (MIFARE Classic) — no NDEF TLV
parsing, no multi-page scan.

    ── ADDING A NEW CARD ──
Append the new name to the end of the right category tuple below. NEVER
reorder or delete existing entries: the arg value is the 1-based position
in the tuple, so reordering silently changes what already-written cards
mean. Append-only keeps every card ever written valid.

This module absorbs the old game_tags.py; game_tags.py now re-exports from
here so existing `from game_tags import ...` lines keep working.
"""

# ─────────────────────────────────────────────
# WIRE FORMAT
# ─────────────────────────────────────────────
MAGIC = 0x5A          # byte 0 sentinel
CARD_PAGE = 5         # NTAG page / Classic block holding the opcode

# ─────────────────────────────────────────────
# OPCODES (byte 1) — the card "type"
# ─────────────────────────────────────────────
OP_GAME       = 0x01
OP_CONTROL    = 0x02
OP_NOTE       = 0x03
OP_COLOR      = 0x04
OP_TRIGGER    = 0x05
OP_COMBINATOR = 0x06
OP_ACTION     = 0x07
OP_SOUND      = 0x08
OP_UTILITY    = 0x09
# Game-specific card sets (only meaningful inside their own game):
OP_INGREDIENT = 0x0A   # cooking
OP_FREEZE     = 0x0B   # freeze_dance roles / commands
OP_GESTURE    = 0x0C   # gestures (training labels — distinct from OP_COLOR)
OP_BROADCAST  = 0x0D   # Broadcast Box pickup cards

# Games only ever tapped as physical cards (arg = 1-based index below).
_GAME_NAMES = (
    "colorquest", "freezedance", "jumpin", "cooking", "melody",
    "shake", "shakerainbow", "rainbow", "jump", "sound", "nfcsound",
    "simpleicecream", "multiicecream", "gestures",
)
# ESP-NOW-only "game" — never printed on a card, but kept in the table so
# GAME_DISPATCH and decode() agree. It gets its own arg after the real games.
_HIDDEN_NAMES = ("finddevice",)

# arg = index + 1 within each tuple. APPEND ONLY — never reorder/remove.
_CATEGORIES = {
    OP_GAME:       _GAME_NAMES + _HIDDEN_NAMES,
    OP_CONTROL:    ("start", "stop", "erase", "color_quest_scan"),
    OP_NOTE:       ("note_c", "note_d", "note_e", "note_f",
                    "note_g", "note_a", "note_b", "note_c_high"),
    OP_COLOR:      ("turnred", "turngreen", "turnblue", "turnpurple",
                    "turnpink", "turnyellow", "turnwhite", "turnoff"),
    OP_TRIGGER:    ("buttondown", "buttonup", "whenshake"),
    OP_COMBINATOR: ("and", "then"),
    OP_ACTION:     ("playnote",),
    OP_SOUND:      ("cat", "chicken", "cow", "dog", "pig",
                    "duck", "elephant", "horse", "goat"),
    OP_UTILITY:    ("battery",),
    OP_INGREDIENT: ("tomato", "milk", "cheese", "flour",
                    "egg", "butter", "sugar"),
    OP_FREEZE:     ("caller", "player", "go", "freeze", "rejoin"),
    OP_GESTURE:    ("red", "green", "blue", "play"),
    OP_BROADCAST:  ("getcode",),
}

# ─────────────────────────────────────────────
# BUILD LOOKUP TABLES (name <-> (op, arg))
# ─────────────────────────────────────────────
NAME_TO_CODE = {}
CODE_TO_NAME = {}
for _op, _names in _CATEGORIES.items():
    for _i, _name in enumerate(_names):
        _arg = _i + 1                       # 1-based; arg 0 stays reserved
        NAME_TO_CODE[_name] = (_op, _arg)
        CODE_TO_NAME[(_op, _arg)] = _name

ALL_NAMES = frozenset(NAME_TO_CODE.keys())


# ─────────────────────────────────────────────
# ENCODE / DECODE
# ─────────────────────────────────────────────
def encode(name):
    """Command name -> 4-byte page-5 payload, or None if the name is unknown."""
    entry = NAME_TO_CODE.get(name)
    if entry is None:
        return None
    op, arg = entry
    chk = (MAGIC ^ op ^ arg) & 0xFF
    return bytes((MAGIC, op, arg, chk))


def decode(data):
    """4+ bytes read from page 5 -> command name, or None.

    Returns None when the bytes are not a valid opcode card: wrong magic
    (blank page, old NDEF card), bad checksum (misread), or an unknown
    (op, arg) pair. Only the first 4 bytes are inspected.
    """
    if not data or len(data) < 4:
        return None
    b0, op, arg, chk = data[0], data[1], data[2], data[3]
    if b0 != MAGIC:
        return None
    if ((b0 ^ op ^ arg) & 0xFF) != chk:
        return None
    return CODE_TO_NAME.get((op, arg))


def names_by_category():
    """Ordered {opcode: (names...)} — for the card-writer's help listing."""
    return _CATEGORIES


# ─────────────────────────────────────────────
# TAG SETS (backward-compatible with the old game_tags.py)
# ─────────────────────────────────────────────
GAME_TAGS = set(_GAME_NAMES)          # games only (no "stop", no "start")
CONTROL_TAGS = {"start", "stop"}
HIDDEN_TAGS = set(_HIDDEN_NAMES)      # ESP-NOW only, never on an NFC card
EXIT_TAGS = GAME_TAGS | {"stop"}      # any tag that exits a running game


def exit_tags_excluding(game_tag):
    """EXIT_TAGS copy without this game's own entry tag.

    The entry tag is often still under the wand when play() starts;
    excluding it avoids an immediate exit on the first NFC poll. Never
    mutates EXIT_TAGS.
    """
    tags = set(EXIT_TAGS)
    tags.discard(game_tag)
    return tags
