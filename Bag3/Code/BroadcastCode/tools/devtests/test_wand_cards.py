"""Splat card parsing and the unpair tag (MockWand/lib/nfc_reader.py, game_tags.py).

Run: python3 tools/devtests/test_wand_cards.py
"""
import os
import sys

BB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BB, "tools", "devtests", "stubs"))
sys.path.insert(0, os.path.join(BB, "MockWand", "lib"))

import nfc_reader  # noqa: E402
from game_tags import CONTROL_TAGS, EXIT_TAGS, GAME_TAGS  # noqa: E402

FAILURES = []


def check(label, ok, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", label, (" -- " + detail) if detail else ""))
    if not ok:
        FAILURES.append(label)


P = nfc_reader.parse_splat_card
WANT = "AB:42:00:00:7E:B6"

check("valid upper", P("splat-AB4200007EB6") == WANT)
check("valid lower (decoded NDEF text is lowercase)", P("splat-ab4200007eb6") == WANT)
check("mixed case prefix and digits", P("Splat-aB4200007eB6") == WANT)
check("11 digits", P("splat-AB4200007EB") is None)
check("13 digits", P("splat-AB4200007EB6A") is None)
check("non-hex digit", P("splat-AB4200007EBG") is None)
check("colons in the MAC", P("splat-AB:42:00:00:7E:B6") is None)
check("missing prefix", P("AB4200007EB6") is None)
check("wrong prefix", P("splut-AB4200007EB6") is None)
check(":slug suffix", P("splat-AB4200007EB6:jump") is None)
check("@id suffix", P("splat-AB4200007EB6@7a3f") is None)
check("empty and None", P("") is None and P(None) is None)
check("non-ASCII digit", P("splat-AB4200007EB٢") is None)
check("splat- alone", P("splat-") is None)

check("unpair is a control tag", "unpair" in CONTROL_TAGS)
check("unpair does not exit a running game", "unpair" not in EXIT_TAGS)
check("unpair is not a game tag", "unpair" not in GAME_TAGS)


class FakeNfc:
    """read_passive_target -> an NTAG whose pages hold one NDEF text record."""
    def __init__(self, text):
        payload = b"\x02en" + text.encode()
        rec = bytes([0xD1, 0x01, len(payload)]) + b"T" + payload
        data = bytes([0x03, len(rec)]) + rec + b"\xFE"
        data += b"\x00" * (64 - len(data))
        self.pages = {4 + i: data[i * 4:i * 4 + 4] for i in range(16)}

    def read_passive_target(self, timeout=0):
        return {"uid_hex": "04AABB", "uid": b"\x04\xaa\xbb", "sak": 0x00}

    def ntag_read_page(self, page):
        return self.pages[page]


def read(text, commands=("stop", "unpair"), prefixes=("getcode",)):
    return nfc_reader.NfcReader(FakeNfc(text), set(commands), prefixes=prefixes).read_command()


check("read_command returns a splat card's text",
      read("splat-AB4200007EB6") == ("splat-ab4200007eb6", "04AABB"), str(read("splat-AB4200007EB6")))
check("read_command still returns unpair", read("unpair") == ("unpair", "04AABB"))
check("read_command still rejects an unknown card", read("splat-AB42")[0] is None)
check("read_command still returns a getcode card", read("getcode:jump")[0] == "getcode:jump")

print()
if FAILURES:
    print("FAILED: %d" % len(FAILURES))
    sys.exit(1)
print("wand card parsing OK")
