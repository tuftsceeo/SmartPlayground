"""
Check the icon display can read a card.

The display's reader is a WS1850S (same chip as the Broadcast Box) while the
card-reading logic in nfc_reader.py was written against a PN532, so a shim --
lib/nfc_ws1850s.py -- presents the four PN532 methods that file calls. The
shim's mapping is the part that can silently be wrong, so this drives the
real nfc_reader.NfcReader against a fake WS1850S holding a real NDEF card
image, built by the Dial's own card_writer.build_ndef_text().

No I2C, no chip: the fake stands in for the register bus only. What is under
test is the shim and the decode path, not the driver.
"""
import os, sys, tempfile, shutil

import os
# BroadcastBox/, two levels up from tools/devtests/.
_BB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEV = _BB + "/IconDisplay"
DIAL = os.path.dirname(_BB) + "/BroadcastDial/BDialFirmware"
SCRATCH = os.path.dirname(os.path.abspath(__file__))

import time as _time
_time.sleep_ms = lambda ms: None
_clock = [0]


def _tick():
    _clock[0] += 5
    return _clock[0]


_time.ticks_ms = _tick
_time.ticks_diff = lambda a, b: a - b
_time.ticks_add = lambda a, b: a + b

TMP = tempfile.mkdtemp(prefix="nfc-")
FLASH = os.path.join(TMP, "display")
shutil.copytree(DEV, FLASH)
os.chdir(FLASH)          # hubtype.py reads hubtype.txt from the cwd, as on flash
sys.path.insert(0, os.path.join(SCRATCH, "stubs"))
sys.path.insert(0, os.path.join(FLASH, "lib"))
sys.path.insert(0, FLASH)
sys.path.insert(0, DIAL)          # for the card writer's NDEF encoder

FAILURES = []


def check(label, ok, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", label, (" -- " + detail) if detail else ""))
    if not ok:
        FAILURES.append(label)


import nfc_ws1850s
from nfc_ws1850s import Ws1850sReader, MIFARE_AUTH_A, MIFARE_AUTH_B
from ws1850s import WS1850S

# The card image is built by the same encoder that writes real cards, so a
# decoder change on either side shows up here rather than on a card.
import card_writer


class FakeWS1850S:
    """Register-bus stand-in. Holds one card, or none."""

    MI_OK = WS1850S.MI_OK
    PICC_AUTHENT1A = WS1850S.PICC_AUTHENT1A
    PICC_AUTHENT1B = WS1850S.PICC_AUTHENT1B
    DEFAULT_ADDR = WS1850S.DEFAULT_ADDR

    def __init__(self, i2c=None, addr=0x28):
        self.addr = addr
        self.uid = b'\x04\xAA\xBB\xCC'
        self.sak = 0x00                 # NTAG
        self.pages = bytearray(4 * 40)  # pages 0..39
        self.present = True
        self.antenna = False
        self.crypto_cleared = 0
        self.auth_calls = []

    # -- what the shim calls --
    def version(self):
        return 0xB2

    def antenna_on(self):
        self.antenna = True

    def antenna_off(self):
        self.antenna = False

    def stop_crypto1(self):
        self.crypto_cleared += 1

    def read_uid_full(self):
        return (self.uid, self.sak) if self.present else None

    def auth(self, mode, block, key, uid):
        self.auth_calls.append((mode, block, key, uid))
        return WS1850S.MI_OK if key == b'\xFF\xFF\xFF\xFF\xFF\xFF' else 2

    def read_block(self, block):
        return WS1850S.MI_OK, bytes(16)

    def ul_read(self, page):
        o = page * 4
        if o + 4 > len(self.pages):
            return 2, None
        return WS1850S.MI_OK, bytes(self.pages[o:o + 4])

    # -- test helper --
    def write_card_text(self, text):
        """Lay an NDEF text record out from page 4, as a written card has it."""
        tlv = card_writer.build_ndef_text(text)
        for i in range(len(self.pages)):
            self.pages[i] = 0
        self.pages[16:16 + len(tlv)] = tlv      # page 4 starts at byte 16


nfc_ws1850s.WS1850S = FakeWS1850S
fake = None


def _reader_for(text, sak=0x00):
    """A NfcReader wired to a fake card carrying `text`."""
    global fake
    nfc = Ws1850sReader(None, addr=0x28)
    fake = nfc.dev
    fake.sak = sak
    fake.write_card_text(text)
    from nfc_reader import NfcReader
    return NfcReader(nfc, {"goalrace", "stop"}, prefixes={"getcode"}), nfc


# ── the shim's own surface ──────────────────────────────────────
_r, _nfc = _reader_for("goalrace")
check("the key-type constants are the MIFARE command bytes, whatever the chip",
      (MIFARE_AUTH_A, MIFARE_AUTH_B) == (0x60, 0x61))
check("begin() confirms the bus and energizes the field",
      _nfc.begin() == 0xB2 and fake.antenna is True)

_before = fake.crypto_cleared
_tag = _nfc.read_passive_target(timeout=50)
check("a detected tag comes back in the PN532's dict shape",
      _tag is not None and _tag['uid'] == fake.uid and _tag['sak'] == 0x00
      and _tag['uid_hex'] == "04:AA:BB:CC", str(_tag))
check("...and every detection clears Crypto1 first",
      fake.crypto_cleared == _before + 1,
      "a latched auth otherwise blocks every later read")

check("an NTAG page read returns 4 bytes", len(_nfc.ntag_read_page(4)) == 4)
check("a Classic block read returns 16 bytes", len(_nfc.mifare_read_block(4)) == 16)
check("auth passes the key type through as the mode byte",
      _nfc.mifare_auth_block(fake.uid, 4, b'\xFF' * 6, MIFARE_AUTH_B) is True
      and fake.auth_calls[-1][0] == MIFARE_AUTH_B)
check("...and a wrong key is a failed auth, not an exception",
      _nfc.mifare_auth_block(fake.uid, 4, b'\x00' * 6, MIFARE_AUTH_A) is False)

fake.present = False
check("no card means no tag, not a hang", _nfc.read_passive_target(timeout=20) == (None))

# ── through nfc_reader, the way main.py uses it ─────────────────
reader, _ = _reader_for("goalrace")
cmd, uid = reader.read_command()
check("a game tag reads back as its command", cmd == "goalrace", repr(cmd))
check("...with the card's uid", uid == "04:AA:BB:CC", repr(uid))

reader, _ = _reader_for("getcode:goalrace")
cmd, _uid = reader.read_command()
check("a getcode tag keeps its slug", cmd == "getcode:goalrace", repr(cmd))

reader, _ = _reader_for("stop")
cmd, _uid = reader.read_command()
check("a control tag reads back", cmd == "stop", repr(cmd))

reader, _ = _reader_for("somethingelse")
cmd, uid = reader.read_command()
check("an unknown tag is None, not a wrong guess", cmd is None, repr(cmd))
check("...but the card was still seen", uid == "04:AA:BB:CC", repr(uid))

# ── main.py's boot wiring ───────────────────────────────────────
from hubtype import HUB_CONFIG
check("hubtype says a reader is fitted", HUB_CONFIG["has_nfc"] is True)
check("...at the WS1850S address, not the PN532's",
      HUB_CONFIG["nfc_addr"] == 0x28, hex(HUB_CONFIG["nfc_addr"]))
check("...on the wand's I2C pins",
      (HUB_CONFIG["i2c_sda"], HUB_CONFIG["i2c_scl"]) == (22, 23))
check("the PN532 driver is gone from this tree",
      not os.path.exists(os.path.join(FLASH, "lib", "pn532.py")))

os.chdir(SCRATCH)

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print("FAILED: %d" % len(FAILURES))
    for f in FAILURES:
        print("  - %s" % f)
    raise SystemExit(1)
print("icon display card reading OK")
