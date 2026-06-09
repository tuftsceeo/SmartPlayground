# program_cards.py — opcode table for the tangible programming system.
#
# Each NFC card represents one "block" in a sequential program. The card's
# SERIAL number (uint16, stored at page 5 bytes 2-3) determines which
# block it is. Color byte is ignored for programming cards (it remains
# whatever the manufacturer set or whatever you wrote there).
#
# Serial namespace
#   0 ..  8999  — reserved for LEGO pairing cards (existing)
#   9000.. 9019 — META    (GO, ERASE, ...)
#   9100.. 9199 — EVENT   (when ... happens — implemented as wait-until)
#   9300.. 9399 — CONTROL (wait until ...)
#   9400.. 9499 — MOTION-move
#   9500.. 9599 — MOTION-turn
#   9600.. 9699 — MOTION-run
#
# To add a card: pick the next serial in the appropriate range, add an
# entry to OPCODES, then write that serial onto a blank NFC card with
# tools/write_card.py.

# ── Categories ────────────────────────────────────────────────────────
CAT_META    = 'meta'
CAT_MOTION  = 'motion'
CAT_SENSING = 'sensing'
CAT_EVENT   = 'event'     # in v1, behaves like CAT_CONTROL
CAT_CONTROL = 'control'

# Per-category LED color (used to flash the bottom 3 rows on card-tap
# acknowledgment, and to color the deck pixel that represents this
# block). Same convention as the Scratch-style blocks shown to users.
# Peak channel 10 to match the wand_ui color palette.
CATEGORY_COLOR = {
    CAT_META   : (10, 10, 10),    # white
    CAT_MOTION : ( 0,  8, 10),    # teal
    CAT_SENSING: (10,  3,  6),    # pink
    CAT_EVENT  : (10,  8,  0),    # yellow
    CAT_CONTROL: (10,  5,  0),    # orange
}

# ── Direction codes (for MOTION blocks) ───────────────────────────────
DIR_FORWARD  = 'forward'
DIR_BACKWARD = 'backward'
DIR_LEFT     = 'left'      # rotate left in place
DIR_RIGHT    = 'right'     # rotate right in place
DIR_CW       = 'cw'        # turn clockwise
DIR_CCW      = 'ccw'       # turn counter-clockwise

# ── Sensor color targets ──────────────────────────────────────────────
# These match the LEGO color sensor's color id output.
SENSE_BLACK     = 0
SENSE_MAGENTA   = 1
SENSE_PURPLE    = 2
SENSE_BLUE      = 3
SENSE_AZURE     = 4
SENSE_TURQUOISE = 5
SENSE_GREEN     = 6
SENSE_YELLOW    = 7
SENSE_ORANGE    = 8
SENSE_RED       = 9
SENSE_WHITE     = 10


# ── Opcode table ──────────────────────────────────────────────────────
# Maps card serial → opcode definition. Each definition is a dict:
#   name     : human-readable label
#   category : one of CAT_*
#   op       : a string handler key (the runtime dispatches on this)
#   args     : parameters baked into the card (varies by op)



OPCODES = {
    # ── META ─────────────────────────────────────────────────
    9000: {'name': 'GO',          'category': CAT_META, 'op': 'go'},
    9001: {'name': 'ERASE',       'category': CAT_META, 'op': 'erase'},
    9002: {'name': 'PROGRAM_MODE','category': CAT_META, 'op': 'program_mode'},
    9003: {'name': 'STOP',        'category': CAT_META, 'op': 'stop'},
    9004: {'name': 'BATTERY',     'category': CAT_META, 'op': 'battery'},

    # ── EVENT (hat blocks — non-blocking pollers, fire on rising edge) ──
    # Wand sensors
    9100: {'name': 'when button pressed', 'category': CAT_EVENT,
           'op': 'check_button'},
    9101: {'name': 'when wand shaken',    'category': CAT_EVENT,
           'op': 'check_shake'},

    # Color sensor (only GREEN and RED per the new spec)
    9112: {'name': 'when GREEN detected',  'category': CAT_EVENT,
           'op': 'check_color', 'args': {'color': SENSE_GREEN}},
    9111: {'name': 'when RED detected',    'category': CAT_EVENT,
           'op': 'check_color', 'args': {'color': SENSE_RED}},
    9113: {'name': 'when BLUE detected',   'category': CAT_EVENT,
           'op': 'check_color', 'args': {'color': SENSE_BLUE}},
    9114: {'name': 'when YELLOW detected', 'category': CAT_EVENT,
           'op': 'check_color', 'args': {'color': SENSE_YELLOW}},

    # Controller (joysticks at the extremes)
    9120: {'name': 'when left joystick = +1',  'category': CAT_EVENT,
           'op': 'check_controller', 'args': {'side': 'left',  'dir': +1}},
    9121: {'name': 'when left joystick = -1',  'category': CAT_EVENT,
           'op': 'check_controller', 'args': {'side': 'left',  'dir': -1}},
    9122: {'name': 'when right joystick = +1', 'category': CAT_EVENT,
           'op': 'check_controller', 'args': {'side': 'right', 'dir': +1}},
    9123: {'name': 'when right joystick = -1', 'category': CAT_EVENT,
           'op': 'check_controller', 'args': {'side': 'right', 'dir': -1}},

    # ── MOTION: Double Motor ─────────────────────────────────
    # Bounded moves (block until 1 rotation completes)
    9400: {'name': 'move forward 1 step',   'category': CAT_MOTION,
           'op': 'move', 'args': {'steps': 1, 'dir': DIR_FORWARD}},
    9401: {'name': 'move backward 1 step',  'category': CAT_MOTION,
           'op': 'move', 'args': {'steps': 1, 'dir': DIR_BACKWARD}},

    # Continuous moves (fire-and-forget — body advances immediately)
    9410: {'name': 'keep moving forward',   'category': CAT_MOTION,
           'op': 'keep_moving', 'args': {'dir': DIR_FORWARD}},
    9411: {'name': 'keep moving backward',  'category': CAT_MOTION,
           'op': 'keep_moving', 'args': {'dir': DIR_BACKWARD}},

    # Stop both motors
    9420: {'name': 'both motors stop',      'category': CAT_MOTION,
           'op': 'stop_double'},

    # Turn in place (90°)
    9430: {'name': 'turn left 90°',         'category': CAT_MOTION,
           'op': 'turn', 'args': {'degrees': 90, 'dir': DIR_CCW}},
    9431: {'name': 'turn right 90°',        'category': CAT_MOTION,
           'op': 'turn', 'args': {'degrees': 90, 'dir': DIR_CW}},

    # ── MOTION: Single Motor ─────────────────────────────────
    # Bounded angle moves
    9500: {'name': 'single motor 90° CW',   'category': CAT_MOTION,
           'op': 'single_angle', 'args': {'degrees': 90, 'dir': DIR_CW}},
    9501: {'name': 'single motor 90° CCW',  'category': CAT_MOTION,
           'op': 'single_angle', 'args': {'degrees': 90, 'dir': DIR_CCW}},

    # Continuous run (fire-and-forget)
    9510: {'name': 'run single motor CW',   'category': CAT_MOTION,
           'op': 'run_single', 'args': {'dir': DIR_CW}},
    9511: {'name': 'run single motor CCW',  'category': CAT_MOTION,
           'op': 'run_single', 'args': {'dir': DIR_CCW}},

    # Stop the single motor
    9520: {'name': 'stop single motor',     'category': CAT_MOTION,
           'op': 'stop_single'},
}


def lookup(serial):
    """Return the opcode definition for ``serial``, or None if not a
    known programming card. Pairing cards (serial < 9000) return None."""
    return OPCODES.get(serial)


def is_pairing_card(serial):
    """Pairing cards live in the low serial range."""
    return serial < 9000


def is_meta(opcode):
    return opcode is not None and opcode.get('category') == CAT_META


def category_color(opcode):
    """Return the LED RGB tuple for an opcode's category."""
    if opcode is None: return (5, 5, 5)
    return CATEGORY_COLOR.get(opcode['category'], (5, 5, 5))


def is_event(opcode):
    """An EVENT opcode starts a new rule when tapped during program
    assembly. Everything else (CONTROL, MOTION, SENSING) joins the
    current rule's body."""
    return opcode is not None and opcode.get('category') == CAT_EVENT


def op_name(opcode_name):
    """Match an opcode by its ``op`` field. Returns the opcode definition
    or None. Used for finding the STOP opcode etc. without hardcoding
    serial numbers."""
    for op in OPCODES.values():
        if op.get('op') == opcode_name:
            return op
    return None


# ─────────────────────────────────────────────────────────────────────
#  NFC card I/O — MIFARE Classic 1K + NTAG-21x
# ─────────────────────────────────────────────────────────────────────
#
# Card types we handle:
#
#   1. LEGO pairing cards   — NTAG-21x. Read works without auth. The
#                             existing wand.read_card() handles these.
#
#   2. Programming cards    — MIFARE Classic 1K. Reading AND writing
#                             require authentication first. The PN532
#                             auth flow is:
#                                a. InListPassiveTarget → get UID
#                                b. InDataExchange + auth cmd + key + UID
#                                c. InDataExchange + read/write cmd
#
# Block layout used (block 5 = sector 1, second block):
#
#     byte 0    : 0x00      (unused, kept for LEGO format compat)
#     byte 1    : color_byte (the LEGO color id, or our category color)
#     byte 2    : serial low byte    ← serial determines what the card IS
#     byte 3    : serial high byte
#     bytes 4-15: zero padding (MIFARE Classic writes 16 bytes at a time)
#
# Block 5 is chosen because the LEGO pairing-card format uses page/block
# 5 already. Sector trailer blocks (3, 7, 11, ...) hold keys and access
# bits — we never touch those.

import time


# ── PN532 protocol constants ─────────────────────────────────────────

_CMD_INLISTPASSIVETARGET   = 0x4A
_CMD_INDATAEXCHANGE        = 0x40

# MIFARE / NTAG commands sent inside InDataExchange
_MIFARE_CMD_AUTH_A         = 0x60   # MIFARE Classic: authenticate with key A
_MIFARE_CMD_AUTH_B         = 0x61   # MIFARE Classic: authenticate with key B
_MIFARE_CMD_READ           = 0x30   # MIFARE Classic & NTAG: read 16 bytes
_MIFARE_CMD_WRITE_CLASSIC  = 0xA0   # MIFARE Classic: 16-byte block write
_NTAG_CMD_WRITE            = 0xA2   # NTAG: 4-byte page write

# Factory-default MIFARE Classic key A on blank cards
DEFAULT_KEY = b'\xff\xff\xff\xff\xff\xff'

# Common MIFARE Classic keys to try when default fails
COMMON_KEYS = [
    b'\xff\xff\xff\xff\xff\xff',  # Default factory key
    b'\xd3\xf7\xd3\xf7\xd3\xf7',  # NDEF key
    b'\xa0\xa1\xa2\xa3\xa4\xa5',  # MAD key
    b'\xb0\xb1\xb2\xb3\xb4\xb5',  # Alternative transport key
    b'\x00\x00\x00\x00\x00\x00',  # All zeros
]

# Where on the card we store our payload
TARGET_BLOCK = 5


# ── Low-level PN532 helpers ──────────────────────────────────────────

def _get_uid(wand, timeout_ms=1000):
    """Run InListPassiveTarget and return the card UID (bytes), or None.

    The wand library's existing _detect_tag() returns only a yes/no,
    but for MIFARE Classic auth we need the UID bytes too."""
    try:
        resp = wand._send_command(_CMD_INLISTPASSIVETARGET,
                                  b'\x01\x00', timeout=timeout_ms)
    except RuntimeError:
        return None
    # PN532 response after _send_command strips the TFI/cmd-echo bytes:
    #   resp[0]            : number of targets (0 = none found)
    #   resp[1]            : target tag number
    #   resp[2..3]         : SENS_RES
    #   resp[4]            : SEL_RES (SAK)
    #   resp[5]            : UID length
    #   resp[6..6+uidlen]  : UID
    if len(resp) < 7 or resp[0] == 0:
        return None
    uid_len = resp[5]
    if len(resp) < 6 + uid_len:
        return None
    return bytes(resp[6:6 + uid_len])


def _get_uid_and_sak(wand, timeout_ms=1000):
    """Run InListPassiveTarget and return (uid, sak) tuple, or (None, None).
    
    SAK (SEL_RES) identifies card type:
        0x08 or 0x18 = MIFARE Classic (needs authentication)
        0x00         = NTAG/Ultralight (no authentication)
    """
    try:
        resp = wand._send_command(_CMD_INLISTPASSIVETARGET,
                                  b'\x01\x00', timeout=timeout_ms)
    except RuntimeError:
        return None, None
    if len(resp) < 7 or resp[0] == 0:
        return None, None
    sak = resp[4]
    uid_len = resp[5]
    if len(resp) < 6 + uid_len:
        return None, None
    uid = bytes(resp[6:6 + uid_len])
    return uid, sak


def _authenticate(wand, block, uid, key=DEFAULT_KEY, use_key_b=False):
    """Authenticate ``block`` so subsequent reads/writes work.
    Returns True on success. MIFARE Classic only — NTAG ignores this."""
    cmd = _MIFARE_CMD_AUTH_B if use_key_b else _MIFARE_CMD_AUTH_A
    # PN532 auth expects exactly 4 UID bytes; if the card has a longer
    # UID, the last 4 are what's used in the authentication.
    uid4 = uid[-4:] if len(uid) >= 4 else uid + b'\x00' * (4 - len(uid))
    params = bytes([0x01, cmd, block]) + key + uid4
    try:
        resp = wand._send_command(_CMD_INDATAEXCHANGE,
                                  params, timeout=1500)
    except RuntimeError:
        return False
    # Status is the low 6 bits of resp[0]; 0 means success.
    return len(resp) >= 1 and (resp[0] & 0x3F) == 0


def _authenticate_multikey(wand, block, uid, timeout_reselect_ms=150):
    """Try to authenticate using multiple common MIFARE keys.
    
    Rotates through COMMON_KEYS, trying both Key A and Key B for each.
    Re-selects the card before each attempt (MIFARE Classic requirement).
    
    Returns the successful (key, use_key_b) tuple, or (None, False) if all fail.
    """
    for key in COMMON_KEYS:
        for use_key_b in [False, True]:  # Try Key A first, then Key B
            # Re-select card before auth attempt (MIFARE Classic drops state on failure)
            reselect_uid = _get_uid(wand, timeout_ms=timeout_reselect_ms)
            if reselect_uid is None:
                continue  # Card disappeared, try next key
            
            if _authenticate(wand, block, reselect_uid, key, use_key_b):
                return key, use_key_b  # Success!
    
    return None, False  # All keys failed


def _read_block(wand, block):
    """Read 16 bytes from ``block``. Returns the raw bytes (status byte
    stripped) or None on failure. Assumes auth was done if needed."""
    params = bytes([0x01, _MIFARE_CMD_READ, block])
    try:
        resp = wand._send_command(_CMD_INDATAEXCHANGE,
                                  params, timeout=1000)
    except RuntimeError:
        return None
    # resp[0] = status byte (0 = ok); resp[1..16] = 16 data bytes
    if len(resp) < 17 or (resp[0] & 0x3F) != 0:
        return None
    return bytes(resp[1:17])


def _write_block_classic(wand, block, data16):
    """Write 16 bytes to ``block`` on a MIFARE Classic card. ``data16``
    must be exactly 16 bytes. Auth must already have succeeded.
    Returns True on success."""
    if len(data16) != 16:
        raise ValueError("MIFARE Classic write needs exactly 16 bytes")
    params = bytes([0x01, _MIFARE_CMD_WRITE_CLASSIC, block]) + bytes(data16)
    try:
        resp = wand._send_command(_CMD_INDATAEXCHANGE,
                                  params, timeout=1500)
    except RuntimeError:
        return False
    return len(resp) >= 1 and (resp[0] & 0x3F) == 0


def _write_page_ntag(wand, page, data4):
    """Write 4 bytes to a page on an NTAG/Ultralight card. ``data4``
    must be exactly 4 bytes. No authentication needed.
    Returns True on success."""
    if len(data4) != 4:
        raise ValueError("NTAG write needs exactly 4 bytes")
    params = bytes([0x01, _NTAG_CMD_WRITE, page]) + bytes(data4)
    try:
        resp = wand._send_command(_CMD_INDATAEXCHANGE,
                                  params, timeout=1500)
    except RuntimeError:
        return False
    return len(resp) >= 1 and (resp[0] & 0x3F) == 0


# ── Public read API ──────────────────────────────────────────────────

# Empirically-derived remap of raw color bytes (as stored on LEGO
# cards or broadcast by LEGO devices) to LEGO app-aligned color IDs.
# The table in wand.py had wrong entries; this one is the working
# version. Update as more cards are tested. THIS IS THE ONLY REMAP
# TABLE IN THE PROJECT — import remap_color() wherever you need to
# translate raw color bytes.
_RAW_TO_APP_COLOR = {
    0x01: 8,   # MAGENTA
    0x02: 2,   # PURPLE
    0x04: 2,   # YELLOW
    0x06: 6,   # GREEN
    0x07: 2,   # YELLOW (multi variant)
    0x08: 9,
    0x09: 1,   # RED
}


def remap_color(raw_byte):
    """Translate a raw color byte (from an NFC card OR a LEGO BLE
    advertisement) to the LEGO app-aligned color ID. Unknown bytes pass
    through unchanged."""
    return _RAW_TO_APP_COLOR.get(raw_byte, raw_byte)


# Set to True to print every step of NFC reading (for debugging which
# code path a card takes through the universal reader).
NFC_DEBUG = True


def read_card_universal(wand, timeout_ms=200):
    """Read a card on the wand reader. Works for both LEGO pairing
    cards (NTAG, no auth) and programming cards (MIFARE Classic, needs
    auth with default key A).

    Returns (color, serial_uint16), or None if no card present or both
    read attempts failed."""
    if not wand._nfc_ready:
        return None

    uid = _get_uid(wand, timeout_ms=timeout_ms)
    if uid is None:
        return None
    if NFC_DEBUG:
        print("  nfc: uid={}".format(' '.join('%02X' % b for b in uid)))

    # Try unauthenticated read first — succeeds on NTAG-21x cards.
    data = _read_block(wand, TARGET_BLOCK)
    if data is not None:
        if NFC_DEBUG:
            print("  nfc: unauth read OK, block5={}".format(
                ' '.join('%02X' % b for b in data[:8])))
    else:
        if NFC_DEBUG:
            print("  nfc: unauth read failed — trying MIFARE auth")
        # A failed InDataExchange on MIFARE Classic puts the card into
        # halt state. Re-activate it with InListPassiveTarget before
        # attempting auth, or auth will fail.
        uid = _get_uid(wand, timeout_ms=500)
        if uid is None:
            if NFC_DEBUG:
                print("  nfc: card lost after unauth-read attempt")
            return None
        # Try multi-key authentication
        key, use_key_b = _authenticate_multikey(wand, TARGET_BLOCK, uid)
        if key is None:
            if NFC_DEBUG:
                print("  nfc: auth failed (tried all common keys)")
            return None
        if NFC_DEBUG:
            print("  nfc: auth OK")
        data = _read_block(wand, TARGET_BLOCK)
        if data is None:
            if NFC_DEBUG:
                print("  nfc: auth+read still failed")
            return None
        if NFC_DEBUG:
            print("  nfc: auth+read OK, block5={}".format(
                ' '.join('%02X' % b for b in data[:8])))

    color  = remap_color(data[1])
    # Big-endian: byte 2 = high, byte 3 = low. Matches wand.read_card()
    # and the layout LEGO uses on its cards.
    serial = (data[2] << 8) | data[3]
    return color, serial


# ── Public write API ─────────────────────────────────────────────────

def write_card_serial(wand, serial, color_byte=0, block=TARGET_BLOCK):
    """Write a programming-card serial to an NFC card (MIFARE Classic or NTAG).
    
    Automatically detects card type via SAK:
        - SAK 0x08/0x18: MIFARE Classic (16-byte block write with auth)
        - SAK 0x00:      NTAG/Ultralight (4-byte page write, no auth)
    
    Data layout (first 4 bytes, same for both card types):
        byte 0    : 0x00       (unused)
        byte 1    : color_byte
        bytes 2-3 : serial (big-endian uint16, matches LEGO format)

    Returns True on success, False otherwise."""
    if not wand._nfc_ready:
        raise RuntimeError("NFC not initialised")

    # Detect card and get type
    uid, sak = _get_uid_and_sak(wand, timeout_ms=1000)
    if uid is None:
        return False
    
    print("  card UID: {}".format(' '.join('%02X' % b for b in uid)))
    print("  card SAK: 0x{:02X}".format(sak))
    
    # Prepare data (first 4 bytes are the same for both card types)
    data4 = bytearray(4)
    data4[0] = 0
    data4[1] = color_byte & 0xFF
    # Big-endian serial: byte 2 = high, byte 3 = low. Matches LEGO format.
    data4[2] = (serial >> 8) & 0xFF
    data4[3] = serial & 0xFF
    
    # Branch based on card type
    if sak in (0x08, 0x18):
        # MIFARE Classic - needs authentication + 16-byte block write
        print("  card type: MIFARE Classic")
        
        # Try multi-key authentication
        key, use_key_b = _authenticate_multikey(wand, block, uid)
        if key is None:
            print("  auth failed (tried all common keys)")
            return False
        
        # Extend to 16 bytes (pad with zeros)
        payload = bytearray(16)
        payload[0:4] = data4
        # payload[4..15] stay zero
        
        if not _write_block_classic(wand, block, payload):
            print("  write rejected")
            return False
        
        # Verify with readback
        data = _read_block(wand, block)
        if data is None:
            print("  readback failed — write may not have persisted")
            return False
        readback_serial = (data[2] << 8) | data[3]
        if readback_serial != serial:
            print("  readback mismatch: expected {}, got {}".format(
                serial, readback_serial))
            return False
        
        return True
    
    elif sak == 0x00:
        # NTAG/Ultralight - no auth, 4-byte page write
        print("  card type: NTAG/Ultralight")
        
        # NTAG pages are 4 bytes - write directly to page 5
        if not _write_page_ntag(wand, block, data4):
            print("  write rejected")
            return False
        
        # Verify with readback (no auth needed for NTAG)
        data = _read_block(wand, block)
        if data is None:
            print("  readback failed — write may not have persisted")
            return False
        readback_serial = (data[2] << 8) | data[3]
        if readback_serial != serial:
            print("  readback mismatch: expected {}, got {}".format(
                serial, readback_serial))
            return False
        
        return True
    
    else:
        print("  unsupported card type (SAK 0x{:02X})".format(sak))
        return False


def list_opcodes():
    """Print a human-readable table of every opcode. Used by the writer
    utility."""
    by_cat = {}
    for serial, op in OPCODES.items():
        by_cat.setdefault(op['category'], []).append((serial, op))

    for cat in (CAT_META, CAT_EVENT, CAT_CONTROL, CAT_MOTION, CAT_SENSING):
        items = by_cat.get(cat, [])
        if not items: continue
        print()
        print("── {} ──".format(cat.upper()))
        for serial, op in sorted(items):
            print("  {:5d}  {}".format(serial, op['name']))