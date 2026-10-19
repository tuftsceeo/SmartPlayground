"""MockWand/lib/pairing.py against a temp directory.

Run: python3 tools/devtests/test_wand_pairing_store.py
"""
import os
import shutil
import sys
import tempfile

BB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BB, "MockWand", "lib"))

import pairing  # noqa: E402

TMP = tempfile.mkdtemp(prefix="pairing-")
pairing.PATH = os.path.join(TMP, "pairing.json")

A = "AB:42:00:00:7E:B6"
B = "AB:42:00:00:20:60"
C = "AB:42:00:00:6D:27"
FAILURES = []


def check(label, ok, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", label, (" -- " + detail) if detail else ""))
    if not ok:
        FAILURES.append(label)


def raw():
    with open(pairing.PATH) as f:
        return f.read()


check("MAX_SPLATS is 2", pairing.MAX_SPLATS == 2)
check("missing file reads empty", pairing.load() == [] and not pairing.exists())
check("add one", pairing.add(A) == [A] and pairing.load() == [A])
check("add keeps tap order", pairing.add(B) == [A, B] and pairing.load() == [A, B])
before = raw()
try:
    pairing.add(C)
    check("add to a full list raises", False)
except ValueError:
    check("add to a full list raises and leaves the file", raw() == before)
check("duplicate add is a no-op", pairing.add(A) == [A, B] and raw() == before)
try:
    pairing.add("AB4200007EB6")
    check("malformed MAC raises", False)
except ValueError:
    check("malformed MAC raises", raw() == before)
try:
    pairing.add("ab:42:00:00:7e:b6")
    check("lowercase MAC raises (callers pass the stored form)", False)
except ValueError:
    check("lowercase MAC raises (callers pass the stored form)", True)

check("remove an absent MAC is a no-op", pairing.remove(C) == [A, B] and raw() == before)
check("remove the first keeps the second", pairing.remove(A) == [B] and pairing.load() == [B])
check("remove the last deletes the file", pairing.remove(B) == [] and not pairing.exists())
check("clear on a missing file is not an error", pairing.clear() is None)
pairing.add(A)
pairing.clear()
check("clear deletes the file", not pairing.exists())

# Corrupt contents read as empty, with a warning.
import contextlib
import io
for label, body in (("not JSON", "{oops"), ("wrong shape", '{"x": 1}'),
                    ("splats not a list", '{"splats": "AB"}'), ("empty file", "")):
    with open(pairing.PATH, "w") as f:
        f.write(body)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        got = pairing.load()
    check("corrupt (%s) reads empty and warns" % label, got == [] and "[WARN]" in buf.getvalue())
with open(pairing.PATH, "w") as f:
    f.write('{"splats": ["AB:42:00:00:7E:B6", "junk", "AB:42:00:00:7E:B6", 5, "AB:42:00:00:20:60", "AB:42:00:00:6D:27"]}')
check("load drops junk and duplicates and caps at MAX_SPLATS", pairing.load() == [A, B])
pairing.clear()

# A failed rename leaves the previous file and no temp file behind.
pairing.add(A)
good = raw()
real_rename = os.rename


def bad_rename(src, dst):
    raise OSError(28, "no space")


os.rename = bad_rename
try:
    pairing.add(B)
    check("rename failure propagates", False)
except OSError:
    check("rename failure propagates", True)
finally:
    os.rename = real_rename
check("rename failure leaves the old file", raw() == good and pairing.load() == [A])
check("rename failure leaves no temp file", not os.path.exists(pairing.PATH + ".tmp"))

# A failed write (open for the temp file) also leaves the old file.
real_open = open


def bad_open(path, mode="r", *a, **k):
    if str(path).endswith(".tmp"):
        raise OSError(28, "no space")
    return real_open(path, mode, *a, **k)


import builtins
builtins.open = bad_open
try:
    pairing.add(B)
    check("write failure propagates", False)
except OSError:
    check("write failure propagates", True)
finally:
    builtins.open = real_open
check("write failure leaves the old file", raw() == good)

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print("FAILED: %d" % len(FAILURES))
    sys.exit(1)
print("wand pairing store OK")
