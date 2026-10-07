"""Check MockWand's PEER copies of the Splat libraries against their sources.

splat_hub.py, splat_link.py, splat_api.py and ble_splat.py are byte copies of
SplatCompanion/Companion's (ble_splat.py also of Bag3/Code/lib's).

Run: python3 tools/devtests/test_wand_copies.py
"""
import os
import sys

BB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WAND_LIB = os.path.join(BB, "MockWand", "lib")
COMP = os.path.join(BB, "SplatCompanion", "Companion")
BAG3_LIB = os.path.join(BB, "..", "lib")

PAIRS = (
    ("splat_hub.py", COMP),
    ("splat_link.py", COMP),
    ("splat_api.py", COMP),
    ("ble_splat.py", os.path.join(COMP, "lib")),
    ("ble_splat.py", BAG3_LIB),
)


def _read(path):
    with open(path, "rb") as f:
        return f.read()


def main():
    bad = []
    for name, src_dir in PAIRS:
        same = _read(os.path.join(WAND_LIB, name)) == _read(os.path.join(src_dir, name))
        print("%-4s MockWand/lib/%s == %s" % ("ok" if same else "FAIL", name,
                                              os.path.relpath(src_dir, BB)))
        if not same:
            bad.append(name)
    if bad:
        print("FAILED: %s" % ", ".join(bad))
        sys.exit(1)
    print("wand Splat library copies OK")


main()
