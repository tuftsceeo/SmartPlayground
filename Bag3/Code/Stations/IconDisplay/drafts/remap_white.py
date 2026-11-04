"""Swap the datasheet neutral (255,171,93) and its greys for the panel-measured
white (185,255,150), at the same brightness, in icon .py files.

    python3 remap_white.py <icons dir>...

A colour counts as neutral when its G/R and B/R are within 0.04 of
171/255 and 93/255; its new value is WHITE * R/255.
"""
import glob, os, re, sys
WHITE = (185, 255, 150)
TRIPLE = re.compile(r"\((\d+),\s*(\d+),\s*(\d+)\)")

def fix(m):
    r, g, b = (int(x) for x in m.groups())
    if r and abs(g / r - 171 / 255) < 0.04 and abs(b / r - 93 / 255) < 0.04:
        k = r / 255
        return "(%d, %d, %d)" % tuple(round(c * k) for c in WHITE)
    return m.group(0)

for d in sys.argv[1:]:
    n = 0
    for p in sorted(glob.glob(os.path.join(d, "*.py"))):
        s = open(p).read()
        t = TRIPLE.sub(fix, s)
        if t != s:
            open(p, "w").write(t); n += 1
    print(d, n, "files changed")
